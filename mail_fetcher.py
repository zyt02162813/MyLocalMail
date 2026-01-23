# mail_fetcher.py
# V16.5 - Fix: 修复 Teams/腾讯会议 链接解析 (HTML反转义 + 长链接支持)
import sqlite3
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta
import os
import uuid
import re 
import hashlib
import config
import html  # 🔥 核心引入：用于处理 URL 中的 &amp; 等转义符

# 尝试导入 icalendar
try:
    import icalendar
    HAS_ICAL = True
except ImportError:
    HAS_ICAL = False
    print("❌ 警告：未安装 icalendar 库")

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

# === 1. 标准 ICS 解析 ===
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

# === 2. 🔥 正文智能提取 (Fix: 增强链接清洗) ===
def extract_meeting_from_text(subject, raw_text):
    """
    raw_text: 原始邮件内容 (HTML/Text)
    """
    info = {
        "uid": "",
        "summary": subject, 
        "start_time": "",
        "end_time": "",
        "location": "",
        "description": "" 
    }

    # --- A. 提取链接 ---
    # 策略：匹配以 http 开头，直到遇到 空格、引号、尖括号 为止的字符串
    link_patterns = [
        # 1. Teams Launcher (复杂长链接, 含 ?, =, %, &)
        r'(https?://teams\.microsoft(?:online)?\.(?:com|cn)/dl/launcher/launcher\.html\?[^\s"\'<>]+)',
        # 2. Teams 常规
        r'(https?://teams\.microsoft(?:online)?\.(?:com|cn)/[^\s"\'<>]+)',
        # 3. 腾讯会议 (精准匹配 /dm/ 短链 和 普通链接)
        r'(https?://meeting\.tencent\.com/[^\s"\'<>]+)',
        r'(https?://voovmeeting\.com/[^\s"\'<>]+)',
        # 4. Zoom
        r'(https?://\w+\.zoom\.us/[^\s"\'<>]+)'
    ]
    
    for pat in link_patterns:
        match = re.search(pat, raw_text)
        if match:
            # 🔥 核心修复：HTML 反转义
            # 邮件里的链接可能是 "launcher.html?url=...&amp;type=..."
            # 必须转回 "&" 才能访问
            extracted_url = match.group(1)
            info["location"] = html.unescape(extracted_url)
            break

    # --- B. 提取时间 ---
    clean_text = re.sub(r'<[^>]+>', ' ', raw_text) 
    info["description"] = clean_text[:200].strip()

    date_part = r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}'
    time_part = r'\d{1,2}:\d{2}'
    
    strong_pattern = rf'(?:会议时间|Meeting Time)[：:]\s*({date_part}.*?{time_part})'
    weak_pattern = rf'(?<!发送)(?<!Sent\s)(?<!Date:\s)(?:时间|Time)[：:]\s*({date_part}.*?{time_part})'

    match = re.search(strong_pattern, clean_text, re.IGNORECASE)
    if not match:
        match = re.search(weak_pattern, clean_text, re.IGNORECASE)
        
    if match:
        raw_time = match.group(1).strip()
        try:
            nums = re.findall(r'\d+', raw_time)
            if len(nums) >= 5: 
                year, month, day, hour, minute = map(int, nums[:5])
                start_dt = datetime(year, month, day, hour, minute)
                info["start_time"] = start_dt.strftime("%Y-%m-%d %H:%M")
                info["end_time"] = (start_dt + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
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

def fetch_mail(init_mode=False):
    conn = sqlite3.connect('local_mail.db'); c = conn.cursor()
    new_count = 0
    
    try: 
        c.execute("SELECT count(*) FROM emails"); 
        if c.fetchone()[0] == 0: init_mode = True
    except: init_mode = True

    print(f"🔄 开始接收邮件 (最近 {FETCH_LIMIT} 封)...")

    for acc in config.ACCOUNTS:
        try:
            print(f"📡 连接 {acc['email']}...")
            mail = imaplib.IMAP4_SSL(acc['imap_server'], acc['imap_port'])
            mail.login(acc['email'], acc['password']); mail.select("INBOX")
            
            if init_mode:
                status, messages = mail.search(None, 'ALL')
                ids = messages[0].split()
                mail_ids = ids[-FETCH_LIMIT:] if len(ids) > FETCH_LIMIT else ids
            else:
                status, messages = mail.search(None, 'UNSEEN')
                mail_ids = messages[0].split()

            for num in reversed(mail_ids):
                try:
                    status, msg_data = mail.fetch(num, '(RFC822)')
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])
                            msg_id = msg.get("Message-ID", "").strip() or str(num)
                            
                            c.execute("SELECT id FROM emails WHERE message_id=?", (msg_id,))
                            if c.fetchone(): continue 

                            subj = decode_str(msg["Subject"])
                            sender = decode_str(msg["From"])
                            recip = decode_str(msg["To"])
                            cc = decode_str(msg["Cc"])
                            date = parse_date(msg["Date"])

                            body_t = ""; body_h = ""; atts = []; ics_data = None
                            
                            if msg.is_multipart():
                                for part in msg.walk():
                                    ctype = part.get_content_type()
                                    fname = part.get_filename()
                                    try: payload = part.get_payload(decode=True)
                                    except: continue
                                    if not payload: continue

                                    if ctype == "text/calendar" or (fname and fname.lower().endswith(".ics")):
                                        if not ics_data: ics_data = extract_ics_data(payload)

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

                            c.execute('''INSERT INTO emails (account_email, message_id, subject, sender, recipient, cc, date_received, body_html, body_text, attachments, folder)
                                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'inbox')''',
                                      (acc['email'], msg_id, subj, sender, recip, cc, date, body_h, body_t, ";".join(atts)))
                            new_count += 1
                            
                            if ics_data and ics_data['uid']:
                                c.execute("SELECT id FROM events WHERE uid=?", (ics_data['uid'],))
                                if not c.fetchone():
                                    c.execute("INSERT INTO events (uid, summary, start_time, end_time, location, description, sender, recipient, minutes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '')",
                                              (ics_data['uid'], ics_data['summary'], ics_data['start_time'], ics_data['end_time'], ics_data['location'], ics_data['description'], sender, recip))

                            conn.commit()
                except Exception as e: print(f"解析错误: {e}"); continue
            mail.logout()
        except Exception as e: print(f"连接错误: {e}")
    conn.close()
    return new_count

if __name__ == "__main__": fetch_mail(init_mode=True)