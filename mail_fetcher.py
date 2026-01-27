# mail_fetcher.py
# V27.1 - Fix: 修复 hashlib 缺失导致无法保存会议的 Bug
import sqlite3
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta
import os
import uuid
import re 
import config
import html 
import socket
import hashlib  # <--- 补上了这关键的一行！

try:
    import icalendar
    HAS_ICAL = True
except ImportError:
    HAS_ICAL = False
    print("❌ 警告：未安装 icalendar 库")

# 限制扫描最新的 30 封
FETCH_LIMIT = 30 
ATTACHMENT_DIR = "attachments"

if not os.path.exists(ATTACHMENT_DIR):
    os.makedirs(ATTACHMENT_DIR)

def decode_str(s):
    if not s: return ""
    try:
        s = str(s).replace('\r', '').replace('\n', '')
        decoded_list = decode_header(s)
        result = ""
        for value, charset in decoded_list:
            if isinstance(value, bytes):
                try: result += value.decode(charset or 'utf-8', errors='ignore')
                except: result += value.decode('utf-8', errors='ignore')
            else: result += str(value)
        return result
    except: return str(s)

def parse_date(date_str):
    if not date_str: return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        dt = email.utils.parsedate_to_datetime(date_str)
        if dt.tzinfo: dt = dt.astimezone()
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except: return str(date_str)

def format_size(size_bytes):
    try:
        s = int(size_bytes)
        if s < 1024: return f"{s}B"
        elif s < 1048576: return f"{s/1024:.1f}KB"
        else: return f"{s/1048576:.1f}MB"
    except: return "0B"

def format_ics_time(dt_obj):
    if dt_obj is None: return ""
    if hasattr(dt_obj, 'dt'): dt_obj = dt_obj.dt
    if not isinstance(dt_obj, datetime): return dt_obj.strftime("%Y-%m-%d 09:00")
    try:
        if dt_obj.tzinfo: dt_obj = dt_obj.astimezone()
        return dt_obj.strftime("%Y-%m-%d %H:%M")
    except: return datetime.now().strftime("%Y-%m-%d %H:%M")

def extract_ics_data(msg_content):
    if not HAS_ICAL: return None
    try:
        cal = icalendar.Calendar.from_ical(msg_content)
        for component in cal.walk():
            if component.name == "VEVENT":
                summary = decode_str(str(component.get('summary', '无标题')))
                location = str(component.get('location', ''))
                description = str(component.get('description', ''))
                uid = str(component.get('uid', ''))
                start_str = format_ics_time(component.get('dtstart'))
                end_str = format_ics_time(component.get('dtend'))
                return {"uid": uid, "summary": summary, "start_time": start_str, "end_time": end_str, "location": location, "description": description}
    except: pass
    return None

def extract_meeting_from_text(subject, raw_text):
    info = {"uid": "", "summary": subject, "start_time": "", "end_time": "", "location": "", "description": ""}
    link_patterns = [
        r'(https?://teams\.microsoft(?:online)?\.(?:com|cn)/dl/launcher/launcher\.html\?[^\s"\'<>]+)',
        r'(https?://teams\.microsoft(?:online)?\.(?:com|cn)/[^\s"\'<>]+)',
        r'(https?://(?:meeting\.tencent\.com|voovmeeting\.com)/[A-Za-z0-9/_?=&%.-]+)',
        r'(https?://\w+\.zoom\.us/[A-Za-z0-9/_?=&%.-]+)'
    ]
    for pat in link_patterns:
        match = re.search(pat, raw_text)
        if match:
            info["location"] = html.unescape(match.group(1))
            break
    clean_text = re.sub(r'<[^>]+>', ' ', raw_text) 
    info["description"] = clean_text[:200].strip()
    date_part = r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}'
    time_part = r'\d{1,2}:\d{2}'
    strong = rf'(?:会议时间|Meeting Time)[：:]\s*({date_part}.*?{time_part})'
    weak = rf'(?<!发送)(?<!Sent\s)(?<!Date:\s)(?:时间|Time)[：:]\s*({date_part}.*?{time_part})'
    match = re.search(strong, clean_text, re.IGNORECASE)
    if not match: match = re.search(weak, clean_text, re.IGNORECASE)
    if match:
        try:
            nums = re.findall(r'\d+', match.group(1).strip())
            if len(nums) >= 5: 
                y, m, d, h, mn = map(int, nums[:5])
                s_dt = datetime(y, m, d, h, mn)
                info["start_time"] = s_dt.strftime("%Y-%m-%d %H:%M")
                info["end_time"] = (s_dt + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        except: pass
    if info["start_time"]:
        seed = f"{info['summary']}_{info['start_time']}"
        info["uid"] = hashlib.md5(seed.encode()).hexdigest()
        return info
    return None

def save_attachment(payload, filename):
    try:
        safe_name = f"{uuid.uuid4().hex[:8]}_{filename}"
        file_path = os.path.join(ATTACHMENT_DIR, safe_name)
        with open(file_path, "wb") as f: f.write(payload)
        return os.path.abspath(file_path)
    except: return ""

def fetch_mail(init_mode=False, callback=None):
    conn = sqlite3.connect('local_mail.db'); c = conn.cursor()
    new_count = 0
    
    if callback: callback(0, "🚀 准备连接服务器...")

    # 遍历所有账号
    total_accounts = len(config.ACCOUNTS)
    
    for idx, acc in enumerate(config.ACCOUNTS):
        try:
            acc_name = acc.get('name', acc['email'])
            base_progress = int((idx / total_accounts) * 100)
            
            if callback: callback(base_progress + 2, f"📡 连接 [{idx+1}/{total_accounts}]: {acc_name}")
            
            socket.setdefaulttimeout(15)
            mail = imaplib.IMAP4_SSL(acc['imap_server'], acc['imap_port'])
            mail.login(acc['email'], acc['password']); mail.select("INBOX")
            
            # 搜索 ALL (含已读)
            status, messages = mail.search(None, 'ALL')
            ids = messages[0].split()
            
            # 截取最后30封
            mail_ids = ids[-FETCH_LIMIT:] if len(ids) > FETCH_LIMIT else ids
            total_mails = len(mail_ids)
            
            print(f"\n--- 账号 {acc_name}: 扫描最新 {total_mails} 封邮件 ---")

            for i, num in enumerate(reversed(mail_ids)):
                step_progress = base_progress + int((i / total_mails) * (100 / total_accounts))
                if callback: callback(step_progress, f"📥 {acc_name}: 邮件 {i+1}/{total_mails}")

                try:
                    status, msg_data = mail.fetch(num, '(RFC822)')
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])
                            msg_id = msg.get("Message-ID", "").strip() or str(num)
                            subj = decode_str(msg["Subject"])
                            
                            c.execute("SELECT id FROM emails WHERE message_id=?", (msg_id,))
                            if c.fetchone(): continue 

                            sender = decode_str(msg["From"]); recip = decode_str(msg["To"]); cc = decode_str(msg["Cc"])
                            date = parse_date(msg["Date"])
                            body_t = ""; body_h = ""; atts = []; ics_data = None
                            
                            if msg.is_multipart():
                                for part in msg.walk():
                                    ctype = part.get_content_type(); fname = part.get_filename()
                                    try: payload = part.get_payload(decode=True)
                                    except: continue
                                    if not payload: continue

                                    if ctype == "text/calendar" or (fname and fname.lower().endswith(".ics")):
                                        if HAS_ICAL: ics_data = extract_ics_data(payload)
                                    
                                    if ctype == "text/plain" and not fname: body_t += payload.decode(errors='ignore')
                                    elif ctype == "text/html" and not fname: body_h += payload.decode(errors='ignore')
                                    elif fname:
                                        fn_str = decode_str(fname)
                                        if not fn_str.lower().endswith('.ics'):
                                            real_path = save_attachment(payload, fn_str)
                                            if real_path: atts.append(f"{fn_str}|{real_path}|{format_size(len(payload))}")
                            else:
                                payload = msg.get_payload(decode=True)
                                if payload:
                                    t = payload.decode(errors='ignore')
                                    if msg.get_content_type() == "text/html": body_h = t
                                    else: body_t = t

                            if not ics_data:
                                search_text = body_h if body_h else body_t 
                                ics_data = extract_meeting_from_text(subj, search_text)

                            c.execute('''INSERT INTO emails (account_email, message_id, subject, sender, recipient, cc, date_received, body_html, body_text, attachments, folder) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'inbox')''', (acc['email'], msg_id, subj, sender, recip, cc, date, body_h, body_t, ";".join(atts)))
                            new_count += 1
                            
                            if ics_data and ics_data['uid']:
                                print(f"   ✅ 发现会议: {ics_data['summary']}")
                                c.execute("SELECT id FROM events WHERE uid=?", (ics_data['uid'],))
                                if not c.fetchone():
                                    c.execute("INSERT INTO events (uid, summary, start_time, end_time, location, description, sender, recipient, minutes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '')", (ics_data['uid'], ics_data['summary'], ics_data['start_time'], ics_data['end_time'], ics_data['location'], ics_data['description'], sender, recip))
                            
                            conn.commit()
                except Exception as e:
                    print(f"   ❌ 出错: {e}")
                    continue
            mail.logout()
        except Exception as e: 
            if callback: callback(100, f"⚠️ 网络错误: {e}")
            print(f"连接错误: {e}")
            
    conn.close()
    if callback: callback(100, f"✅ 完成: 新增 {new_count} 封")
    return new_count

if __name__ == "__main__": fetch_mail(init_mode=True)