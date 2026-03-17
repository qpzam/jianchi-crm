#!/usr/bin/env python3
"""
A股减持法规问答助手
- 本地法规库检索
- AI生成专业回答
- 受让方锁定期速查
- 减持方案合规检查器
- 智能问答增强
"""

import os
import sys
import re
import json
from pathlib import Path
from collections import defaultdict
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import argparse

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


# ============================================================================
# 模块1：受让方锁定期速查器
# ============================================================================

@dataclass
class LockPeriodResult:
    """锁定期判断结果"""
    locked: bool          # 是否需要锁定
    lock_period: str      # 锁定期时长（如"6个月"、"不锁定"）
    rule_source: str      # 法规依据
    notes: List[str]      # 注意事项
    confidence: str       # 确定度（确定/需核实/存在争议）
    applicable_rules: List[str]  # 适用的具体法规条文


class LockPeriodChecker:
    """受让方锁定期速查器"""

    # 法规依据映射
    RULE_SOURCES = {
        "大宗交易_大股东": "《深交所自律监管指引第18号》第十三条",
        "大宗交易_特定股东": "《深交所自律监管指引第18号》第十三条",
        "大宗交易_创投基金豁免": "《上市公司创业投资基金股东减持股份的特别规定》",
        "协议转让": "《深交所自律监管指引第18号》第十五条",
        "询价转让": "《深圳证券交易所创业板上市公司股东询价和配售方式转让股份业务指引》",
        "集中竞价": "无锁定期要求（但需遵守减持比例限制）",
    }

    # 创投基金投资期限与锁定期豁免
    VC_LOCK_EXEMPTION_MONTHS = 60  # 投资满60个月豁免锁定期

    def __init__(self):
        """初始化锁定期速查器"""
        pass

    def check_lock_period(
        self,
        share_source: str = None,      # 股份来源：IPO前/定增/二级市场买入/协议转让/司法拍卖
        seller_identity: str = None,    # 卖方身份：控股股东/实控人/5%以上股东/董监高/一般股东/创投基金
        reduce_method: str = None,      # 减持方式：大宗交易/协议转让/询价转让/集中竞价
        current_holding: str = None,     # 卖方当前持股比例（如"8%"、"3%"）
        investment_months: int = None,   # 创投基金投资期限（月数）
        already_transferred: bool = False # 股份是否已经过一次非交易过户
    ) -> LockPeriodResult:
        """
        判断受让方锁定期

        Args:
            share_source: 股份来源
            seller_identity: 卖方身份
            reduce_method: 减持方式
            current_holding: 卖方当前持股比例
            investment_months: 创投基金投资期限（月数）
            already_transferred: 是否已过一次非交易过户

        Returns:
            LockPeriodResult: 锁定期判断结果
        """
        result = LockPeriodResult(
            locked=False,
            lock_period="不锁定",
            rule_source="",
            notes=[],
            confidence="确定",
            applicable_rules=[]
        )

        # 解析持股比例
        holding_pct = self._parse_percentage(current_holding)

        # === 规则1：集中竞价交易 ===
        if reduce_method and "集中竞价" in reduce_method:
            result.locked = False
            result.lock_period = "无锁定期"
            result.rule_source = "无专门锁定期要求"
            result.notes.append("集中竞价交易受让方无锁定期限制")
            result.confidence = "确定"
            result.applicable_rules = []
            return result

        # === 规则2：大宗交易 ===
        if reduce_method and "大宗交易" in reduce_method:
            # 判断卖方身份
            is_vc = seller_identity and "创投" in seller_identity
            is_vc_qualified = is_vc and investment_months is not None

            if is_vc_qualified:
                # 创投基金特殊规定
                if investment_months >= self.VC_LOCK_EXEMPTION_MONTHS:
                    # 投资满60个月，豁免锁定期
                    result.locked = False
                    result.lock_period = "豁免锁定（投资≥60个月）"
                    result.rule_source = self.RULE_SOURCES["大宗交易_创投基金豁免"]
                    result.notes.append(f"创投基金投资期限{investment_months}个月，≥60个月，豁免受让方锁定期")
                    result.confidence = "确定"
                else:
                    # 投资不满60个月，仍需锁定6个月
                    result.locked = True
                    result.lock_period = "6个月"
                    result.rule_source = self.RULE_SOURCES["大宗交易_创投基金豁免"]
                    result.notes.append(f"创投基金投资期限{investment_months}个月，<60个月，仍需锁定6个月")
                    result.confidence = "确定"
            else:
                # 非创投基金，适用一般规则
                result.locked = True
                result.lock_period = "6个月"
                is_major = seller_identity and ("控股" in seller_identity or "实控" in seller_identity or "5%" in seller_identity or (holding_pct and holding_pct >= 5))
                if is_major:
                    result.rule_source = self.RULE_SOURCES["大宗交易_大股东"]
                    result.notes.append("大股东通过大宗交易减持，受让方需锁定6个月")
                else:
                    result.rule_source = self.RULE_SOURCES["大宗交易_特定股东"]
                    result.notes.append("特定股东通过大宗交易减持，受让方需锁定6个月")
                result.confidence = "确定"

            return result

        # === 规则3：协议转让 ===
        if reduce_method and "协议转让" in reduce_method:
            result.locked = True
            result.lock_period = "6个月"
            result.rule_source = self.RULE_SOURCES["协议转让"]
            result.notes.append("协议转让受让方需锁定6个月")
            result.notes.append("协议转让单个受让方受让比例不得低于公司股份总数的5%")
            result.confidence = "确定"
            return result

        # === 规则4：询价转让（创业板） ===
        if reduce_method and "询价转让" in reduce_method:
            result.locked = True
            result.lock_period = "6个月"
            result.rule_source = self.RULE_SOURCES["询价转让"]
            result.notes.append("创业板询价转让受让方需锁定6个月")
            result.confidence = "确定"
            return result

        # === 规则5：司法拍卖/强制执行 ===
        if share_source and "司法" in share_source:
            # 司法拍卖根据执行方式分别适用不同规则
            result.locked = False
            result.lock_period = "待确认"
            result.rule_source = "根据具体执行方式确定"
            result.notes.append("司法强制执行需根据执行方式分别适用:")
            result.notes.append("  - 通过集中竞价执行：无锁定期")
            result.notes.append("  - 通过大宗交易执行：受让方6个月")
            result.notes.append("  - 通过司法扣划等非交易过户：参照协议转让，6个月")
            result.confidence = "需核实"
            return result

        # === 规则6：已过一次非交易过户 ===
        if already_transferred:
            result.locked = True
            result.lock_period = "6个月"
            result.rule_source = "《深交所自律监管指引第18号》"
            result.notes.append("首发前股份在解除限售前发生非交易过户，受让方后续减持适用特定股东规定")
            result.notes.append("若通过大宗交易减持，受让方仍需锁定6个月")
            result.confidence = "确定"
            return result

        # === 规则7：信息不足 ===
        result.locked = None
        result.lock_period = "待确认"
        result.rule_source = "信息不足"
        result.notes.append("缺少关键信息，请提供:")
        result.notes.append("  - 股份来源（IPO前/定增/二级市场买入等）")
        result.notes.append("  - 卖方身份（控股股东/实控人/5%以上股东/创投基金等）")
        result.notes.append("  - 减持方式（大宗交易/协议转让/询价转让/集中竞价）")
        result.confidence = "信息不足"
        return result

    def _parse_percentage(self, pct_str: Optional[str]) -> Optional[float]:
        """解析百分比字符串"""
        if pct_str is None:
            return None
        match = re.search(r'(\d+(?:\.\d+)?)', str(pct_str))
        if match:
            return float(match.group(1))
        return None

    def format_result(self, result: LockPeriodResult) -> str:
        """格式化输出锁定期判断结果"""
        output = []
        output.append("🔒 受让方锁定期判断")
        output.append("━" * 50)

        # 基本信息
        lock_icon = "需锁定" if result.locked else "无需锁定" if result.locked is not None else "待确认"
        output.append(f"✅ 判断结果: {lock_icon}")
        output.append(f"⏰ 锁定期: {result.lock_period}")
        output.append(f"📜 法规依据: {result.rule_source}")
        output.append(f"🎯 确定度: {result.confidence}")

        # 注意事项
        if result.notes:
            output.append("\n⚠️  注意事项:")
            for note in result.notes:
                output.append(f"   • {note}")

        return "\n".join(output)


# ============================================================================
# 模块2：减持方案合规检查器
# ============================================================================

@dataclass
class PlanCheckItem:
    """单项检查结果"""
    check_name: str          # 检查项名称
    result: str              # 合规/不合规/不适用/待核实
    actual_value: str         # 实际值
    limit_value: str         # 限制值
    rule_source: str         # 法规依据
    notes: List[str]         # 注意事项


@dataclass
class PlanCheckResult:
    """减持方案合规检查结果"""
    overall_status: str       # 整体状态：合规/不合规/部分不合规
    checks: List[PlanCheckItem]  # 各项检查结果
    warnings: List[str]       # 警告信息
    suggestions: List[str]    # 改进建议


class PlanChecker:
    """减持方案合规检查器"""

    # 减持比例限制
    CONCENTRATED_AUCTION_LIMIT = 1.0   # 集中竞价90日≤1%
    BLOCK_TRADE_LIMIT = 2.0              # 大宗交易90日≤2%
    TOTAL_LIMIT = 3.0                     # 合计≤3%

    # 法规依据
    RULE_SOURCES = {
        "集中竞价限制": "《深交所自律监管指引第18号》第十二条",
        "大宗交易限制": "《深交所自律监管指引第18号》第十三条",
        "合计限制": "《上市公司股东减持股份管理暂行办法》",
        "预披露": "《深交所自律监管指引第18号》第十一条",
        "窗口期": "《深交所自律监管指引第18号》及《公司法》",
        "董监高限制": "《上市公司董监高持股变动管理规则》",
        "权益变动": "《证券法》第六十三条",
        "创投基金": "《上市公司创业投资基金股东减持股份的特别规定》",
    }

    # 窗口期定义
    WINDOW_PERIODS = {
        "年报半年报": "前15日",
        "季报业绩预告": "前10日",
    }

    def __init__(self):
        """初始化方案检查器"""
        pass

    def check_plan(
        self,
        # 基本信息
        shareholder_name: str = None,      # 股东姓名
        identity: str = None,               # 身份：控股股东/实控人/5%以上股东/董监高/一般股东/创投基金
        current_holding: float = None,     # 当前持股比例（%）
        total_shares: int = None,          # 公司总股本
        share_source: str = None,          # 股份来源

        # 减持计划
        reduce_amount: float = None,        # 计划减持数量
        reduce_ratio: float = None,         # 计划减持比例（%）
        reduce_methods: List[str] = None,    # 减持方式：集中竞价、大宗交易、协议转让等
        start_date: str = None,            # 开始日期 YYYY-MM-DD
        end_date: str = None,              # 结束日期 YYYY-MM-DD

        # 创投基金特有
        investment_months: int = None,      # 投资期限（月数）

        # 董监高特有
        annual_transfer_limit: float = 25.0, # 年度减持比例限制（%）
        current_holding_shares: int = None, # 当前持有股数

        # 预披露状态
        pre_disclosed: bool = False,        # 是否已预披露
        pre_disclose_date: str = None,     # 预披露日期

        # 窗口期检查
        check_window_period: bool = True,   # 是否检查窗口期
        report_dates: List[str] = None,    # 定期报告日期列表
    ) -> PlanCheckResult:
        """
        检查减持方案合规性

        Returns:
            PlanCheckResult: 合规检查结果
        """
        checks = []
        warnings = []
        suggestions = []

        # 计算减持比例
        if reduce_ratio is None and reduce_amount and total_shares:
            reduce_ratio = (reduce_amount / total_shares) * 100

        # 检查1：减持比例限制
        if reduce_methods and current_holding and reduce_ratio:
            # 判断是否为大股东/特定股东
            is_major = self._is_major_shareholder(identity, current_holding)

            if is_major and "集中竞价" in reduce_methods:
                check = self._check_concentrated_auction_limit(reduce_ratio)
                checks.append(check)
                if check.result == "不合规":
                    suggestions.append(f"集中竞价减持比例超过1%限制，建议分多次减持或改用其他方式")

            if is_major and "大宗交易" in reduce_methods:
                check = self._check_block_trade_limit(reduce_ratio)
                checks.append(check)
                if check.result == "不合规":
                    suggestions.append(f"大宗交易减持比例超过2%限制，建议分多次减持")

            # 合计限制
            if is_major and reduce_methods:
                check = self._check_total_limit(reduce_ratio, reduce_methods)
                checks.append(check)
                if check.result == "不合规":
                    suggestions.append(f"合计减持比例超过3%限制，建议调整减持方式组合")

        # 检查2：创投基金特殊规则
        if identity and "创投" in identity and investment_months:
            check = self._check_vc_rules(investment_months, reduce_methods, reduce_ratio)
            checks.append(check)

        # 检查3：预披露义务
        if self._need_pre_disclosure(identity, current_holding):
            check = self._check_pre_disclosure(
                pre_disclosed,
                pre_disclose_date,
                start_date
            )
            checks.append(check)
            if check.result == "不合规":
                warnings.append(f"减持前需提前15个交易日预披露，否则可能构成违规减持")

        # 检查4：窗口期限制
        if check_window_period and self._is_director_officer(identity) and report_dates:
            check = self._check_window_period(start_date, report_dates)
            checks.append(check)
            if check.result == "不合规":
                warnings.append(f"减持时间处于窗口期内，董监高在此期间不得减持")

        # 检查5：董监高年度减持限制
        if self._is_director_officer(identity) and current_holding_shares:
            check = self._check_director_officer_limit(
                reduce_amount,
                current_holding_shares,
                annual_transfer_limit
            )
            checks.append(check)
            if check.result == "不合规":
                warnings.append(f"超过董监高年度25%减持限制")

        # 检查6：5%权益变动线
        if current_holding and reduce_ratio:
            check = self._check_5_percent_line(current_holding, reduce_ratio)
            checks.append(check)
            if check.result == "不合规":
                warnings.append(f"减持后持股触及或跌破5%整数倍，需暂停并披露")

        # 检查7：不能减持情形（破发、破净、分红不达标）
        if self._is_controlling_shareholder(identity):
            check = self._check_no_sell_restrictions()
            checks.append(check)

        # 计算整体状态
        overall = "合规"
        for check in checks:
            if check.result == "不合规":
                overall = "不合规"
                break
            elif check.result == "待核实" and overall == "合规":
                overall = "部分不合规"

        return PlanCheckResult(
            overall_status=overall,
            checks=checks,
            warnings=warnings,
            suggestions=suggestions
        )

    def _is_major_shareholder(self, identity: str, holding: float) -> bool:
        """判断是否为大股东"""
        if not identity or not holding:
            return False
        return (
            "控股" in identity or
            "实控" in identity or
            "5%" in identity or
            holding >= 5.0
        )

    def _is_controlling_shareholder(self, identity: str) -> bool:
        """判断是否为控股股东/实控人"""
        if not identity:
            return False
        return "控股" in identity or "实控" in identity

    def _is_director_officer(self, identity: str) -> bool:
        """判断是否为董监高"""
        if not identity:
            return False
        return "董监高" in identity or "董事" in identity or "监事" in identity or "高级管理人员" in identity

    def _need_pre_disclosure(self, identity: str, holding: float) -> bool:
        """判断是否需要预披露"""
        return self._is_major_shareholder(identity, holding)

    def _check_concentrated_auction_limit(self, reduce_ratio: float) -> PlanCheckItem:
        """检查集中竞价90日1%限制"""
        is_compliant = reduce_ratio <= self.CONCENTRATED_AUCTION_LIMIT
        return PlanCheckItem(
            check_name="集中竞价90日减持比例",
            result="合规" if is_compliant else "不合规",
            actual_value=f"{reduce_ratio}%",
            limit_value=f"≤{self.CONCENTRATED_AUCTION_LIMIT}%",
            rule_source=self.RULE_SOURCES["集中竞价限制"],
            notes=["大股东/特定股东通过集中竞价减持，90日内不得超过公司股份总数1%"]
        )

    def _check_block_trade_limit(self, reduce_ratio: float) -> PlanCheckItem:
        """检查大宗交易90日2%限制"""
        is_compliant = reduce_ratio <= self.BLOCK_TRADE_LIMIT
        return PlanCheckItem(
            check_name="大宗交易90日减持比例",
            result="合规" if is_compliant else "不合规",
            actual_value=f"{reduce_ratio}%",
            limit_value=f"≤{self.BLOCK_TRADE_LIMIT}%",
            rule_source=self.RULE_SOURCES["大宗交易限制"],
            notes=["大股东/特定股东通过大宗交易减持，90日内不得超过公司股份总数2%"]
        )

    def _check_total_limit(self, reduce_ratio: float, methods: List[str]) -> PlanCheckItem:
        """检查合计3%限制"""
        # 简化处理：假设不同方式的减持比例相加不超过3%
        is_compliant = reduce_ratio <= self.TOTAL_LIMIT
        method_str = "+".join(methods)
        return PlanCheckItem(
            check_name="减持方式合计比例",
            result="合规" if is_compliant else "不合规",
            actual_value=f"{reduce_ratio}% ({method_str})",
            limit_value=f"≤{self.TOTAL_LIMIT}%",
            rule_source=self.RULE_SOURCES["合计限制"],
            notes=["大股东通过多种方式减持，合计比例不得超过公司股份总数3%"]
        )

    def _check_vc_rules(self, investment_months: int, methods: List[str], reduce_ratio: float) -> PlanCheckItem:
        """检查创投基金特殊规则"""
        notes = []

        if investment_months < 36:
            limit_desc = "90日≤1%（竞价），90日≤2%（大宗）"
        elif investment_months < 48:
            limit_desc = "60日≤1%（竞价），60日≤2%（大宗）"
        elif investment_months < 60:
            limit_desc = "30日≤1%（竞价），30日≤2%（大宗）"
        else:
            limit_desc = "无比例限制（投资≥60个月豁免）"
            return PlanCheckItem(
                check_name="创投基金减持比例",
                result="合规",
                actual_value=f"投资{investment_months}个月，{reduce_ratio}%",
                limit_value=limit_desc,
                rule_source=self.RULE_SOURCES["创投基金"],
                notes=["投资期限≥60个月，减持不受比例限制"]
            )

        return PlanCheckItem(
            check_name="创投基金减持比例",
            result="合规",
            actual_value=f"投资{investment_months}个月，{reduce_ratio}%",
            limit_value=limit_desc,
            rule_source=self.RULE_SOURCES["创投基金"],
            notes=[f"投资期限{investment_months}个月，适用{limit_desc}"]
        )

    def _check_pre_disclosure(self, pre_disclosed: bool, pre_date: str, start_date: str) -> PlanCheckItem:
        """检查预披露义务"""
        notes = [
            "大股东/董监高减持需在首次卖出前15个交易日披露计划"
        ]

        if not pre_disclosed:
            return PlanCheckItem(
                check_name="减持预披露",
                result="不合规",
                actual_value="未预披露",
                limit_value="首次卖出前15个交易日",
                rule_source=self.RULE_SOURCES["预披露"],
                notes=notes
            )

        # 检查是否提前15个交易日
        # 这里简化处理，实际需要考虑交易日
        if start_date and pre_date:
            notes.append(f"已预披露，日期: {pre_date}")
            return PlanCheckItem(
                check_name="减持预披露",
                result="合规",
                actual_value=f"已预披露（{pre_date}）",
                limit_value="首次卖出前15个交易日",
                rule_source=self.RULE_SOURCES["预披露"],
                notes=notes
            )

        return PlanCheckItem(
            check_name="减持预披露",
            result="待核实",
            actual_value="需确认预披露日期",
            limit_value="首次卖出前15个交易日",
            rule_source=self.RULE_SOURCES["预披露"],
            notes=notes
        )

    def _check_window_period(self, start_date: str, report_dates: List[str]) -> PlanCheckItem:
        """检查窗口期限制"""
        if not start_date:
            return PlanCheckItem(
                check_name="减持窗口期",
                result="待核实",
                actual_value="缺少减持日期",
                limit_value="定期报告前15日，季报/业绩预告前10日",
                rule_source=self.RULE_SOURCES["窗口期"],
                notes=["董监高在定期报告、业绩预告、业绩快报公告窗口期内不得减持"]
            )

        if not report_dates:
            return PlanCheckItem(
                check_name="减持窗口期",
                result="待核实",
                actual_value="缺少定期报告日期",
                limit_value="定期报告前15日，季报/业绩预告前10日",
                rule_source=self.RULE_SOURCES["窗口期"],
                notes=["请提供定期报告、业绩预告/快报公告日期以判断窗口期"]
            )

        return PlanCheckItem(
            check_name="减持窗口期",
            result="待核实",
            actual_value=f"计划减持日: {start_date}",
            limit_value="定期报告前15日，季报/业绩预告前10日",
            rule_source=self.RULE_SOURCES["窗口期"],
            notes=[f"需对比减持日期与以下报告日期: {', '.join(report_dates)}"]
        )

    def _check_director_officer_limit(self, reduce_amount: int, holding_shares: int, limit: float) -> PlanCheckItem:
        """检查董监高年度减持25%限制"""
        if not holding_shares:
            return PlanCheckItem(
                check_name="董监高年度减持比例",
                result="待核实",
                actual_value="缺少持有股数",
                limit_value=f"≤{limit}%",
                rule_source=self.RULE_SOURCES["董监高限制"],
                notes=["董监高任职期间每年减持不得超过其所持本公司股份总数的25%"]
            )

        if holding_shares <= 1000:
            return PlanCheckItem(
                check_name="董监高年度减持比例",
                result="合规",
                actual_value=f"持有{holding_shares}股（≤1000股可一次全部转让）",
                limit_value=f"≤{limit}%",
                rule_source=self.RULE_SOURCES["董监高限制"],
                notes=["持股不超过1000股，可一次全部转让"]
            )

        max_reduce = int(holding_shares * limit / 100)
        actual_ratio = (reduce_amount / holding_shares * 100) if reduce_amount else 0
        is_compliant = reduce_amount <= max_reduce if reduce_amount else True

        return PlanCheckItem(
            check_name="董监高年度减持比例",
            result="合规" if is_compliant else "不合规",
            actual_value=f"{actual_ratio:.2f}%（{reduce_amount}股）",
            limit_value=f"≤{limit}%（{max_reduce}股）",
            rule_source=self.RULE_SOURCES["董监高限制"],
            notes=[f"董监高年度可转让不超过所持股份的{limit}%"]
        )

    def _check_5_percent_line(self, current_holding: float, reduce_ratio: float) -> PlanCheckItem:
        """检查5%权益变动线"""
        new_holding = current_holding - reduce_ratio

        # 检查是否触及5%整数倍
        five_percent_lines = [i * 5 for i in range(1, 21)]  # 5%, 10%, ..., 100%
        crossed_lines = []

        for line in five_percent_lines:
            if (current_holding > line and new_holding <= line) or \
               (current_holding >= line and new_holding < line):
                crossed_lines.append(line)

        if crossed_lines:
            return PlanCheckItem(
                check_name="5%权益变动线",
                result="不合规",
                actual_value=f"{current_holding}% → {new_holding:.2f}%",
                limit_value=f"触及{crossed_lines}%线需暂停并披露",
                rule_source=self.RULE_SOURCES["权益变动"],
                notes=[
                    f"减持后持股从{current_holding}%降至{new_holding:.2f}%",
                    f"触及或跌破{crossed_lines}%整数倍",
                    "需要在持股每增减5%时报告并公告",
                    "权益变动后3日内不得买卖"
                ]
            )

        return PlanCheckItem(
            check_name="5%权益变动线",
            result="合规",
            actual_value=f"{current_holding}% → {new_holding:.2f}%",
            limit_value="未触及5%整数倍",
            rule_source=self.RULE_SOURCES["权益变动"],
            notes=["未触及5%权益变动披露线"]
        )

    def _check_no_sell_restrictions(self) -> PlanCheckItem:
        """检查不能减持情形（破发、破净、分红不达标）"""
        return PlanCheckItem(
            check_name="不能减持情形",
            result="待核实",
            actual_value="需核查公司财务状况",
            limit_value="破发、破净、分红不达标时不得减持",
            rule_source="《深交所自律监管指引第18号》第七条、第八条",
            notes=[
                "破发：股价跌破IPO发行价",
                "破净：股价跌破每股净资产",
                "分红不达标：最近3年未分红或分红<年均净利润30%",
                "控股股东/实控人触发上述情形不得通过竞价/大宗减持"
            ]
        )

    def format_result(self, result: PlanCheckResult) -> str:
        """格式化输出合规检查结果"""
        output = []

        # 整体状态
        status_icon = {
            "合规": "✅",
            "不合规": "❌",
            "部分不合规": "⚠️"
        }.get(result.overall_status, "❓")

        output.append("=" * 60)
        output.append("📊 减持方案合规检查结果")
        output.append("=" * 60)
        output.append(f"\n🎯 整体状态: {status_icon} {result.overall_status}")
        output.append("\n" + "─" * 60)

        # 详细检查项
        output.append("\n📋 详细检查项:")
        for i, check in enumerate(result.checks, 1):
            result_icon = {
                "合规": "✅",
                "不合规": "❌",
                "待核实": "⚠️",
                "不适用": "○"
            }.get(check.result, "❓")

            output.append(f"\n{i}. {check.check_name}")
            output.append(f"   状态: {result_icon} {check.result}")
            output.append(f"   实际值: {check.actual_value}")
            output.append(f"   限制值: {check.limit_value}")
            output.append(f"   法规: {check.rule_source}")

            if check.notes:
                output.append(f"   说明:")
                for note in check.notes:
                    output.append(f"     • {note}")

        # 警告
        if result.warnings:
            output.append("\n" + "─" * 60)
            output.append("\n⚠️  警告:")
            for warning in result.warnings:
                output.append(f"   • {warning}")

        # 改进建议
        if result.suggestions:
            output.append("\n" + "─" * 60)
            output.append("\n💡 改进建议:")
            for suggestion in result.suggestions:
                output.append(f"   • {suggestion}")

        output.append("\n" + "=" * 60)

        return "\n".join(output)

    def parse_plan_string(self, plan_str: str) -> Dict[str, any]:
        """解析减持方案字符串"""
        params = {
            "shareholder_name": None,
            "identity": None,
            "current_holding": None,
            "total_shares": None,
            "share_source": None,
            "reduce_amount": None,
            "reduce_ratio": None,
            "reduce_methods": None,
            "start_date": None,
            "end_date": None,
            "investment_months": None,
            "pre_disclosed": False,
            "check_window_period": True,
        }

        key_value_map = {
            "股东": "shareholder_name",
            "姓名": "shareholder_name",
            "身份": "identity",
            "持股": "current_holding",
            "计划减持": "reduce_ratio",
            "方式": "reduce_methods",
            "时间": "start_date",
            "期间": "start_date",
            "开始": "start_date",
            "结束": "end_date",
        }

        for part in plan_str.split(","):
            part = part.strip()
            if ":" in part:
                key, value = [p.strip() for p in part.split(":", 1)]
                mapped_key = key_value_map.get(key)
                if mapped_key:
                    if mapped_key in ["current_holding", "reduce_ratio"]:
                        match = re.search(r'([\d.]+)', value)
                        if match:
                            params[mapped_key] = float(match.group(1))
                    elif mapped_key == "reduce_methods":
                        methods = []
                        if "集中竞价" in value:
                            methods.append("集中竞价")
                        if "大宗交易" in value:
                            methods.append("大宗交易")
                        if "协议转让" in value:
                            methods.append("协议转让")
                        if methods:
                            params[mapped_key] = methods
                    elif mapped_key == "start_date":
                        # 解析时间区间
                        if "至" in value or "-" in value:
                            dates = re.split(r'至|-', value)
                            params["start_date"] = dates[0].strip()
                            params["end_date"] = dates[1].strip()
                        else:
                            params[mapped_key] = value.strip()
                    else:
                        params[mapped_key] = value

        return params


# ============================================================================
# 法规库索引器
# ============================================================================

class LegalIndexer:
    """法规库索引器 - 建立关键词到法规片段的映射"""

    # 减持相关关键词
    KEYWORDS = [
        "减持", "锁定期", "预披露", "大宗交易", "集中竞价", "协议转让",
        "创投基金", "董监高", "5%", "权益变动", "信息披露", "受让方",
        "窗口期", "计划", "实际", "减持比例", "减持数量", "减持期间",
        "大股东", "控股股东", "实际控制人", "一致行动人", "非公开",
        "首发前", "定增", "配售", "战略配售", "禁售", "限售",
        "股东", "股份", "变动", "报告", "公告", "监管"
    ]

    def __init__(self, legal_dir: str = None):
        """
        初始化法规库

        Args:
            legal_dir: 法规目录路径，默认为 main/法律法规/
        """
        if legal_dir is None:
            legal_dir = PROJECT_ROOT / "main" / "法律法规"
        self.legal_dir = Path(legal_dir)
        self.index = defaultdict(list)  # keyword -> [(content, source, line), ...]
        self.documents = []  # 存储所有文档信息
        self._load_documents()

    def _load_documents(self):
        """扫描法规目录，建立索引"""
        if not self.legal_dir.exists():
            return

        # 静默模式，不打印加载信息
        pass

        # 支持的文件扩展名
        extensions = ['.txt', '.md']

        for ext in extensions:
            for file_path in self.legal_dir.rglob(f"*{ext}"):
                self._parse_file(file_path)

    def _parse_file(self, file_path: Path):
        """解析单个法规文件"""
        try:
            content = file_path.read_text(encoding='utf-8')
            lines = content.split('\n')

            source = file_path.name

            # 逐行解析
            for i, line in enumerate(lines, 1):
                line = line.strip()
                if len(line) < 5:  # 跳过太短的行
                    continue

                # 查找关键词
                found_keywords = [kw for kw in self.KEYWORDS if kw in line]

                if found_keywords:
                    # 获取上下文（前后几行）
                    context = self._get_context(lines, i - 1, context_lines=2)

                    for kw in found_keywords:
                        self.index[kw].append({
                            "content": context,
                            "source": source,
                            "line": i,
                            "keywords": found_keywords
                        })

            self.documents.append({
                "path": str(file_path),
                "name": source,
                "lines": len(lines)
            })

        except Exception as e:
            pass  # 静默模式

    def _get_context(self, lines: List[str], center_idx: int, context_lines: int = 2) -> str:
        """获取行周围的上下文"""
        start = max(0, center_idx - context_lines)
        end = min(len(lines), center_idx + context_lines + 1)
        return '\n'.join(lines[start:end])

    def search(self, query: str, top_n: int = 5) -> List[Dict]:
        """
        根据问题搜索相关法规片段

        Args:
            query: 用户问题
            top_n: 返回前N个最相关的结果

        Returns:
            匹配的法规片段列表
        """
        # 从问题中提取关键词
        query_keywords = [kw for kw in self.KEYWORDS if kw in query]

        # 收集相关片段
        all_results = []

        for kw in query_keywords:
            for item in self.index.get(kw, []):
                all_results.append(item)

        # 如果没找到关键词，尝试搜索所有片段
        if not query_keywords:
            for kw, items in self.index.items():
                all_results.extend(items)

        # 按匹配关键词数量排序
        all_results.sort(key=lambda x: len(x.get('keywords', [])), reverse=True)

        # 去重（按来源+行号）
        seen = set()
        unique_results = []
        for item in all_results:
            key = f"{item['source']}:{item['line']}"
            if key not in seen:
                seen.add(key)
                unique_results.append(item)

        return unique_results[:top_n]


# ============================================================================
# 模块3：智能问答增强
# ============================================================================

@dataclass
class QuestionType:
    """问题类型"""
    category: str      # 锁定期/比例限制/信息披露/窗口期/创投基金/其他
    keywords: List[str]
    description: str
    action: str        # 调用的动作


class QuestionClassifier:
    """问题分类器"""

    QUESTION_TYPES = [
        QuestionType(
            category="锁定期",
            keywords=["锁定期", "锁定", "受让方", "接盘方", "接手", "解禁后多久能卖"],
            description="关于受让方股份锁定期的问题",
            action="check_lock_period"
        ),
        QuestionType(
            category="比例限制",
            keywords=["比例", "减持多少", "减持上限", "90日", "集中竞价", "大宗交易", "协议转让"],
            description="关于减持比例限制的问题",
            action="check_ratio_limit"
        ),
        QuestionType(
            category="信息披露",
            keywords=["披露", "公告", "预披露", "提前几天", "公告日", "报告"],
            description="关于信息披露义务的问题",
            action="check_disclosure"
        ),
        QuestionType(
            category="窗口期",
            keywords=["窗口期", "年报前", "半年报前", "季报前", "业绩预告", "定期报告"],
            description="关于减持窗口期限制的问题",
            action="check_window_period"
        ),
        QuestionType(
            category="创投基金",
            keywords=["创投", "私募", "VC", "反向挂钩", "特别规定"],
            description="关于创投基金减持特殊规定的问题",
            action="check_vc_rules"
        ),
        QuestionType(
            category="不能减持",
            keywords=["不能减持", "禁止减持", "不得减持", "限制", "破发", "破净", "分红不达标"],
            description="关于什么情况下不能减持的问题",
            action="check_restriction"
        ),
        QuestionType(
            category="方案检查",
            keywords=["方案", "计划", "合规", "检查", "是否符合"],
            description="关于减持方案合规检查的问题",
            action="check_plan"
        ),
    ]

    @classmethod
    def classify(cls, question: str) -> QuestionType:
        """分类问题类型"""
        question_lower = question.lower()

        # 计算每个类型的关键词匹配数
        scores = []
        for qt in cls.QUESTION_TYPES:
            score = sum(1 for kw in qt.keywords if kw.lower() in question_lower)
            if score > 0:
                scores.append((score, qt))

        # 返回得分最高的类型
        if scores:
            scores.sort(key=lambda x: x[0], reverse=True)
            return scores[0][1]

        # 默认返回其他
        return QuestionType(
            category="其他",
            keywords=[],
            description="一般性减持法规问题",
            action="general_query"
        )

    @classmethod
    def extract_lock_params(cls, question: str) -> Dict[str, str]:
        """从问题中提取锁定期查询参数"""
        params = {}

        # 股份来源
        share_sources = {
            "IPO前": ["ipo", "首发", "首次公开发行", "原始股"],
            "定增": ["定增", "非公开", "定向增发"],
            "二级市场买入": ["二级市场", "集中竞价买入", "增持"],
            "协议转让": ["协议转让"],
            "司法拍卖": ["司法", "拍卖", "强制执行"],
        }
        for source, keywords in share_sources.items():
            if any(kw in question.lower() for kw in keywords):
                params["share_source"] = source
                break

        # 卖方身份
        seller_identities = {
            "控股股东": ["控股股东", "控股"],
            "实控人": ["实际控制人", "实控"],
            "5%以上股东": ["5%", "持股5", "大股东"],
            "创投基金": ["创投", "vc", "私募基金"],
            "董监高": ["董监高", "董事", "监事", "高级管理人员"],
        }
        for identity, keywords in seller_identities.items():
            if any(kw in question.lower() for kw in keywords):
                params["seller_identity"] = identity
                break

        # 减持方式
        methods = {
            "大宗交易": ["大宗交易", "大宗"],
            "协议转让": ["协议转让", "协议"],
            "询价转让": ["询价转让", "询价"],
            "集中竞价": ["集中竞价", "竞价"],
        }
        for method, keywords in methods.items():
            if any(kw in question.lower() for kw in keywords):
                params["reduce_method"] = method
                break

        return params

    @classmethod
    def get_one_line_summary(cls, category: str) -> str:
        """获取实操要点的一句话总结"""
        summaries = {
            "锁定期": "大宗交易/协议转让受让方通常需锁6个月，创投基金投资≥60个月可豁免",
            "比例限制": "大股东集中竞价90日≤1%，大宗交易90日≤2%，合计≤3%",
            "信息披露": "大股东减持前15个交易日需披露计划，实施完毕后2个交易日内披露结果",
            "窗口期": "年报半年报前15日、季报业绩预告前10日董监高不得减持",
            "创投基金": "投资期限越长减持限制越宽松，≥60个月可豁免受让方锁定期",
            "不能减持": "破发破净分红不达标时控股股东/实控人不得通过竞价/大宗减持",
            "方案检查": "减持方案需同时满足比例限制、预披露、窗口期等多重约束"
        }
        return summaries.get(category, "具体请参照最新法规执行")


# ============================================================================
# AI问答器
# ============================================================================

class LegalAIAdvisor:
    """基于AI的法规问答助手"""

    SYSTEM_PROMPT = """你是A股上市公司减持政策法规专家。

回答问题时请遵循以下格式：

1️⃣ 法规原文
   - 引用具体的法规条文原文（包含法规名称、条款号）

2️⃣ 通俗解释
   - 用通俗易懂的语言解释法规要求
   - 说明适用对象和情形

3️⃣ 实操要点
   - 列出实际操作中的注意事项
   - 常见误区提醒

4️⃣ 特别提醒
   - 如涉及最新政策变化，提醒用户核实
   - 不同交易所/板块可能有差异

请基于提供的法规原文进行回答，不要编造条文。
"""

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        """
        初始化AI问答器

        Args:
            api_key: OpenAI API密钥
            base_url: OpenAI API基础URL
            model: 模型名称
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.4")
        self.enabled = bool(self.api_key)

    def ask(self, question: str, legal_context: List[Dict] = None, add_summary: bool = True) -> str:
        """
        向AI提问

        Args:
            question: 用户问题
            legal_context: 相关法规片段
            add_summary: 是否在回答末尾添加实操要点总结

        Returns:
            AI回答
        """
        if not self.enabled:
            # API未配置，返回提示信息
            return ("⚠️  AI回答功能未启用（未配置 OPENAI_API_KEY）\n"
                    "请配置 .env 文件中的 OPENAI_API_KEY 和 OPENAI_BASE_URL\n"
                    "参考 .env.example 文件配置格式")

        # 构建法规上下文
        context_text = ""
        if legal_context:
            context_text = "\n\n相关法规原文：\n" + "="*50 + "\n"
            for i, item in enumerate(legal_context, 1):
                context_text += f"\n【{i}】{item['source']} 第{item['line']}行附近：\n"
                context_text += item['content'] + "\n"

        # 构建用户提示
        user_prompt = f"问题：{question}{context_text}"

        # 调用API
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=120.0
            )

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )

            result = response.choices[0].message.content

            # 添加实操要点总结
            if add_summary:
                qt = QuestionClassifier.classify(question)
                summary = QuestionClassifier.get_one_line_summary(qt.category)
                result += f"\n\n📌 实操要点（一句话）：{summary}"

            return result

        except ImportError:
            # 备用方案：使用requests直接调用
            import requests

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 2000
            }

            if self.base_url:
                url = f"{self.base_url.rstrip('/')}/chat/completions"
            else:
                url = "https://api.openai.com/v1/chat/completions"

            response = requests.post(url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            result = response.json()["choices"][0]["message"]["content"]

            # 添加实操要点总结
            if add_summary:
                qt = QuestionClassifier.classify(question)
                summary = QuestionClassifier.get_one_line_summary(qt.category)
                result += f"\n\n📌 实操要点（一句话）：{summary}"

            return result


# ============================================================================
# 主程序
# ============================================================================

def print_header():
    """打印程序标题"""
    print("=" * 60)
    print("📖 减持法规问答")
    print("=" * 60)


def print_footer():
    """打印程序脚注"""
    print("=" * 60)
    print("⚠️  提示：以上回答基于本地法规库，具体以最新法规为准")
    print("=" * 60)


def check_lock_period_mode(args):
    """锁定期速查模式"""
    print_header()
    print("🔒 受让方锁定期速查模式")
    print()

    checker = LockPeriodChecker()

    # 解析输入参数
    if args.lock:
        # 命令行参数格式: "IPO前取得,控股股东,大宗交易"
        parts = [p.strip() for p in args.lock.split(",")]
        params = {
            "share_source": parts[0] if len(parts) > 0 else None,
            "seller_identity": parts[1] if len(parts) > 1 else None,
            "reduce_method": parts[2] if len(parts) > 2 else None,
            "investment_months": getattr(args, 'investment_months', None),
        }
    else:
        # 从其他参数读取
        params = {
            "share_source": getattr(args, 'share_source', None),
            "seller_identity": getattr(args, 'seller_identity', None),
            "reduce_method": getattr(args, 'reduce_method', None),
            "investment_months": getattr(args, 'investment_months', None),
        }

    # 执行判断
    result = checker.check_lock_period(**params)

    # 输出结果
    print(checker.format_result(result))
    print()

    # 如果信息不足，给出建议
    if result.confidence == "信息不足":
        print("💡 建议用法：")
        print("   python3 jianchi/legal_advisor.py --lock \"IPO前取得,控股股东,大宗交易\"")
        print()
        print("   或使用完整参数：")
        print("   python3 jianchi/legal_advisor.py --lock \\")
        print("       --share-source \"IPO前取得\" \\")
        print("       --seller-identity \"控股股东\" \\")
        print("       --reduce-method \"大宗交易\"")
        print()


def check_plan_mode(args):
    """减持方案合规检查模式"""
    print_header()

    checker = PlanChecker()

    # 解析输入参数
    if args.plan:
        # 从字符串解析
        params = checker.parse_plan_string(args.plan)
    else:
        # 从单独参数读取
        params = {
            "shareholder_name": getattr(args, 'plan_shareholder', None),
            "identity": getattr(args, 'plan_identity', None),
            "current_holding": getattr(args, 'plan_holding', None),
            "total_shares": getattr(args, 'plan_total_shares', None),
            "share_source": getattr(args, 'plan_share_source', None),
            "reduce_ratio": getattr(args, 'plan_reduce_ratio', None),
            "reduce_methods": getattr(args, 'plan_methods', None),
            "start_date": getattr(args, 'plan_start_date', None),
            "end_date": getattr(args, 'plan_end_date', None),
            "investment_months": getattr(args, 'plan_investment_months', None),
            "pre_disclosed": getattr(args, 'plan_pre_disclosed', False),
        }

    # 执行检查
    result = checker.check_plan(**params)

    # 输出结果
    print(checker.format_result(result))
    print()

    # 如果信息不足，给出建议
    insufficient = any([
        params.get("current_holding") is None,
        params.get("reduce_ratio") is None,
        params.get("identity") is None
    ])

    if insufficient or result.overall_status == "待核实":
        print("💡 建议用法：")
        print("   python3 jianchi/legal_advisor.py --plan \\")
        print("       \"股东:张三,身份:控股股东,持股:8%,计划减持:3%,方式:大宗交易,时间:2026-04-01\"")
        print()
        print("   或使用完整参数：")
        print("   python3 jianchi/legal_advisor.py --plan-check \\")
        print("       --plan-identity \"控股股东\" \\")
        print("       --plan-holding 8 \\")
        print("       --plan-reduce-ratio 3 \\")
        print("       --plan-methods \"大宗交易\"")
        print()


def ask_question(question: str, indexer: LegalIndexer, ai: LegalAIAdvisor, verbose: bool = False):
    """
    处理单个问题（增强版 - 自动识别问题类型并调用相应模块）

    Args:
        question: 用户问题
        indexer: 法规索引器
        ai: AI问答器
        verbose: 是否显示检索到的法规片段
    """
    print()
    print(f"❓ 问题：{question}")
    print()

    # 问题分类
    qt = QuestionClassifier.classify(question)
    print(f"🏷️  问题类型：{qt.category}")
    print()

    # 锁定期问题：先调用速查器
    if qt.category == "锁定期":
        print("🔒 检测到锁定期相关问题，调用速查器...")
        print()

        checker = LockPeriodChecker()
        params = QuestionClassifier.extract_lock_params(question)
        result = checker.check_lock_period(**params)

        # 打印速查结果
        print(checker.format_result(result))
        print()

        # 如果信息足够且判断确定，可以跳过AI回答
        if result.confidence == "确定" and result.locked is not None:
            print("📚 法规库检索结果已给出明确答案")
            return

    # 检索相关法规
    legal_context = indexer.search(question, top_n=5)

    # 显示检索到的法规
    if legal_context:
        if verbose:
            print("📜 相关法规片段：")
            print("-" * 60)
            for i, item in enumerate(legal_context, 1):
                print(f"\n【{i}】{item['source']} 第{item['line']}行附近：")
                print(item['content'])
            print("-" * 60)
            print()
        else:
            print("📜 相关法规：")
            for i, item in enumerate(legal_context, 1):
                print(f"  - 《{item['source']}》第{item['line']}行附近")
            print()

    # AI回答
    print("💡 回答：")
    print("-" * 60)
    answer = ai.ask(question, legal_context, add_summary=True)
    print(answer)
    print("-" * 60)


def interactive_mode(indexer: LegalIndexer, ai: LegalAIAdvisor):
    """
    交互式问答模式

    Args:
        indexer: 法规索引器
        ai: AI问答器
    """
    print_header()
    print("💡 输入问题进行咨询，输入 'quit' 或 'exit' 退出")
    print("💡 使用 --lock 可快速查询锁定期")
    print("💡 使用 --plan 可检查减持方案合规性")
    print()

    while True:
        try:
            question = input("👤 请输入问题: ").strip()

            if not question:
                continue

            if question.lower() in ['quit', 'exit', 'q', '退出']:
                print("👋 再见！")
                break

            ask_question(question, indexer, ai, verbose=False)
            print()

        except KeyboardInterrupt:
            print("\n👋 再见！")
            break
        except Exception as e:
            print(f"❌ 发生错误: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="A股减持法规问答助手",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 单次问答
  python3 jianchi/legal_advisor.py "大股东减持需要提前多少天披露？"

  # 交互模式
  python3 jianchi/legal_advisor.py --chat

  # 锁定期速查（简洁格式）
  python3 jianchi/legal_advisor.py --lock "IPO前取得,控股股东,大宗交易"

  # 减持方案合规检查（简洁格式）
  python3 jianchi/legal_advisor.py --plan "股东:张三,身份:控股股东,持股:8%,计划减持:3%,方式:大宗交易"

  # 减持方案合规检查（完整参数）
  python3 jianchi/legal_advisor.py --plan-check \\
      --plan-identity "控股股东" \\
      --plan-holding 8 \\
      --plan-reduce-ratio 3 \\
      --plan-methods "大宗交易"

  # 显示检索到的法规片段
  python3 jianchi/legal_advisor.py "创投基金减持有什么特殊规定？" --verbose
        """
    )

    parser.add_argument(
        "question",
        nargs="?",
        help="要询问的问题（交互模式下可省略）"
    )
    parser.add_argument(
        "--chat", "-c",
        action="store_true",
        help="进入交互式问答模式"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示检索到的法规片段"
    )
    parser.add_argument(
        "--legal-dir",
        help="法规目录路径（默认: main/法律法规/）"
    )
    parser.add_argument(
        "--model",
        help="指定AI模型（覆盖.env中的设置）"
    )
    parser.add_argument(
        "--lock",
        nargs="?",
        const="",
        default=None,
        help="锁定期速查，格式: \"股份来源,卖方身份,减持方式\""
    )
    parser.add_argument(
        "--share-source",
        help="股份来源（用于--lock）"
    )
    parser.add_argument(
        "--seller-identity",
        help="卖方身份（用于--lock）"
    )
    parser.add_argument(
        "--reduce-method",
        help="减持方式（用于--lock）"
    )
    parser.add_argument(
        "--investment-months",
        type=int,
        help="创投基金投资期限月数（用于--lock）"
    )
    parser.add_argument(
        "--plan",
        help="减持方案合规检查，格式: \"股东:XX,身份:XX,持股:X%%,计划减持:X%%,方式:XXX\""
    )
    parser.add_argument(
        "--plan-check",
        action="store_true",
        help="进入减持方案合规检查模式"
    )
    parser.add_argument(
        "--plan-shareholder",
        help="股东姓名（用于--plan-check）"
    )
    parser.add_argument(
        "--plan-identity",
        help="股东身份（用于--plan-check）"
    )
    parser.add_argument(
        "--plan-holding",
        type=float,
        help="当前持股比例（用于--plan-check）"
    )
    parser.add_argument(
        "--plan-total-shares",
        type=int,
        help="公司总股本（用于--plan-check）"
    )
    parser.add_argument(
        "--plan-share-source",
        help="股份来源（用于--plan-check）"
    )
    parser.add_argument(
        "--plan-reduce-ratio",
        type=float,
        help="计划减持比例（用于--plan-check）"
    )
    parser.add_argument(
        "--plan-methods",
        help="减持方式，用逗号分隔（用于--plan-check）"
    )
    parser.add_argument(
        "--plan-start-date",
        help="减持开始日期 YYYY-MM-DD（用于--plan-check）"
    )
    parser.add_argument(
        "--plan-end-date",
        help="减持结束日期 YYYY-MM-DD（用于--plan-check）"
    )
    parser.add_argument(
        "--plan-investment-months",
        type=int,
        help="创投基金投资期限月数（用于--plan-check）"
    )
    parser.add_argument(
        "--plan-pre-disclosed",
        action="store_true",
        help="是否已预披露（用于--plan-check）"
    )

    args = parser.parse_args()

    # 检查是否为锁定期速查模式
    if args.lock is not None or any(getattr(args, arg, None) for arg in ['share_source', 'seller_identity', 'reduce_method', 'investment_months']):
        # 静默加载法规库
        LegalIndexer(args.legal_dir)
        check_lock_period_mode(args)
        return

    # 检查是否为减持方案合规检查模式
    if args.plan or args.plan_check:
        # 静默加载法规库
        LegalIndexer(args.legal_dir)
        check_plan_mode(args)
        return

    # 初始化法规索引器
    indexer = LegalIndexer(args.legal_dir)
    print(f"📚 正在加载法规库: {indexer.legal_dir}")
    print(f"✅ 已加载 {len(indexer.documents)} 个法规文件，索引 {sum(len(v) for v in indexer.index.values())} 条条目")
    print()

    # 初始化AI问答器
    ai = LegalAIAdvisor(model=args.model)

    # 根据参数选择模式
    if args.chat or not args.question:
        # 交互模式
        interactive_mode(indexer, ai)
    else:
        # 单次问答模式
        print_header()
        ask_question(args.question, indexer, ai, verbose=args.verbose)
        print_footer()


if __name__ == "__main__":
    main()
