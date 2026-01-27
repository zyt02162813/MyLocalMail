import config
import imaplib
import email
from email.header import decode_header
import sys
import os

# === 1. 检查依赖库 ===
print("\n🔍 --- 步骤 1: 检查依赖库 ---")
try:
    import icalendar
    print("✅ icalendar 库已安装")
except ImportError:
    print("❌ 严重错误: icalendar 库未安装！请运行 pip install icalendar")
    sys.exit(1)

# === 辅助函数 ===
def decode_str(s):
    if not s: return ""
    try:
        decoded_list = decode_header(s)
        result = ""
        for value, charset in decoded_list:
            if isinstance(value, bytes):
                try: result += value.decode(charset or 'utf-8', errors='ignore')
                except: result += value.decode('utf-8', errors='ignore')
            else: result += str(value)
        return result
    except: return str(s)

# === 2. 开始连接 ===
print("\n📡 --- 步骤 2: 连接邮箱服务器 ---")
if not config.ACCOUNTS:
    print("❌ 错误: config.py 中没有配置任何账号！")
    sys.exit(1)

for acc in config.ACCOUNTS:
    email_addr = acc['email']
    print(f"\n[ 正在尝试连接: {email_addr} ]")
    
    try:
        # 连接 IMAP
        mail = imaplib.IMAP4_SSL(acc['imap_server'], acc['imap_port'])
        print("   ✅ 服务器连接成功")
        
        # 登录
        mail.login(email_addr, acc['password'])
        print("   ✅ 登录成功")
        
        # 选择文件夹
        status, _ = mail.select("INBOX")
        if status != 'OK':
            print("   ❌ 无法打开 INBOX 文件夹")
            continue
        print("   ✅ INBOX 文件夹打开成功")
        
        # 搜索邮件
        print("   🔍 正在搜索最近的 50 封邮件 (ALL)...")
        status, messages = mail.search(None, 'ALL')
        if not messages or messages[0] is None:
            print("   ⚠️ 未找到任何邮件！")
            continue
            
        mail_ids = messages[0].split()
        total_emails = len(mail_ids)
        print(f"   📊 收件箱共有 {total_emails} 封邮件")
        
        # 只看最后 50 封
        fetch_list = mail_ids[-50:] if total_emails > 50 else mail_ids
        
        print("\n   📨 --- 开始扫描邮件头 ---")
        found_target = False
        
        for num in reversed(fetch_list):
            try:
                # 只获取头信息，速度快
                _, msg_data = mail.fetch(num, '(BODY.PEEK[HEADER])')
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        subject = decode_str(msg["Subject"])
                        date = msg["Date"]
                        
                        # 打印每一封邮件的标题，证明真的在抓取
                        print(f"   - 邮件: {subject[:40]}... ({date})")
                        
                        # 检测是否包含 "Event" 或 "预算" 关键字
                        if "预算" in subject or "Event" in subject:
                            print(f"\n   🎯 ---> 找到疑似目标邮件！正在深入分析...")
                            found_target = True
                            
                            # 重新获取完整内容来分析附件
                            _, full_data = mail.fetch(num, '(RFC822)')
                            full_msg = email.message_from_bytes(full_data[0][1])
                            
                            if full_msg.is_multipart():
                                for part in full_msg.walk():
                                    ctype = part.get_content_type()
                                    fname = part.get_filename() or ""
                                    
                                    print(f"      [Part] Type: {ctype}, File: {fname}")
                                    
                                    if ctype == "text/calendar" or fname.endswith(".ics"):
                                        print("      ✅ 发现日历附件！正在尝试解析...")
                                        try:
                                            ics_content = part.get_payload(decode=True)
                                            cal = icalendar.Calendar.from_ical(ics_content)
                                            for component in cal.walk():
                                                if component.name == "VEVENT":
                                                    print(f"         📅 解析成功! 会议: {component.get('summary')}")
                                                    print(f"         ⏰ 时间: {component.get('dtstart').dt}")
                                        except Exception as e:
                                            print(f"      ❌ 解析失败: {e}")
                                            print(f"      📝 原始内容片段: {ics_content[:100]}")
                            else:
                                print("      ⚠️ 这封邮件不是多部分格式 (Multipart)，没有附件。")
                                
            except Exception as e:
                print(f"   ❌ 读取邮件出错: {e}")
        
        if not found_target:
            print("\n   ⚠️ 扫描了最近 50 封邮件，没有找到标题包含 '预算' 或 'Event' 的邮件。")
            print("   👉 建议：检查这封邮件是否太久远（超过50封）？或者在垃圾箱？")

        mail.logout()
        
    except Exception as e:
        print(f"❌ 连接发生异常: {e}")

print("\n🏁 --- 诊断结束 ---")