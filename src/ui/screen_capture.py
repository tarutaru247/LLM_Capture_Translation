"""
画面キャプチャと範囲選択 + ズーム／パン対応モジュール
"""
import sys
import logging
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QRubberBand,
    QMainWindow,
    QMessageBox,
)
from PyQt5.QtCore import Qt, QRect, QPoint, QSize
from PyQt5.QtGui import QPainter, QPen, QColor

logger = logging.getLogger("ocr_translator")


class ScreenCaptureWidget(QWidget):
    """
    全画面スクリーンショットを用いて
      ・ホイールでズーム
      ・右ボタンでパン
      ・左ボタンで範囲選択
    を行うウィジェット
    """

    MIN_SCALE = 0.1
    MAX_SCALE = 4.0
    SCALE_STEP = 1.1

    def __init__(self, parent=None, callback=None):
        super().__init__(parent)
        self.callback = callback
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowState(Qt.WindowFullScreen)

        # スクリーンと原寸ピクセルマップ
        self.screen = QApplication.primaryScreen()
        self.full_pixmap = self.screen.grabWindow(0)

        # ジオメトリは仮想デスクトップに合わせる
        self.setGeometry(QApplication.desktop().screenGeometry())
        self.setWindowOpacity(0)  # 背景透過

        # ズームとパン状態
        self.scale_factor = 1.0
        self.offset = QPoint(0, 0)  # ビュー座標系での平行移動
        self._pan_active = False
        self._pan_start = QPoint()

        # 選択状態（イメージ座標系）
        self.select_origin_img = QPoint()
        self.selection_img = QRect()
        self.is_selecting = False
        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self)

        self.help_text = (
            "左ドラッグ: 範囲選択 | 右ドラッグ: パン | ホイール: ズーム | Enter: 確定 | Esc: キャンセル"
        )
        self.setFocusPolicy(Qt.StrongFocus)
        logger.info("ScreenCaptureWidget 初期化完了")

    # ────────────────────────────────────────────
    # 座標変換ユーティリティ
    # ----------------------------------------------------------------
    def view_to_img(self, p: QPoint) -> QPoint:
        """ウィジェット座標 → 画像ピクセル座標"""
        return QPoint(
            int((p.x() - self.offset.x()) / self.scale_factor),
            int((p.y() - self.offset.y()) / self.scale_factor),
        )

    def img_to_view(self, p: QPoint) -> QPoint:
        """画像ピクセル座標 → ウィジェット座標"""
        return QPoint(
            int(p.x() * self.scale_factor + self.offset.x()),
            int(p.y() * self.scale_factor + self.offset.y()),
        )

    def rect_img_to_view(self, r: QRect) -> QRect:
        tl = self.img_to_view(r.topLeft())
        br = self.img_to_view(r.bottomRight())
        return QRect(tl, br)

    # ────────────────────────────────────────────
    # 描画
    # ----------------------------------------------------------------
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)

        # 平行移動 + スケール
        painter.translate(self.offset)
        painter.scale(self.scale_factor, self.scale_factor)
        painter.drawPixmap(0, 0, self.full_pixmap)
        painter.resetTransform()

        # 暗幕
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        # 選択範囲ハイライト
        if not self.selection_img.isNull():
            view_rect = self.rect_img_to_view(self.selection_img)
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(view_rect, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawRect(view_rect)
            size_txt = f"{self.selection_img.width()} x {self.selection_img.height()}"
            painter.drawText(view_rect.x(), view_rect.y() - 5, size_txt)

        # ヘルプテキスト
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.drawText(10, 20, self.help_text)

    # ────────────────────────────────────────────
    # マウス操作
    # ----------------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 範囲選択開始
            self.select_origin_img = self.view_to_img(event.pos())
            self.selection_img = QRect(self.select_origin_img, QSize())
            self.is_selecting = True
            self.rubber_band.setGeometry(self.rect_img_to_view(self.selection_img))
            self.rubber_band.show()
            self.update()
        elif event.button() == Qt.RightButton:
            # パン開始
            self._pan_active = True
            self._pan_start = event.pos()

    def mouseMoveEvent(self, event):
        if self.is_selecting:
            end_img = self.view_to_img(event.pos())
            self.selection_img = QRect(self.select_origin_img, end_img).normalized()
            self.rubber_band.setGeometry(self.rect_img_to_view(self.selection_img))
            self.update()
        elif self._pan_active:
            delta = event.pos() - self._pan_start
            self.offset += delta
            self._pan_start = event.pos()
            self.update()
            if self.is_selecting:
                self.rubber_band.setGeometry(self.rect_img_to_view(self.selection_img))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.is_selecting:
            self.is_selecting = False
            self.rubber_band.hide()
            self.update()
        elif event.button() == Qt.RightButton:
            self._pan_active = False

    # ────────────────────────────────────────────
    # ズーム
    # ----------------------------------------------------------------
    def wheelEvent(self, event):
        angle = event.angleDelta().y()
        if angle == 0:
            return
        old_scale = self.scale_factor
        if angle > 0:
            self.scale_factor = min(self.scale_factor * self.SCALE_STEP, self.MAX_SCALE)
        else:
            self.scale_factor = max(self.scale_factor / self.SCALE_STEP, self.MIN_SCALE)

        # カーソル位置を中心にズーム
        cursor_pos = event.pos()
        self.offset = cursor_pos - (
            (cursor_pos - self.offset) * self.scale_factor / old_scale
        )
        self.update()
        if self.is_selecting:
            self.rubber_band.setGeometry(self.rect_img_to_view(self.selection_img))

    # ────────────────────────────────────────────
    # キー操作
    # ----------------------------------------------------------------
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            logger.info("範囲選択をキャンセル")
            self.close()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if not self.selection_img.isNull():
                self.capture_selected_area()
            else:
                QMessageBox.information(self, "選択エラー", "範囲が選択されていません。")

    # ────────────────────────────────────────────
    # キャプチャ実行
    # ----------------------------------------------------------------
    def capture_selected_area(self):
        if self.selection_img.isNull():
            return
        try:
            cap = self.screen.grabWindow(
                0,
                self.selection_img.x(),
                self.selection_img.y(),
                self.selection_img.width(),
                self.selection_img.height(),
            )
        except Exception:
            cap = self.full_pixmap.copy(self.selection_img)
        logger.info(
            "キャプチャ %dx%d", self.selection_img.width(), self.selection_img.height()
        )
        if self.callback:
            self.callback(cap)
        self.close()


class ScreenCaptureManager:
    """
    ScreenCaptureWidget を起動するだけのシンプルなマネージャ
    """

    def __init__(self, parent=None):
        self.parent = parent
        self.widget = None

    def start_capture(self, callback=None):
        if self.widget:
            self.widget.close()
        self.widget = ScreenCaptureWidget(self.parent, callback)
        self.widget.show()


# ────────────────────────────────
# 単体テスト起動
# --------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)

    def on_captured(pix):
        win = QMainWindow()
        win.setWindowTitle("キャプチャ結果")
        lbl = QLabel()
        lbl.setPixmap(pix)
        win.setCentralWidget(lbl)
        win.resize(pix.width(), pix.height())
        win.show()

    mgr = ScreenCaptureManager()
    mgr.start_capture(on_captured)
    sys.exit(app.exec_())
