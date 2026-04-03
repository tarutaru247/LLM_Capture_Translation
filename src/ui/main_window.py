"""
メインウィンドウモジュール
"""
import ctypes
import logging
from ctypes import wintypes

from PyQt5.QtCore import QBuffer, QIODevice, QRect, QSize, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QFrame,
    QGridLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
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


class TranslationWorkerThread(QThread):
    """OCR / 翻訳処理をバックグラウンドで実行する。"""

    result_ready = pyqtSignal(dict)

    def __init__(self, image_bytes: bytes, target_lang: str, transcribe_original: bool):
        super().__init__()
        self.image_bytes = image_bytes
        self.target_lang = target_lang
        self.transcribe_original = transcribe_original

    def run(self):
        result = {
            "translated_text": None,
            "extracted_text": "",
            "error_message": None,
            "last_used_model": None,
        }

        try:
            if self.transcribe_original:
                ocr_service = VisionOCRService()
                translation_manager = TranslationManager()
                extracted_text = ocr_service.extract_text(self.image_bytes)
                if extracted_text and not extracted_text.startswith("エラー:"):
                    result["extracted_text"] = extracted_text
                    translated_text = translation_manager.translate(extracted_text, target_lang=self.target_lang)
                    result["translated_text"] = translated_text
                    result["last_used_model"] = translation_manager.get_last_used_image_model()
                else:
                    result["error_message"] = extracted_text or "テキストの抽出に失敗しました。"
            else:
                translation_manager = TranslationManager()
                translated_text = translation_manager.translate_image(self.image_bytes, self.target_lang)
                result["translated_text"] = translated_text
                result["last_used_model"] = translation_manager.get_last_used_image_model()
        except Exception as exc:
            logger.exception("バックグラウンド翻訳処理で予期せぬエラーが発生しました")
            result["error_message"] = str(exc)

        self.result_ready.emit(result)


class ProcessingOverlay(QWidget):
    """翻訳中であることを示す半透明オーバーレイ。"""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(20, 24, 33, 170);")

        panel = QFrame(self)
        panel.setObjectName("processingPanel")
        panel.setStyleSheet(
            """
            QFrame#processingPanel {
                background-color: rgba(255, 255, 255, 240);
                border: 1px solid #d9e2ef;
                border-radius: 18px;
            }
            QLabel {
                color: #203044;
            }
            QProgressBar {
                border: 1px solid #cbd6e2;
                border-radius: 8px;
                background: #eef3f8;
                min-height: 16px;
            }
            QProgressBar::chunk {
                border-radius: 8px;
                background-color: #2f7cf6;
            }
            """
        )

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        self.title_label = QLabel()
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-size: 22px; font-weight: 700;")
        layout.addWidget(self.title_label)

        self.detail_label = QLabel()
        self.detail_label.setAlignment(Qt.AlignCenter)
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.detail_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        grid = QGridLayout(self)
        grid.setContentsMargins(40, 40, 40, 40)
        grid.addWidget(panel, 0, 0, alignment=Qt.AlignCenter)

        self.hide()

    def update_texts(self, title: str, detail: str):
        self.title_label.setText(title)
        self.detail_label.setText(detail)


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
        self.worker_thread: TranslationWorkerThread | None = None

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

        self.processing_overlay = ProcessingOverlay(central_widget)

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
        self.processing_overlay.update_texts(
            self.tr_ui("processing_overlay_title"),
            self.tr_ui("processing_overlay_detail"),
        )

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

        target_lang = self.settings_manager.get_app_language()
        transcribe_original = self.settings_manager.get_transcribe_original_text()
        self._update_ui_visibility()
        self._start_translation_worker(pixmap, target_lang, transcribe_original)

    def _pixmap_to_png_bytes(self, pixmap: QPixmap) -> bytes:
        qbuffer = QBuffer()
        qbuffer.open(QIODevice.ReadWrite)
        try:
            pixmap.save(qbuffer, "PNG")
            return bytes(qbuffer.data())
        finally:
            qbuffer.close()

    def _start_translation_worker(self, pixmap: QPixmap, target_lang: str, transcribe_original: bool):
        image_bytes = self._pixmap_to_png_bytes(pixmap)
        self._set_processing_state(True)
        logger.info("バックグラウンド翻訳スレッドを開始します。")

        self.worker_thread = TranslationWorkerThread(image_bytes, target_lang, transcribe_original)
        self.worker_thread.result_ready.connect(self._handle_translation_result)
        self.worker_thread.finished.connect(self._clear_worker_references)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.start()

    def _clear_worker_references(self):
        logger.info("バックグラウンド翻訳スレッドを終了しました。")
        self.worker_thread = None

    def _set_processing_state(self, is_processing: bool):
        self.capture_button.setEnabled(not is_processing)
        self.copy_original_button.setEnabled(not is_processing)
        self.copy_translation_button.setEnabled(not is_processing)
        self.settings_action.setEnabled(not is_processing)
        self.exit_action.setEnabled(not is_processing)
        self.progress_label.setVisible(is_processing)
        self.processing_overlay.setVisible(is_processing)
        self.processing_overlay.setGeometry(self.centralWidget().rect())
        if is_processing:
            self.processing_overlay.raise_()
            self.progress_label.setText(self.tr_ui("progress_label"))
            self.progress_label.show()
        else:
            self.progress_label.hide()
            self.processing_overlay.hide()

    def _handle_translation_result(self, result: dict):
        self._set_processing_state(False)
        self.show()

        extracted_text = result.get("extracted_text", "")
        translated_text = result.get("translated_text")
        error_message = result.get("error_message")
        last_used_model = result.get("last_used_model")

        if extracted_text:
            self.extracted_text = extracted_text
            self.original_text_edit.setPlainText(extracted_text)

        if translated_text and not translated_text.startswith("エラー:"):
            self.translated_text = translated_text
            self.translation_text_edit.setPlainText(translated_text)
            if last_used_model:
                self.status_bar.showMessage(
                    self.tr_ui("status_translation_done_with_model", model=last_used_model),
                    5000,
                )
            else:
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
                if self.worker_thread is not None:
                    logger.info("翻訳処理中のためホットキー入力を無視しました。")
                    return True, 0
                logger.info("グローバルホットキーが検出されました。")
                self.start_capture()
                return True, 0
        return super().nativeEvent(eventType, message)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.processing_overlay.setGeometry(self.centralWidget().rect())

    def closeEvent(self, event):
        if self.worker_thread is not None:
            self.status_bar.showMessage(self.tr_ui("status_processing_locked"), 3000)
            event.ignore()
            return
        self._unregister_global_hotkey()
        self.settings_manager.reload_settings()
        self.settings_manager.save_settings()
        logger.info("アプリケーションを終了します。")
        event.accept()
