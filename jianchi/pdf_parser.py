"""
减持公告PDF解析器
整合自: cninfo_scraper.py (正则解析), batch_pdf_parse_ai.py (AI解析)

支持两种模式:
  1. regex模式: 快速、免费，覆盖常见格式
  2. ai模式: 使用Claude API语义理解，处理复杂/非标格式
"""
import json
import os
import re
from datetime import datetime

from .utils.stock import extract_company_name, normalize_share_source
from .utils.date_parser import parse_date_range


# ============================================================
# 正则解析模式（零成本，覆盖80%+场景）
# ============================================================

# 股东名称提取模式（按优先级排列）
_SHAREHOLDER_PATTERNS = [
    # 1. 标准格式: "减持股东名称：XXX"
    r"减持股东名称[:：\uff1a]\s*([^\n\uff08(]+)",
    # 2. 编号格式: "1、股东名称：XXX"
    r"1、股东名称[:：]\s*([^\n。]+)",
    # 3. 叙述格式: "公司股东XXX及其一致行动人YYY"
    r"公司股东\s*([\u4e00-\u9fff]{2,4})及其一致行动人\s*([\u4e00-\u9fff]{2,4}(?:、[\u4e00-\u9fff]{2,4})*)",
    # 4. 拟减持格式: "XXX及其一致行动人YYY拟计划减持"
    r"([\u4e00-\u9fff]{2,4})及其一致行动人\s*([\u4e00-\u9fff]{2,4}(?:、[\u4e00-\u9fff]{2,4})*)\s*拟",
    # 5. 告知函: "收到股东XXX出具"（支持有限公司/有限合伙/银行/分行）
    r"收到.*?股东\s*([^\n。]{4,60}?(?:有限公司|股份公司|有限合伙[)）]|分行))\s*出具",
    # 6. 特定股东: "特定股东XXX（占总股本"或"特定股东XXX拟"
    r"特定股东\s*([\u4e00-\u9fff\w（）\(\)]+?(?:投资|合伙|公司|基金)[\w（）\(\)]*?)(?:[,，\s（(]|拟)",
    # 7. 特定股东多个: "特定股东AAA、BBB"
    r"特定股东\s*([\u4e00-\u9fff\w]+(?:、[\u4e00-\u9fff\w]+)+)",
    # 8. 表格: 股东名称后换行跟名字
    r"股东名称[^\n]*?\n\s*([^\n]{4,60}?(?:有限公司|股份公司|银行|分行|有限合伙[)）]))",
    # 9. 持股5%以上股东叙述: "持股5%以上股东XXX出具"
    r"持股\s*\d+%\s*以上股东\s*([^\n。]{4,60}?(?:有限公司|有限合伙[)）]|分行|银行))",
    # 10. 高管格式
    r"高级管理人员\s*([\u4e00-\u9fff]{2,8})\s*(?:先生|女士)",
    # 11. 董事格式
    r"(?:副?董事长?|总经理|财务总监|董秘)\s*([\u4e00-\u9fff]{2,4})\s*(?:先生|女士)",
    # 12. 收到+告知函（宽松版，兜底）
    r"收到[^\n]{0,20}股东\s*([^\n]{4,60}?)\s*出具的\s*《",
]

# 减持比例提取模式
_RATIO_PATTERNS = [
    r"减持.*?不超过.*?总股本[的]?\s*(\d+\.?\d*)\s*%",
    r"减持比例[^\n]{0,20}?(\d+\.?\d*)\s*%",
    r"减持.*?不超过.*?(\d+\.?\d*)\s*%",
    r"合计.*?不超过.*?(\d+\.?\d*)\s*%",
    r"占公司总股本[的比例为]*?\s*(\d+\.?\d*)\s*%",
    r"占总股本[比例为]*?\s*(\d+\.?\d*)\s*%",
    r"比例[为不超过]*?\s*(\d+\.?\d*)\s*%",
    # 表格内: 数字后紧跟百分比（如 "11,291,100 2.49%"）
    r"[\d,]+\s+(\d+\.?\d*)\s*%",
]

# 减持数量提取模式
_SHARES_PATTERNS = [
    r"不超过\s*([\d,，]+\.?\d*)\s*万?\s*股",
    r"合计.*?不超过\s*([\d,，]+\.?\d*)\s*万?\s*股",
    r"减持.*?([\d,，]+\.?\d*)\s*万?\s*股",
]

# 减持方式
_METHOD_PATTERNS = [
    r"(集中竞价[及和与\/]大宗交易)",
    r"(大宗交易[及和与\/]集中竞价)",
    r"(集中竞价(?:交易)?(?:方式)?)",
    r"(大宗交易(?:方式)?)",
]

# 股份来源
_SOURCE_PATTERNS = [
    r"股份来源[：:为]\s*([^\n。]{5,80})",
    r"(?:所持|其持有).*?股份.*?(?:系|为|来源于|来自)\s*([^\n。]{5,80})",
    r"(首次公开发行[前股票]*[^\n。]{2,30})",
    r"(非公开发行[^\n。]{2,30})",
    r"(股权激励[^\n。]{2,30})",
]


def parse_regex(text: str, meta: dict = None) -> dict:
    """
    用正则表达式解析公告文本

    参数:
      text: PDF提取的纯文本
      meta: 巨潮网元数据 (stock_code, stock_name, announcement_date 等)

    返回: 结构化记录 dict
    """
    meta = meta or {}
    rec = {
        "股票代码": meta.get("stock_code", ""),
        "股票名称": meta.get("stock_name", ""),
        "公告日期": meta.get("announcement_date", ""),
        "公告标题": meta.get("announcement_title", ""),
        "公告链接": meta.get("announcement_url", ""),
        "股东名称": "",
        "股东类型": "",
        "减持数量(万股)": "",
        "减持比例(%)": "",
        "减持方式": "",
        "股份来源": "未披露",
        "起始日期": "",
        "截止日期": "",
        "warnings": [],
    }

    if not text:
        rec["warnings"].append("PDF提取失败")
        return rec

    search_zone = text[:2000]  # 关键信息通常在前2000字

    # --- 股东名称 ---
    shareholders = []
    for pattern in _SHAREHOLDER_PATTERNS:
        m = re.search(pattern, search_zone)
        if m:
            groups = m.groups()
            for g in groups:
                if g:
                    names = [n.strip() for n in re.split(r'[、,，]', g) if n.strip() and len(n.strip()) >= 2]
                    shareholders.extend(names)
            if shareholders:
                break

    if shareholders:
        rec["股东名称"] = "、".join(shareholders)
    else:
        rec["warnings"].append("未提取到股东名称")

    # --- 减持比例 ---（取所有匹配中的最大值，防止只抓到分项比例）
    all_ratios = []
    for pattern in _RATIO_PATTERNS:
        for m in re.finditer(pattern, text):
            try:
                ratio = float(m.group(1))
                if 0 < ratio <= 100:
                    all_ratios.append(ratio)
            except:
                pass
    if all_ratios:
        rec["减持比例(%)"] = f"{max(all_ratios):.2f}"

    # --- 减持数量 ---
    for pattern in _SHARES_PATTERNS:
        m = re.search(pattern, text)
        if m:
            num_str = m.group(1).replace(',', '').replace('，', '')
            try:
                rec["减持数量(万股)"] = f"{float(num_str):.4f}"
            except ValueError:
                pass
            break

    # --- 减持方式 ---
    for pattern in _METHOD_PATTERNS:
        m = re.search(pattern, text)
        if m:
            rec["减持方式"] = m.group(1)
            break

    # --- 股份来源 ---
    for pattern in _SOURCE_PATTERNS:
        m = re.search(pattern, text)
        if m:
            raw_source = m.group(1).strip()
            rec["股份来源"] = normalize_share_source(raw_source)
            break

    # --- 减持期间 ---
    start, end = parse_date_range(text, rec["公告日期"])
    rec["起始日期"] = start
    rec["截止日期"] = end

    return rec


# ============================================================
# AI 解析模式（支持 OpenAI 兼容接口 / Anthropic）
# ============================================================

def _load_ai_prompt():
    """从外部文件加载AI解析prompt"""
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "parse_reduction.txt")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()

_AI_PROMPT = _load_ai_prompt()


def _create_ai_client():
    """
    创建 AI 客户端，优先级:
    1. OPENAI_API_KEY + 黑宇/OpenAI兼容接口
    2. ANTHROPIC_API_KEY + Anthropic 接口
    """
    from dotenv import load_dotenv
    load_dotenv()

    import os
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

    # 优先 OpenAI 兼容接口（黑宇 GPT-5.4）
    if OPENAI_API_KEY:
        try:
            from openai import OpenAI
            base_url = OPENAI_BASE_URL or "https://api.openai.com/v1"
            model = OPENAI_MODEL or "gpt-4"
            client = OpenAI(api_key=OPENAI_API_KEY, base_url=base_url)
            return ("openai", client, model)
        except Exception as e:
            print(f"  ⚠️ OpenAI 客户端初始化失败: {e}")

    # Fallback: Anthropic
    if ANTHROPIC_API_KEY:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            return ("anthropic", client, "claude-sonnet-4-20250514")
        except Exception as e:
            print(f"  ⚠️ Anthropic 客户端初始化失败: {e}")

    return (None, None, None)


def _call_ai(provider: str, client, prompt: str, model: str = None) -> str:
    """统一调用 AI，返回文本响应"""
    if provider == "openai":
        response = client.chat.completions.create(
            model=model or "gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0,
        )
        return response.choices[0].message.content.strip()

    elif provider == "anthropic":
        response = client.messages.create(
            model=model or "claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()

    raise ValueError(f"未知 provider: {provider}")


def parse_ai(text: str, meta: dict = None, client_info=None) -> dict:
    """
    用 AI 语义解析公告

    client_info: (provider, client, model) 元组，不传则自动创建
    """
    meta = meta or {}

    if client_info is None:
        client_info = _create_ai_client()

    provider, client, model = client_info
    if not provider:
        print(f"  ✗ 无可用 AI 接口（设置 OPENAI_API_KEY 或 ANTHROPIC_API_KEY）")
        return parse_regex(text, meta)

    # 截取前4000字（控制token用量）
    truncated = text[:4000] if len(text) > 4000 else text

    try:
        content = _call_ai(provider, client, _AI_PROMPT + truncated, model)

        # 清理可能的markdown代码块
        content = re.sub(r'^```json\s*', '', content)
        content = re.sub(r'\s*```$', '', content)

        parsed = json.loads(content)
    except Exception as e:
        print(f"  ✗ AI解析失败 ({provider}): {e}")
        return parse_regex(text, meta)

    # 组装为标准格式
    rec = {
        "股票代码": meta.get("stock_code", ""),
        "股票名称": meta.get("stock_name", ""),
        "公告日期": meta.get("announcement_date", ""),
        "公告标题": meta.get("announcement_title", ""),
        "公告链接": meta.get("announcement_url", ""),
        "股东名称": parsed.get("股东名称", ""),
        "股东类型": parsed.get("股东类型", ""),
        "减持数量(万股)": str(parsed.get("减持数量_万股", "")),
        "减持比例(%)": str(parsed.get("减持比例", "")),
        "股东持股比例(%)": str(parsed.get("股东持股比例", "")),
        "减持方式": parsed.get("减持方式", ""),
        "股份来源": normalize_share_source(parsed.get("股份来源", "")),
        "起始日期": parsed.get("起始日期", ""),
        "截止日期": parsed.get("截止日期", ""),
        "减持原因": parsed.get("减持原因", ""),
        "是否创投基金减持": parsed.get("是否创投基金减持", "否"),
        "warnings": [],
    }

    return rec


def parse_announcement(text: str, meta: dict = None, mode: str = "regex",
                       client_info=None) -> dict:
    """
    统一入口：解析减持公告

    mode:
      'regex' - 正则模式（默认，免费快速）
      'ai'    - AI 语义理解（OpenAI兼容/Anthropic）
      'auto'  - 先 regex，质量不够则 fallback 到 ai
    """
    if mode == "ai":
        return parse_ai(text, meta, client_info)
    elif mode == "auto":
        # 全部走AI，提取更精准
        return parse_ai(text, meta, client_info)
    else:
        return parse_regex(text, meta)
