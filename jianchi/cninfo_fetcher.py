"""
巨潮网减持公告抓取器
整合自: cninfo_scraper.py, auto_fetch_and_match.py, cninfo_download_and_parse.py

功能:
  1. 搜索指定日期的减持公告
  2. 过滤出预披露/计划类公告
  3. 下载PDF并提取文本
"""
import os
import re
import time
from datetime import datetime, timedelta

import requests

from .config import (
    CNINFO_API_URL, CNINFO_PDF_BASE, CNINFO_HEADERS,
    INCLUDE_KEYWORDS, EXCLUDE_KEYWORDS, PDF_DIR,
)


def search_announcements(date_str: str) -> list[dict]:
    """
    搜索指定日期的减持相关公告
    date_str: 'YYYY-MM-DD'
    返回: 巨潮网原始公告列表
    """
    items, page = [], 1
    while True:
        payload = {
            "pageNum": page, "pageSize": 30,
            "tabName": "fulltext", "column": "", "stock": "",
            "searchkey": "减持", "secid": "", "plate": "",
            "category": "", "trade": "",
            "seDate": f"{date_str}~{date_str}",
            "sortName": "", "sortType": "", "isHLtitle": "true",
        }
        data = None
        for attempt in range(3):
            try:
                r = requests.post(CNINFO_API_URL, headers=CNINFO_HEADERS,
                                  data=payload, timeout=15)
                data = r.json()
                break
            except Exception as e:
                print(f"  ✗ 请求失败 pg={page} (第{attempt+1}次): {e}")
                if attempt < 2:
                    time.sleep(3)

        if data is None:
            print(f"  ✗ pg={page} 重试3次均失败，跳过")
            break

        ann = data.get("announcements") or []
        if not ann:
            break
        items.extend(ann)
        print(f"  pg={page} 获取 {len(ann)} 条")

        if not data.get("hasMore"):
            break
        page += 1
        time.sleep(1)

    return items


def search_date_range(start_date: str, end_date: str) -> list[dict]:
    """搜索日期范围内的公告"""
    items, page = [], 1
    while True:
        payload = {
            "pageNum": page, "pageSize": 30,
            "tabName": "fulltext", "column": "", "stock": "",
            "searchkey": "减持", "secid": "", "plate": "",
            "category": "", "trade": "",
            "seDate": f"{start_date}~{end_date}",
            "sortName": "", "sortType": "", "isHLtitle": "true",
        }
        data = None
        for attempt in range(3):
            try:
                r = requests.post(CNINFO_API_URL, headers=CNINFO_HEADERS,
                                  data=payload, timeout=15)
                data = r.json()
                break
            except Exception as e:
                print(f"  ✗ 请求失败 pg={page} (第{attempt+1}次): {e}")
                if attempt < 2:
                    time.sleep(3)

        if data is None:
            print(f"  ✗ pg={page} 重试3次均失败，跳过")
            break

        ann = data.get("announcements") or []
        if not ann:
            break
        items.extend(ann)
        if not data.get("hasMore"):
            break
        page += 1
        time.sleep(1)

    return items


def filter_announcements(items: list[dict]) -> list[dict]:
    """
    过滤公告：保留预披露/计划类，排除结果/完成/进展类
    """
    results, seen = [], set()
    for item in items:
        title = item.get("announcementTitle", "").replace("<em>","").replace("</em>","")
        aid = item.get("announcementId", "")

        if aid in seen:
            continue
        if "减持" not in title:
            continue
        if not any(kw in title for kw in INCLUDE_KEYWORDS):
            continue
        if any(kw in title for kw in EXCLUDE_KEYWORDS):
            continue

        seen.add(aid)
        results.append(item)

    return results


def download_pdf(item: dict, output_dir: str = None) -> str | None:
    """
    下载公告PDF
    返回本地文件路径，失败返回 None
    """
    adj_url = item.get("adjunctUrl", "")
    if not adj_url:
        return None

    output_dir = output_dir or str(PDF_DIR)
    os.makedirs(output_dir, exist_ok=True)

    url = CNINFO_PDF_BASE + adj_url
    filename = adj_url.split("/")[-1]
    filepath = os.path.join(output_dir, filename)

    # 已下载则跳过
    if os.path.exists(filepath) and os.path.getsize(filepath) > 500:
        return filepath

    try:
        r = requests.get(url, headers={"User-Agent": CNINFO_HEADERS["User-Agent"]},
                         timeout=30)
        if r.status_code == 200 and len(r.content) > 500:
            with open(filepath, "wb") as f:
                f.write(r.content)
            return filepath
    except Exception as e:
        print(f"  ✗ 下载失败 {filename}: {e}")

    return None


def pdf_to_text(filepath: str) -> str:
    """
    PDF → 纯文本（先尝试 pdfplumber，fallback 到 PyPDF2）
    """
    # 方式1: pdfplumber（效果更好）
    try:
        import pdfplumber
        text = ""
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
        if text.strip():
            return text
    except Exception:
        pass

    # 方式2: PyPDF2
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(filepath)
        text = ""
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n"
        if text.strip():
            return text
    except Exception:
        pass

    return ""


def extract_meta(item: dict) -> dict:
    """从巨潮网公告元数据中提取基础信息"""
    ts = item.get("announcementTime", 0)
    date_str = ""
    if ts:
        date_str = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")

    return {
        "stock_code": item.get("secCode", ""),
        "stock_name": item.get("secName", ""),
        "announcement_date": date_str,
        "announcement_title": item.get("announcementTitle", ""),
        "announcement_url": CNINFO_PDF_BASE + item.get("adjunctUrl", ""),
        "announcement_id": item.get("announcementId", ""),
    }


def fetch_and_filter(date_str: str) -> list[dict]:
    """
    一站式：搜索 + 过滤 + 提取元数据
    搜索当天 + 前一天（覆盖晚间发布的公告）
    返回过滤后的公告元数据列表
    """
    from datetime import datetime, timedelta
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    prev_str = (dt - timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"🔍 搜索 {prev_str} ~ {date_str} 的减持公告...")
    raw_today = search_announcements(date_str)
    raw_prev = search_announcements(prev_str)

    # 合并去重
    seen = set()
    combined = []
    for r in raw_today + raw_prev:
        aid = r.get("announcementId", "")
        if aid not in seen:
            seen.add(aid)
            combined.append(r)

    print(f"  原始结果: {len(raw_today)}+{len(raw_prev)}={len(combined)} 条（去重后）")

    filtered = filter_announcements(combined)
    print(f"  过滤后: {len(filtered)} 条（预披露/计划类）")

    return [extract_meta(item) | {"_raw": item} for item in filtered]
