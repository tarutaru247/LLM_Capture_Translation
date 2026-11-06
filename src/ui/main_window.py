"""
メインウィンドウモジュール
"""
import ctypes
import json
import logging
import subprocess
import threading
import sys
import base64
import time
import tempfile
from pathlib import Path
from ctypes import wintypes

from PyQt5.QtCore import QBuffer, QIODevice, QMimeData, QObject, QRect, QSize, Qt, QTimer, pyqtSignal
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
    QTextBrowser,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)

from ..ui.screen_capture import ScreenCaptureWindow
from ..ui.settings_dialog import SettingsDialog
from ..utils.localization import get_ui_string
from ..utils.settings_manager import SettingsManager
from ..utils.utils import sanitize_sensitive_data
from ..translator.plamo_runtime import PlamoRuntime, resource_root

logger = logging.getLogger("ocr_translator")

MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
VK_X = 0x58
VK_C = 0x43
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312


class TranslationResultBridge(QObject):
    """ワーカースレッドからメインスレッドへ結果を返す。"""
    result_ready = pyqtSignal(dict)
    model_ready = pyqtSignal(str)


class ProcessingOverlay(QWidget):
    """翻訳中であることを示す半透明オーバーレイ。"""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(10, 18, 32, 190);")

        panel = QFrame(self)
        panel.setObjectName("processingPanel")
        panel.setStyleSheet(
            """
            QFrame#processingPanel {
                background-color: rgba(17, 25, 40, 245);
                border: 1px solid #4f8cff;
                border-radius: 18px;
            }
            QLabel {
                color: #f8fbff;
                background-color: transparent;
            }
            QProgressBar {
                border: 1px solid #4f8cff;
                border-radius: 8px;
                background: #142033;
                min-height: 16px;
            }
            QProgressBar::chunk {
                border-radius: 8px;
                background-color: #66b3ff;
            }
            """
        )

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        self.title_label = QLabel()
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-size: 22px; font-weight: 700; color: #ffffff; background-color: transparent;")
        layout.addWidget(self.title_label)

        self.detail_label = QLabel()
        self.detail_label.setAlignment(Qt.AlignCenter)
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet("font-size: 14px; color: #d7e7ff; background-color: transparent;")
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
        self.selection_hotkey_id = 2
        self._selection_pending = False
        self._closing = False
        self._model_loading = False
        self.settings_manager = SettingsManager()
        self.capture_window = None
        self.captured_pixmap = None
        self.extracted_text = ""
        self.translated_text = ""
        self.overlay = None
        self._last_capture_global_rect: QRect | None = None
        self.worker_thread: threading.Thread | None = None
        self.result_bridge = TranslationResultBridge()
        self.result_bridge.result_ready.connect(self._handle_translation_result)
        self.result_bridge.model_ready.connect(self._handle_model_ready)
        self.runtime = PlamoRuntime(self.settings_manager)

        self._init_ui()
        self._register_global_hotkey()
        QTimer.singleShot(0, self._load_local_model)
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
        self.licenses_action.setText(self.tr_ui("licenses"))
        self.reload_model_action.setText(self.tr_ui("reload_model"))

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
        self.reload_model_action = QAction("", self)
        self.reload_model_action.triggered.connect(self._reload_local_model)
        self.settings_menu.addAction(self.reload_model_action)

        self.help_menu = menu_bar.addMenu("")
        self.about_action = QAction(QIcon("icons/info.png"), "", self)
        self.about_action.triggered.connect(self._show_about_dialog)
        self.help_menu.addAction(self.about_action)

        self.usage_action = QAction(QIcon("icons/help.png"), "", self)
        self.usage_action.triggered.connect(self._show_usage_dialog)
        self.help_menu.addAction(self.usage_action)
        self.licenses_action = QAction("", self)
        self.licenses_action.triggered.connect(self._show_licenses)
        self.help_menu.addAction(self.licenses_action)

    def start_capture(self):
        """領域選択キャプチャを開始する。"""
        if not self._can_translate():
            return
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
        self.show()
        self.raise_()
        self.activateWindow()
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
        logger.info("バックグラウンド翻訳サブプロセスを開始します。")

        self.worker_thread = threading.Thread(
            target=self._run_translation_subprocess,
            args=(image_bytes, target_lang, transcribe_original),
            name="translation-worker",
            daemon=True,
        )
        self.worker_thread.start()

    def _build_translation_subprocess_command(self) -> list[str]:
        if getattr(sys, "frozen", False):
            return [sys.executable, "--translation-worker"]
        return [sys.executable, "-m", "src.translator.translation_job_runner"]

    def _run_translation_subprocess(self, image_bytes: bytes, target_lang: str, transcribe_original: bool):
        payload = {
            "image_bytes_b64": base64.b64encode(image_bytes).decode("ascii"),
            "target_lang": target_lang,
            "transcribe_original": transcribe_original,
        }
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        try:
            # Windowed PyInstaller workers have no sys.stdin/sys.stdout. Use
            # short-lived files for both source and exe execution instead.
            with tempfile.TemporaryDirectory(prefix="ocr-job-", dir=self.settings_manager.config_dir) as folder:
                input_path = Path(folder) / "input.json"
                output_path = Path(folder) / "output.json"
                input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                completed = subprocess.run(
                    self._build_translation_subprocess_command() + ["--input-json", str(input_path), "--output-json", str(output_path)],
                    capture_output=True,
                    cwd=str(self._get_project_root()),
                    creationflags=creationflags,
                    timeout=self.settings_manager.get_timeout() + 30,
                )
                result_text = output_path.read_text(encoding="utf-8") if output_path.is_file() else ""
            stdout_text = (completed.stdout or b"").decode("utf-8", errors="replace")
            stderr_text = (completed.stderr or b"").decode("utf-8", errors="replace")
            if completed.returncode == 0:
                result = json.loads(result_text)
                if not result.get("error_message") and result.get("extracted_text"):
                    result["translated_text"] = self.runtime.translate(result["extracted_text"], target_lang)
                    result["last_used_model"] = self.runtime.model_name
            else:
                stderr = (stderr_text or stdout_text).strip()
                result = {
                    "translated_text": None,
                    "extracted_text": "",
                    "error_message": f"翻訳サブプロセスが異常終了しました。(code={completed.returncode}) {stderr[-400:]}".strip(),
                    "last_used_model": None,
                }
        except Exception as exc:
            result = {
                "translated_text": None,
                "extracted_text": "",
                "error_message": f"翻訳に失敗しました: {sanitize_sensitive_data(str(exc))}",
                "last_used_model": None,
            }

        self.result_bridge.result_ready.emit(result)

    def _get_project_root(self):
        return Path(__file__).resolve().parents[2]

    def _clear_worker_references(self):
        logger.info("バックグラウンド翻訳サブプロセス処理を終了しました。")
        self.worker_thread = None

    def _set_processing_state(self, is_processing: bool):
        self.capture_button.setEnabled(not is_processing and self.runtime.ready)
        self.copy_original_button.setEnabled(not is_processing)
        self.copy_translation_button.setEnabled(not is_processing)
        self.settings_action.setEnabled(not is_processing)
        self.reload_model_action.setEnabled(not is_processing and not self._model_loading)
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
        self._clear_worker_references()
        self._set_processing_state(False)
        self.show()

        extracted_text = result.get("extracted_text", "")
        translated_text = result.get("translated_text")
        error_message = result.get("error_message")
        last_used_model = result.get("last_used_model")

        self.extracted_text = extracted_text
        self.original_text_edit.setPlainText(extracted_text)
        self.original_widget.setVisible(True)
        self.raise_()
        self.activateWindow()

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
        if self._selection_pending or self.worker_thread is not None or self._model_loading:
            return
        old_local_settings = dict(self.settings_manager.settings["local_model"])
        settings_dialog = SettingsDialog(self)
        if settings_dialog.exec_():
            self.settings_manager.reload_settings()
            self._update_ui_visibility()
            self._apply_texts()
            self.status_bar.showMessage(self.tr_ui("status_settings_saved"), 3000)
            if old_local_settings != self.settings_manager.settings["local_model"]:
                self.runtime.close()
                self.runtime = PlamoRuntime(self.settings_manager)
                self._load_local_model()

    def _show_about_dialog(self):
        QMessageBox.about(self, self.tr_ui("about_title"), self.tr_ui("about_text"))

    def _show_usage_dialog(self):
        QMessageBox.information(self, self.tr_ui("usage_title"), self.tr_ui("usage_text"))

    def _show_licenses(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr_ui("licenses"))
        dialog.resize(760, 600)
        layout = QVBoxLayout(dialog)
        browser = QTextBrowser()
        notice = resource_root() / "docs/THIRD_PARTY_NOTICES.md"
        license_path = resource_root() / "docs/licenses/PLaMo-ja.txt"
        browser.setPlainText(notice.read_text(encoding="utf-8") + "\n\n" + license_path.read_text(encoding="utf-8"))
        layout.addWidget(browser)
        dialog.exec_()

    def _register_global_hotkey(self):
        try:
            user32 = ctypes.windll.user32
            hwnd = self.winId()
            for hotkey_id, key in ((self.hotkey_id, VK_X), (self.selection_hotkey_id, VK_C)):
                if not user32.RegisterHotKey(wintypes.HWND(int(hwnd)), hotkey_id, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, key):
                    self.status_bar.showMessage(self.tr_ui("hotkey_failed", shortcut=chr(key)))
                    logger.error("ホットキー登録失敗: Ctrl+Shift+%s", chr(key))
        except Exception as e:
            logger.error("ホットキー登録中に予期せぬエラーが発生しました: %s", e)
            self.status_bar.showMessage(f"{self.tr_ui('error_title')}: hotkey")

    def _unregister_global_hotkey(self):
        try:
            user32 = ctypes.windll.user32
            hwnd = self.winId()
            user32.UnregisterHotKey(wintypes.HWND(int(hwnd)), self.hotkey_id)
            user32.UnregisterHotKey(wintypes.HWND(int(hwnd)), self.selection_hotkey_id)
            logger.info("グローバルホットキーを解除しました。")
        except Exception as e:
            logger.error("ホットキー解除中にエラーが発生しました: %s", e)

    def nativeEvent(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(message.__int__())
            if msg.message == WM_HOTKEY and msg.wParam in (self.hotkey_id, self.selection_hotkey_id):
                if self.worker_thread is not None or self._selection_pending or self._model_loading or QApplication.activeModalWidget() is not None:
                    logger.info("翻訳処理中のためホットキー入力を無視しました。")
                    return True, 0
                logger.info("グローバルホットキーが検出されました。")
                if msg.wParam == self.selection_hotkey_id:
                    self.translate_selection()
                else:
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
        self._closing = True
        self.runtime.close()
        self.settings_manager.reload_settings()
        self.settings_manager.save_settings()
        logger.info("アプリケーションを終了します。")
        event.accept()
        QApplication.instance().quit()

    def _load_local_model(self):
        self._model_loading = True
        self.capture_button.setEnabled(False)
        self.settings_action.setEnabled(False)
        self.reload_model_action.setEnabled(False)
        self.status_bar.showMessage(self.tr_ui("model_loading"))
        runtime = self.runtime

        def load():
            error = ""
            try:
                runtime.start()
            except Exception as exc:
                runtime.close()
                error = sanitize_sensitive_data(str(exc))
            if not self._closing:
                self.result_bridge.model_ready.emit(error)

        threading.Thread(target=load, name="plamo-loader", daemon=True).start()

    def _handle_model_ready(self, error):
        if self._closing:
            return
        self._model_loading = False
        self.settings_action.setEnabled(True)
        self.reload_model_action.setEnabled(True)
        self.capture_button.setEnabled(not error)
        self.status_bar.showMessage(self.tr_ui("model_failed", detail=error) if error else self.tr_ui("status_ready"))
        if error:
            self.translation_text_edit.setPlainText(self.tr_ui("model_failed", detail=error))

    def _can_translate(self):
        if self.worker_thread is not None or self._selection_pending or QApplication.activeModalWidget() is not None:
            return False
        if not self.runtime.ready:
            self.status_bar.showMessage(self.tr_ui("model_not_ready"), 5000)
            return False
        return True

    def _reload_local_model(self):
        if self.worker_thread is not None or self._selection_pending or self._model_loading:
            return
        self.runtime.close()
        self.runtime = PlamoRuntime(self.settings_manager)
        self._load_local_model()

    def translate_selection(self):
        """Copy the selection in the foreground app, then restore clipboard contents."""
        if not self._can_translate():
            return
        self._selection_pending = True
        self._selection_deadline = time.monotonic() + 3
        self._selection_foreground = ctypes.windll.user32.GetForegroundWindow()
        self._wait_for_hotkey_release()

    def _wait_for_hotkey_release(self):
        if self._closing:
            return
        user32 = ctypes.windll.user32
        if user32.GetForegroundWindow() != self._selection_foreground:
            self._selection_pending = False
            return
        if any(user32.GetAsyncKeyState(key) & 0x8000 for key in (0x10, 0x11, 0x12, VK_C)):
            if time.monotonic() < self._selection_deadline:
                QTimer.singleShot(30, self._wait_for_hotkey_release)
            else:
                self._selection_pending = False
            return
        clipboard = QApplication.clipboard()
        saved = QMimeData()
        for fmt in clipboard.mimeData().formats():
            saved.setData(fmt, clipboard.mimeData().data(fmt))
        self._saved_clipboard = saved
        self._clipboard_sequence = user32.GetClipboardSequenceNumber()
        # Key releases above prevent Ctrl+Shift+C becoming Ctrl+Shift+Insert, etc.
        from pynput.keyboard import Controller, Key
        keyboard = Controller()
        try:
            with keyboard.pressed(Key.ctrl):
                keyboard.press("c")
                keyboard.release("c")
        except Exception:
            self._selection_pending = False
            self._saved_clipboard = None
            self.status_bar.showMessage(self.tr_ui("selection_empty"), 5000)
            return
        self._selection_deadline = time.monotonic() + 2
        QTimer.singleShot(50, self._read_selection)

    def _read_selection(self):
        if self._closing:
            return
        user32 = ctypes.windll.user32
        sequence = user32.GetClipboardSequenceNumber()
        if sequence == self._clipboard_sequence:
            if time.monotonic() < self._selection_deadline:
                QTimer.singleShot(50, self._read_selection)
                return
            self._selection_pending = False
            self._saved_clipboard = None
            self.status_bar.showMessage(self.tr_ui("selection_empty"), 5000)
            return
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        # Never replace a subsequent clipboard change made by another app/user.
        if user32.GetClipboardSequenceNumber() == sequence:
            clipboard.setMimeData(self._saved_clipboard)
        self._saved_clipboard = None
        self._selection_pending = False
        if not text.strip():
            self.status_bar.showMessage(self.tr_ui("selection_empty"), 5000)
            return
        self._set_processing_state(True)
        target_lang = self.settings_manager.get_app_language()

        def translate():
            result = {"extracted_text": text, "last_used_model": self.runtime.model_name}
            try:
                result["translated_text"] = self.runtime.translate(text, target_lang)
            except Exception as exc:
                result["error_message"] = sanitize_sensitive_data(str(exc))
            self.result_bridge.result_ready.emit(result)

        self.worker_thread = threading.Thread(target=translate, name="selection-translator", daemon=True)
        self.worker_thread.start()
