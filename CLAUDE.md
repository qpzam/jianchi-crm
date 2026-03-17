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
