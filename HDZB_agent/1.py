import os

# 检查所有包含"ARK"的环境变量
print("=== 检查环境变量 ===")
for key, value in os.environ.items():
    if "ARK" in key.upper():
        print(f"{key} = {value[:10]}..." if value else f"{key} = (空值)")

# 专门检查目标环境变量
api_key = os.environ.get("ARK_API_KEY")
print(f"\nARK_API_KEY 是否存在: {api_key is not None}")
if api_key:
    print(f"ARK_API_KEY 值: {api_key[:10]}...")  # 只显示前10位，保护密钥
else:
    print("❌ ARK_API_KEY 环境变量未设置！")