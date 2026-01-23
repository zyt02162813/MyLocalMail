import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

def send_test_email():
    print("----- 📤 邮件发送测试启动 -----")
    
    # 1. 发件人信息 (还是用你刚才那个账号)
    my_sender = input("请输入你的邮箱地址: ")
    my_pass = input("请输入你的密码(或授权码): ")
    
    # 2. 收件人信息 (为了测试，建议发给自己)
    my_receiver = input("请输入收件人邮箱(推荐填自己): ")
    
    # 3. 邮件内容
    subject = "【测试】来自我的 Python 本地客户端"
    content = "你好！\n\n这是一封通过我亲手写的 Python 代码发送的邮件。\n如果不报错，说明 SMTP 发送功能完全正常！\n\n加油！"
    
    # 构造邮件格式
    msg = MIMEText(content, 'plain', 'utf-8')
    msg['From'] = formataddr(["我的本地客户端", my_sender])
    msg['To'] = formataddr(["测试收件人", my_receiver])
    msg['Subject'] = subject

    # 4. 连接服务器发送
    # 腾讯企业邮箱 SMTP 服务器: smtp.exmail.qq.com, 端口: 465 (SSL)
    smtp_server = "smtp.exmail.qq.com" 
    server_port = 465

    print(f"\n正在连接发送服务器 {smtp_server}...")
    
    try:
        server = smtplib.SMTP_SSL(smtp_server, server_port)
        server.login(my_sender, my_pass)
        print("✅ 发送服务器登录成功！")
        
        server.sendmail(my_sender, [my_receiver], msg.as_string())
        server.quit()
        print("🚀 邮件发送成功！快去收件箱看看！")
        
    except Exception as e:
        print(f"\n❌ 发送失败: {e}")

if __name__ == "__main__":
    send_test_email()
