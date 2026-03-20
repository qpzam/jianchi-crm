#!/bin/bash
# 减持获客系统 - 一键安装脚本

set -e

echo "=========================================="
echo "  减持获客系统 JianChi CRM - 安装脚本"
echo "=========================================="

# 检查 Python 版本
if ! command -v python3 &>/dev/null; then
    echo "✗ 未找到 python3，请先安装 Python 3.12+"
    exit 1
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✓ Python 版本: $PY_VER"

# 创建虚拟环境
if [ ! -d "venv" ]; then
    echo "→ 创建虚拟环境..."
    python3 -m venv venv
    echo "✓ 虚拟环境已创建"
else
    echo "✓ 虚拟环境已存在"
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "→ 安装依赖..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "✓ 依赖安装完成"

# 创建必要目录
mkdir -p jianchi/data jianchi/daily_output jianchi/pdfs jianchi/logs jianchi/prompts
echo "✓ 目录结构已就绪"

# 配置环境变量
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "→ 已创建 .env 文件，请编辑填入 API 密钥:"
    echo "   vim .env"
else
    echo "✓ .env 文件已存在"
fi

echo ""
echo "=========================================="
echo "  安装完成！"
echo "=========================================="
echo ""
echo "下一步："
echo "  1. 编辑 .env 填入 AI API 密钥"
echo "  2. 将联系方式库放入 jianchi/data/"
echo "  3. 运行: source venv/bin/activate && python -m jianchi --mode auto"
