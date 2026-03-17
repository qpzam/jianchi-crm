#!/usr/bin/env python3
"""
环境变量检查脚本
确保所有必要的API密钥都已正确配置
"""
import os

def check_env():
    """检查环境变量配置"""
    print("=" * 50)
    print("环境变量检查")
    print("=" * 50)

    # 检查必需的环境变量
    required_vars = ["TINYSHARE_TOKEN"]
    missing_required = []

    for var in required_vars:
        value = os.getenv(var)
        if value and value.strip():
            print(f"✓ {var}: 已设置")
        else:
            print(f"✗ {var}: 未设置或为空")
            missing_required.append(var)

    # 检查AI相关的环境变量（至少需要一个）
    ai_vars = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"]
    ai_providers = []

    for var in ai_vars:
        value = os.getenv(var)
        if value and value.strip():
            ai_providers.append(var)

    if ai_providers:
        print(f"\n✓ AI解析模式可用: {', '.join(ai_providers)}")
    else:
        print("\n⚠️ 未配置任何AI解析接口")
        print("请设置以下变量之一：")
        print("  OPENAI_API_KEY      # OpenAI兼容接口")
        print("  ANTHROPIC_API_KEY   # Anthropic Claude")

    # 检查可选的环境变量
    optional_vars = ["OPENAI_BASE_URL", "OPENAI_MODEL"]
    for var in optional_vars:
        value = os.getenv(var)
        if value and value.strip():
            print(f"✓ {var}: 已设置为 '{value}'")
        else:
            print(f"- {var}: 未设置（使用默认值）")

    # 总结
    print("\n" + "=" * 50)
    if missing_required:
        print("❌ 错误：缺少必需的环境变量")
        print(f"请设置：{' '.join(missing_required)}")
        print("\n获取API密钥：")
        print("  1. TinyShare: https://tushare.pro/")
        print("  2. OpenAI: https://platform.openai.com/")
        print("  3. Anthropic: https://console.anthropic.com/")
        return False
    else:
        print("✅ 环境变量检查通过")
        return True

if __name__ == "__main__":
    check_env()