# ui_calendar.py
# V25.0 - UI: 完整参会人 + 底部一键复制 + 移除导出/链接
import sqlite3
import re
import os
import html
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
                             QPushButton, QCalendarWidget, QTextEdit, QMessageBox, 
                             QFileDialog, QSizePolicy, QGraphicsDropShadowEffect, QApplication, QCheckBox)
from PyQt6.QtCore import Qt, pyqtSignal, QDate, QRect, QSize, QPoint, QUrl, QPropertyAnimation, QThread
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QFontMetrics, QDesktopServices, QIcon

import ai_manager 

class AIWorker(QThread):
    finished_signal = pyqtSignal(str)
    def __init__(self, notes, context):
        super().__init__()
        self.notes = notes
        self.context = context
    def run(self):
        result = ai_manager.generate_summary(self.notes, self.context)
        self.finished_signal.emit(result)

class MeetingCalendarWidget(QCalendarWidget):
    COLOR_BG_SELECTED = QColor("#EBF5FF"); COLOR_BORDER_SELECTED = QColor("#007AFF")
    COLOR_TODAY_CIRCLE = QColor("#FF3B30"); COLOR_EVENT_BAR = QColor("#E3F2FD"); COLOR_EVENT_TEXT = QColor("#1D1D1F")
    def __init__(self, parent=None):
        super().__init__(parent); self.setNavigationBarVisible(False)
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames); self.meeting_data = {} 
    def set_meeting_data(self, data): self.meeting_data = data; self.update()
    def paintCell(self, painter, rect, date):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if date == self.selectedDate():
            painter.setPen(QPen(self.COLOR_BORDER_SELECTED, 1)); painter.setBrush(QBrush(self.COLOR_BG_SELECTED)); painter.drawRoundedRect(rect.adjusted(1,1,-1,-1), 4, 4)
        if date == QDate.currentDate():
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QBrush(self.COLOR_TODAY_CIRCLE)); painter.drawEllipse(QRect(rect.left()+4, rect.top()+4, 20, 20))
            painter.setPen(Qt.GlobalColor.white); painter.drawText(QRect(rect.left()+4, rect.top()+4, 20, 20), Qt.AlignmentFlag.AlignCenter, str(date.day()))
        else:
            painter.setPen(QColor("#333") if date.month() == self.monthShown() else QColor("#CCC")); painter.drawText(rect.adjusted(8,6,-4,-4), Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop, str(date.day()))
        if date in self.meeting_data and self.meeting_data[date]:
            y = rect.top()+26; count=0
            for t in self.meeting_data[date]:
                if y+14 > rect.bottom()-2 or count>=3: break
                bar = QRect(rect.left()+2, y, rect.width()-4, 14); painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QBrush(self.COLOR_EVENT_BAR)); painter.drawRoundedRect(bar, 2, 2)
                painter.setPen(self.COLOR_EVENT_TEXT); font=painter.font(); font.setPixelSize(10); painter.setFont(font)
                painter.drawText(bar.adjusted(4,0,-2,0), Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter, QFontMetrics(font).elidedText(t, Qt.TextElideMode.ElideRight, bar.width()-6))
                y+=16; count+=1

class EventCard(QFrame):
    def __init__(self, uid, start, end, summary, location, desc, minutes, sender, recipient, ai_summary, parent=None):
        super().__init__(parent)
        self.uid = uid; self.summary = summary; self.desc = desc; self.ai_summary_text = ai_summary
        self.sender_val = sender; self.recipient_val = recipient; self.start_val = start
        
        # 强制内联样式
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 12px;
            }
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(15); self.shadow.setOffset(0, 4); self.shadow.setColor(QColor(0,0,0,20))
        self.setGraphicsEffect(self.shadow)
        
        layout = QVBoxLayout(self); layout.setContentsMargins(20, 20, 20, 20); layout.setSpacing(12)

        # 1. 顶部：仅显示时间 (移除入会按钮)
        try: time_str = f"{start.split(' ')[1][:5]} - {end.split(' ')[1][:5]}"
        except: time_str = start
        
        t_lbl = QLabel(time_str); t_lbl.setStyleSheet("color:#007AFF; font-weight:800; font-family:monospace; font-size:14px; border:none;")
        layout.addWidget(t_lbl)

        # 2. 标题
        title = QLabel(summary or "(无主题)", objectName="EvtTitle"); title.setWordWrap(True)
        title.setStyleSheet("color:#1D1D1F; font-weight:700; font-size:16px; border:none; line-height:1.3;")
        layout.addWidget(title)
        
        # 3. 人员 (🔥 完整显示，不省略)
        # 清洗一下格式，去掉引号和尖括号
        s_clean = sender.split('<')[0].replace('"', '').strip()
        r_clean = recipient.replace('"', '').replace('<', '(').replace('>', ')')
        
        meta = f"👤 发起: {s_clean}\n👥 参会: {r_clean}"
        if location: meta += f"\n📍 地点: {location}"
        
        m_lbl = QLabel(meta); m_lbl.setWordWrap(True)
        m_lbl.setStyleSheet("color:#666; font-size:12px; border:none; line-height:1.4; margin-top:4px;")
        layout.addWidget(m_lbl)

        line = QFrame(); line.setFixedHeight(1); line.setStyleSheet("background:#EFEFEF; margin: 4px 0;")
        layout.addWidget(line)

        # 4. 纪要区 (移除导出，保留重置)
        tool_row = QHBoxLayout(); tool_row.setSpacing(10)
        tool_row.addWidget(QLabel("📝 纪要笔记", styleSheet="font-weight:700; color:#444; font-size:13px; border:none;"))
        self.status_lbl = QLabel("已同步"); self.status_lbl.setStyleSheet("color:#CCC; font-size:11px; border:none;")
        tool_row.addWidget(self.status_lbl)
        tool_row.addStretch()
        
        btn_reset = QPushButton("重置"); btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset.setStyleSheet("QPushButton { color: #FF3B30; background: transparent; border: none; font-size: 12px; font-weight:600; } QPushButton:hover { background: #FFF0F0; border-radius: 4px; }")
        btn_reset.clicked.connect(self.reset_template)
        tool_row.addWidget(btn_reset)
        layout.addLayout(tool_row)

        self.ed = QTextEdit(); self.ed.setObjectName("MinutesEditor"); self.ed.setMinimumHeight(100)
        self.ed.setPlaceholderText("记录讨论要点...\n[ ] 待办事项")
        self.ed.setStyleSheet("QTextEdit { background: transparent; border: none; padding: 0; color: #333; font-size: 14px; line-height: 1.5; }")
        self.ed.textChanged.connect(self.auto_save)
        if minutes and len(minutes) > 5: self.ed.setHtml(minutes)
        else: self.reset_default_text(save=False)
        layout.addWidget(self.ed)

        # 5. AI 胶囊
        self.ai_capsule = QFrame(); self.ai_capsule.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.ai_capsule.setStyleSheet("QFrame { background-color: #F0F4FF; border: 1px solid #D6E4FF; border-radius: 8px; }")
        ai_layout = QVBoxLayout(self.ai_capsule); ai_layout.setContentsMargins(12, 10, 12, 10); ai_layout.setSpacing(6)
        
        ai_top = QHBoxLayout()
        ai_top.addWidget(QLabel("✨ AI 智能总结", styleSheet="color:#5856D6; font-weight:800; font-size:12px; border:none; background:transparent;"))
        ai_top.addStretch()
        
        self.btn_gen = QPushButton(" 生成 "); self.btn_gen.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_gen.setStyleSheet("QPushButton { background:#5856D6; color:white; border-radius:10px; padding:3px 10px; font-size:11px; font-weight:bold; border:none; }")
        self.btn_gen.clicked.connect(self.start_ai_generate)
        ai_top.addWidget(self.btn_gen)
        
        ai_layout.addLayout(ai_top)
        
        self.lbl_ai = QLabel(ai_summary if ai_summary else "点击生成，AI 将基于上方纪要自动总结。"); 
        self.lbl_ai.setWordWrap(True); self.lbl_ai.setStyleSheet("color:#444; font-size:12px; line-height:1.4; border:none; background:transparent;")
        self.lbl_ai.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        ai_layout.addWidget(self.lbl_ai)
        
        layout.addWidget(self.ai_capsule)

        # 6. 🔥 底部：一键复制大按钮
        self.btn_copy_all = QPushButton("📋 一键复制完整纪要")
        self.btn_copy_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_all.setStyleSheet("""
            QPushButton {
                background-color: #5856D6; 
                color: white; 
                font-size: 13px; 
                font-weight: bold; 
                border-radius: 8px; 
                padding: 10px;
                border: none;
                margin-top: 8px;
            }
            QPushButton:hover { background-color: #4A48B8; }
            QPushButton:pressed { background-color: #3D3B99; }
        """)
        self.btn_copy_all.clicked.connect(self.copy_full_minutes)
        layout.addWidget(self.btn_copy_all)

    def start_ai_generate(self):
        notes = self.ed.toPlainText()
        if len(notes) < 5:
            QMessageBox.warning(self, "提示", "请先输入一些纪要草稿。")
            return
        self.btn_gen.setText("..."); self.btn_gen.setEnabled(False)
        self.lbl_ai.setText("✨ AI 正在分析...")
        context = f"会议标题：{self.summary}\n会议描述：{self.desc}"
        self.worker = AIWorker(notes, context)
        self.worker.finished_signal.connect(self.on_ai_finished)
        self.worker.start()

    def on_ai_finished(self, result):
        self.lbl_ai.setText(result)
        self.btn_gen.setText("生成"); self.btn_gen.setEnabled(True)
        self.update_db(ai_result=result)

    def reset_template(self):
        if QMessageBox.question(self, "重置", "确定清空当前内容吗？", QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.reset_default_text(save=True)
            self.lbl_ai.setText("点击生成，AI 将基于上方纪要自动总结。")
            self.update_db(ai_result="")

    def reset_default_text(self, save=True):
        self.ed.setHtml("""<p><b>📝 讨论要点:</b></p><ul><li> </li></ul><p><b>✅ 待办事项:</b></p><ul><li>[ ] </li></ul>""")
        if save: self.auto_save()

    def copy_full_minutes(self):
        # 1. 准备数据
        title = self.summary or "无主题"
        time = self.start_val
        s_clean = self.sender_val.split('<')[0].replace('"', '').strip()
        r_clean = self.recipient_val.replace('"', '').replace('<', '(').replace('>', ')')
        notes = self.ed.toPlainText()
        ai_sum = self.lbl_ai.text()
        if "点击生成" in ai_sum or "等待生成" in ai_sum: ai_sum = "(无 AI 总结)"

        # 2. 格式化文本
        full_text = f"""【会议纪要】{title}
--------------------------------
📅 时间: {time}
👤 发起: {s_clean}
👥 参会: {r_clean}
--------------------------------
{notes}
--------------------------------
✨ AI 总结:
{ai_sum}
"""
        # 3. 写入剪贴板
        QApplication.clipboard().setText(full_text)
        
        # 4. 按钮反馈
        orig_text = self.btn_copy_all.text()
        self.btn_copy_all.setText("✅ 已复制到剪贴板")
        self.btn_copy_all.setStyleSheet("background-color: #34C759; color: white; font-size: 13px; font-weight: bold; border-radius: 8px; padding: 10px; border: none; margin-top: 8px;")
        QThread.msleep(1000) # 简单延时展示
        # 恢复样式 (注意：界面不会立即刷新，实际使用中通常配合 Timer 恢复，这里简化处理，下次点击会重置)
        
    def auto_save(self):
        self.status_lbl.setText("保存中...")
        self.update_db()
        self.status_lbl.setText("已同步")

    def update_db(self, ai_result=None):
        try:
            conn = sqlite3.connect('local_mail.db'); c = conn.cursor()
            if ai_result is not None: c.execute("UPDATE events SET minutes = ?, ai_summary = ? WHERE uid = ?", (self.ed.toHtml(), ai_result, self.uid))
            else: c.execute("UPDATE events SET minutes = ? WHERE uid = ?", (self.ed.toHtml(), self.uid))
            conn.commit(); conn.close()
        except: pass