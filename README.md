# 减持获客系统 (Shareholder Reduction CRM)

一个用于监控A股减持公告、自动匹配联系方式并生成日报的Python系统。

## 功能特性

- 📈 自动抓取巨潮网减持公告
- 🤖 AI解析PDF公告（支持OpenAI兼容接口和Claude）
- 📇 智能匹配联系方式
- 🎯 减持概率评分系统
- 📊 自动生成日报
- 💬 自动短信/邮件触达
- 💾 SQLite数据持久化
- 🔍 CLI命令行管理工具

## 系统架构

```
jianchi/
├── __main__.py          # 程序入口
├── pipeline.py          # 主管线流程
├── cninfo_fetcher.py    # 巨潮网抓取
├── pdf_parser.py        # PDF解析
├── contact_matcher.py   # 联系方式匹配
├── reduction_scorer.py  # 评分模型
├── auto_outreach.py     # 自动触达
├── db.py               # 数据库操作
├── gen_daily_report.py  # 日报生成
├── cli.py              # 命令行界面
├── config.py           # 配置管理
└── utils/              # 工具模块
    ├── stock.py        # 股票相关工具
    ├── date_parser.py  # 日期解析
    └── io.py          # 文件IO工具
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填入API密钥：

```bash
cp jianchi/.env.example jianchi/.env
```

需要配置的API：

- **TinyShare/Tushare**：获取市场数据（可选）
- **OpenAI API** 或 **Anthropic Claude**：用于AI解析PDF

### 3. 运行系统

```bash
# 抓取今日公告
python -m jianchi

# 抓取最近7天
python -m jianchi --days 7 --mode auto

# 指定日期
python -m jianchi --date 2026-03-17
```

## 命令行工具

### 基础命令

```bash
# 仪表盘 - 查看整体情况
python -m jianchi dash

# 今日工作清单
python -m jianchi todo

# 列出线索
python -m jianchi leads --limit 50
python -m jianchi leads --status 新线索
python -m jianchi leads --priority 高

# 搜索线索
python -m jianchi search 海能

# 查看详情
python -m jianchi detail 1

# 记录跟进
python -m jianchi log 1 电话 有意向 "客户有兴趣，下周再谈"
python -m jianchi log 2 电话 未接通

# 改变状态
python -m jianchi status 1 已签约

# 批量操作
python -m jianchi batch 1,2,3 未接通

# 查看待跟进
python -m jianchi followup

# 转化漏斗
python -m jianchi funnel
```

### 自动化运行

使用 `daily_run.sh` 设置定时任务：

```bash
# 编辑crontab
crontab -e

# 添加每日运行（每天早上9点）
0 9 * * * /path/to/your/project/daily_run.sh
```

## 数据文件

系统使用以下数据文件：

- `jianchi/data/` - 联系方式库（Excel/TXT格式）
- `jianchi/daily_output/` - 每日输出（JSON/TXT）
- `jianchi/jianchi.db` - SQLite数据库
- `jianchi/pdfs/` - 下载的PDF文件

## 联系方式库格式

支持多种格式：

### Excel格式
```excel
股票代码 | 股票名称 | 联系人 | 手机 | 邮箱 | 职务
```

### TXT格式
```
公司名 联系人 职务 电话：13800138000
```

## API配置说明

### TinyShare (可选)
用于获取股价、PE、质押率等市场数据
- 注册：https://tushare.pro/
- 在 `.env` 中设置 `TINYSHARE_TOKEN`

### AI解析接口

#### OpenAI兼容接口（推荐）
```env
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4
```

#### Anthropic Claude
```env
ANTHROPIC_API_KEY=sk-ant-xxx
```

## 工作流程

1. **抓取**：从巨潮网获取减持公告
2. **解析**：使用正则或AI解析PDF内容
3. **评分**：根据8个维度评估减持概率
4. **匹配**：对接联系方式库
5. **入库**：存入SQLite数据库
6. **输出**：生成TXT日报
7. **触达**：自动发送短信/邮件

## 注意事项

1. **联系方式库**：不上传到GitHub，自行准备
2. **API密钥**：保存在 `.env` 文件中，不要提交
3. **PDF下载**：需要网络连接访问巨潮网
4. **短信发送**：需要macOS和iPhone配置iMessage

## 开发说明

项目采用模块化设计，各功能模块相对独立：

- `config.py` - 集中管理所有配置
- `utils/` - 可复用的工具函数
- 每个模块都有详细的注释和中文说明

## 许可证

MIT License - 详见 LICENSE 文件