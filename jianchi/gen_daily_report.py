#!/usr/bin/env python3
# ╔══════════════════════════════════════════════════════════╗
# ║  ⚠️  核心文件 - 稳定版本 v2.5                           ║
# ║  修改此文件前必须：                                      ║
# ║  1. git stash 保存当前改动                               ║
# ║  2. 理解六级排序规则（见 config_report.py）               ║
# ║  3. 修改后运行 python3 jianchi/gen_daily_report.py 验证  ║
# ║  4. 确认输出：无重复、有分组、有锁定判断、有AI备注       ║
# ║  5. 如果改坏了: git checkout v2.5-stable -- jianchi/gen_daily_report.py ║
# ╚══════════════════════════════════════════════════════════╝
"""
每日减持简报生成器
读取 parsed JSON + 合并联系方式库 → 生成清晰的TXT报告
格式参照 近期减持计划联系方式.pdf
"""
import json, os, re, sys
from datetime import datetime
from collections import defaultdict

try:
    from jianchi.config_report import (
        sort_key as config_sort_key, GROUP_HEADERS, LOCK_PRIORITY,
        NO_LOCK_KEYWORDS, DISPUTED_KEYWORDS, LOCK_KEYWORDS,
        DERIVED_KEYWORDS, DISPUTED_THRESHOLD,
    )
except ImportError:
    from config_report import (
        sort_key as config_sort_key, GROUP_HEADERS, LOCK_PRIORITY,
        NO_LOCK_KEYWORDS, DISPUTED_KEYWORDS, LOCK_KEYWORDS,
        DERIVED_KEYWORDS, DISPUTED_THRESHOLD,
    )

BASE = os.path.expanduser("~/Desktop/减持获客系统")

def to_float_ratio(val):
    """将可能带%的比率字符串转为浮点数"""
    if not val:
        return 0
    try:
        return float(str(val).rstrip('%'))
    except:
        return 0

def load_contacts_index():
    """加载联系方式库(contacts_final.txt)，按公司名建索引"""
    index = defaultdict(list)
    fp = os.path.join(BASE, "jianchi/data/contacts_final.txt")
    if not os.path.exists(fp):
        print(f"未找到联系方式库: {fp}")
        return index
    with open(fp, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # 格式: 前缀数字+公司名 人名 职务 电话：号码
            phone_match = re.search(r"电话[：:]\s*(\d{11})", line)
            phone = phone_match.group(1) if phone_match else ""
            text = re.sub(r"电话[：:].*$", "", line).strip()
            # 去掉开头的数字/字母前缀
            text = re.sub(r"^[0-9A-Za-z\*\.]+", "", text).strip()
            parts = text.split()
            if len(parts) >= 2:
                company = parts[0].replace("ST", "").replace("*", "").strip()
                name = parts[1]
                title = " ".join(parts[2:]) if len(parts) > 2 else ""
            else:
                continue
            if company and name:
                index[company].append({"name": name, "title": title, "phone": phone})
    return index

def match_company(stock_name, contacts):
    """匹配公司名，返回该公司全部有效联系人"""
    clean = stock_name.replace("ST","").replace("*","").strip()

    def filter_valid(people):
        """过滤掉垃圾联系人：必须有人名(2-4个中文字)且有电话"""
        import re
        valid = []
        seen = set()
        for p in people:
            name = p.get("name","").strip()
            phone = p.get("phone","").strip()
            # 人名必须是2-6个字符，不能是纯描述
            if not name or len(name) < 2:
                continue
            # 过滤掉明显不是人名的
            if any(kw in name for kw in ["股东","持股","董事长","监事会","实际控制","副总经理","第一大","第二大","第三大","第四","科创板","创业板"]):
                continue
            # 去重
            key = (name, phone)
            if key in seen:
                continue
            seen.add(key)
            valid.append(p)
        return valid

    # 1. 精确匹配
    for key in [stock_name, clean]:
        if key in contacts:
            result = filter_valid(contacts[key])
            if result:
                return result

    # 2. 精确匹配变体：加"股份"、加"科技"等
    for suffix in ["股份", "科技", "集团", "电子", "新材", "医药"]:
        for key in [clean + suffix, clean.replace(suffix,"")]:
            if key and key in contacts:
                result = filter_valid(contacts[key])
                if result:
                    return result

    # 3. 严格包含匹配：完整公司名必须在key里，且key长度不超过公司名2倍
    if len(clean) >= 3:
        for key in contacts:
            if len(key) >= 3 and clean in key and len(key) <= len(clean) * 2:
                result = filter_valid(contacts[key])
                if result:
                    return result

    return []

def is_vc_fund(rec):
    """判断是否创投基金减持 - 仅依赖AI从公告原文中的判断"""
    return rec.get("是否创投基金减持", "") == "是"


# ── 受让方锁定判断 ──────────────────────────────────────
# 关键词列表统一从 config_report.py 导入：
#   NO_LOCK_KEYWORDS, DISPUTED_KEYWORDS, LOCK_KEYWORDS, DERIVED_KEYWORDS
# 本地别名，方便 judge_lock_status 中使用
_NO_LOCK_KEYWORDS = NO_LOCK_KEYWORDS + ["集中竞价交易取得", "向特定对象发行", "特定对象发行"]
_DERIVED_KEYWORDS = DERIVED_KEYWORDS + ["资本公积金转增", "转增", "送转"]
_FLAW_KEYWORDS = DISPUTED_KEYWORDS
_LOCK_KEYWORDS = LOCK_KEYWORDS + ["首次公开发行股票前"]


def judge_lock_status(rec):
    """
    判断受让方锁定状态。
    返回 (emoji, 标签, 说明)
    """
    source = rec.get("股份来源", "")

    # 创投基金 → 不锁
    if is_vc_fund(rec):
        return ("💚", "受让方不锁定", "创投基金减持")

    if not source or source.strip() in ("", "未知", "不详", "无"):
        return ("❓", "锁定待确认", "缺少股份来源信息")

    # 创投基金条款（公告原文中提到证监会公告[2020]17号）
    if "2020" in source and "17号" in source:
        return ("💚", "受让方不锁定", "适用创投基金减持新规")

    # ── 先对整段来源文本做关键词扫描 ──
    # 衍生方式检测（资本公积转增、送股等不是独立来源）
    has_derived = False
    matched_derived = ""
    for kw in _DERIVED_KEYWORDS:
        if kw in source:
            has_derived = True
            matched_derived = kw
            break

    # 在整段来源中检测实质性来源关键词（忽略衍生词干扰）
    # 先用整段文本匹配，再用拆分后的parts匹配
    has_no_lock = False
    has_flaw = False
    has_lock = False
    matched_no_lock = ""
    matched_flaw = ""
    matched_lock = ""

    # 整段文本匹配（捕获如"IPO前及上市后权益分派资本公积转增股本取得"中的IPO前）
    for kw in _NO_LOCK_KEYWORDS:
        if kw in source:
            has_no_lock = True
            matched_no_lock = kw
            break
    for kw in _FLAW_KEYWORDS:
        if kw in source:
            has_flaw = True
            matched_flaw = kw
            break
    for kw in _LOCK_KEYWORDS:
        if kw in source:
            has_lock = True
            matched_lock = kw
            break

    # 再按分隔符拆分逐段补充匹配
    parts = re.split(r"[/；;，,、]", source)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if not has_no_lock:
            for kw in _NO_LOCK_KEYWORDS:
                if kw in part:
                    has_no_lock = True
                    matched_no_lock = kw
                    break
        if not has_flaw:
            for kw in _FLAW_KEYWORDS:
                if kw in part:
                    has_flaw = True
                    matched_flaw = kw
                    break
        if not has_lock:
            for kw in _LOCK_KEYWORDS:
                if kw in part:
                    has_lock = True
                    matched_lock = kw
                    break

    # ── 判断逻辑（衍生方式不作为独立来源） ──

    # 有实质性来源时，衍生方式不影响判断
    real_source_found = has_no_lock or has_flaw or has_lock

    if real_source_found:
        # 规则：任一来源属于确定不锁 → 整体不锁
        if has_no_lock and not has_flaw and not has_lock:
            return ("💚", "受让方不锁定", f"{matched_no_lock}")

        # 混合来源：既有不锁也有锁定/瑕疵
        if has_no_lock and (has_flaw or has_lock):
            return ("💛", "混合来源，需确认", f"含{matched_no_lock}（不锁）+ 其他来源")

        # 瑕疵不锁 - 用股东持股比例判断5%线
        if has_flaw and not has_lock:
            hold_ratio = to_float_ratio(rec.get("股东持股比例(%)", 0))
            # fallback: 从公告标题判断
            title = rec.get("公告标题", "")
            holder_type = rec.get("股东类型", "")
            if hold_ratio > 0:
                if hold_ratio >= DISPUTED_THRESHOLD:
                    return ("🔴", "瑕疵锁定（≥5%，受让方锁6个月）",
                            f"{matched_flaw}取得，持股{hold_ratio}%≥5%")
                else:
                    return ("💛", "瑕疵不锁（<5%，需与股东确认）",
                            f"{matched_flaw}取得，持股{hold_ratio}%<5%")
            elif "5%以上" in title or "5%以上" in holder_type or "百分之五以上" in title:
                return ("🔴", "瑕疵锁定（≥5%，受让方锁6个月）",
                        f"{matched_flaw}取得，公告标题显示持股≥5%")
            else:
                return ("💛", "瑕疵不锁（持股比例未知，需确认）",
                        f"{matched_flaw}取得，持股比例未知")

        # 确定锁定
        if has_lock:
            return ("🔒", "受让方锁定6个月", f"{matched_lock}")

    # 仅有衍生方式，无实质来源 → 待确认
    if has_derived and not real_source_found:
        return ("❓", "锁定待确认", f"仅有{matched_derived}信息，需确认原始股份来源")

    # 无法匹配任何关键词
    return ("❓", "锁定待确认", "股份来源信息不明确")


def lock_group(rec):
    """
    返回锁定分组的状态key（对应 config_report.LOCK_PRIORITY）
    使用 config_report 中定义的分组标题和优先级
    """
    if is_vc_fund(rec):
        return "创投不锁"
    emoji, _, _ = judge_lock_status(rec)
    if emoji == "💚":
        return "确定不锁"
    elif emoji == "💛":
        return "瑕疵不锁"
    elif emoji == "🔴":
        return "瑕疵锁定"
    elif emoji == "🔒":
        return "确定锁定"
    else:
        return "待确认"


def lock_sort_order(rec):
    """返回锁定状态排序值（越小越优先）"""
    return LOCK_PRIORITY.get(lock_group(rec), 5)


def gen_ai_notes(rec):
    """生成AI备注"""
    # 创投基金优先返回
    if is_vc_fund(rec):
        return "🌟 创投基金减持，受让方无锁定期，无比例限制，优先跟进"

    notes = []
    ratio = to_float_ratio(rec.get("减持比例(%)", 0))
    holder = rec.get("股东名称", "")
    method = rec.get("减持方式", "")
    start = rec.get("起始日期", "")

    # 检查减持比例
    if ratio >= 3:
        notes.append("高比例减持")
        if "大宗交易" in method:
            notes.append("大宗交易概率大")

    # 检查中等比例且含大宗交易
    if ratio >= 2 and "大宗交易" in method:
        notes.append("中等规模，建议尽早联系")

    # 检查股东类型
    if any(kw in holder for kw in ["合伙", "基金", "投资", "有限合伙", "投资中心"]):
        notes.append("机构股东")
        if ratio >= 1:
            notes.append("可能有承接需求")

    # 检查窗口期
    if start:
        from datetime import datetime
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d")
            today = datetime.now()
            days_until = (start_date - today).days
            if 0 <= days_until <= 5:
                if days_until == 0:
                    notes.append("减持窗口今日开始")
                else:
                    notes.append(f"减持窗口{days_until}天后开始")
        except:
            pass

    return " + ".join(notes) if notes else "普通减持"

def merge_concert_parties(records):
    """
    合并一致行动人：同一公告(同股票代码+同公告链接)中，
    股东类型为"一致行动人"的多条记录合并为一条。
    减持比例取其共用值（一致行动人共用一个合计减持计划），
    股东名称拼接显示。
    """
    from collections import defaultdict

    # 按(股票代码, 公告链接)分组
    groups = defaultdict(list)
    for rec in records:
        key = (rec.get("股票代码", ""), rec.get("公告链接", ""))
        groups[key].append(rec)

    merged = []
    for key, recs in groups.items():
        # 分离：一致行动人 vs 普通股东
        concert = [r for r in recs if r.get("股东类型", "") == "一致行动人"]
        normal = [r for r in recs if r.get("股东类型", "") != "一致行动人"]

        # 普通股东直接保留
        merged.extend(normal)

        # 一致行动人合并为一条
        if concert:
            base = dict(concert[0])  # 以第一条为基础
            names = [r.get("股东名称", "") for r in concert]
            base["股东名称"] = " + ".join(names)
            # 减持比例取第一条（一致行动人共用合计比例）
            # 股东持股比例取合计
            total_hold = sum(to_float_ratio(r.get("股东持股比例(%)", 0)) for r in concert)
            if total_hold > 0:
                base["股东持股比例(%)"] = f"{total_hold:.2f}"
            base["股东类型"] = f"一致行动人（{len(concert)}家合计）"
            merged.append(base)

    return merged


def gen_report(date_str=None):
    # 校验排序规则完整性
    assert len(LOCK_PRIORITY) == 6, "锁定优先级必须有6个级别"
    assert all(k in GROUP_HEADERS for k in LOCK_PRIORITY), "每个优先级必须有对应的分组标题"

    if not date_str:
        date_str = datetime.now().strftime("%Y%m%d")

    parsed_file = os.path.join(BASE, f"jianchi/daily_output/parsed_{date_str}.json")
    if not os.path.exists(parsed_file):
        print(f"未找到: {parsed_file}")
        return

    with open(parsed_file, "r", encoding="utf-8") as f:
        records = json.load(f)

    print(f"加载 {len(records)} 条解析记录")

    # 按 (代码, 股东) 去重
    seen = {}
    for rec in records:
        # 用(股票名称,股东名称)去重，防止同公司不同代码重复（如A股+H股）
        key = (rec.get("股票名称",""), rec.get("股东名称",""))
        if key not in seen:
            seen[key] = rec

    unique = list(seen.values())

    # 合并一致行动人：同一公告中股东类型为"一致行动人"的记录合并为一条
    unique = merge_concert_parties(unique)

    # 加载联系方式（排序需要用到）
    contacts = load_contacts_index()
    print(f"联系方式库: {len(contacts)} 家公司")

    # 预计算每条记录的联系方式和锁定状态
    rec_contacts = {}
    for rec in unique:
        name = rec.get("股票名称", "")
        people = match_company(name, contacts)
        rec_contacts[id(rec)] = people
        # 计算锁定状态并存入记录（供 config_sort_key 使用）
        rec["锁定状态"] = lock_group(rec)

    # 三层排序（规则定义在 config_report.py）：
    #   锁定状态 → 减持比例降序 → 有联系方式优先
    unique.sort(key=lambda r: config_sort_key(
        r, has_contact=len(rec_contacts.get(id(r), [])) > 0
    ))
    print(f"去重后 {len(unique)} 家")

    # 生成报告
    out_path = os.path.join(BASE, f"jianchi/daily_output/今日减持_{date_str}.txt")

    matched_count = 0
    unmatched = []

    # 按分组组织记录（使用 config_report 的分组标题）
    from collections import OrderedDict
    groups = OrderedDict()
    for rec in unique:
        gkey = rec["锁定状态"]  # 已在排序前计算
        if gkey not in groups:
            groups[gkey] = {"label": GROUP_HEADERS[gkey], "records": []}
        groups[gkey]["records"].append(rec)

    # 统计各分组数量
    group_counts = {gkey: len(g["records"]) for gkey, g in groups.items()}

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write(f"  减持获客日报  {date_str}\n")
        f.write(f"  抓取: {len(records)} 条 | 解析: {len(unique)} 家\n")
        f.write("=" * 60 + "\n")

        seq = 0  # 全局序号
        for gkey, gdata in groups.items():
            glabel = gdata["label"]
            recs = gdata["records"]

            # 分组标题（来自 config_report.GROUP_HEADERS）
            f.write(f"\n{glabel}\n")

            for rec in recs:
                seq += 1
                code = rec.get("股票代码", "")
                name = rec.get("股票名称", "")
                holder = rec.get("股东名称", "")
                ratio = rec.get("减持比例(%)", "")
                method = rec.get("减持方式", "")
                source = rec.get("股份来源", "")
                start = rec.get("起始日期", "")
                end = rec.get("截止日期", "")
                ratio_float = to_float_ratio(ratio)

                # 分组emoji作为行首标记
                _emoji_map = {"创投不锁": "🌟", "确定不锁": "💚", "瑕疵不锁": "💛",
                              "瑕疵锁定": "🔴", "确定锁定": "🔒", "待确认": "❓"}
                group_emoji = _emoji_map.get(gkey, "❓")
                f.write(f"\n{group_emoji} [{seq}] {code} {name} | {holder} | {ratio}%\n")

                # 减持比例合理性校验
                if ratio_float > 5:
                    f.write(f"    ⚠️ 比例异常({ratio}%)，可能是持股比例而非减持比例，需人工核实\n")
                elif ratio_float > 3:
                    f.write(f"    ⚠️ 高于常规上限({ratio}%)，请确认\n")

                f.write(f"    减持方式: {method} | 减持期间: {start} ~ {end}\n")
                if source:
                    f.write(f"    股份来源: {source}\n")
                if is_vc_fund(rec):
                    f.write(f"    🌟 创投基金减持 | 受让方不锁定 | 不受比例限制 | 可按市场价承接\n")

                # 联系方式
                people = rec_contacts.get(id(rec), [])
                has_contact = len(people) > 0

                if has_contact:
                    f.write(f"    ✅ 有联系方式\n")
                else:
                    f.write(f"    ❌ 无联系方式\n")

                # AI备注
                ai_notes = gen_ai_notes(rec)
                if ai_notes:
                    f.write(f"    🤖 AI备注: {ai_notes}\n")

                # 锁定判断详情（非创投时显示）
                if not is_vc_fund(rec):
                    lock_emoji, lock_label, lock_detail = judge_lock_status(rec)
                    f.write(f"    {lock_emoji} {lock_label}（{lock_detail}）\n")

                # 联系方式列表
                seen_p = set()
                with_phone = []
                for p in people:
                    pk = (p["name"], p["phone"])
                    if pk in seen_p:
                        continue
                    seen_p.add(pk)
                    if p["phone"]:
                        with_phone.append(p)

                if with_phone:
                    matched_count += 1
                    f.write(f"    联系方式 ({len(with_phone)} 条):\n")
                    for p in with_phone:
                        f.write(f"      - {p['name']} | {p['phone']} | {p['title']}\n")
                else:
                    unmatched.append(f"{code} {name}")

        # 统计
        f.write("\n" + "=" * 60 + "\n")
        f.write(f"  统计:\n")
        f.write(f"    总计: {len(unique)} 家\n")

        vc_n = group_counts.get("创投不锁", 0)
        nl_n = group_counts.get("确定不锁", 0)
        fl_n = group_counts.get("瑕疵不锁", 0) + group_counts.get("瑕疵锁定", 0)
        lk_n = group_counts.get("确定锁定", 0)
        uk_n = group_counts.get("待确认", 0)
        f.write(f"    🌟 创投: {vc_n} 家 | 💚 不锁: {nl_n} 家 | 💛 瑕疵: {fl_n} 家 | 🔒 锁定: {lk_n} 家 | ❓ 待确认: {uk_n} 家\n")
        f.write(f"    有联系方式: {matched_count} 家 | 无联系方式: {len(unmatched)} 家\n")
        f.write("=" * 60 + "\n")

        if unmatched:
            f.write("\n【未匹配联系方式的公司】\n")
            for u in unmatched:
                f.write(f"  - {u}\n")

    print(f"\n已生成: {out_path}")
    print(f"  {len(unique)} 家公司 | {matched_count} 家有联系方式 | {len(unmatched)} 家无")

    # 自动打开
    os.system(f"open '{out_path}'")

if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    gen_report(date)
