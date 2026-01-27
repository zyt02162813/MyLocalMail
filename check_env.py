import sys
import os

print("-" * 30)
print("🔍 环境诊断工具")
print("-" * 30)

# 1. 检查 icalendar 库
try:
    import icalendar
    print("✅ icalendar 库: 已安装")
except ImportError:
    print("❌ icalendar 库: 未安装 (这是导致日历空白的主要原因！)")
    print("   -> 请在终端运行: pip install icalendar")

# 2. 检查网络连接 (尝试连接 Outlook)
import socket
print("\n📡 网络连通性测试 (Outlook):")
try:
    # 尝试连接 Outlook IMAP 端口
    sock = socket.create_connection(("outlook.office365.com", 993), timeout=5)
    print("✅ 连接成功: 您的网络可以直接访问邮箱服务器")
    sock.close()
except Exception as e:
    print(f"❌ 连接失败: {e}")
    print("   -> 您的网络可能需要全局代理，或者代理端口未对 Python 生效")

print("-" * 30)