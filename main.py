import sys
import logging
from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow
from src.translator.translation_job_runner import main as translation_job_runner_main
from src.utils.utils import setup_logger
from src.utils.settings_manager import SettingsManager
from src.ui.onboarding import ensure_terms, ModelSetupDialog
from src.translator.plamo_runtime import resource_root
from PySide6.QtGui import QIcon

logger = logging.getLogger('ocr_translator')

def main():
    """アプリケーションのメインエントリーポイント"""
    setup_logger()
    logger.info("アプリケーションを起動しています...")

    # PySide6アプリケーションの作成
    app = QApplication(sys.argv)
    app.setApplicationName("たる翻訳")
    app.setOrganizationName("OCR Translator")
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(QIcon(str(resource_root() / 'resources/icon.ico')))
    settings = SettingsManager()
    if not ensure_terms(settings):
        return
    if not settings.get_setting('onboarding', 'completed', False):
        if ModelSetupDialog(settings).exec() != ModelSetupDialog.Accepted:
            return

    # メインウィンドウの作成と表示
    # ホットキー処理はMainWindowに集約
    main_window = MainWindow()
    main_window.show()

    logger.info("メインウィンドウを表示しました")

    # アプリケーションの実行
    sys.exit(app.exec())

if __name__ == "__main__":
    if "--translation-worker" in sys.argv:
        raise SystemExit(translation_job_runner_main())
    main()
