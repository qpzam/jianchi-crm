#!/bin/bash
set -e

# 使用绝对路径，避免cron环境变量问题
BASE_DIR="/Users/yaoyajing/Desktop/减持获客系统"
export TZ=Asia/Shanghai

source "$BASE_DIR/venv/bin/activate"
cd "$BASE_DIR"

# 从 .env 安全加载密钥（逐行解析，避免暴露到所有子进程）
if [ -f "$BASE_DIR/.env" ]; then
    chmod 600 "$BASE_DIR/.env" 2>/dev/null
    while IFS='=' read -r key value; do
        # 跳过注释和空行
        [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
        # 去掉值的引号
        value="${value%\"}"
        value="${value#\"}"
        value="${value%\'}"
        value="${value#\'}"
        export "$key=$value"
    done < "$BASE_DIR/.env"
fi

# 只在工作日运行
DOW=$(date +%u)
if [ "$DOW" -gt 5 ]; then
    echo "周末不运行"
    exit 0
fi

# 备份数据库
mkdir -p jianchi/backups
cp jianchi/jianchi.db "jianchi/backups/jianchi.db.$(date +%Y%m%d)" 2>/dev/null || true

python3 -m jianchi --no-score --mode auto 2>&1 | tee jianchi/daily_output/log_$(date +%Y%m%d).txt

# 检查解析结果是否为空
PARSED_FILE="jianchi/daily_output/parsed_$(date +%Y%m%d).json"
if [ ! -s "$PARSED_FILE" ]; then
    echo "⚠️ 解析结果为空，跳过日报生成"
    exit 0
fi

python3 jianchi/gen_daily_report.py $(date +%Y%m%d)

if [ -f "jianchi/daily_output/今日减持_$(date +%Y%m%d).txt" ]; then
    osascript -e 'display notification "减持日报已生成" with title "减持获客系统" sound name "Glass"' 2>/dev/null || true
else
    osascript -e 'display notification "减持日报生成失败！" with title "⚠️ 减持获客系统" sound name "Basso"' 2>/dev/null || true
fi
