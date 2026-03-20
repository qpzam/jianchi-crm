#!/bin/bash
# 使用绝对路径，避免cron环境变量问题
BASE_DIR="/Users/yaoyajing/Desktop/减持获客系统"

source "$BASE_DIR/venv/bin/activate"
cd "$BASE_DIR"

# 从 .env 加载密钥（使用绝对路径）
if [ -f "$BASE_DIR/.env" ]; then
    export $(grep -v '^#' "$BASE_DIR/.env" | xargs)
fi

# 只在工作日运行
DOW=$(date +%u)
if [ "$DOW" -gt 5 ]; then
    echo "周末不运行"
    exit 0
fi

# 备份数据库
cp jianchi/jianchi.db "jianchi/jianchi.db.bak.$(date +%Y%m%d)" 2>/dev/null || true

python3 -m jianchi --no-score --mode auto 2>&1 | tee jianchi/daily_output/log_$(date +%Y%m%d).txt
python3 jianchi/gen_daily_report.py $(date +%Y%m%d)
osascript -e 'display notification "减持日报已生成" with title "减持获客系统" sound name "Glass"' 2>/dev/null || true
