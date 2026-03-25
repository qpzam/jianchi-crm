# 减持获客系统 JianChi CRM

## 项目概述
A股减持公告自动监控+获客系统。每天自动抓取巨潮网减持公告，AI解析PDF，匹配联系方式，生成日报。

## 环境
- Python 3.14, venv虚拟环境
- AI: OpenAI兼容接口（支持GPT-4、Claude等）
- 密钥在 .env 文件中，不要硬编码

## 每日运行命令
source venv/bin/activate
python3 -m jianchi --no-score --mode auto
python3 jianchi/gen_daily_report.py

## 关键文件
- jianchi/cninfo_fetcher.py - 巨潮网公告抓取
- jianchi/pdf_parser.py - AI全量PDF解析(auto模式直接走AI)
- jianchi/contact_matcher.py - 联系方式匹配
- jianchi/gen_daily_report.py - TXT简报生成器
- jianchi/auto_outreach.py - 短信/邮件触达
- jianchi/data/contacts_final.txt - 联系方式库（用户自备）
- daily_run.sh - 定时任务脚本
- .env - 环境变量(API密钥等，不提交到git)

## 注意事项
- 代码中不要硬编码API密钥、手机号等敏感信息
- 联系方式库contacts_final.txt不上传GitHub
- auto模式已改为全部走AI解析，不再用regex
- 短信通过iMessage发送，需要iPhone开启短信转发+蓝牙
## CC使用规则
- 每完成一个任务后主动总结结果，避免上下文膨胀
- 读文件时只读关键部分（用行号范围），不要读整个文件
- 不要在一次会话中做超过3个修改任务

## 法规问答模块
- 项目内含减持法规库：main/法律法规/ 目录，包含证监会、深交所、上交所的减持相关法规原文
- 当用户询问减持相关法律法规问题时，先在本地法规库中检索相关条文，再结合AI生成回答
- AI模型：黑宇GPT-5.4（OPENAI_BASE_URL=从.env读取）
- 法规问答命令：python3 jianchi/legal_advisor.py "你的问题"

## 指令映射（收到以下指令时直接执行，不要修改任何代码）
- "获取今天减持公告" / "抓取减持" / "今日减持" / "跑一下" = 执行以下命令：
  source venv/bin/activate
  python3 -m jianchi --no-score --mode auto
  python3 jianchi/gen_daily_report.py
  cat jianchi/daily_output/今日减持_$(date +%Y%m%d).txt
  执行完汇报：抓取数量、解析数量、匹配率、高优先级列表。不要改代码。

## 代码保护规则
- 修改任何.py文件后，必须运行一次完整测试确认功能正常：
  python3 -m jianchi --no-score --mode auto && python3 jianchi/gen_daily_report.py
- 不要直接push到main分支。改代码时先 git checkout -b fix/描述，确认没问题后再合并
- 以下文件是核心文件，修改前必须完整阅读理解：
  * gen_daily_report.py（锁定判断逻辑：不锁/瑕疵不锁/锁定）
  * pdf_parser.py（AI prompt是系统核心，改动需谨慎）
  * cninfo_fetcher.py（数据入口，改坏=无数据）
  * config.py（过滤规则，改坏=抓错数据）
- 每日AI调用不超过100次，超过立即停止
- jianchi/config_report.py 是日报排序和锁定判断的核心规则文件
  * 排序逻辑：锁定状态(创投不锁>确定不锁>瑕疵不锁>瑕疵锁定>确定锁定>待确认) → 减持比例降序 → 有联系方式优先
  * 此文件不得随意修改。修改前必须与用户确认。
  * gen_daily_report.py 的排序必须调用 config_report.sort_key()，禁止硬编码排序逻辑

## 紧急恢复
如果gen_daily_report.py被改坏（症状：重复数据、缺失分组、读全量数据库），立即执行：
git checkout v2.5-stable -- jianchi/gen_daily_report.py
然后只做最小改动，不要重写文件。
