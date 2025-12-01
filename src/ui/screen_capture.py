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

        self.full_pixmap = None
        self.target_screen = None
        self.screen_geometry = None

        # マルチモニター環境でどこにいてもクリックを拾えるよう、まずは仮想デスクトップ全体を覆う
        # 背景は全スクリーンを合成した画像にしておく（実際のキャプチャは後で対象モニターに切り替える）
        self._prepare_virtual_background()

        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        self.origin = QPoint()

    def _prepare_virtual_background(self):
        """
        全モニターのスクリーンショットを仮想デスクトップ座標に合成して表示用の背景を作る。
        実際の切り出しはマウスドラッグ開始時に対象モニターへ切り替える。
        """
        app = QApplication.instance()
        screens = app.screens()
        if not screens:
            return

        primary = app.primaryScreen()
        virtual_geo = primary.virtualGeometry()
        self.setGeometry(virtual_geo)

        composite = QPixmap(virtual_geo.size())
        composite.fill(QColor(0, 0, 0, 0))

        painter = QPainter(composite)
        for screen in screens:
            geo = screen.geometry()
            pix = screen.grabWindow(0)
            # virtual_geo.topLeft() を原点として各モニターを配置
            painter.drawPixmap(geo.topLeft() - virtual_geo.topLeft(), pix)
        painter.end()

        self.full_pixmap = composite

    def paintEvent(self, event):
        """
        背景にスクリーンショットと半透明のオーバーレイを描画する。
        """
        painter = QPainter(self)
        # 1. 背景にスクリーンショットを描画
        if self.full_pixmap:
            painter.drawPixmap(self.rect(), self.full_pixmap)
        else:
            painter.fillRect(self.rect(), QColor(0, 0, 0, 180))
        # 2. 半透明の暗いオーバーレイをかける
        painter.fillRect(self.rect(), QColor(0, 0, 0, 128))

    def mousePressEvent(self, event):
        """
        マウスボタンが押されたら、選択開始点を記録し、ラバーバンドの表示を開始する。
        """
        if event.button() == Qt.LeftButton:
            # ドラッグ開始時点のモニターを決定し、そのスクリーンだけをキャプチャ対象にする
            if not self.target_screen:
                self._lock_to_screen(event.globalPos())

            # 座標は対象モニター基準に正規化
            self.origin = self.mapFromGlobal(event.globalPos())
            self.rubber_band.setGeometry(QRect(self.origin, QSize()))
            self.rubber_band.show()

    def mouseMoveEvent(self, event):
        """
        マウスをドラッグしている間、ラバーバンドのサイズを更新する。
        """
        if not self.origin.isNull():
            current_pos = self.mapFromGlobal(event.globalPos()) if self.target_screen else event.pos()
            self.rubber_band.setGeometry(QRect(self.origin, current_pos).normalized())

    def mouseReleaseEvent(self, event):
        """
        マウスボタンが離されたら、選択を確定し、シグナルを発行して閉じる。
        """
        if event.button() == Qt.LeftButton and not self.origin.isNull():
            self.rubber_band.hide()
            release_pos = self.mapFromGlobal(event.globalPos()) if self.target_screen else event.pos()
            selection_rect = QRect(self.origin, release_pos).normalized()

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

    def _lock_to_screen(self, global_pos: QPoint):
        """
        ドラッグ開始時点のカーソル位置から対象モニターを確定し、
        そのモニターのスクリーンショットとジオメトリに切り替える。
        """
        app = QApplication.instance()
        screen = app.screenAt(global_pos)
        if screen is None:
            screen = app.primaryScreen()

        self.target_screen = screen
        self.screen_geometry = screen.geometry()

        # 対象モニターの画像だけを使う（他モニターにまたがらないようにする）
        self.full_pixmap = screen.grabWindow(0)

        # ウィンドウも対象モニター範囲に合わせる
        self.setGeometry(self.screen_geometry)
        self.move(self.screen_geometry.topLeft())
        self.resize(self.screen_geometry.size())
        self.update()

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
