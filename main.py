import sys
import logging
from PyQt5.QtWidgets import QApplication

from src.ui.main_window import MainWindow
from src.utils.utils import setup_logger

logger = setup_logger()

def main():
    """アプリケーションのメインエントリーポイント"""
    logger.info("アプリケーションを起動しています...")

    # PyQt5アプリケーションの作成
    app = QApplication(sys.argv)
    app.setApplicationName("OCR翻訳ツール")
    app.setOrganizationName("OCR Translator")

    # メインウィンドウの作成と表示
    # ホットキー処理はMainWindowに集約
    main_window = MainWindow()
    main_window.show()

    logger.info("メインウィンドウを表示しました")

    # アプリケーションの実行
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
