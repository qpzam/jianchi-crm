"""
减持概率评分模型
整合自: reduction_predictor_v3.py

100分制评分体系:
  已发公告  40分 (确定性信号)
  解禁日期  25分 (时间窗口)
  股价涨幅  15分 (减持动机)
  质押率    10分 (资金压力)
  历史减持   8分 (行为模式)
  股东类型   7分 (减持倾向)
  股份来源   5分 (解锁意愿)
  PE估值     5分 (高估套现)
"""
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Semaphore

import pandas as pd

from .config import TINYSHARE_TOKEN, SCORE_WEIGHTS, INDUSTRY_PE_AVG
from .utils.stock import clean_stock_code, format_ts_code, classify_shareholder


# ============================================================
# TinyShare API 封装
# ============================================================

class TinyShareAPI:
    """TinyShare/Tushare 数据接口"""

    def __init__(self, token: str = None):
        self.token = token or TINYSHARE_TOKEN
        if not self.token:
            raise ValueError("TINYSHARE_TOKEN 环境变量未设置，请设置后重试")
        self.available = False
        try:
            import tinyshare as ts
            ts.set_token(self.token)
            self.pro = ts.pro_api()
            self.available = True
        except Exception as e:
            print(f"⚠️ TinyShare 初始化失败: {e}")

    def get_daily(self, ts_code: str, days: int = 120):
        """日线行情"""
        if not self.available:
            return None
        try:
            end = datetime.now().strftime('%Y%m%d')
            start = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
            return self.pro.daily(ts_code=ts_code, start_date=start, end_date=end)
        except Exception:
            return None

    def get_basic(self, ts_code: str):
        """基本面（PE/PB等）"""
        if not self.available:
            return None
        try:
            df = self.pro.daily_basic(ts_code=ts_code,
                                      trade_date=datetime.now().strftime('%Y%m%d'))
            if df is None or df.empty:
                df = self.pro.daily_basic(ts_code=ts_code)
            return df
        except Exception:
            return None

    def get_pledge(self, ts_code: str):
        """质押数据"""
        if not self.available:
            return None
        try:
            return self.pro.pledge_stat(ts_code=ts_code)
        except Exception:
            return None

    def get_holder_trade(self, ts_code: str, days: int = 365):
        """股东增减持历史"""
        if not self.available:
            return None
        try:
            end = datetime.now().strftime('%Y%m%d')
            start = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
            return self.pro.stk_holdertrade(ts_code=ts_code, start_date=start,
                                            end_date=end, in_de='减持')
        except Exception:
            return None


# API限流信号量：同时最多3个请求，避免触发TinyShare频率限制
_API_SEMAPHORE = Semaphore(3)


def _fetch_stock_data(api: TinyShareAPI, ts_code: str) -> dict:
    """获取单只股票的所有维度数据"""
    data = {"ts_code": ts_code}

    # 30日涨幅
    df = api.get_daily(ts_code, days=60)
    if df is not None and len(df) >= 2:
        recent = df.iloc[0]['close']
        d30_ago = df.iloc[min(29, len(df) - 1)]['close']
        data['change_pct'] = (recent - d30_ago) / d30_ago * 100

    # PE
    df = api.get_basic(ts_code)
    if df is not None and not df.empty:
        data['pe_ttm'] = df.iloc[0].get('pe_ttm')

    # 质押率
    df = api.get_pledge(ts_code)
    if df is not None and not df.empty:
        data['pledge_ratio'] = df.iloc[0].get('pledge_ratio')

    # 历史减持次数
    df = api.get_holder_trade(ts_code)
    if df is not None:
        data['reduction_count'] = len(df)
    else:
        data['reduction_count'] = 0

    return data


def _fetch_with_throttle(api: TinyShareAPI, ts_code: str) -> dict:
    """带限流的数据获取"""
    with _API_SEMAPHORE:
        result = _fetch_stock_data(api, ts_code)
        time.sleep(0.2)  # 每次请求后短暂等待
        return result


def batch_fetch(stocks: set, max_workers: int = 5) -> dict:
    """并行批量获取所有股票数据（限流保护）"""
    try:
        api = TinyShareAPI()
    except ValueError as e:
        print(f"⚠️ {e}，跳过市场数据获取")
        return {}

    if not api.available:
        print("⚠️ TinyShare 不可用，跳过市场数据获取")
        return {}

    results = {}
    ts_codes = {s: format_ts_code(s) for s in stocks}
    valid = {s: tc for s, tc in ts_codes.items() if tc}

    print(f"📊 并行获取 {len(valid)} 只股票数据 (workers={max_workers}, 限流=3并发)...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_fetch_with_throttle, api, tc): code
            for code, tc in valid.items()
        }
        for future in as_completed(futures):
            code = futures[future]
            try:
                results[code] = future.result()
            except Exception:
                results[code] = {}

    print(f"  完成: {len(results)} 只")
    return results


# ============================================================
# 评分模型
# ============================================================

class ReductionScorer:
    """减持概率评分器"""

    def __init__(self, industry_pe: float = None):
        self.today = datetime.now()
        self.industry_pe = industry_pe or INDUSTRY_PE_AVG

    def score_announcement(self, code: str, announcements_df: pd.DataFrame) -> tuple[int, str]:
        """已发公告 (0-40分)"""
        if announcements_df is None or announcements_df.empty:
            return 0, "无减持公告数据"
        code_col = 'clean_code' if 'clean_code' in announcements_df.columns else '股票代码'
        if code in announcements_df[code_col].values:
            return SCORE_WEIGHTS["announcement"], "已发布减持公告"
        return 0, "无减持公告"

    def score_unlock(self, days_to_unlock: int | None) -> tuple[int, str]:
        """解禁日期 (0-25分)"""
        if days_to_unlock is None:
            return 0, "无解禁数据"
        if days_to_unlock < 0:
            return 0, f"已解禁{abs(days_to_unlock)}天"
        if days_to_unlock <= 30:
            return 25, f"解禁在{days_to_unlock}天后"
        if days_to_unlock <= 90:
            return 15, f"解禁在{days_to_unlock}天后"
        return 5, f"解禁在{days_to_unlock}天后"

    def score_price(self, change_pct: float | None) -> tuple[int, str]:
        """股价涨幅 (0-15分)"""
        if change_pct is None:
            return 0, "涨幅数据缺失"
        if change_pct > 50:
            return 15, f"涨幅{change_pct:.1f}%"
        if change_pct > 30:
            return 12, f"涨幅{change_pct:.1f}%"
        if change_pct > 15:
            return 8, f"涨幅{change_pct:.1f}%"
        if change_pct > 5:
            return 4, f"涨幅{change_pct:.1f}%"
        return 0, f"涨幅{change_pct:.1f}%"

    def score_pledge(self, ratio: float | None) -> tuple[int, str]:
        """质押率 (0-10分)"""
        if ratio is None:
            return 0, "质押率未知"
        if ratio > 70:
            return 10, f"质押率{ratio:.1f}%"
        if ratio > 50:
            return 7, f"质押率{ratio:.1f}%"
        if ratio > 30:
            return 4, f"质押率{ratio:.1f}%"
        return 1, f"质押率{ratio:.1f}%"

    def score_history(self, count: int) -> tuple[int, str]:
        """历史减持记录 (0-8分)"""
        if count >= 3:
            return 8, f"历史减持{count}次"
        if count >= 1:
            return 5, f"历史减持{count}次"
        return 0, "无减持记录"

    def score_holder(self, name: str) -> tuple[int, str]:
        """股东类型 (0-7分)"""
        category = classify_shareholder(name)
        scores = {
            "PE/VC基金": 7,
            "一致行动人": 5,
            "个人股东": 5,
            "机构股东": 4,
            "公司高管": 4,
            "控股股东": 1,
            "未知": 3,
        }
        score = scores.get(category, 3)
        return score, category

    def score_source(self, source: str) -> tuple[int, str]:
        """股份来源 (0-5分)"""
        if not source or source == "未披露":
            return 0, "股份来源未知"
        source_lower = source.lower()
        if '股权激励' in source_lower:
            return 5, "股权激励"
        if '非公开发行' in source_lower or '定增' in source_lower:
            return 4, "非公开发行"
        if '集中竞价' in source_lower:
            return 3, "集中竞价买入"
        if '协议' in source_lower:
            return 2, "协议受让"
        if 'ipo' in source_lower or '首发' in source_lower or '首次公开' in source_lower:
            return 1, "IPO前取得"
        return 2, "其他来源"

    def score_pe(self, pe_ttm: float | None) -> tuple[int, str]:
        """PE估值 (0-5分)"""
        if pe_ttm is None:
            return 0, "PE数据缺失"
        ratio = pe_ttm / self.industry_pe
        if ratio > 2:
            return 5, f"PE{pe_ttm:.1f}(行业{self.industry_pe:.1f})"
        if ratio > 1.5:
            return 3, f"PE{pe_ttm:.1f}(行业{self.industry_pe:.1f})"
        return 0, f"PE{pe_ttm:.1f}(行业{self.industry_pe:.1f})"

    def calculate(self, record: dict, market_data: dict = None,
                  announcements_df: pd.DataFrame = None) -> dict:
        """
        计算单只股票的综合得分

        参数:
          record: 减持公告记录
          market_data: batch_fetch 返回的市场数据
          announcements_df: 所有减持公告 DataFrame（用于判断是否已发公告）

        返回: 带评分的记录 dict
        """
        market_data = market_data or {}
        code = clean_stock_code(record.get("股票代码", ""))

        result = {**record, "总分": 0, "信号明细": [], "各项得分": {}}

        # 1. 已发公告
        s, d = self.score_announcement(code, announcements_df)
        result["各项得分"]["已发公告"] = s
        if s > 0:
            result["信号明细"].append(f"已发公告({s})")

        # 2. 解禁日期
        from .utils.date_parser import days_until
        date_str = record.get("解禁日期") or record.get("起始日期", "")
        days = days_until(date_str)
        s, d = self.score_unlock(days)
        result["各项得分"]["解禁信号"] = s
        if s > 0:
            result["信号明细"].append(f"解禁({s})")

        # 3. 股价涨幅
        s, d = self.score_price(market_data.get("change_pct"))
        result["各项得分"]["30日涨幅"] = s
        result["30日涨幅"] = d
        if s > 0:
            result["信号明细"].append(f"涨幅({s})")

        # 4. 质押率
        s, d = self.score_pledge(market_data.get("pledge_ratio"))
        result["各项得分"]["质押率"] = s
        if s > 0:
            result["信号明细"].append(f"质押({s})")

        # 5. 历史减持
        s, d = self.score_history(market_data.get("reduction_count", 0))
        result["各项得分"]["历史减持"] = s
        if s > 0:
            result["信号明细"].append(f"减持历史({s})")

        # 6. 股东类型
        holder = record.get("股东名称", "")
        s, d = self.score_holder(holder)
        result["各项得分"]["股东类型"] = s
        if s > 0:
            result["信号明细"].append(f"股东({s})")

        # 7. 股份来源
        s, d = self.score_source(record.get("股份来源", ""))
        result["各项得分"]["股份来源"] = s
        if s > 0:
            result["信号明细"].append(f"来源({s})")

        # 8. PE估值
        s, d = self.score_pe(market_data.get("pe_ttm"))
        result["各项得分"]["PE估值"] = s
        if s > 0:
            result["信号明细"].append(f"PE({s})")

        # 汇总
        result["总分"] = sum(result["各项得分"].values())
        result["信号明细"] = " | ".join(result["信号明细"])

        return result
