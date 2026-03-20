[English](README_EN.md)

# 减持获客智能系统 JianChi CRM Pro

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![AI Powered](https://img.shields.io/badge/AI-Powered-purple.svg)](https://openai.com/)
[![macOS](https://img.shields.io/badge/macOS-Compatible-lightgrey.svg)](https://www.apple.com/macos/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 产品定位

减持获客智能系统（JianChi CRM Pro）是一套面向大宗交易机构、禁售期股份承接方的智能获客系统。系统通过AI技术自动监控A股市场上市公司股东减持计划公告，实时提取关键信息并自动匹配联系方式，帮助业务团队第一时间触达潜在客户

## 📢 最近更新

### v2.3.0 (2026-03-20)
- 🕐 daily_run.sh强制设置Asia/Shanghai时区，cron环境下日期判断更可靠
- 🔒 .env文件权限收紧为600，防止密钥泄露
- 🛡️ PDF下载前校验URL域名必须为cninfo.com.cn
- 🔍 巨潮网API返回结构校验，字段变更时自动告警
- 💰 AI调用每日100次硬性上限，超限自动停止并降级regex
- 📡 抓取范围扩展为前2天+当天，防漏抓晚间/周末公告
- 📜 免责声明扩展（投资建议、个人信息、触达合规）

### v2.2.0 (2026-03-20)
- 📋 多股东公告自动拆分为独立记录，各自保留减持比例
- ⏰ 减持窗口临近判断扩展至5天，备注显示具体天数
- 🚫 自动过滤更正/补充公告，避免数据重复
- 💾 数据库备份改为独立backups目录，sent_sms.json改为原子写入
- ⚠️ AI解析降级时打印明确WARNING警告
- 🔔 定时任务增加失败告警通知
- 📜 README增加免责声明

### v2.1.0 (2026-03-20)
- 🌟 新增创投基金智能识别，自动标记适用创投减持新规的公告
- 🔒 新增受让方锁定期自动判断（不锁/瑕疵不锁/锁定），基于股份来源+持股比例
- 🧠 新增AI智能备注，自动标注高比例、机构股东、窗口临近等信号
- 📊 日报按锁定状态优先级排序，不锁定的排最前

### v2.0.0 (2026-03-17)
- 🤖 全面切换AI解析模式，淘汰正则，准确率>95%
- 📖 新增减持法规问答模块，内置法规库+AI问答
- 💬 新增iMessage短信+邮件自动触达
- ⏰ 新增定时任务，每日自动唤醒+抓取+生成日报
- 📇 股份来源完整提取，不再简化归类

### v1.0.0 (2026-03-05)
- 📡 巨潮网公告自动抓取
- 📄 PDF解析提取减持信息
- 📇 联系方式库匹配

## 一句话介绍

每天早8点自动抓取A股减持公告 → AI解析PDF → 匹配电话 → 生成日报，比同行快2小时触达客户。


## 效果对比

| 对比维度 | 传统人工方式 | 本系统 |
|---------|------------|--------|
| 公告监控 | 刷巨潮网、微信群，容易遗漏 | 自动抓取巨潮网全覆盖 |
| PDF解析 | 逐个打开阅读，耗时费力 | AI批量解析，秒级完成 |
| 联系方式 | 查企查查、翻通讯录 | 自动匹配库中联系方式 |
| 触达效率 | 发短信、打电话需手动录入 | 一键批量触达 |
| 响应速度 | 公告后2-4小时才能联系 | 公告发布后30分钟内触达 |

---

## 功能特性

| 功能 | 说明 |
|------|------|
| 📈 **公告抓取** | 每日自动抓取巨潮网减持公告，支持指定日期范围 |
| 🤖 **AI解析** | 支持OpenAI/Claude API，智能解析PDF提取关键信息 |
| 📇 **联系匹配** | 自动匹配联系方式库，支持多种数据格式 |
| 📊 **日报生成** | 自动生成带优先级标记的日报，含AI智能备注 |
| 💬 **智能触达** | 支持iMessage短信批量发送，自动去重 |
| ⏰ **定时运行** | 支持crontab定时任务，合盖休眠自动唤醒 |
| 🔍 **CRM管理** | 线索状态跟踪、跟进记录、转化漏斗分析 |


---

## 快速开始

### 一键安装

```bash
# 克隆仓库
git clone https://github.com/qpzam/jianchi-crm.git
cd jianchi-crm

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt
```

### 配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填入AI密钥
# OPENAI_API_KEY=sk-your-api-key-here
# OPENAI_BASE_URL=https://api.openai.com/v1
# OPENAI_MODEL=gpt-4
```

准备联系方式库，放入 `jianchi/data/` 目录：
- Excel格式：包含股票代码、股票名称、联系人、手机、邮箱、职务
- TXT格式：`公司名 联系人 职务 电话：138xxxx1234`

### 运行

```bash
# 抓取今日公告（AI模式）
python -m jianchi --mode auto

# 抓取最近7天
python -m jianchi --days 7 --mode auto

# 生成日报
python jianchi/gen_daily_report.py

# 查看仪表盘
python -m jianchi dash
```

### 设置定时任务

```bash
# 编辑crontab
crontab -e

# 添加每天早上8点运行
0 8 * * * cd /path/to/jianchi-crm && source venv/bin/activate && python -m jianchi --mode auto && python jianchi/gen_daily_report.py

# 配置macOS合盖不休眠（需管理员权限）
sudo pmset -b disablesleep 0
sudo pmset -b sleep 0  # 合盖不休眠
sudo pmset -b disablesleep 1  # 合盖休眠但定时任务会唤醒
```

**⚠️ 注意：请选择"合盖休眠不要关机"，定时任务仍会自动唤醒运行。**

---

## 日报示例

```
============================================================
  减持获客日报  2026-03-20
  抓取: 18 条 | 新增: 0 | 匹配: 15/18
============================================================

🌟 [1] 300567 某芯片公司 | 深圳创新投资合伙企业 | 2.80%
    减持方式: 大宗交易 | 减持期间: 2026-03-25 ~ 2026-09-24
    股份来源: IPO前取得
    🌟 创投基金减持 | 受让方不锁定 | 不受比例限制 | 可按市场价承接
    ✅ 有联系方式
    🤖 AI备注: 🌟 创投基金减持，受让方无锁定期，无比例限制，优先跟进
    💚 受让方不锁定（创投基金减持）
    联系方式 (1 条):
      - 赵强 | 136xxxx7890 | 董秘

🔴 [2] 600123 某科技公司 | 创新合伙人 | 3.50%
    减持方式: 大宗交易 | 减持期间: 2026-03-20 ~ 2026-09-19
    股份来源: IPO前取得
    ✅ 有联系方式
    🤖 AI备注: 高比例减持 + 大宗交易概率大 + 机构股东 + 可能有承接需求
    🔒 受让方锁定6个月（IPO前取得）
    联系方式 (2 条):
      - 王明 | 138xxxx1234 | 董秘
      - 李华 | 139xxxx5678 | 证券事务代表

🟡 [3] 002456 某制造公司 | 南方资本 | 1.80%
    减持方式: 集中竞价 | 减持期间: 2026-03-25 ~ 2026-09-24
    股份来源: 二级市场买入
    ✅ 有联系方式
    🤖 AI备注: 机构股东 + 可能有承接需求
    💚 受让方不锁定（二级市场买入）
    联系方式 (1 条):
      - 张伟 | 137xxxx9012 | 投资总监

🟢 [4] 300789 某电气公司 | 苏州高新区 | 0.50%
    减持方式: 大宗交易 | 减持期间: 2026-04-01 ~ 2026-09-30
    股份来源: 协议转让
    ❌ 无联系方式
    🤖 AI备注: 普通减持
    💛 瑕疵不锁（持股比例未知，需确认）（协议转让取得，持股比例未知）

============================================================
  本次汇总:
    解析: 18 条 → 新增 0 + 更新 15
    优先级: 🌟创投 1 | 🔴高 3 | 🟡中 5 | 🟢低 6
    创投基金减持: 1 家（受让方不锁定）
    锁定判断: 💚 不锁定: 5 家 | 💛 瑕疵不锁: 3 家 | 🔒 锁定: 2 家 | ❓ 待确认: 5 家
    匹配率: 15/18 (83%)
    输出: jianchi/daily_output/今日减持_20260320.txt
============================================================
```

---

## 触达功能

### 短信发送（iMessage）

```bash
# 预览短信（不发送）
python jianchi/auto_outreach.py sms

# 发送短信
python jianchi/auto_outreach.py sms --send

# 电话跟进模板
python jianchi/auto_outreach.py sms --followup

# 测试发送
python jianchi/auto_outreach.py test 138xxxx1234
```

### 邮件发送

在 `.env` 中配置SMTP：
```env
SMTP_HOST=smtp.exmail.qq.com
SMTP_PORT=465
SMTP_USER=your-email@example.com
SMTP_PASSWORD=your-password
SMTP_FROM=your-name <your-email@example.com>
```

### 触达最佳实践

| 项目 | 建议 |
|------|------|
| 触达时机 | 公告发布后30分钟内，或上午9-10点 |
| 优先顺序 | 🔴高比例减持 → 🟡机构股东 → 🟢普通减持 |
| 策略 | 高比例先电话，中比例先短信 |
| 频率 | 首次触达后3天未回复可再次跟进 |
| 防重复 | 系统自动记录已发送，避免重复联系 |

---

## 项目结构

```
jianchi-crm/
├── docs/                              # 文档
│   └── 减持获客系统_操作手册_V2.0.docx
├── jianchi/                           # 核心代码
│   ├── __init__.py                    # 包初始化
│   ├── __main__.py                    # 程序入口
│   ├── pipeline.py                    # 主管线流程
│   ├── cninfo_fetcher.py             # 巨潮网公告抓取
│   ├── pdf_parser.py                 # PDF解析（正则+AI）
│   ├── contact_matcher.py            # 联系方式匹配
│   ├── reduction_scorer.py           # 减持概率评分
│   ├── auto_outreach.py              # 短信/邮件触达
│   ├── gen_daily_report.py           # 日报生成器
│   ├── db.py                         # SQLite数据库操作
│   ├── cli.py                        # 命令行界面
│   ├── config.py                     # 配置管理
│   ├── data/                         # 数据目录（不提交）
│   │   ├── contacts_final.txt        # 联系方式库
│   │   └── contacts_merged.txt       # 合并库
│   ├── daily_output/                 # 每日输出（不提交）
│   ├── logs/                        # 日志目录
│   ├── pdfs/                        # PDF缓存（不提交）
│   └── utils/                       # 工具模块
│       ├── __init__.py
│       ├── stock.py                 # 股票相关工具
│       ├── date_parser.py           # 日期解析
│       └── io.py                    # 文件IO工具
├── daily_run.sh                      # 定时任务脚本
├── deploy.sh                         # 部署脚本
├── .env.example                      # 环境变量模板
├── .gitignore                        # Git忽略配置
├── requirements.txt                  # Python依赖
├── README.md                         # 项目说明
└── LICENSE                           # MIT许可证
```

---

## 联系方式库格式

### Excel格式

| 股票代码 | 股票名称 | 联系人 | 手机 | 邮箱 | 职务 |
|---------|---------|--------|------|------|------|
| 600123 | 某科技公司 | 王明 | 138xxxx1234 | wm@example.com | 董秘 |
| 002456 | 某制造公司 | 李华 | 139xxxx5678 | lh@example.com | 证券事务代表 |

### TXT格式

```
某科技公司 王明 董秘 电话：138xxxx1234
某制造公司 李华 证券事务代表 电话：139xxxx5678
某电气公司 张伟 投资总监 电话：137xxxx9012
```

---

## 环境要求

| 组件 | 要求 |
|------|------|
| 操作系统 | macOS 12+（推荐），Linux（部分功能） |
| Python | 3.12 或更高版本 |
| AI API | OpenAI API 或 Claude API |
| 网络 | 稳定的互联网连接 |
| iPhone | 短信功能需要iPhone + iCloud同步（可选） |

---

## 技术指标

| 指标 | 数据 |
|------|------|
| 抓取范围 | 巨潮网全市场减持公告 |
| 日均公告数 | 10-50条/日 |
| AI解析准确率 | >95%（基于GPT-4/Claude） |
| 联系库规模 | 支持自定义联系方式库，自动匹配上市公司董秘/证代电话 |
| 匹配率 | 60%-80%（取决于库质量）|
| 单次耗时 | 约2-5分钟（15条公告） |

---

## 定时任务

### Crontab配置

```bash
# 每天早上8点运行
0 8 * * * cd ~/Desktop/减持获客系统 && source venv/bin/activate && python -m jianchi --mode auto && python jianchi/gen_daily_report.py

# 工作日早上8点运行
0 8 * * 1-5 cd ~/Desktop/减持获客系统 && source venv/bin/activate && python -m jianchi --mode auto && python jianchi/gen_daily_report.py
```

### macOS电源管理

```bash
# 查看当前设置
pmset -g

# 合盖不休眠（不推荐，费电）
sudo pmset -b sleep 0

# 合盖休眠但定时任务可唤醒（推荐）
sudo pmset -b disablesleep 0
sudo pmset -b powernap 1

# 定时唤醒检查
sudo pmset repeat wake MTWRFSU 08:00:00
```

**⚠️ 重要：请使用"合盖休眠不要关机"模式，系统会在定时任务触发时自动唤醒。**

---

## 📖 减持法律法规库

本项目内置完整的A股减持法律法规库，包含证监会规章、深交所/上交所规则、实施细则等，共101个文件。

👉 [查看完整法规目录](docs/REGULATIONS.md)

常用法规速查：
| 场景 | 适用法规 |
|------|---------|
| 大股东/特定股东减持比例限制 | [深交所自律监管指引第18号](docs/法律法规/深圳证券交易所上市公司自律监管指引第18号-股东及董事、监事、高级管理人员减持股份.pdf) |
| 创投基金减持特别规定 | [证监会公告[2020]17号](docs/法律法规/上市公司创业投资基金股东减持股份的特别规定（2020%20年修订）.pdf) |
| 董监高减持限制 | [上市公司董事监事高管持股变动管理规则](docs/法律法规/附件1：上市公司董事、监事和高级管理人员所持本公司股份及其变动管理规则（2022年修订）.pdf) |
| 大宗交易受让方锁定期 | [深交所自律监管指引第18号](docs/法律法规/深圳证券交易所上市公司自律监管指引第18号-股东及董事、监事、高级管理人员减持股份.pdf) |

---

## 常见问题

<details>
<summary><b>Q1: AI解析失败怎么办？</b></summary>

检查以下几点：
1. `.env` 中的 `OPENAI_API_KEY` 是否正确
2. `OPENAI_BASE_URL` 是否可访问（国内可能需要代理）
3. API额度是否充足
4. 可尝试切换 `--mode regex` 使用正则解析
</details>

<details>
<summary><b>Q2: 联系方式匹配率低？</b></summary>

1. 检查联系方式库格式是否正确
2. 公司名称是否一致（去除ST/*等标记）
3. 尝试使用Excel格式，系统自动列名识别
4. 手动补充缺失的联系方式
</details>

<details>
<summary><b>Q3: iMessage短信发送失败？</b></summary>

1. 确认macOS和iPhone在同一iCloud账户
2. iPhone设置 → 信息 → iMessage → 打开"短信转发"
3. 检查手机号格式是否正确（需+86前缀）
4. macOS系统设置确保"信息"应用已登录iMessage
</details>

<details>
<summary><b>Q4: 定时任务不执行？</b></summary>

1. 检查crontab格式：`crontab -l`
2. 确认Python环境路径正确：`which python3`
3. 查看cron日志：`log show --predicate 'process == "cron"'`
4. 测试命令能否手动执行
</details>

<details>
<summary><b>Q5: 如何增加AI解析准确率？</b></summary>

1. 使用更高版本的模型（如GPT-4）
2. 在 `pdf_parser.py` 中调整Prompt
3. 结合正则+AI双模式验证
4. 手动标注错误样本，持续优化
</details>

<details>
<summary><b>Q6: 支持Windows系统吗？</b></summary>

核心功能支持，但有限制：
- ✅ 公告抓取、PDF解析、日报生成
- ✅ 邮件发送
- ❌ iMessage短信（Windows不支持）
- ⚠️ 定时任务需用Windows Task Scheduler替代crontab
</details>

---

## 免责声明

- 本项目仅供学习交流，不构成任何投资建议
- 联系方式库由用户自行准备，本项目不提供也不鼓励非法获取个人信息
- 使用者应遵守《个人信息保护法》及相关法规
- 短信/邮件触达功能请合理使用，避免骚扰

---

## License

MIT License - 详见 [LICENSE](LICENSE) 文件

---

## 致谢

- [Anthropic](https://claude.com/product/claude-code) - vibe coding  
- [巨潮资讯网](http://www.cninfo.com.cn) - 公告数据来源
- [OpenAI](https://openai.com/) - GPT模型支持
- [pdfplumber](https://github.com/jsvine/pdfplumber) - PDF解析库


## 联系作者
Richardclovesmom@163.com

如果有帮助请给 ⭐️ Star
