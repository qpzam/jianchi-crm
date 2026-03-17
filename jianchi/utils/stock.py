"""
股票代码、公司名称处理工具集
整合自: cninfo_parser_v5, reduction_predictor_v3, auto_fetch_and_match, 
        match_contacts, tinyshare_scraper, cninfo_scraper
"""
import re
from ..config import COMPANY_SUFFIXES, SHARE_SOURCE_MAP


def clean_stock_code(code) -> str | None:
    """
    清洗股票代码，提取纯6位数字
    '300586.SZ' → '300586'
    'SZ300586' → '300586'
    '0*ST, 海马' → None
    """
    if not code or (hasattr(code, '__class__') and code.__class__.__name__ == 'float'):
        import math
        if isinstance(code, float) and math.isnan(code):
            return None
    code = str(code).strip()
    m = re.search(r'(\d{6})', code)
    return m.group(1) if m else None


def format_ts_code(code: str) -> str | None:
    """
    6位代码 → TinyShare/Tushare 格式
    '600000' → '600000.SH'
    '300586' → '300586.SZ'
    '920925' → '920925.BJ'
    """
    code = clean_stock_code(code)
    if not code:
        return None
    if code.startswith('6'):
        return f'{code}.SH'
    elif code.startswith(('0', '3')):
        return f'{code}.SZ'
    elif code.startswith(('8', '9', '4')):
        return f'{code}.BJ'
    return code


def extract_stock_code(raw: str) -> str:
    """从含代码的文本中提取6位股票代码: '艾罗能源(688717)' → '688717'"""
    m = re.search(r'(\d{6})', str(raw))
    return m.group(1) if m else ""


def extract_company_name(raw: str) -> str:
    """
    从各种格式提取纯公司名
    '艾罗能源(688717)' → '艾罗能源'
    '0*ST, 海马'       → '海马'
    '*ST海马'          → '海马'
    '海马汽车股份有限公司' → '海马汽车'
    """
    raw = str(raw).strip()
    if not raw:
        return ""

    # 1. 去掉括号中的股票代码
    raw = re.sub(r'[（(]\d{6}[)）]', '', raw)

    # 2. 去掉 ST 前缀（含 *ST, 0*ST 及前面的逗号空格）
    raw = re.sub(r'^[\d\*]*ST[,，\s]*', '', raw)

    # 3. 去掉公司后缀（按长度从长到短，避免先去掉"公司"导致"有限"残留）
    for suffix in COMPANY_SUFFIXES:
        raw = raw.replace(suffix, "")

    return raw.strip()


def normalize_company_name(name: str) -> str:
    """
    标准化公司名，用于匹配（比 extract_company_name 多去掉括号和空格）
    """
    result = extract_company_name(name)
    result = re.sub(r'[（()）\s]', '', result)
    return result


def parse_stock_field(raw: str) -> tuple[str | None, str | None]:
    """
    从"公司名(代码)"格式同时提取公司名和代码
    '艾罗能源(688717)' → ('艾罗能源', '688717')
    """
    raw = str(raw).strip()
    m = re.match(r'(.*?)\(?(\d{6})\)?', raw)
    if m:
        return m.group(1).strip(), m.group(2)
    return None, None


def classify_shareholder(name: str) -> str:
    """
    判断股东类型
    返回: 'PE/VC基金' | '一致行动人' | '公司高管' | '控股股东' | '个人股东' | '机构股东' | '未知'
    """
    if not name:
        return "未知"
    name = str(name)

    # 机构关键词
    if any(kw in name for kw in ['投资', '基金', '合伙', '创投', '资本', '私募', '股权']):
        return "PE/VC基金"
    if '一致行动' in name:
        return "一致行动人"
    if any(kw in name for kw in ['董事长', '总经理', '董事', '监事', '高管', '副总', '财务总监', '董秘']):
        return "公司高管"
    if '控股' in name or '实际控制人' in name:
        return "控股股东"
    if any(kw in name for kw in ['有限公司', '股份公司', '集团', '银行', '信托']):
        return "机构股东"
    # 2-4个汉字且不含公司关键词 → 大概率个人
    if re.match(r'^[\u4e00-\u9fff]{2,4}$', name.strip()):
        return "个人股东"

    return "未知"


def normalize_share_source(source: str) -> str:
    """
    标准化股份来源描述
    '公司首次公开发行股票前持有的股份' → 'IPO前取得'
    """
    if not source:
        return "未披露"
    source_lower = str(source)
    for keyword, standard in SHARE_SOURCE_MAP.items():
        if keyword in source_lower:
            return standard
    return source
