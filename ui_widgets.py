# ui_widgets.py
# V12.65 - Fix: 附件交互修复 (双击打开 + 右键另存为)
import os
import shutil
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame, 
                             QPushButton, QMenu, QGraphicsDropShadowEffect, 
                             QGraphicsOpacityEffect, QFileDialog, QMessageBox, QCheckBox)
from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QUrl, QPoint, QPropertyAnimation, QEasingCurve, QSize
from PyQt6.QtGui import QColor, QAction, QDesktopServices, QCursor, QIcon

# 1. 联系人胶囊 (Pill Shape)
class PersonChip(QFrame):
    click_signal = pyqtSignal(str, str, QPoint)
    def __init__(self, raw_str, parent=None):
        super().__init__(parent)
        self.setObjectName("PersonChipFrame")
        
        # 容错解析
        raw_str = str(raw_str).strip()
        if '<' in raw_str:
            parts = raw_str.split('<')
            self.name = parts[0].replace('"', '').strip()
            self.email = parts[1].replace('>', '').strip()
        else:
            self.name = raw_str
            self.email = raw_str
            
        if not self.name: self.name = self.email.split('@')[0]
        
        layout = QHBoxLayout(self); layout.setContentsMargins(10, 4, 10, 4); layout.setSpacing(6)
        
        lbl = QLabel(self.name); lbl.setObjectName("ChipName")
        layout.addWidget(lbl)
        
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: 
            self.click_signal.emit(self.name, self.email, e.globalPosition().toPoint())

# 2. 附件卡片 (带左侧色条 + 右键菜单)
class AttachmentChip(QFrame):
    def __init__(self, filename, filepath, size_str, parent=None):
        super().__init__(parent)
        self.setObjectName("AttachmentChip")
        self.filepath = os.path.abspath(filepath)
        self.filename = filename
        
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedWidth(200)
        self.setFixedHeight(50) 
        
        # 悬停事件
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.installEventFilter(self)

        ext = os.path.splitext(filename)[1].lower()
        
        # 颜色定义
        color_map = {
            'xls': '#1D6F42', 'xlsx': '#1D6F42', 'csv': '#1D6F42',
            'doc': '#2B579A', 'docx': '#2B579A',
            'pdf': '#E82020', 'ppt': '#D24726', 'pptx': '#D24726',
            'zip': '#F1C40F', 'jpg': '#8E44AD', 'png': '#8E44AD'
        }
        bar_color = color_map.get(ext[1:], '#95A5A6')

        # 布局
        main_layout = QHBoxLayout(self); main_layout.setContentsMargins(0, 0, 0, 0); main_layout.setSpacing(0)
        
        # 左侧色条
        color_bar = QLabel()
        color_bar.setFixedWidth(5)
        color_bar.setStyleSheet(f"background-color: {bar_color}; border-top-left-radius: 6px; border-bottom-left-radius: 6px;")
        main_layout.addWidget(color_bar)
        
        # 内容
        content_l = QVBoxLayout(); content_l.setContentsMargins(10, 8, 10, 8); content_l.setSpacing(2)
        
        name_lbl = QLabel(filename); name_lbl.setObjectName("AttName")
        # 超长截断
        metric = name_lbl.fontMetrics()
        elided_name = metric.elidedText(filename, Qt.TextElideMode.ElideMiddle, 160)
        name_lbl.setText(elided_name)
        
        size_lbl = QLabel(size_str if size_str != "0" else "未知大小"); size_lbl.setObjectName("AttSize")
        
        content_l.addWidget(name_lbl)
        content_l.addWidget(size_lbl)
        main_layout.addLayout(content_l)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.HoverEnter:
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(15); shadow.setColor(QColor(0,0,0,20)); shadow.setOffset(0, 3)
            self.setGraphicsEffect(shadow)
        elif event.type() == QEvent.Type.HoverLeave:
            self.setGraphicsEffect(None)
        return super().eventFilter(obj, event)

    # 🔥 左键双击：直接打开
    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.open_file()

    # 🔥 右键点击：弹出菜单
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.RightButton:
            self.show_context_menu(e.globalPosition().toPoint())
        else:
            super().mousePressEvent(e)

    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #FFFFFF; border: 1px solid #E5E5E5; border-radius: 6px; padding: 4px; }
            QMenu::item { padding: 6px 20px; border-radius: 4px; color: #333; font-size: 13px; }
            QMenu::item:selected { background-color: #007AFF; color: white; }
        """)
        
        action_open = QAction("📄 打开文件", self)
        action_open.triggered.connect(self.open_file)
        
        action_save = QAction("📥 另存为...", self)
        action_save.triggered.connect(self.save_as)
        
        menu.addAction(action_open)
        menu.addSeparator()
        menu.addAction(action_save)
        
        menu.exec(pos)

    def open_file(self):
        if os.path.exists(self.filepath):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.filepath))
        else:
            QMessageBox.warning(self, "文件不存在", 
                                f"无法找到文件：\n{self.filename}\n\n可能是旧数据或文件已被手动删除。\n路径: {self.filepath}")

    def save_as(self):
        if not os.path.exists(self.filepath):
            QMessageBox.warning(self, "错误", "源文件丢失，无法另存。")
            return
            
        # 弹出保存对话框
        dest_path, _ = QFileDialog.getSaveFileName(self, "另存附件", self.filename)
        if dest_path:
            try:
                shutil.copy2(self.filepath, dest_path)
                QMessageBox.information(self, "成功", f"文件已保存到：\n{dest_path}")
            except Exception as e:
                QMessageBox.critical(self, "保存失败", str(e))

# 3. 联系人弹窗
class PersonPopup(QWidget):
    action_signal = pyqtSignal(str, str)
    def __init__(self, name, email, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.email = email
        
        container = QFrame(self); container.setObjectName("PersonCard")
        shadow = QGraphicsDropShadowEffect(self); shadow.setBlurRadius(20); shadow.setColor(QColor(0,0,0,40)); shadow.setOffset(0,4)
        container.setGraphicsEffect(shadow)
        container.setStyleSheet("background-color: white; border-radius: 12px; border: 1px solid #E5E5E5;")
        
        ml = QVBoxLayout(self); ml.setContentsMargins(10,10,10,10); ml.addWidget(container)
        l = QVBoxLayout(container); l.setContentsMargins(20,20,20,20); l.setSpacing(15)
        
        h = QHBoxLayout(); h.setSpacing(15)
        av = QLabel(name[0].upper() if name else "?")
        av.setStyleSheet("background-color:#EBF5FF;color:#007AFF;border-radius:20px;font-size:18px;font-weight:bold;min-width:40px;min-height:40px;qproperty-alignment:AlignCenter;")
        
        info_l = QVBoxLayout(); info_l.setSpacing(2)
        n = QLabel(name); n.setStyleSheet("font-size:16px; font-weight:bold; color:#333; border:none;")
        e = QLabel(email); e.setStyleSheet("font-size:13px; color:#888; border:none;")
        info_l.addWidget(n); info_l.addWidget(e)
        
        h.addWidget(av); h.addLayout(info_l); l.addLayout(h)
        
        line = QFrame(); line.setFixedHeight(1); line.setStyleSheet("background:#F0F0F0;"); l.addWidget(line)
        
        btn_layout = QHBoxLayout(); btn_layout.setSpacing(10)
        
        b1 = QPushButton("✉️ 发送邮件"); 
        b1.setStyleSheet("background-color:#F2F2F7; border:none; border-radius:6px; color:#333; padding:8px 12px;")
        b1.clicked.connect(lambda: self.emit_action("compose"))
        
        b2 = QPushButton("🔍 查看往来"); 
        b2.setStyleSheet("background-color:#F2F2F7; border:none; border-radius:6px; color:#333; padding:8px 12px;")
        b2.clicked.connect(lambda: self.emit_action("history"))
        
        btn_layout.addWidget(b1); btn_layout.addWidget(b2); l.addLayout(btn_layout)
        
    def emit_action(self, t): self.action_signal.emit(t, self.email); self.close()

# 4. 搜索筛选弹窗
class SearchFilterPopup(QWidget):
    filterChanged = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.c = QFrame(self); self.c.setObjectName("FilterPopupFrame")
        sh = QGraphicsDropShadowEffect(self); sh.setBlurRadius(20); sh.setColor(QColor(0,0,0,30)); sh.setOffset(0,4)
        self.c.setGraphicsEffect(sh)
        self.c.setStyleSheet("background-color: #FFFFFF; border: 1px solid #E0E0E0; border-radius: 8px;")
        
        l = QVBoxLayout(self); l.setContentsMargins(10,10,10,10); l.addWidget(self.c)
        i = QVBoxLayout(self.c); i.setContentsMargins(15,15,15,15); i.setSpacing(8)
        
        lbl = QLabel("搜索范围"); lbl.setStyleSheet("color:#888;font-size:11px;font-weight:600;margin-bottom:4px; border:none;")
        i.addWidget(lbl)
        
        self.cb1 = QCheckBox("标题"); self.cb1.setChecked(True); self.cb1.stateChanged.connect(self.filterChanged.emit)
        self.cb2 = QCheckBox("正文"); self.cb2.setChecked(True); self.cb2.stateChanged.connect(self.filterChanged.emit)
        self.cb3 = QCheckBox("发件人"); self.cb3.setChecked(True); self.cb3.stateChanged.connect(self.filterChanged.emit)
        
        i.addWidget(self.cb1); i.addWidget(self.cb2); i.addWidget(self.cb3)

# 5. 气泡提示
class ToastOverlay(QLabel):
    def __init__(self, parent, text):
        super().__init__(parent)
        self.setText(text)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color:rgba(30,30,30,0.9);color:white;border-radius:6px;padding:8px 16px;font-size:13px;font-weight:500;")
        self.adjustSize()
        
        if parent:
            p = parent.rect()
            self.move(int(p.width()/2 - self.width()/2), int(p.height() - 80))
        
        self.raise_()
        self.show()
        
        self.op = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.op)
        self.an = QPropertyAnimation(self.op, b"opacity")
        self.an.setDuration(2500)
        self.an.setStartValue(1.0)
        self.an.setEndValue(0.0)
        self.an.setEasingCurve(QEasingCurve.Type.InExpo)
        self.an.finished.connect(self.deleteLater)
        self.an.start()