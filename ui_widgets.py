# ui_widgets.py
# V26.0 - New: 优雅的进度胶囊 & Toast
from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QFrame, QProgressBar, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen

# === 1. 简单的 Toast (保留) ===
class ToastOverlay(QWidget):
    def __init__(self, parent, text):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.SubWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        layout = QHBoxLayout(self)
        self.lbl = QLabel(text)
        self.lbl.setStyleSheet("background-color: rgba(0, 0, 0, 0.75); color: white; padding: 10px 20px; border-radius: 20px; font-weight: 500; font-size: 13px;")
        layout.addWidget(self.lbl)
        
        self.adjustSize()
        # 居中偏下
        p_geo = parent.geometry()
        self.move(p_geo.width()//2 - self.width()//2, p_geo.height() - 100)
        
        self.show()
        QTimer.singleShot(2500, self.close)

# === 2. 优雅的进度胶囊 (New) ===
class ProgressPill(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.SubWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 容器 Frame
        self.container = QFrame(self)
        self.container.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E5E5E5;
                border-radius: 24px;
            }
        """)
        # 阴影
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20); shadow.setOffset(0, 8); shadow.setColor(QColor(0,0,0,30))
        self.container.setGraphicsEffect(shadow)
        
        # 布局
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(20, 12, 20, 16); layout.setSpacing(8)
        
        # 上层：图标 + 文字
        top_layout = QHBoxLayout()
        self.icon_lbl = QLabel("🔄")
        self.icon_lbl.setStyleSheet("font-size: 14px; border:none; background:transparent;")
        
        self.text_lbl = QLabel("准备同步...")
        self.text_lbl.setStyleSheet("color: #333; font-weight: 600; font-size: 13px; border:none; background:transparent;")
        
        top_layout.addWidget(self.icon_lbl)
        top_layout.addWidget(self.text_lbl)
        top_layout.addStretch()
        
        layout.addLayout(top_layout)
        
        # 下层：细进度条
        self.bar = QProgressBar()
        self.bar.setFixedHeight(4)
        self.bar.setTextVisible(False)
        self.bar.setStyleSheet("""
            QProgressBar { border: none; background-color: #F0F0F0; border-radius: 2px; }
            QProgressBar::chunk { background-color: #007AFF; border-radius: 2px; }
        """)
        layout.addWidget(self.bar)
        
        # 调整大小
        self.container.setFixedSize(300, 70)
        self.setFixedSize(320, 90) # 给阴影留空间
        
        # 动画容器
        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        
        self.hide() # 默认隐藏

    def show_progress(self):
        # 定位到父窗口底部居中
        p_rect = self.parent().rect()
        x = (p_rect.width() - self.width()) // 2
        y = p_rect.height() - 120 # 距离底部 120px
        self.move(x, y)
        
        self.setWindowOpacity(0)
        self.show()
        self.raise_()
        
        # 淡入
        self.opacity_anim.setDuration(300)
        self.opacity_anim.setStartValue(0)
        self.opacity_anim.setEndValue(1)
        self.opacity_anim.start()

    def update_status(self, value, text):
        self.bar.setValue(value)
        self.text_lbl.setText(text)
        
        # 简单的旋转动画模拟 (通过切换 emoji)
        if value < 100:
            current = self.icon_lbl.text()
            self.icon_lbl.setText("⏳" if current == "🔄" else "🔄")
        else:
            self.icon_lbl.setText("✅")

    def finish(self, success=True, msg="完成"):
        self.bar.setValue(100)
        self.text_lbl.setText(msg)
        self.icon_lbl.setText("✅" if success else "❌")
        
        # 2秒后淡出
        QTimer.singleShot(2000, self.fade_out)

    def fade_out(self):
        self.opacity_anim.setDuration(300)
        self.opacity_anim.setStartValue(1)
        self.opacity_anim.setEndValue(0)
        self.opacity_anim.finished.connect(self.hide)
        self.opacity_anim.start()