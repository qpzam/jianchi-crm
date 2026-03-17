#!/bin/bash
# GitHub一键部署脚本

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 默认值（可通过命令行参数覆盖）
REPO_NAME="${1:-jianchi-crm}"
GITHUB_USER="${2:-}"
PRIVATE="${3:-public}"

echo -e "${YELLOW}=== 减持获客系统 GitHub 部署 ===${NC}"
echo "仓库名: $REPO_NAME"
echo "私有: $PRIVATE"
echo ""

# 检查是否安装了gh CLI
if command -v gh &> /dev/null; then
    echo -e "${GREEN}检测到 GitHub CLI${NC}"

    # 创建并推送
    if [ "$PRIVATE" = "private" ]; then
        gh repo create $REPO_NAME --private --source=. --push
    else
        gh repo create $REPO_NAME --public --source=. --push
    fi

    echo -e "\n${GREEN}✓ 部署完成！${NC}"
    echo "仓库地址: https://github.com/$(gh api user --jq .login)/$REPO_NAME"

elif [ -n "$GITHUB_USER" ]; then
    echo -e "${YELLOW}使用传统方式${NC}"

    REPO_URL="https://github.com/$GITHUB_USER/$REPO_NAME.git"

    # 添加远程仓库
    if git remote | grep -q "origin"; then
        git remote set-url origin $REPO_URL
    else
        git remote add origin $REPO_URL
    fi

    # 推送
    echo -e "${GREEN}正在推送代码...${NC}"
    git push -u origin main

    echo -e "\n${GREEN}✓ 部署完成！${NC}"
    echo "仓库地址: $REPO_URL"

else
    echo -e "${RED}错误: 需要安装 gh CLI 或提供 GitHub 用户名${NC}"
    echo ""
    echo "使用方法:"
    echo "  ./deploy.sh                    # 使用 gh CLI（推荐）"
    echo "  ./deploy.sh 仓库名             # 使用 gh CLI 指定仓库名"
    echo "  ./deploy.sh 仓库名 用户名      # 传统方式"
    echo "  ./deploy.sh 仓库名 用户名 private  # 私有仓库"
    echo ""
    echo "安装 gh CLI: brew install gh"
    exit 1
fi
