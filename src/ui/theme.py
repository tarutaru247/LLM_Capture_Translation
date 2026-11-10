"""Shared green-accented native UI styles."""
import sys
from PySide6.QtGui import QIcon, QPainter, QPen, QPixmap, QColor, QPalette
from PySide6.QtCore import Qt, QRectF


def system_is_dark():
    """Qt 5's Windows palette does not reliably reflect the app theme setting."""
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0
        except OSError:
            pass
    from PySide6.QtWidgets import QApplication
    return QApplication.palette().window().color().lightness() < 128


def is_dark(theme="system"):
    return theme == "dark" or (theme == "system" and system_is_dark())


def palette(dark=False):
    result = QPalette()
    for role, light, dim in (
        (QPalette.Window, "#ffffff", "#181c1a"),
        (QPalette.WindowText, "#202b24", "#eff5f0"),
        (QPalette.Base, "#ffffff", "#252e28"),
        (QPalette.AlternateBase, "#f6f8f7", "#1e2420"),
        (QPalette.Text, "#202b24", "#eff5f0"),
        (QPalette.Button, "#f6f8f7", "#252e28"),
        (QPalette.ButtonText, "#202b24", "#eff5f0"),
        (QPalette.Highlight, "#d9f5e2", "#294e35"),
        (QPalette.HighlightedText, "#173e23", "#d3f6de"),
        (QPalette.PlaceholderText, "#6e7b72", "#a0b0a5"),
        (QPalette.ToolTipBase, "#f6f8f7", "#252e28"),
        (QPalette.ToolTipText, "#202b24", "#eff5f0"),
    ):
        result.setColor(role, QColor(dim if dark else light))
    for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
        result.setColor(QPalette.Disabled, role, QColor("#819086" if dark else "#89958d"))
    return result


def apply_palette(window, dark):
    # Qt 5 input widgets may retain their own placeholder/disabled palette.
    from PySide6.QtWidgets import QWidget
    colors = palette(dark)
    window.setPalette(colors)
    for child in window.findChildren(QWidget):
        child.setPalette(colors)


def native_title_bar(window, dark):
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
        enabled = wintypes.BOOL(dark)
        for attribute in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    wintypes.HWND(int(window.winId())), attribute,
                    ctypes.byref(enabled), ctypes.sizeof(enabled)) == 0:
                break
    except (AttributeError, OSError):
        pass


def stylesheet(dark=False):
    bg, panel, side, text, muted, line, input_bg = (
        ("#181c1a", "#1e2420", "#141916", "#eff5f0", "#a0b0a5", "#354139", "#252e28") if dark else
        ("#ffffff", "#f6f8f7", "#f3f5f4", "#202b24", "#6e7b72", "#e0e6e2", "#ffffff"))
    selected, selected_text = (
        ("#294e35", "#d3f6de") if dark else ("#d9f5e2", "#173e23"))
    return f"""
    QWidget {{ color:{text}; font-family:'Segoe UI','Yu Gothic UI','Meiryo'; font-size:14px; }}
    QMainWindow, QDialog, QMessageBox, QWidget#workspace, QWidget#settingsContent {{ background:{bg}; }}
    QWidget#sidebar, QListWidget#settingsNav {{ background:{side}; border:0; }}
    QWidget#originalPanel, QFrame#statusPanel {{ background:{panel}; border-radius:12px; }}
    QLabel {{ background:transparent; }}
    QLabel#brand {{ font-size:19px; font-weight:700; }}
    QLabel#heading {{ font-size:26px; font-weight:700; }}
    QLabel#sectionTitle {{ font-size:16px; font-weight:600; }}
    QLabel#muted, QLabel#metadata {{ color:{muted}; font-size:12px; }}
    QLabel#notice {{ color:{muted}; font-size:12px; padding:8px 0; }}
    QPushButton {{ background:transparent; border:1px solid {line}; border-radius:8px; padding:9px 14px; }}
    QPushButton:hover {{ background:{panel}; border-color:#71c88b; }}
    QPushButton:disabled {{ color:{muted}; border-color:{line}; }}
    QPushButton#primary {{ background:#79e79e; color:#123b20; border:1px solid #79e79e; font-weight:600; }}
    QPushButton#primary:hover {{ background:#65db8c; }}
    QPushButton#primary:disabled {{ background:{line}; color:{muted}; border-color:{line}; }}
    QPushButton#ghost {{ border:0; padding:8px 10px; text-align:left; }}
    QPushButton#providerChoice {{ text-align:left; font-size:16px; font-weight:600; }}
    QPushButton#providerChoice:checked {{ background:{selected}; border-color:#54c97a; color:{selected_text}; }}
    QPushButton#danger {{ color:{'#ff9696' if dark else '#c24444'}; }}
    QLineEdit, QComboBox, QSpinBox, QKeySequenceEdit {{ background:{input_bg}; border:1px solid {line}; border-radius:8px; padding:9px 10px; selection-background-color:#bceccb; selection-color:#143e22; }}
    QLineEdit:focus, QComboBox:focus, QKeySequenceEdit:focus {{ border-color:#50ba72; }}
    QComboBox::drop-down {{ border:0; width:24px; }}
    QComboBox QAbstractItemView {{ background:{input_bg}; color:{text}; selection-background-color:{selected}; selection-color:{selected_text}; }}
    QTextEdit, QTextBrowser {{ background:transparent; border:0; selection-background-color:#bceccb; selection-color:#143e22; }}
    QTextEdit#translation {{ font-size:22px; }}
    QTextEdit#original {{ font-size:15px; }}
    QListWidget {{ background:transparent; border:0; outline:0; }}
    QListWidget::item {{ border-radius:9px; padding:9px 10px; margin:2px 8px; }}
    QListWidget::item:hover {{ background:{line}; }}
    QListWidget::item:selected {{ background:{selected}; color:{selected_text}; }}
    QListWidget#settingsNav::item {{ padding:14px 14px; margin:3px 12px; }}
    QScrollArea {{ background:transparent; border:0; }}
    QScrollBar:vertical {{ background:transparent; width:8px; margin:3px; }}
    QScrollBar::handle:vertical {{ background:{'#53645a' if dark else '#bdc9c1'}; border-radius:3px; min-height:28px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
    QSplitter::handle {{ background:{line}; height:1px; width:1px; }}
    QFrame#divider {{ background:{line}; max-height:1px; min-height:1px; border:0; }}
    QCheckBox {{ spacing:10px; padding:5px 0; }}
    QCheckBox::indicator {{ width:17px; height:17px; border:1px solid {line}; border-radius:5px; background:{input_bg}; }}
    QCheckBox::indicator:checked {{ background:#65db8c; border-color:#35a75a; }}
    QProgressBar {{ border:0; border-radius:3px; background:{line}; height:5px; text-align:center; }}
    QProgressBar::chunk {{ background:#5bd482; border-radius:3px; }}
    QToolTip {{ background:{panel}; color:{text}; border:1px solid {line}; padding:5px; }}
    QMenu {{ background:{bg}; border:1px solid {line}; padding:5px; }}
    QMenu::item {{ padding:8px 20px; }}
    QMenu::item:selected {{ background:{selected}; color:{selected_text}; }}
    """


def icon(name, color="#477354", size=20):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor(color), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.scale(size / 24, size / 24)
    if name == "capture":
        for x, y, dx, dy in ((4,4,5,5),(20,4,-5,5),(4,20,5,-5),(20,20,-5,-5)):
            painter.drawLine(x,y,x+dx,y); painter.drawLine(x,y,x,y+dy)
    elif name == "copy":
        painter.drawRoundedRect(QRectF(8,4,12,13),2,2); painter.drawRoundedRect(QRectF(4,8,12,13),2,2)
    elif name == "plus":
        painter.drawLine(12,5,12,19); painter.drawLine(5,12,19,12)
    elif name == "settings":
        painter.drawEllipse(QRectF(5,5,14,14)); painter.drawEllipse(QRectF(9,9,6,6))
        for x,y,x2,y2 in ((12,2,12,5),(12,19,12,22),(2,12,5,12),(19,12,22,12),(5,5,7,7),(17,17,19,19),(5,19,7,17),(17,7,19,5)):
            painter.drawLine(x,y,x2,y2)
    elif name == "sidebar":
        painter.drawRoundedRect(QRectF(3,4,18,16),2,2); painter.drawLine(9,4,9,20)
    elif name == "search":
        painter.drawEllipse(QRectF(4,3,12,12)); painter.drawLine(14,14,20,20)
    painter.end()
    return QIcon(pixmap)
