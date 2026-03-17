# 减持获客系统 v2.0

## 重构说明

从 v1（38个散落的 .py 文件，12,764行）重构为 v2（10个模块，1,827行），代码量减少 85%。

### 新项目结构

```
jianchi/
├── __init__.py           # 包入口
├── __main__.py           # python -m jianchi 入口
├── config.py             # 统一配置（路径、API密钥、常量）
├── utils/                # 公共工具集
│   ├── __init__.py
│   ├── stock.py          # 股票代码/公司名处理（7个函数）
│   ├── date_parser.py    # 日期解析（3个函数）
│   └── io.py             # 文件读写/列名映射/Excel输出
├── cninfo_fetcher.py     # 巨潮网抓取（搜索+过滤+下载PDF+提取文本）
├── pdf_parser.py         # 公告解析（regex模式 + AI模式 + auto模式）
├── contact_matcher.py    # 联系方式匹配（精确→包含→代码→模糊 四级策略）
├── reduction_scorer.py   # 减持概率评分（100分制，8个维度）
└── pipeline.py           # 主管线（抓取→解析→评分→匹配→输出）
```

### 旧文件 → 新模块映射

| 旧文件 | 合并到 |
|--------|--------|
| `cninfo_scraper.py` | `cninfo_fetcher.py` |
| `cninfo_download_and_parse.py` | `cninfo_fetcher.py` |
| `cninfo_search_*.py` | `cninfo_fetcher.py` |
| `download_pdfs*.py` | `cninfo_fetcher.py` |
| `download_missing_pdfs.py` | `cninfo_fetcher.py` |
| `cninfo_parser_v2~v5.py` | `pdf_parser.py` |
| `cninfo_parser_fixed.py` | `pdf_parser.py` |
| `batch_pdf_parse*.py` | `pdf_parser.py` |
| `process_*_announcements*.py` | `pdf_parser.py` |
| `parse_new_pdfs_ai.py` | `pdf_parser.py` |
| `match_contacts.py` | `contact_matcher.py` |
| `auto_fetch_and_match.py` | `pipeline.py` + 各模块 |
| `reduction_predictor*.py` | `reduction_scorer.py` |
| `tinyshare_scraper.py` | `reduction_scorer.py` (TinyShareAPI类) |
| `generate_worklist.py` | 待迁移（晨报功能保留） |
| `outreach_interface.py` | 待迁移（外联接口保留） |
| `debug_*.py` | 删除（临时调试脚本） |
| `search_announcements.py` | `cninfo_fetcher.py` |
| `pdf_to_word.py` | 独立工具，按需保留 |

### 重复函数整合清单

| 函数 | 原来出现在 | 现在位于 |
|------|-----------|---------|
| `clean_stock_code()` | reduction_predictor ×2 | `utils/stock.py` |
| `format_ts_code()` | reduction_predictor ×2 | `utils/stock.py` |
| `extract_company_name()` | auto_fetch_and_match, tinyshare_scraper, SKILL.md | `utils/stock.py` |
| `normalize_company_name()` | match_contacts | `utils/stock.py` |
| `parse_stock()` | reduction_predictor ×2 | `utils/stock.py` → `parse_stock_field()` |
| `parse_date()` | reduction_predictor ×2, SKILL.md | `utils/date_parser.py` |
| `parse_date_range()` | cninfo_parser_v2~v4_1 ×4 | `utils/date_parser.py` |
| `normalize_code()` | cninfo_parser_v5 | `utils/stock.py` → `format_ts_code()` |
| `load_data()` / `load_worklist()` | match_contacts, generate_worklist | `utils/io.py` → `load_dataframe()` |
| `auto_map_columns()` | match_contacts | `utils/io.py` |
| `fetch()` / `search_announcements()` | cninfo_scraper, auto_fetch_and_match, cninfo_download_and_parse | `cninfo_fetcher.py` |
| `filt()` / `filter_announcements()` | cninfo_scraper, auto_fetch_and_match | `cninfo_fetcher.py` |

---

## 快速开始

### 安装依赖

```bash
pip install pandas openpyxl requests pdfplumber
# 可选（AI解析模式）
pip install anthropic
# 可选（评分需要TinyShare）
pip install tinyshare
```

### 使用方式

#### 步骤1: 配置环境变量

```bash
# 1. 复制模板文件
cp .env.example .env

# 2. 编辑 .env，填入你的API密钥
# 至少需要 TINYSHARE_TOKEN
# AI解析模式二选一：OPENAI_API_KEY 或 ANTHROPIC_API_KEY

# 3. 检查环境变量是否正确
python check_env.py
```

#### 步骤2: 运行系统

#### 方式1: 命令行

```bash
# 抓取今日公告（regex解析，无评分）
python -m jianchi --no-score

# 指定日期 + AI解析 + 联系方式匹配
python -m jianchi --date 2026-03-04 --mode ai --contacts data/联系方式库.xlsx

# 最近7天 + 完整流程
python -m jianchi --days 7 --contacts data/contacts.xlsx
```

#### 方式2: Python 调用

```python
from jianchi.pipeline import run_pipeline

records = run_pipeline(
    dates=["2026-03-04"],
    contacts_file="data/联系方式库.xlsx",
    parse_mode="auto",      # regex优先，失败自动切AI
    enable_score=True,       # 启用评分（需TinyShare）
)
```

#### 方式3: 单独使用各模块

```python
# 只用公司名工具
from jianchi.utils.stock import extract_company_name, classify_shareholder
print(extract_company_name("*ST海马"))  # → "海马"
print(classify_shareholder("宁波康运福股权投资有限公司"))  # → "PE/VC基金"

# 只用日期解析
from jianchi.utils.date_parser import parse_date
print(parse_date("3.20"))  # → "2026-03-20"

# 只抓公告不解析
from jianchi.cninfo_fetcher import fetch_and_filter
metas = fetch_and_filter("2026-03-04")

# 只做匹配
from jianchi.contact_matcher import match_company
print(match_company("海马", "海马汽车"))  # → "包含"
```

### 环境变量（必须配置）

⚠️ **安全提示**：所有API密钥必须通过环境变量配置，不得硬编码在代码中。

```bash
# TinyShare/Tushare API（用于获取市场数据和评分）
export TINYSHARE_TOKEN="your_token_here"

# AI解析模式二选一
export OPENAI_API_KEY="your_key_here"        # OpenAI兼容接口（推荐）
export OPENAI_BASE_URL="https://your-endpoint/v1"
export OPENAI_MODEL="gpt-4"
# 或
export ANTHROPIC_API_KEY="your_key_here"     # Anthropic Claude
```

---

## 配置说明

所有配置集中在 `config.py`，包括：

- **路径**: `PROJECT_ROOT`, `DATA_DIR`, `OUTPUT_DIR`, `PDF_DIR` — 自动检测，支持任何机器
- **API密钥**: 优先读环境变量，fallback到默认值
- **巨潮网**: API地址、请求头、过滤关键词
- **匹配**: 公司后缀列表、列名候选映射
- **评分**: 各维度权重、行业平均PE

---

## 与 Claude Code 集成

将 `jianchi/` 目录放入项目后，CLAUDE.md 中的指令仍然有效。Claude Code 可以直接 import 各模块：

```
"帮我抓今天的减持公告" → from jianchi.pipeline import run_pipeline
"匹配联系方式"       → from jianchi.contact_matcher import match_records
"这个股东什么类型"    → from jianchi.utils.stock import classify_shareholder
```
