"""
メインウィンドウモジュール
"""
import ctypes
import logging
from ctypes import wintypes

from PyQt5.QtCore import QRect, QSize, Qt
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)

from ..ocr.vision_ocr_service import VisionOCRService
from ..translator.translation_manager import TranslationManager
from ..ui.screen_capture import ScreenCaptureWindow
from ..ui.settings_dialog import SettingsDialog
from ..utils.localization import get_ui_string
from ..utils.settings_manager import SettingsManager
from ..utils.utils import sanitize_sensitive_data

logger = logging.getLogger("ocr_translator")

MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
VK_X = 0x58
WM_HOTKEY = 0x0312


class MainWindow(QMainWindow):
    """アプリケーションのメインウィンドウ"""

    def __init__(self):
        super().__init__()

        self.hotkey_id = 1
        self.settings_manager = SettingsManager()
        self.capture_window = None
        self.ocr_service = VisionOCRService()
        self.translation_manager = TranslationManager()
        self.captured_pixmap = None
        self.extracted_text = ""
        self.translated_text = ""
        self.overlay = None
        self._last_capture_global_rect: QRect | None = None

        self._init_ui()
        self._register_global_hotkey()
        logger.info("メインウィンドウを初期化しました")

    def tr_ui(self, key: str, **kwargs) -> str:
        return get_ui_string(self.settings_manager.get_app_language(), key, **kwargs)

    def _init_ui(self):
        """UIの初期化"""
        self.setMinimumSize(800, 600)
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #f0f0f0;
            }
            QLabel {
                font-family: "Yu Gothic UI", "Meiryo UI", sans-serif;
                font-size: 14px;
                color: #333333;
            }
            QPushButton {
                font-family: "Yu Gothic UI", "Meiryo UI", sans-serif;
                font-size: 14px;
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QTextEdit {
                font-family: "Yu Gothic UI", "Meiryo UI", monospace;
                font-size: 14px;
                border: 1px solid #cccccc;
                border-radius: 5px;
                padding: 5px;
                background-color: white;
            }
            QStatusBar {
                background-color: #e0e0e0;
                color: #333333;
            }
            """
        )

        self._create_menu_bar()

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.capture_button = QPushButton(QIcon("icons/capture.png"), "")
        self.capture_button.setIconSize(QSize(24, 24))
        self.capture_button.setMinimumHeight(40)
        self.capture_button.clicked.connect(self._on_capture_button_clicked)
        main_layout.addWidget(self.capture_button)

        self.data_notice_label = QLabel()
        self.data_notice_label.setWordWrap(True)
        self.data_notice_label.setStyleSheet(
            "color: #b22222; font-size: 12px; background-color: #fff8f0; padding: 6px; border: 1px solid #f4c6a6; border-radius: 4px;"
        )
        main_layout.addWidget(self.data_notice_label)

        result_layout = QHBoxLayout()

        self.original_widget = QWidget()
        original_layout = QVBoxLayout(self.original_widget)
        original_layout.setContentsMargins(0, 0, 0, 0)
        self.original_label = QLabel()
        original_layout.addWidget(self.original_label)

        self.original_text_edit = QTextEdit()
        self.original_text_edit.setReadOnly(True)
        self.original_text_edit.setAcceptRichText(False)
        original_layout.addWidget(self.original_text_edit)

        self.copy_original_button = QPushButton()
        self.copy_original_button.clicked.connect(self._copy_original_text)
        original_layout.addWidget(self.copy_original_button)

        result_layout.addWidget(self.original_widget)

        translation_layout = QVBoxLayout()
        self.translation_label = QLabel()
        translation_layout.addWidget(self.translation_label)

        self.translation_text_edit = QTextEdit()
        self.translation_text_edit.setReadOnly(True)
        self.translation_text_edit.setAcceptRichText(False)
        translation_layout.addWidget(self.translation_text_edit)

        self.copy_translation_button = QPushButton()
        self.copy_translation_button.clicked.connect(self._copy_translation_text)
        translation_layout.addWidget(self.copy_translation_button)

        result_layout.addLayout(translation_layout)
        main_layout.addLayout(result_layout)

        self.progress_label = QLabel()
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.setStyleSheet("font-size: 18px; color: #007bff; font-weight: bold;")
        self.progress_label.hide()
        main_layout.addWidget(self.progress_label)

        self._update_ui_visibility()
        self._apply_texts()

        if self.settings_manager.get_setting("ui", "start_minimized", False):
            self.showMinimized()

    def _apply_texts(self):
        """現在のアプリ言語に合わせて文言を反映"""
        self.setWindowTitle(self.tr_ui("window_title"))
        self.status_bar.showMessage(self.tr_ui("status_ready"))
        self.capture_button.setText(self.tr_ui("capture_button"))
        self.data_notice_label.setText(self.tr_ui("notice"))
        self.original_label.setText(self.tr_ui("original_label"))
        self.translation_label.setText(self.tr_ui("translation_label"))
        self.copy_original_button.setText(self.tr_ui("copy_button"))
        self.copy_translation_button.setText(self.tr_ui("copy_button"))
        self.progress_label.setText(self.tr_ui("progress_label"))

        self.file_menu.setTitle(self.tr_ui("file_menu"))
        self.exit_action.setText(self.tr_ui("exit_action"))
        self.settings_menu.setTitle(self.tr_ui("settings_menu"))
        self.settings_action.setText(self.tr_ui("settings_action"))
        self.help_menu.setTitle(self.tr_ui("help_menu"))
        self.about_action.setText(self.tr_ui("about_action"))
        self.usage_action.setText(self.tr_ui("usage_action"))

    def _update_ui_visibility(self):
        """設定に基づいてUIの表示/非表示を切り替える"""
        transcribe_original = self.settings_manager.get_transcribe_original_text()
        self.original_widget.setVisible(transcribe_original)

    def _create_menu_bar(self):
        """メニューバーの作成"""
        menu_bar = self.menuBar()

        self.file_menu = menu_bar.addMenu("")
        self.exit_action = QAction(QIcon("icons/exit.png"), "", self)
        self.exit_action.triggered.connect(self.close)
        self.file_menu.addAction(self.exit_action)

        self.settings_menu = menu_bar.addMenu("")
        self.settings_action = QAction(QIcon("icons/settings.png"), "", self)
        self.settings_action.triggered.connect(self._show_settings_dialog)
        self.settings_menu.addAction(self.settings_action)

        self.help_menu = menu_bar.addMenu("")
        self.about_action = QAction(QIcon("icons/info.png"), "", self)
        self.about_action.triggered.connect(self._show_about_dialog)
        self.help_menu.addAction(self.about_action)

        self.usage_action = QAction(QIcon("icons/help.png"), "", self)
        self.usage_action.triggered.connect(self._show_usage_dialog)
        self.help_menu.addAction(self.usage_action)

    def start_capture(self):
        """領域選択キャプチャを開始する。"""
        if self.capture_window and self.capture_window.isVisible():
            return

        logger.info("領域選択キャプチャを開始します。")
        self.status_bar.showMessage(self.tr_ui("status_select_area"))
        self.hide()
        QApplication.processEvents()

        self.capture_window = ScreenCaptureWindow()
        self.capture_window.region_selected.connect(self._on_capture_complete)
        self.capture_window.destroyed.connect(self.show)
        self.capture_window.show()

    def _on_capture_button_clicked(self):
        self.start_capture()

    def _on_capture_complete(self, pixmap: QPixmap):
        if not pixmap or pixmap.isNull():
            logger.info("キャプチャがキャンセルまたは失敗しました。")
            self.status_bar.showMessage(self.tr_ui("status_capture_cancelled"), 3000)
            self.show()
            return

        try:
            capture_rect = self.capture_window.rubber_band.geometry()
            window_geo = self.capture_window.geometry()
            self._last_capture_global_rect = capture_rect.translated(window_geo.topLeft())
        except Exception as exc:
            logger.warning("キャプチャ矩形の保存に失敗: %s", sanitize_sensitive_data(str(exc)))
            self._last_capture_global_rect = None

        self.captured_pixmap = pixmap
        self.status_bar.showMessage(self.tr_ui("status_processing"))
        self.progress_label.setText(self.tr_ui("progress_label"))
        self.progress_label.show()
        QApplication.processEvents()

        target_lang = self.settings_manager.get_app_language()
        transcribe_original = self.settings_manager.get_transcribe_original_text()
        self._update_ui_visibility()

        translated_text = None
        error_message = None

        if transcribe_original:
            extracted_text = self.ocr_service.extract_text(self.captured_pixmap)
            if extracted_text and not extracted_text.startswith("エラー:"):
                self.extracted_text = extracted_text
                self.original_text_edit.setPlainText(extracted_text)
                translated_text = self.translation_manager.translate(extracted_text, target_lang=target_lang)
            else:
                error_message = extracted_text or self.tr_ui("capture_failed")
        else:
            translated_text = self.translation_manager.translate_image(self.captured_pixmap, target_lang)

        self.progress_label.hide()
        self.show()

        if translated_text and not translated_text.startswith("エラー:"):
            self.translated_text = translated_text
            self.translation_text_edit.setPlainText(translated_text)
            self.status_bar.showMessage(self.tr_ui("status_translation_done"), 5000)
            logger.info("翻訳成功")
            self._show_overlay(translated_text)
        else:
            final_error = error_message or translated_text or self.tr_ui("generic_error")
            self.status_bar.showMessage(f"{self.tr_ui('error_title')}: {final_error}", 5000)
            self.translation_text_edit.setPlainText(self.tr_ui("translation_failed", detail=final_error))
            logger.error("翻訳失敗: %s", final_error)

    def _copy_original_text(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.original_text_edit.toPlainText())
        self.status_bar.showMessage(self.tr_ui("status_copy_original"), 3000)

    def _copy_translation_text(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.translation_text_edit.toPlainText())
        self.status_bar.showMessage(self.tr_ui("status_copy_translation"), 3000)

    def _show_overlay(self, translated_text: str):
        return

    def _show_settings_dialog(self):
        settings_dialog = SettingsDialog(self)
        if settings_dialog.exec_():
            self.settings_manager.reload_settings()
            self._update_ui_visibility()
            self._apply_texts()
            self.status_bar.showMessage(self.tr_ui("status_settings_saved"), 3000)

    def _show_about_dialog(self):
        QMessageBox.about(self, self.tr_ui("about_title"), self.tr_ui("about_text"))

    def _show_usage_dialog(self):
        QMessageBox.information(self, self.tr_ui("usage_title"), self.tr_ui("usage_text"))

    def _register_global_hotkey(self):
        try:
            user32 = ctypes.windll.user32
            hwnd = self.winId()
            if not user32.RegisterHotKey(wintypes.HWND(int(hwnd)), self.hotkey_id, MOD_CONTROL | MOD_SHIFT, VK_X):
                error_code = ctypes.GetLastError()
                logger.error("グローバルホットキーの登録に失敗しました。エラーコード: %s", error_code)
                self.status_bar.showMessage(f"{self.tr_ui('error_title')}: hotkey")
            else:
                logger.info("グローバルホットキー(Ctrl+Shift+X)を登録しました。")
        except Exception as e:
            logger.error("ホットキー登録中に予期せぬエラーが発生しました: %s", e)
            self.status_bar.showMessage(f"{self.tr_ui('error_title')}: hotkey")

    def _unregister_global_hotkey(self):
        try:
            user32 = ctypes.windll.user32
            hwnd = self.winId()
            user32.UnregisterHotKey(wintypes.HWND(int(hwnd)), self.hotkey_id)
            logger.info("グローバルホットキーを解除しました。")
        except Exception as e:
            logger.error("ホットキー解除中にエラーが発生しました: %s", e)

    def nativeEvent(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(message.__int__())
            if msg.message == WM_HOTKEY and msg.wParam == self.hotkey_id:
                logger.info("グローバルホットキーが検出されました。")
                self.start_capture()
                return True, 0
        return super().nativeEvent(eventType, message)

    def closeEvent(self, event):
        self._unregister_global_hotkey()
        self.settings_manager.save_settings()
        logger.info("アプリケーションを終了します。")
        event.accept()
