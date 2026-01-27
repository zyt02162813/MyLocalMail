# main.py
# V27.4 - UI: 彻底移除 QSplitter，强制右侧固定 380px，无拖拽
import sys
sys.stdout.reconfigure(encoding='utf-8')
import sqlite3
import os
import subprocess
import re
from datetime import datetime, timedelta

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --disable-software-rasterizer"

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                             QVBoxLayout, QLabel, QPushButton, QFrame, 
                             QScrollArea, QSizePolicy, QMessageBox) # 移除了 QSplitter
from PyQt6.QtCore import Qt, QTimer, QDate, QThread, pyqtSignal

import config 
import mail_fetcher 
from ui_styles import STYLESHEET
from ui_widgets import ToastOverlay, ProgressPill 
from ui_calendar import MeetingCalendarWidget, EventCard

def migrate_db():
    try:
        conn = sqlite3.connect('local_mail.db'); c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            uid TEXT UNIQUE, 
            summary TEXT, 
            start_time TEXT, 
            end_time TEXT, 
            location TEXT, 
            description TEXT, 
            sender TEXT, 
            recipient TEXT, 
            minutes TEXT, 
            ai_summary TEXT
        )''')
        try: c.execute("ALTER TABLE events ADD COLUMN ai_summary TEXT"); 
        except: pass
        c.execute('''CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            account_email TEXT,
            message_id TEXT, 
            subject TEXT, 
            sender TEXT, 
            recipient TEXT, 
            cc TEXT, 
            date_received TEXT, 
            body_html TEXT, 
            body_text TEXT, 
            attachments TEXT, 
            folder TEXT
        )''') 
        conn.commit(); conn.close()
    except Exception as e: print(f"DB Init Error: {e}")

class SyncWorker(QThread):
    progress_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal(int)
    def run(self):
        def callback(progress, msg): self.progress_signal.emit(progress, msg)
        try:
            count = mail_fetcher.fetch_mail(init_mode=True, callback=callback)
            self.finished_signal.emit(count)
        except Exception as e:
            print(f"Critical Sync Error: {e}")
            self.progress_signal.emit(100, f"同步失败: {str(e)}")
            self.finished_signal.emit(0)

class NotificationThread(QThread):
    def __init__(self): super().__init__(); self.notified_events = set()
    def run(self):
        while True: self.check_meetings(); self.sleep(60)
    def check_meetings(self):
        try:
            conn = sqlite3.connect('local_mail.db'); c = conn.cursor()
            now = datetime.now(); today_str = now.strftime("%Y-%m-%d")
            c.execute("SELECT uid, summary, start_time FROM events WHERE start_time LIKE ?", (f"{today_str}%",))
            rows = c.fetchall(); conn.close()
            for uid, title, start_str in rows:
                if uid in self.notified_events: continue
                try:
                    meeting_time = datetime.strptime(start_str[:16], "%Y-%m-%d %H:%M")
                    diff = (meeting_time - now).total_seconds() / 60
                    if 0 < diff <= 10:
                        self.send_mac_notification(title, f"会议将在 {int(diff)} 分钟后开始"); self.notified_events.add(uid)
                except: pass
        except: pass
    def send_mac_notification(self, title, message):
        try: subprocess.run(["osascript", "-e", f'display notification "{message}" with title "{title}" subtitle "MyCalendar 提醒" sound name "Glass"'])
        except: pass

class CalendarApp(QMainWindow):
    def __init__(self):
        super().__init__()
        if not mail_fetcher.HAS_ICAL:
            QMessageBox.critical(None, "缺少关键库", "检测到未安装 'icalendar' 库，无法解析会议邀请！\n\n请在终端运行：\npip install icalendar")
            sys.exit(1)

        self.setWindowTitle("MyCalendar - AI 智能助手")
        self.resize(1200, 800)
        self.setStyleSheet(STYLESHEET)
        central = QWidget(); self.main_layout = QVBoxLayout(central); self.main_layout.setContentsMargins(0,0,0,0); self.main_layout.setSpacing(0)
        self.setCentralWidget(central)
        
        self.setup_header()
        self.setup_content_area()
        self.progress_pill = ProgressPill(self)
        self.load_calendar_data()
        self.timer = QTimer(); self.timer.timeout.connect(self.run_background_sync); self.timer.start(300000) 
        self.notify_thread = NotificationThread(); self.notify_thread.start()

    def setup_header(self):
        header = QFrame(); header.setObjectName("UnifiedHeader"); header.setFixedHeight(64)
        h = QHBoxLayout(header); h.setContentsMargins(24,0,24,0); h.setSpacing(16)
        h.addWidget(QLabel("📅", styleSheet="font-size:20px")); h.addWidget(QLabel("我的会议日程", objectName="HeaderTitle"))
        h.addStretch()
        self.btn_sync = QPushButton("🔄 同步 (最新30封)", objectName="SyncBtn", cursor=Qt.CursorShape.PointingHandCursor)
        self.btn_sync.clicked.connect(self.manual_sync)
        h.addWidget(self.btn_sync)
        self.main_layout.addWidget(header)

    def setup_content_area(self):
        # 🔥🔥🔥 核心修改：使用普通 QHBoxLayout 替代 QSplitter
        content_container = QWidget()
        content_layout = QHBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # 1. 左侧日历 (伸缩)
        cal_con = QFrame(objectName="CalendarContainer")
        cl = QVBoxLayout(cal_con); cl.setContentsMargins(30,20,30,30)
        nav = QHBoxLayout()
        bp = QPushButton("◀", objectName="NavBtn"); bp.clicked.connect(lambda: self.calendar.showPreviousMonth())
        bn = QPushButton("▶", objectName="NavBtn"); bn.clicked.connect(lambda: self.calendar.showNextMonth())
        self.bym = QPushButton("2026年 1月", objectName="YearMonthBtn", flat=True)
        nav.addWidget(bp); nav.addStretch(); nav.addWidget(self.bym); nav.addStretch(); nav.addWidget(bn)
        self.calendar = MeetingCalendarWidget()
        self.calendar.currentPageChanged.connect(lambda y,m: self.bym.setText(f"{y}年 {m}月"))
        self.calendar.selectionChanged.connect(self.show_events_for_date)
        cl.addLayout(nav); cl.addWidget(self.calendar)
        
        content_layout.addWidget(cal_con, 1) # 1 = 占用剩余所有空间

        # 2. 右侧日程栏 (🔥 固定宽度 380px，不使用 Splitter)
        right_panel = QFrame(objectName="AgendaPanel")
        right_panel.setFixedWidth(380) # 锁死宽度
        right_panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding) # 禁止横向缩放
        
        rl = QVBoxLayout(right_panel); rl.setContentsMargins(0,0,0,0)
        self.scroll_area = QScrollArea(widgetResizable=True, styleSheet="border:none; background:transparent;")
        self.scroll_contents = QWidget(); self.scroll_contents.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.scroll_layout = QVBoxLayout(self.scroll_contents); 
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop); self.scroll_layout.setContentsMargins(20, 20, 20, 20)
        self.scroll_layout.setSpacing(16) 
        self.scroll_area.setWidget(self.scroll_contents)
        self.event_label = QLabel("今日日程", styleSheet="font-size:18px; font-weight:bold; margin-left:20px; margin-top:20px; margin-bottom:10px;")
        rl.addWidget(self.event_label)
        rl.addWidget(self.scroll_area)

        content_layout.addWidget(right_panel)
        
        self.main_layout.addWidget(content_container, 1)

    def load_calendar_data(self):
        conn = sqlite3.connect('local_mail.db'); c = conn.cursor()
        try:
            c.execute("SELECT start_time, summary FROM events"); rows = c.fetchall(); conn.close(); data = {}
            for row in rows:
                s = row[0].split(" ")[0].replace("/", "-")
                try: d = QDate.fromString(s, "yyyy-MM-dd"); data.setdefault(d, []).append(row[1])
                except: pass
            self.calendar.set_meeting_data(data)
            if self.calendar.selectedDate() == QDate.currentDate(): self.calendar.setSelectedDate(QDate.currentDate())
            self.show_events_for_date()
        except: pass

    def show_events_for_date(self):
        d = self.calendar.selectedDate(); self.event_label.setText(f"{d.toString('M月d日 dddd')} 的安排")
        while self.scroll_layout.count(): 
            item = self.scroll_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        conn = sqlite3.connect('local_mail.db'); c = conn.cursor()
        k1 = d.toString("yyyy-MM-dd"); k2 = d.toString("yyyy/MM/dd")
        try:
            c.execute("""SELECT uid, start_time, end_time, summary, location, description, minutes, sender, recipient, ai_summary 
                        FROM events WHERE start_time LIKE ? OR start_time LIKE ? ORDER BY start_time""", (f"{k1}%", f"{k2}%"))
            rows = c.fetchall()
        except: rows = []
        conn.close()
        if not rows: self.scroll_layout.addWidget(QLabel("☕️ 无会议安排", alignment=Qt.AlignmentFlag.AlignCenter, styleSheet="color:#999; font-size:16px; margin-top:50px;"))
        else:
            for row in rows: self.scroll_layout.addWidget(EventCard(*row))

    def run_background_sync(self):
        if mail_fetcher.fetch_mail(init_mode=False) > 0: self.show_toast("📅 发现新会议")
        self.load_calendar_data()
    
    def manual_sync(self):
        self.btn_sync.setEnabled(False) 
        self.progress_pill.show_progress() 
        self.sync_worker = SyncWorker()
        self.sync_worker.progress_signal.connect(self.progress_pill.update_status)
        self.sync_worker.finished_signal.connect(self.on_sync_finished)
        self.sync_worker.start()

    def on_sync_finished(self, new_count):
        self.progress_pill.finish(success=True, msg=f"成功更新 {new_count} 个项目" if new_count > 0 else "已经是最新")
        self.btn_sync.setEnabled(True)
        self.load_calendar_data()

    def show_toast(self, text): self.current_toast = ToastOverlay(self, text)

    def resizeEvent(self, event):
        if self.progress_pill.isVisible():
            r = self.rect()
            self.progress_pill.move((r.width()-320)//2, r.height()-120)
        super().resizeEvent(event)

if __name__ == "__main__":
    migrate_db()
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    font = app.font(); font.setFamily(".AppleSystemUIFont"); app.setFont(font)
    window = CalendarApp(); window.show(); sys.exit(app.exec())