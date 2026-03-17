#!/usr/bin/env python3
"""
每日减持简报生成器
读取 parsed JSON + 合并联系方式库 → 生成清晰的TXT报告
格式参照 近期减持计划联系方式.pdf
"""
import json, os, re, sys
from datetime import datetime
from collections import defaultdict

BASE = os.path.expanduser("~/Desktop/减持获客系统")

def load_contacts_index():
    """加载合并联系方式库，按公司名建索引"""
    index = defaultdict(list)
    fp = os.path.join(BASE, "jianchi/data/contacts_merged.txt")
    if not os.path.exists(fp):
        print("未找到合并库，请先运行 merge_contacts.py")
        return index
    with open(fp, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 4:
                company, name, title, phone = parts[0], parts[1], parts[2], parts[3]
            elif len(parts) == 3:
                company, name, title, phone = parts[0], parts[1], parts[2], ""
            else:
                continue
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

def gen_ai_notes(rec):
    """生成AI备注"""
    notes = []
    ratio = float(rec.get("减持比例(%)", 0))
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
            if 0 <= days_until <= 3:
                notes.append("减持窗口临近")
                if days_until == 0:
                    notes.append("今日开始")
        except:
            pass

    return " + ".join(notes) if notes else "普通减持"

def gen_report(date_str=None):
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
    print(f"去重后 {len(unique)} 家")

    # 加载联系方式
    contacts = load_contacts_index()
    print(f"联系方式库: {len(contacts)} 家公司")

    # 生成报告
    out_path = os.path.join(BASE, f"jianchi/daily_output/今日减持_{date_str}.txt")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    matched_count = 0
    unmatched = []

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write(f"  减持获客日报  {date_str[:4]}-{date_str[4:6]}-{date_str[6:]}\n")
        f.write(f"  抓取: {len(records)} 条 | 新增: 0 | 匹配: {len(unique)}/{len(records)}\n")
        f.write("=" * 60 + "\n")

        for rec in unique:
            code = rec.get("股票代码", "")
            name = rec.get("股票名称", "")
            holder = rec.get("股东名称", "")
            ratio = rec.get("减持比例(%)", "")
            method = rec.get("减持方式", "")
            source = rec.get("股份来源", "")
            start = rec.get("起始日期", "")
            end = rec.get("截止日期", "")

            # 确定优先级和标记
            priority = "🟡"
            ratio_float = float(ratio) if ratio else 0
            if ratio_float >= 3:
                priority = "🔴"
            elif ratio_float >= 1:
                priority = "🟡"
            else:
                priority = "🟢"

            # 匹配联系方式
            people = match_company(name, contacts)
            has_contact = len(people) > 0

            f.write(f"\n{priority} [{unique.index(rec) + 1}] {code} {name} | {holder} | {ratio}\n")
            f.write(f"    减持方式: {method} | 减持期间: {start} ~ {end}\n")
            if source:
                f.write(f"    股份来源: {source}\n")
            if has_contact:
                f.write(f"    ✅ 有联系方式\n")
            else:
                f.write(f"    ❌ 无联系方式\n")

            # 添加AI备注
            ai_notes = gen_ai_notes(rec)
            if ai_notes:
                f.write(f"    🤖 AI备注: {ai_notes}\n")
            # 有电话的排前面，去重
            seen_p = set()
            with_phone = []
            without_phone = []
            for p in people:
                pk = (p["name"], p["phone"])
                if pk in seen_p:
                    continue
                seen_p.add(pk)
                if p["phone"]:
                    with_phone.append(p)
                else:
                    without_phone.append(p)

            all_people = with_phone + without_phone
            if with_phone:
                matched_count += 1
                f.write(f"    联系方式 ({len(with_phone)} 条):\n")
                for p in with_phone:
                    f.write(f"      - {p['name']} | {p['phone']} | {p['title']}\n")
            else:
                unmatched.append(f"{code} {name}")

        # 统计
        f.write("\n" + "=" * 60 + "\n")
        f.write(f"  本次汇总:\n")
        f.write(f"    解析: {len(records)} 条 → 新增 0 + 更新 {len(unique)}\n")
        f.write(f"    优先级: 🔴高 {len([r for r in unique if float(r.get('减持比例(%)', 0)) >= 3])} | 🟡中 {len([r for r in unique if 1 <= float(r.get('减持比例(%)', 0)) < 3])} | 🟢低 {len([r for r in unique if float(r.get('减持比例(%)', 0)) < 1])}\n")
        f.write(f"    匹配率: {len(unique)}/{len(records)} ({int(len(unique)/len(records)*100) if len(records) > 0 else 0}%)\n")
        f.write(f"    输出: {out_path}\n")
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
