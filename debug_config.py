import config
import sys
import traceback
import imaplib

# 强制显示所有字符（包括隐藏的）
def show_hidden_chars(s):
    return repr(s)

print("----- 🔍 开始配置诊断 -----")
print(f"Python 版本: {sys.version}")

try:
    for i, acc in enumerate(config.ACCOUNTS):
        print(f"\n[账户 {i+1}]")
        
        # 1. 检查邮箱地址
        email = acc['email']
        print(f"  邮箱 (原始值): {show_hidden_chars(email)}")
        if not email.isascii():
            print("  ❌ 警告：邮箱里包含非 ASCII 字符（如中文或全角符号）！请检查！")
        else:
            print("  ✅ 邮箱格式正常")

        # 2. 检查密码
        pwd = acc['password']
        # 为了安全，只显示长度和是否包含非法字符
        print(f"  密码 (长度): {len(pwd)}")
        if not pwd.isascii():
            print(f"  ❌ 警告：密码里包含非 ASCII 字符！(原始内容: {show_hidden_chars(pwd)})")
            print("     请确保密码里没有中文、全角空格或特殊符号。")
        else:
            print("  ✅ 密码格式正常")

        # 3. 尝试连接（带详细报错）
        print(f"  📡 正在尝试连接服务器: {acc['imap_server']} ...")
        try:
            mail = imaplib.IMAP4_SSL(acc['imap_server'])
            print("     连接建立成功，正在登录...")
            mail.login(email, pwd)
            print("  ✅ 🎉 登录成功！账号配置没问题。")
            mail.logout()
        except Exception:
            print("  ❌ 登录失败！详细报错如下：")
            traceback.print_exc()

except Exception as e:
    print(f"\n❌ 读取配置时严重错误: {e}")
    traceback.print_exc()

print("\n----- 诊断结束 -----")
