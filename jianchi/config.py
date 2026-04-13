"""
统一配置文件
所有路径、API密钥、常量集中管理
"""
import os
import time
import base64
from pathlib import Path

# ============================================================
# 项目根目录（自动检测，支持任何机器）
# ============================================================
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "daily_output"
PDF_DIR = PROJECT_ROOT / "pdfs"
LOG_DIR = PROJECT_ROOT / "logs"

# 确保目录存在
for d in [DATA_DIR, OUTPUT_DIR, PDF_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ============================================================
# API 密钥（必须从环境变量读取）
# ============================================================
TINYSHARE_TOKEN = os.getenv("TINYSHARE_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
OPENAI_MODEL = os.getenv("OPENAI_MODEL")

# ============================================================
# 巨潮网 API
# ============================================================
CNINFO_API_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_PDF_BASE = "http://static.cninfo.com.cn/"

# User-Agent 池，随机轮换防反爬
CNINFO_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


def _gen_accept_enckey() -> str:
    """生成巨潮网 Accept-Enckey 加密参数（AES-CBC加密时间戳）"""
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding as crypto_padding

        key = b"1234567887654321"
        iv = b"1234567887654321"
        plaintext = str(int(time.time())).encode("utf-8")

        padder = crypto_padding.PKCS7(128).padder()
        padded = padder.update(plaintext) + padder.finalize()

        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        ct = encryptor.update(padded) + encryptor.finalize()

        return base64.b64encode(ct).decode("utf-8")
    except Exception:
        return ""


def get_cninfo_headers() -> dict:
    """获取巨潮网请求头（含动态加密参数和随机UA）"""
    import random
    headers = {
        "User-Agent": random.choice(CNINFO_UA_POOL),
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "application/json, text/plain, */*",
        "Origin": "http://www.cninfo.com.cn",
        "Referer": "http://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/search",
    }
    enckey = _gen_accept_enckey()
    if enckey:
        headers["Accept-Enckey"] = enckey
    return headers


# 保持向后兼容（静态引用），但推荐使用 get_cninfo_headers()
CNINFO_HEADERS = {
    "User-Agent": CNINFO_UA_POOL[0],
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "application/json, text/plain, */*",
    "Origin": "http://www.cninfo.com.cn",
    "Referer": "http://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/search",
}

# 公告过滤关键词
INCLUDE_KEYWORDS = ["预披露", "减持计划", "拟减持", "减持股份计划", "股份计划公告", "股份的计划", "股份计划的公告", "减持公司股份", "减持A股"]
EXCLUDE_KEYWORDS = [
    "减持结果", "减持实施", "减持进展", "减持完成", "减持完毕",
    "实施完毕", "实施结果", "实施情况", "实施进展", "实施完成的公告", "实施完毕的公告", "实施情况的公告",
    "计划完成", "减持计划完成",
    "期限届满", "暨减持", "达到 1%", "达到1%", "提前终止",
    "更正公告", "补充公告", "更正",
]

# 股份来源标准化映射
SHARE_SOURCE_MAP = {
    "首次公开发行前": "IPO前取得",
    "首次公开发行股票前": "IPO前取得",
    "首发前": "IPO前取得",
    "上市前取得": "IPO前取得",
    "非公开发行": "非公开发行取得",
    "定向增发": "非公开发行取得",
    "股权激励": "股权激励授予",
    "限制性股票": "股权激励授予",
    "协议受让": "协议受让",
    "协议转让": "协议受让",
    "集中竞价买入": "集中竞价买入",
    "二级市场买入": "集中竞价买入",
    "资本公积转增": "资本公积转增",
    "配股": "配股获得",
    "继承": "继承/赠与",
    "赠与": "继承/赠与",
    "债转股": "债转股取得",
}

# ============================================================
# 联系方式匹配
# ============================================================
COMPANY_SUFFIXES = [
    "股份有限公司", "有限责任公司", "有限公司", "集团公司",
    "集团", "股份", "有限", "公司", "控股",
]

# 列名自动映射候选
UNLOCK_COL_CANDIDATES = {
    "stock_code": ["股票代码", "代码", "stock_code", "code", "ticker", "证券代码"],
    "stock_name": ["股票名称", "名称", "stock_name", "name", "简称", "证券简称", "股票"],
    "unlock_date": ["解禁日期", "日期", "unlock_date", "date", "解禁日", "上市日期"],
    "unlock_volume": ["解禁数量", "数量", "unlock_volume", "volume", "shares", "解禁股数"],
    "unlock_value": ["解禁市值", "市值", "unlock_value", "value"],
    "shareholder_name": ["股东名称", "股东", "shareholder", "holder", "持有人"],
    "shareholder_type": ["股东类型", "类型", "shareholder_type", "type"],
}

CONTACT_COL_CANDIDATES = {
    "contact_name": ["姓名", "联系人", "name", "contact_name", "联系人姓名"],
    "phone": ["手机", "电话", "mobile", "phone", "手机号", "联系电话"],
    "email": ["邮箱", "email", "mail", "电子邮箱"],
    "company": ["公司", "单位", "company", "corp", "公司名称", "所属公司"],
    "wechat": ["微信", "wechat", "wx", "微信号"],
    "position": ["职务", "职位", "position", "role", "title"],
    "status": ["状态", "status", "联系状态"],
    "notes": ["备注", "notes", "remark"],
}

# ============================================================
# 评分模型权重
# ============================================================
SCORE_WEIGHTS = {
    "announcement": 40,   # 已发公告（确定性最强）
    "unlock_date": 25,    # 解禁日期临近
    "price_change": 15,   # 股价涨幅（减持动机）
    "pledge_ratio": 10,   # 质押率（资金压力）
    "history": 8,         # 历史减持记录
    "holder_type": 7,     # 股东类型
    "share_source": 5,    # 股份来源
    "pe_valuation": 5,    # PE估值
}
INDUSTRY_PE_AVG = 30.0  # 行业平均PE（默认值）
