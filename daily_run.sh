#!/bin/bash
source ~/Desktop/减持获客系统/venv/bin/activate
cd ~/Desktop/减持获客系统

# 从 .env 加载密钥
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# 只在工作日运行
DOW=$(date +%u)
if [ "$DOW" -gt 5 ]; then
    echo "周末不运行"
    exit 0
fi

python3 -m jianchi --no-score --mode auto 2>&1 | tee jianchi/daily_output/log_$(date +%Y%m%d).txt
python3 jianchi/gen_daily_report.py $(date +%Y%m%d)
osascript -e 'display notification "减持日报已生成" with title "减持获客系统" sound name "Glass"' 2>/dev/null || true
