# ui_styles.py
# V24.0 - UI: 基础样式 (卡片样式移至组件内以确保生效)

STYLESHEET = """
* {
    font-family: ".AppleSystemUIFont", "SF Pro Text", "Helvetica Neue", sans-serif;
    outline: none;
    border: none;
}

QMainWindow { background-color: #FFFFFF; }

/* === Header === */
QFrame#UnifiedHeader { background-color: #FFFFFF; border-bottom: 1px solid #E5E5E5; }
QPushButton#SyncBtn { background-color: #007AFF; color: white; border-radius: 6px; padding: 6px 16px; font-size: 13px; font-weight: 600; }
QPushButton#SyncBtn:hover { background-color: #006ADB; }

/* === Calendar === */
QFrame#CalendarContainer { background-color: #FFFFFF; }
QPushButton#NavBtn { background-color: transparent; border-radius: 15px; font-weight: bold; color: #555; width: 30px; height: 30px; }
QPushButton#NavBtn:hover { background-color: #f2f2f7; color: #000; }
QPushButton#YearMonthBtn { background-color: #F2F4F8; border-radius: 8px; font-size: 16px; font-weight: bold; color: #333; padding: 6px 14px; }
QPushButton#YearMonthBtn:hover { background-color: #E6E8EC; }
QCalendarWidget QWidget { alternate-background-color: white; }
QCalendarWidget QAbstractItemView:enabled { background-color: white; selection-background-color: transparent; selection-color: #333; }

/* === 右侧背景 (深一点的灰，让白色卡片更明显) === */
QFrame#AgendaPanel { 
    background-color: #F2F3F5; 
    border-left: 1px solid #E0E0E0; 
}

/* === ScrollBar === */
QScrollBar:vertical { border: none; background: transparent; width: 6px; margin: 0px; }
QScrollBar::handle:vertical { background: #C1C1C1; min-height: 40px; border-radius: 3px; }
QScrollBar::handle:vertical:hover { background: #8E8E93; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

QSplitter::handle { background-color: #E0E0E0; width: 1px; }
"""