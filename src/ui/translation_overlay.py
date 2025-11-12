import logging
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QColor, QPalette, QFont

logger = logging.getLogger("ocr_translator")

class TranslationOverlay(QWidget):
    """
    翻訳結果を画面上にオーバーレイ表示するための、枠なし・半透明のウィジェット。
    指定時間経過後にフェードアウトして消える。
    """
    def __init__(self, text: str, position: tuple[int, int], duration_ms: int = 5000):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool  # タスクバーに表示されないようにする
        )
        self.setAttribute(Qt.WA_TranslucentBackground) # 背景透過
        self.setAttribute(Qt.WA_DeleteOnClose) # 閉じたら自動で削除

        self.duration = duration_ms
        self._setup_ui(text)
        self.adjustSize() # コンテンツに合わせてサイズを調整
        self.move(position[0], position[1])

        logger.info(f"オーバーレイ表示: position={position}, duration={duration_ms}ms")

    def _setup_ui(self, text: str):
        """UI要素のセットアップ"""
        layout = QVBoxLayout(self)
        self.label = QLabel()
        self.label.setTextFormat(Qt.PlainText)
        self.label.setText(text)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True) # テキストの折り返しを有効化

        # スタイル設定
        font = QFont("Yu Gothic UI", 14)
        self.label.setFont(font)
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 180);
                color: white;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        layout.addWidget(self.label)

    def show_and_fade_out(self):
        """ウィンドウを表示し、タイマーを開始してフェードアウトさせる"""
        self.setWindowOpacity(1.0)
        self.show()

        # フェードアウトアニメーション
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(1000) # 1秒かけてフェードアウト
        self.animation.setStartValue(1.0)
        self.animation.setEndValue(0.0)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation.finished.connect(self.close)

        # 指定時間後にアニメーションを開始するタイマー
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.animation.start)
        self.timer.start(self.duration)

    def closeEvent(self, event):
        """ウィジェットが閉じられる際に、タイマーとアニメーションを停止する"""
        self.timer.stop()
        self.animation.stop()
        super().closeEvent(event)

# 単体テスト用のコード
if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)

    # テスト用のテキストと表示位置
    test_text = "これは翻訳結果のテストです。\nThis is a test of the translation result."
    screen_geometry = QApplication.desktop().screenGeometry()
    pos_x = screen_geometry.width() // 2 - 200
    pos_y = screen_geometry.height() // 2 - 50

    # オーバーレイを作成して表示
    overlay = TranslationOverlay(test_text, position=(pos_x, pos_y), duration_ms=3000)
    overlay.show_and_fade_out()

    sys.exit(app.exec_())
