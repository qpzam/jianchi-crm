"""
日期解析工具集
整合自: reduction_predictor_v3, SKILL.md, cninfo_parser_v4_1, auto_fetch_and_match

⚠️ 核心原则: 绝不用 pd.to_datetime() 直接转换 "月.日" 格式
"""
import re
from datetime import datetime, timedelta


def parse_date(raw, year: int = 2026) -> str | None:
    """
    解析各种格式的日期，返回 'YYYY-MM-DD' 或 None

    支持格式:
      '3.20'        → '2026-03-20'  (月.日)
      '3/20'        → '2026-03-20'  (月/日)
      '2026-03-20'  → '2026-03-20'  (完整日期)
      '2026/03/20'  → '2026-03-20'
      '20260320'    → '2026-03-20'  (纯数字)
      45000.0       → Excel数字日期
    """
    raw = str(raw).strip()
    if not raw or raw.lower() in ('nan', 'none', ''):
        return None

    # 格式1: 月.日
    m = re.match(r'^(\d{1,2})\.(\d{1,2})$', raw)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year}-{month:02d}-{day:02d}"

    # 格式2: 月/日
    m = re.match(r'^(\d{1,2})/(\d{1,2})$', raw)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year}-{month:02d}-{day:02d}"

    # 格式3: YYYY-MM-DD 或 YYYY/MM/DD
    m = re.match(r'^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$', raw)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    # 格式4: YYYYMMDD 纯数字
    m = re.match(r'^(\d{4})(\d{2})(\d{2})$', raw)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    # 格式5: Excel 数字日期（浮点数如 45000.0）
    try:
        num = float(raw)
        if 40000 < num < 55000:
            dt = datetime(1899, 12, 30) + timedelta(days=int(num))
            return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        pass

    # 格式6: 中文日期 '2026年3月20日'
    m = re.match(r'^(\d{4})年(\d{1,2})月(\d{1,2})日?$', raw)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    return None


def parse_date_range(text: str, announcement_date: str = None) -> tuple[str, str]:
    """
    从公告文本中提取减持期间的起止日期

    尝试顺序:
    1. 明确日期: "自2026年3月24日起至2026年6月23日"
    2. 相对日期: "自本公告披露之日起15个交易日后的3个月内"
    3. 表格中的日期

    返回: (start_date, end_date) 都是 'YYYY-MM-DD' 格式，解析失败返回 ('', '')
    """
    start, end = '', ''

    # 1. 明确日期范围: 自X年X月X日起至X年X月X日
    m = re.search(
        r'自\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*(?:起)?'
        r'[至到]\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日',
        text
    )
    if m:
        start = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        end = f"{m.group(4)}-{int(m.group(5)):02d}-{int(m.group(6)):02d}"
        return start, end

    # 2. 相对日期: "公告披露之日起N个交易日后的M个月内"
    base = None
    if announcement_date:
        try:
            base = datetime.strptime(announcement_date, "%Y-%m-%d")
        except ValueError:
            pass
    if not base:
        base = datetime.now()

    m = re.search(r'(\d{1,2})\s*个\s*交易日\s*后.*?(\d{1,2})\s*个\s*月', text)
    if m:
        trading_days = int(m.group(1))
        months = int(m.group(2))
        # 交易日 ≈ 日历日 × 1.5
        start_dt = base + timedelta(days=int(trading_days * 1.5))
        end_dt = start_dt + timedelta(days=months * 30)
        return start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")

    # 3. 仅有 N 个交易日后（无月数）
    m = re.search(r'(\d{1,2})\s*个\s*交易日\s*后', text)
    if m:
        trading_days = int(m.group(1))
        start_dt = base + timedelta(days=int(trading_days * 1.5))
        # 默认6个月
        end_dt = start_dt + timedelta(days=180)
        return start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")

    return start, end


def days_until(date_str: str) -> int | None:
    """计算距今天数，负数表示已过期"""
    try:
        target = datetime.strptime(date_str, "%Y-%m-%d")
        return (target - datetime.now()).days
    except (ValueError, TypeError):
        return None
