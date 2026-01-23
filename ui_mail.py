# ui_mail.py
# V12.60 - Fix: 增加全套邮件操作按钮 + 智能引用回复
import os
import smtplib
from datetime import datetime
from email.utils import formataddr, parsedate_to_datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

from PyQt6.QtWidgets import (QWidget, QFrame, QVBoxLayout, QHBoxLayout, 
                             QLabel, QSizePolicy, QDialog, QComboBox, QLineEdit, 
                             QPushButton, QMessageBox, QFileDialog, QScrollArea, QTextEdit)
from PyQt6.QtCore import Qt, pyqtSignal
import config
from ui_widgets import PersonChip, AttachmentChip

def format_email_date(s):
    if not s: return ""
    try:
        dt = datetime.fromisoformat(s) if '-' in s and ':' in s else parsedate_to_datetime(s)
        if dt.tzinfo: dt = dt.astimezone()
        return dt.strftime("%Y/%m/%d %H:%M")
    except: return str(s)[:16]

# === Header 布局 (阅读器头部) ===
class MailReaderHeader(QFrame):
    # 增加 action_type 定义: reply, reply_all, forward, delete
    action_trigger = pyqtSignal(str, dict) 

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ReaderHeader")
        self.current_mail_data = {} # 存储当前邮件的元数据，供回复使用
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(24, 20, 24, 15)
        self.layout.setSpacing(12)
        
        # 1. 标题
        self.lbl_subject = QLabel("选择一封邮件以阅读"); 
        self.lbl_subject.setObjectName("DetailSubject")
        self.lbl_subject.setWordWrap(True)
        self.layout.addWidget(self.lbl_subject)
        
        # 2. 发件人信息栏
        meta_row = QHBoxLayout(); meta_row.setSpacing(12)
        
        self.lbl_avatar = QLabel("M"); self.lbl_avatar.setObjectName("DetailAvatar")
        meta_row.addWidget(self.lbl_avatar)
        
        sender_col = QVBoxLayout(); sender_col.setSpacing(2)
        name_email_row = QHBoxLayout(); name_email_row.setSpacing(6)
        self.lbl_sender_name = QLabel(""); self.lbl_sender_name.setObjectName("DetailSenderName")
        self.lbl_sender_email = QLabel(""); self.lbl_sender_email.setObjectName("DetailSenderEmail")
        name_email_row.addWidget(self.lbl_sender_name); name_email_row.addWidget(self.lbl_sender_email); name_email_row.addStretch()
        
        self.lbl_time = QLabel(""); self.lbl_time.setObjectName("DetailTime")
        sender_col.addLayout(name_email_row); sender_col.addWidget(self.lbl_time)
        meta_row.addLayout(sender_col)
        
        meta_row.addStretch() 
        
        # 🔥🔥🔥 核心修复：完整的动作按钮组
        btn_reply = QPushButton("↩ 回复"); btn_reply.setObjectName("HeaderActionBtn")
        btn_reply.clicked.connect(lambda: self.emit_action("reply"))
        
        btn_reply_all = QPushButton("👥 全回"); btn_reply_all.setObjectName("HeaderActionBtn")
        btn_reply_all.clicked.connect(lambda: self.emit_action("reply_all"))
        
        btn_forward = QPushButton("↪ 转发"); btn_forward.setObjectName("HeaderActionBtn")
        btn_forward.clicked.connect(lambda: self.emit_action("forward"))
        
        btn_del = QPushButton("🗑 删除"); btn_del.setObjectName("HeaderActionBtn")
        btn_del.clicked.connect(lambda: self.emit_action("delete"))
        
        meta_row.addWidget(btn_reply)
        meta_row.addWidget(btn_reply_all)
        meta_row.addWidget(btn_forward)
        meta_row.addWidget(btn_del)
        
        self.layout.addLayout(meta_row)
        
        # 3. 收件人
        self.to_layout = QHBoxLayout(); self.to_layout.setSpacing(6)
        self.layout.addLayout(self.to_layout)
        
        # 4. 抄送
        self.cc_container = QWidget(); 
        self.cc_layout = QHBoxLayout(self.cc_container); self.cc_layout.setContentsMargins(0,0,0,0)
        self.layout.addWidget(self.cc_container)
        self.cc_container.hide()
        
        # 5. 分割线
        line = QFrame(); line.setFixedHeight(1); line.setStyleSheet("background: #EAEAEA; margin-top: 5px;")
        self.layout.addWidget(line)
        
        # 6. 附件
        self.att_area = QWidget(); 
        self.att_layout = QHBoxLayout(self.att_area); self.att_layout.setContentsMargins(0, 10, 0, 0); self.att_layout.setSpacing(10)
        self.att_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.layout.addWidget(self.att_area)
        self.att_area.hide()

    def emit_action(self, action_type):
        if not self.current_mail_data: return
        self.action_trigger.emit(action_type, self.current_mail_data)

    def update_data(self, subject, sender, recipient, cc, date_str, attachments, body_text, person_click_callback):
        # 保存当前邮件数据，供回复/转发使用
        self.current_mail_data = {
            "subject": subject,
            "sender": sender,
            "recipient": recipient,
            "cc": cc,
            "date": date_str,
            "body": body_text
        }
        
        self.lbl_subject.setText(subject if subject else "无主题")
        self.lbl_time.setText(format_email_date(date_str))
        
        sender_str = str(sender).strip()
        if '<' in sender_str:
            name = sender_str.split('<')[0].replace('"','').strip()
            email_addr = sender_str.split('<')[1].replace('>','').strip()
        else:
            name = sender_str; email_addr = ""
            
        self.lbl_sender_name.setText(name if name else "Unknown")
        self.lbl_sender_email.setText(f"<{email_addr}>" if email_addr else "")
        self.lbl_avatar.setText(name[0].upper() if name else "?")
        
        self._fill_people(self.to_layout, "发给:", recipient, person_click_callback)
        
        if cc and len(str(cc).strip()) > 2:
            self.cc_container.show()
            self._fill_people(self.cc_layout, "抄送:", cc, person_click_callback)
        else:
            self.cc_container.hide()
            
        self._fill_attachments(attachments)

    def _fill_people(self, layout, label_str, raw_str, callback):
        while layout.count(): 
            item = layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        lbl = QLabel(label_str); lbl.setStyleSheet("color:#999; font-size:12px; margin-right:5px;")
        layout.addWidget(lbl)
        
        if raw_str:
            people = raw_str.replace(';', ',').split(',')
            for p in people[:6]: 
                if p.strip():
                    chip = PersonChip(p.strip())
                    chip.click_signal.connect(callback)
                    layout.addWidget(chip)
            if len(people) > 6:
                layout.addWidget(QLabel(f"...等 {len(people)} 人"))
        layout.addStretch()

    def _fill_attachments(self, attachments):
        while self.att_layout.count():
            item = self.att_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        if attachments:
            att_list = attachments.split(';')
            valid_count = 0
            for a in att_list:
                if '|' in a:
                    p = a.split('|')
                    if len(p) >= 3:
                        # p[0]=name, p[1]=path, p[2]=size
                        self.att_layout.addWidget(AttachmentChip(p[0], p[1], p[2]))
                        valid_count += 1
            if valid_count > 0: self.att_area.show()
            else: self.att_area.hide()
        else:
            self.att_area.hide()

class MailListCard(QFrame):
    def __init__(self, subject, sender, date_str, preview, parent=None):
        super().__init__(parent); self.setObjectName("MailCard")
        l = QVBoxLayout(self); l.setContentsMargins(12, 10, 12, 10); l.setSpacing(3)
        top = QHBoxLayout()
        s_name = sender.split('<')[0].replace('"','').strip()
        ls = QLabel(s_name); ls.setObjectName("MailSender")
        top.addWidget(ls, 1)
        ld = QLabel(format_email_date(date_str).split(' ')[0]); ld.setObjectName("MailDate")
        top.addWidget(ld, 0)
        l.addLayout(top)
        lsub = QLabel(subject if subject else "(无主题)"); lsub.setObjectName("MailSubject")
        l.addWidget(lsub)
        lpre = QLabel(preview[:60].replace('\n',' ')); lpre.setObjectName("MailPreview")
        l.addWidget(lpre)

    def set_selected(self, selected):
        pass 

# 写信窗口 (增强版)
class ComposeWindow(QDialog):
    def __init__(self):
        super().__init__(); self.setWindowTitle("写邮件"); self.resize(800, 600)
        self.att = [] 
        
        l = QVBoxLayout(self); l.setContentsMargins(20,20,20,20); l.setSpacing(10)
        
        form = QFrame(); form_layout = QVBoxLayout(form); form_layout.setContentsMargins(0,0,0,0)
        
        h1 = QHBoxLayout(); h1.addWidget(QLabel("发件人:")); self.c_from = QComboBox(); h1.addWidget(self.c_from, 1)
        for a in config.ACCOUNTS: self.c_from.addItem(f"{a['name']} <{a['email']}>", a)
        form_layout.addLayout(h1)
        
        h2 = QHBoxLayout(); h2.addWidget(QLabel("收件人:")); self.i_to = QLineEdit(); h2.addWidget(self.i_to, 1)
        form_layout.addLayout(h2)
        
        h3 = QHBoxLayout(); h3.addWidget(QLabel("主   题:")); self.i_subject = QLineEdit(); h3.addWidget(self.i_subject, 1)
        form_layout.addLayout(h3)
        l.addWidget(form)
        
        tb = QHBoxLayout()
        btn_att = QPushButton("📎 添加附件"); btn_att.clicked.connect(self.add_att)
        self.lbl_att = QLabel(""); self.lbl_att.setStyleSheet("color:#666; margin-left:10px;")
        tb.addWidget(btn_att); tb.addWidget(self.lbl_att); tb.addStretch()
        l.addLayout(tb)
        
        self.txt = QTextEdit(); self.txt.setStyleSheet("border:1px solid #CCC; border-radius:4px; padding:8px; font-size:14px;")
        l.addWidget(self.txt)
        
        # 默认签名
        acc = self.c_from.currentData()
        self.signature = "\n\n" + acc.get('signature', '') if acc else ""
        self.txt.setPlainText(self.signature)
        
        bot = QHBoxLayout()
        btn_send = QPushButton("🚀 发送"); btn_send.setFixedSize(100, 36); 
        btn_send.setStyleSheet("background:#007AFF; color:white; font-weight:bold; border-radius:6px;")
        btn_send.clicked.connect(self.send)
        bot.addStretch(); bot.addWidget(btn_send)
        l.addLayout(bot)

    # 🔥🔥🔥 智能填充：支持回复、全回、转发模式
    def set_initial_data(self, mode="new", data=None):
        if mode == "new":
            if data and "to" in data: self.i_to.setText(data["to"])
            return

        if not data: return
        
        original_sender = data.get("sender", "")
        # 提取纯邮箱用于回复
        reply_to_addr = original_sender
        if '<' in original_sender:
            reply_to_addr = original_sender.split('<')[1].replace('>','').strip()

        quote_header = f"\n\n\n------------------ 原始邮件 ------------------\n" \
                       f"发件人: {data.get('sender')}\n" \
                       f"发送时间: {data.get('date')}\n" \
                       f"收件人: {data.get('recipient')}\n" \
                       f"主题: {data.get('subject')}\n\n" \
                       f"{data.get('body')}"

        if mode == "reply":
            self.i_to.setText(reply_to_addr)
            self.i_subject.setText("Re: " + data.get("subject", "").replace("Re: ", ""))
            self.txt.setPlainText(self.signature + quote_header)
            
        elif mode == "reply_all":
            # 简单的全回逻辑：发件人 + 原收件人 (需去重和排除自己)
            others = data.get("recipient", "")
            all_recipients = f"{reply_to_addr}, {others}".strip(', ')
            self.i_to.setText(all_recipients)
            self.i_subject.setText("Re: " + data.get("subject", "").replace("Re: ", ""))
            self.txt.setPlainText(self.signature + quote_header)
            
        elif mode == "forward":
            self.i_subject.setText("Fwd: " + data.get("subject", "").replace("Fwd: ", ""))
            self.txt.setPlainText(self.signature + quote_header)
            # 转发不自动填收件人
        
    def add_att(self):
        fs, _ = QFileDialog.getOpenFileNames(self); self.att.extend(fs); self.lbl_att.setText(f"已添加 {len(self.att)} 个附件")
        
    def send(self):
        try:
            acc = self.c_from.currentData(); m = MIMEMultipart()
            m['From'] = formataddr([acc['name'], acc['email']])
            m['To'] = self.i_to.text(); m['Subject'] = self.i_subject.text()
            m.attach(MIMEText(self.txt.toPlainText(), 'plain', 'utf-8'))
            for f in self.att: 
                with open(f, 'rb') as x: 
                    part = MIMEApplication(x.read())
                    part.add_header('Content-Disposition', 'attachment', filename=os.path.basename(f))
                    m.attach(part)
            s = smtplib.SMTP_SSL(acc['smtp_server'], acc['smtp_port'])
            s.login(acc['email'], acc['password'])
            s.sendmail(acc['email'], self.i_to.text().split(','), m.as_string()); s.quit()
            QMessageBox.information(self, "成功", "邮件已发送"); self.close()
        except Exception as e: QMessageBox.critical(self, "发送失败", str(e))