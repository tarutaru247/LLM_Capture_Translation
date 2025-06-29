import sys
import logging
from PyQt5.QtWidgets import QApplication, QWidget, QRubberBand
from PyQt5.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPixmap

logger = logging.getLogger("ocr_translator")

class ScreenCaptureWindow(QWidget):
    """
    画面全体のスクリーンショットを背景に、ユーザーがドラッグで選択した領域を
    切り出すための全画面ウィンドウ。
    """
    # シグナル定義: 選択された領域のQPixmapを渡す
    region_selected = pyqtSignal(QPixmap)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowState(Qt.WindowFullScreen)
        self.setCursor(Qt.CrossCursor)

        # 仮想デスクトップ全体のジオメトリを取得
        desktop_geometry = QApplication.instance().desktop().screenGeometry()
        self.setGeometry(desktop_geometry)

        # スクリーンショットを取得
        self.full_pixmap = QApplication.instance().primaryScreen().grabWindow(
            QApplication.instance().desktop().winId(),
            desktop_geometry.x(),
            desktop_geometry.y(),
            desktop_geometry.width(),
            desktop_geometry.height(),
        )

        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        self.origin = QPoint()

    def paintEvent(self, event):
        """
        背景にスクリーンショットと半透明のオーバーレイを描画する。
        """
        painter = QPainter(self)
        # 1. 背景にスクリーンショットを描画
        painter.drawPixmap(self.rect(), self.full_pixmap)
        # 2. 半透明の暗いオーバーレイをかける
        painter.fillRect(self.rect(), QColor(0, 0, 0, 128))

    def mousePressEvent(self, event):
        """
        マウスボタンが押されたら、選択開始点を記録し、ラバーバンドの表示を開始する。
        """
        if event.button() == Qt.LeftButton:
            self.origin = event.pos()
            self.rubber_band.setGeometry(QRect(self.origin, QSize()))
            self.rubber_band.show()

    def mouseMoveEvent(self, event):
        """
        マウスをドラッグしている間、ラバーバンドのサイズを更新する。
        """
        if not self.origin.isNull():
            self.rubber_band.setGeometry(QRect(self.origin, event.pos()).normalized())

    def mouseReleaseEvent(self, event):
        """
        マウスボタンが離されたら、選択を確定し、シグナルを発行して閉じる。
        """
        if event.button() == Qt.LeftButton and not self.origin.isNull():
            self.rubber_band.hide()
            selection_rect = QRect(self.origin, event.pos()).normalized()

            # 小さすぎる選択は無視
            if selection_rect.width() > 5 and selection_rect.height() > 5:
                logger.info(f"キャプチャ領域確定: {selection_rect}")
                captured_pixmap = self.full_pixmap.copy(selection_rect)
                self.region_selected.emit(captured_pixmap)
            else:
                logger.info("選択領域が小さすぎるためキャンセル")

            self.close()

    def keyPressEvent(self, event):
        """
        Escキーが押されたら、ウィンドウを閉じる（キャンセル）。
        """
        if event.key() == Qt.Key_Escape:
            logger.info("ユーザーにより範囲選択がキャンセルされました。")
            self.close()

# 単体テスト用のコード
if __name__ == "__main__":
    from PyQt5.QtWidgets import QMainWindow, QLabel

    app = QApplication(sys.argv)

    # メインウィンドウ（テスト用）
    main_win = QMainWindow()
    main_win.setWindowTitle("キャプチャ結果表示")
    label = QLabel("ここにキャプチャ画像が表示されます")
    label.setAlignment(Qt.AlignCenter)
    main_win.setCentralWidget(label)
    main_win.resize(400, 300)
    main_win.show()

    # キャプチャウィンドウ
    capture_win = ScreenCaptureWindow()

    # シグナルとスロットを接続
    def show_captured_image(pixmap):
        label.setPixmap(pixmap.scaled(label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        main_win.resize(pixmap.size())
        main_win.show()
        # 通常のアプリではここで次の処理（OCRなど）を呼び出す
        print(f"画像がキャプチャされました: {pixmap.width()}x{pixmap.height()}")

    capture_win.region_selected.connect(show_captured_image)
    capture_win.show()

    sys.exit(app.exec_())