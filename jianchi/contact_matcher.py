"""
联系方式匹配引擎
整合自: match_contacts.py, auto_fetch_and_match.py

匹配策略（按优先级）:
  1. 精确匹配: 纯公司名完全一致
  2. 包含匹配: 一方公司名包含另一方
  3. 代码匹配: 6位股票代码一致
  4. 模糊匹配: 2个以上汉字重叠且比例>50%
"""
import pandas as pd
from datetime import datetime, timedelta

from .config import UNLOCK_COL_CANDIDATES, CONTACT_COL_CANDIDATES
from .utils.stock import extract_company_name, normalize_company_name, extract_stock_code
from .utils.io import load_dataframe, auto_map_columns



import re as _re

def load_text_contacts(filepaths):
    """
    解析纯文本联系方式文件（all_contacts_dedup.txt / contacts_final.txt / iphone_contacts.txt）
    格式: 前缀+公司名 人名 职务 电话：号码
    返回 DataFrame，列: company, name, title, phone
    """
    rows = []
    if isinstance(filepaths, str):
        filepaths = [filepaths]
    for fp in filepaths:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    # 支持两种格式：tab分隔(合并库) 和 原始文本格式
                    if "\t" in line:
                        # tab分隔: company\tname\ttitle\tphone
                        parts = line.split("\t")
                        company = parts[0].strip() if len(parts) > 0 else ""
                        person = parts[1].strip() if len(parts) > 1 else ""
                        title = parts[2].strip() if len(parts) > 2 else ""
                        phone = parts[3].strip() if len(parts) > 3 else ""
                    else:
                        phone_match = _re.search(r"电话[：:]\s*(\d{11})", line)
                        phone = phone_match.group(1) if phone_match else ""
                        text = _re.sub(r"电话[：:].*$", "", line).strip()
                        text = _re.sub(r"^[0-9A-Za-z\*\.]+", "", text).strip()
                        parts = text.split()
                        if len(parts) >= 2:
                            company = parts[0].replace("ST","").replace("*","").strip()
                            person = parts[1]
                            title = " ".join(parts[2:]) if len(parts) > 2 else ""
                        elif len(parts) == 1:
                            company = parts[0].replace("ST","").replace("*","").strip()
                            person = ""
                            title = ""
                        else:
                            continue
                    rows.append({"company": company, "name": person, "title": title, "phone": phone})
        except Exception as e:
            print(f"  ⚠️ 读取 {fp} 失败: {e}")
    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["company","name","title","phone"])
    return df


def match_company(name_a: str, name_b: str) -> str:
    """
    判断两个公司名的匹配类型
    返回: '精确' | '包含' | '模糊' | '不匹配'
    """
    a = normalize_company_name(name_a)
    b = normalize_company_name(name_b)

    if not a or not b:
        return "不匹配"
    if a == b:
        return "精确"
    if a in b or b in a:
        return "包含"

    # 共同汉字比例
    common = set(a) & set(b)
    if len(common) >= 2 and len(common) / max(len(a), len(b)) > 0.5:
        return "模糊"

    return "不匹配"


def build_contact_index(contact_df: pd.DataFrame, company_col: str) -> dict:
    """
    构建联系方式库的公司名索引
    返回 {normalized_name: [row_dict, ...]}
    """
    index = {}
    for _, row in contact_df.iterrows():
        raw = str(row.get(company_col, ""))
        norm = normalize_company_name(raw)
        if norm:
            index.setdefault(norm, []).append(row.to_dict())

        # 同时用股票代码建索引
        code = extract_stock_code(raw)
        if code:
            index.setdefault(f"CODE:{code}", []).append(row.to_dict())

    return index


def match_single(stock_name: str, stock_code: str, shareholder: str,
                 contact_index: dict) -> list[dict]:
    """
    匹配单条记录，返回 [{contact_row, match_type}, ...]
    """
    results = []
    stock_norm = normalize_company_name(stock_name)
    holder_norm = normalize_company_name(shareholder)

    # 1) 精确匹配
    for norm in [stock_norm, holder_norm]:
        if norm and norm in contact_index:
            for row in contact_index[norm]:
                results.append({"contact": row, "match_type": "精确"})

    if results:
        return results

    # 2) 包含匹配
    for norm in [stock_norm, holder_norm]:
        if not norm or len(norm) < 2:
            continue
        for key, rows in contact_index.items():
            if key.startswith("CODE:"):
                continue
            if norm in key or key in norm:
                for row in rows:
                    results.append({"contact": row, "match_type": "包含"})

    if results:
        return results

    # 3) 代码匹配
    if stock_code:
        code_key = f"CODE:{stock_code}"
        if code_key in contact_index:
            for row in contact_index[code_key]:
                results.append({"contact": row, "match_type": "代码"})

    if results:
        return results

    # 4) 模糊匹配
    for norm in [stock_norm, holder_norm]:
        if not norm or len(norm) < 2:
            continue
        for key, rows in contact_index.items():
            if key.startswith("CODE:"):
                continue
            common = set(norm) & set(key)
            if len(common) >= 2 and len(common) / max(len(norm), len(key)) > 0.5:
                for row in rows:
                    results.append({"contact": row, "match_type": "模糊"})

    return results


def match_records(records: list[dict], contact_df: pd.DataFrame,
                  contact_cols: dict = None) -> list[dict]:
    """
    批量匹配: 减持公告记录 × 联系方式库

    参数:
      records: pdf_parser 输出的记录列表 [{"股票代码", "股票名称", "股东名称", ...}]
      contact_df: 联系方式库 DataFrame
      contact_cols: 列名映射 (自动检测如不提供)

    返回: 带联系方式的记录列表
    """
    if contact_cols is None:
        contact_cols = auto_map_columns(contact_df, CONTACT_COL_CANDIDATES)

    company_col = contact_cols.get("company")
    if not company_col:
        print("⚠️ 联系方式库中未找到「公司」列")
        return records

    # 构建索引
    index = build_contact_index(contact_df, company_col)
    print(f"📇 联系方式索引: {len(index)} 个条目")

    results = []
    matched_count = 0

    for rec in records:
        stock_name = rec.get("股票名称", "") or rec.get("stock_name", "")
        stock_code = rec.get("股票代码", "") or rec.get("stock_code", "")
        shareholder = rec.get("股东名称", "") or rec.get("shareholder_name", "")

        matches = match_single(stock_name, stock_code, shareholder, index)

        if matches:
            matched_count += 1
            for m in matches:
                merged = {**rec}
                contact = m["contact"]
                merged["联系人"] = contact.get(contact_cols.get("contact_name", ""), "")
                merged["手机"] = contact.get(contact_cols.get("phone", ""), "")
                merged["邮箱"] = contact.get(contact_cols.get("email", ""), "")
                merged["微信"] = contact.get(contact_cols.get("wechat", ""), "")
                merged["职务"] = contact.get(contact_cols.get("position", ""), "")
                merged["匹配方式"] = m["match_type"]
                results.append(merged)
        else:
            merged = {**rec, "联系人": "", "手机": "", "邮箱": "",
                      "微信": "", "职务": "", "匹配方式": "未匹配"}
            results.append(merged)

    print(f"✅ 匹配完成: {matched_count}/{len(records)} 家找到联系方式")
    return results


def assign_priority(record: dict) -> str:
    """
    按减持业务价值判断优先级

    评分维度:
      减持比例: >3% → +3, 1~3% → +2, <1% → +1
      减持方式: 含大宗交易 → +2（佣金更高）, 集中竞价 → +1
      股份来源: 股权激励 → +2（减持意愿最强）, 非公开发行 → +1
      窗口期:  已开窗/即将关窗 → +2, 未开窗30天内 → +1

    得分: ≥6 高, ≥3 中, <3 低
    """
    score = 0

    # 减持比例
    ratio_str = record.get("减持比例(%)", "") or record.get("reduction_ratio", "")
    try:
        ratio = float(str(ratio_str).replace("%", "").strip())
        if ratio >= 3:
            score += 3
        elif ratio >= 1:
            score += 2
        elif ratio > 0:
            score += 1
    except (ValueError, TypeError):
        pass

    # 减持方式
    method = record.get("减持方式", "") or record.get("reduction_method", "")
    if "大宗" in method:
        score += 2
    elif "集中竞价" in method:
        score += 1

    # 股份来源
    source = record.get("股份来源", "") or record.get("share_source", "")
    if any(k in source for k in ["股权激励", "激励"]):
        score += 2
    elif any(k in source for k in ["非公开", "定增"]):
        score += 1

    # 窗口期
    from .utils.date_parser import days_until
    start = record.get("起始日期") or record.get("start_date", "")
    end = record.get("截止日期") or record.get("end_date", "")
    start_days = days_until(start) if start else None
    end_days = days_until(end) if end else None

    if start_days is not None and start_days <= 0 and end_days is not None and end_days > 0:
        score += 2  # 已开窗
        if end_days <= 7:
            score += 1  # 即将关窗
    elif start_days is not None and 0 < start_days <= 30:
        score += 1  # 30天内开窗

    if score >= 6:
        return "高"
    elif score >= 3:
        return "中"
    return "低"
