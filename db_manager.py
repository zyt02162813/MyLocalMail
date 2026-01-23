import sqlite3
import os

DB_NAME = 'local_mail.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. 邮件表 (增加 uid 字段，用于增量同步)
    c.execute('''CREATE TABLE IF NOT EXISTS emails
                 (id INTEGER PRIMARY KEY, 
                  account_email TEXT,
                  uid INTEGER,
                  message_id TEXT, 
                  subject TEXT, 
                  sender TEXT, 
                  recipient TEXT, 
                  date_received DATETIME, 
                  body_html TEXT, 
                  body_text TEXT, 
                  attachments TEXT,
                  folder TEXT DEFAULT 'INBOX',
                  is_read BOOLEAN DEFAULT 0,
                  UNIQUE(account_email, uid))''')

    # 2. 附件表 (用于记录附件存放路径)
    c.execute('''CREATE TABLE IF NOT EXISTS attachments
                 (id INTEGER PRIMARY KEY,
                  email_id INTEGER,
                  filename TEXT,
                  file_path TEXT,
                  file_size INTEGER)''')

    # 3. 草稿表
    c.execute('''CREATE TABLE IF NOT EXISTS drafts
                 (id INTEGER PRIMARY KEY, 
                  account_email TEXT,
                  recipient TEXT, 
                  cc TEXT,
                  subject TEXT, 
                  body_html TEXT, 
                  attachments TEXT,
                  last_saved TEXT)''')
                  
    # 4. 会议表
    c.execute('''CREATE TABLE IF NOT EXISTS events
                 (id INTEGER PRIMARY KEY, 
                  uid TEXT UNIQUE, 
                  summary TEXT, 
                  start_time TEXT, 
                  end_time TEXT, 
                  location TEXT, 
                  description TEXT)''')
    
    conn.commit()
    conn.close()
    
    # 创建附件存储目录
    if not os.path.exists("downloaded_attachments"):
        os.mkdir("downloaded_attachments")

if __name__ == "__main__":
    init_db()
    print("✅ V1.1 数据库结构升级完成！")