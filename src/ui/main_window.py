"""History-first translation workspace with a persistent local model."""
import base64
import ctypes
from ctypes import wintypes
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

from PyQt5.QtCore import QBuffer, QIODevice, QMimeData, QObject, Qt, QTimer, QSize, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QTextBlockFormat, QTextCursor
from PyQt5.QtWidgets import (
    QAction, QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QProgressBar,
    QPushButton, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)
from .screen_capture import ScreenCaptureWindow
from .settings_dialog import SettingsDialog, parse_shortcut
from .theme import icon, stylesheet
from ..translator.plamo_runtime import PlamoRuntime
from ..utils.history_store import HistoryStore
from ..utils.localization import SUPPORTED_APP_LANGUAGES, get_language_name, get_ui_string
from ..utils.settings_manager import SettingsManager
from ..utils.utils import sanitize_sensitive_data

WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000


class ResultBridge(QObject):
    result_ready = pyqtSignal(dict)
    model_ready = pyqtSignal(str)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings_manager = SettingsManager()
        self.history_store = HistoryStore(self.settings_manager.config_dir)
        self.runtime = PlamoRuntime(self.settings_manager)
        self.bridge = ResultBridge(self)
        self.bridge.result_ready.connect(self._handle_translation_result)
        self.bridge.model_ready.connect(self._handle_model_ready)
        self.worker_thread = None
        self._model_loading = False
        self._closing = False
        self._selection_pending = False
        self.capture_window = None
        self._captured = False
        self._registered_hotkeys = []
        self._hotkey_warnings = []
        self._current_history_id = None
        self._current_result = None
        self._active_job = None
        self.extracted_text = ""
        self.translated_text = ""
        self._init_ui()
        self._register_global_hotkey()
        self._load_history()
        QTimer.singleShot(0, self._load_local_model)

    def tr_ui(self, key, **kwargs):
        return get_ui_string(self.settings_manager.get_app_language(), key, **kwargs)

    def _label(self, text="", role=""):
        label = QLabel(text)
        if role:
            label.setObjectName(role)
        return label

    def _button(self, text, callback, glyph=None, primary=False):
        button = QPushButton(text)
        if glyph:
            button.setIcon(icon(glyph))
            button.setIconSize(QSize(19, 19))
        if primary:
            button.setObjectName("primary")
        button.clicked.connect(callback)
        return button

    def _init_ui(self):
        self.setMinimumSize(900, 620)
        self.resize(1180, 800)
        self.setWindowTitle("スクショAI翻訳")
        central = QWidget()
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(264)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(14, 24, 14, 18)
        side.setSpacing(15)
        side.addWidget(self._label("スクショAI翻訳", "brand"))
        self.new_button = self._button(self.tr_ui("new_translation"), self._new_translation, "plus")
        side.addWidget(self.new_button)
        self.history_search = QLineEdit()
        self.history_search.setPlaceholderText(self.tr_ui("search_history"))
        self.history_search.addAction(icon("search"), QLineEdit.LeadingPosition)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(150)
        self.search_timer.timeout.connect(self._load_history)
        self.history_search.textChanged.connect(lambda: self.search_timer.start())
        side.addWidget(self.history_search)
        self.history_list = QListWidget()
        self.history_list.setSpacing(1)
        self.history_list.itemClicked.connect(self._open_history)
        self.history_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self._history_menu)
        side.addWidget(self.history_list, 1)
        self.history_empty_label = self._label(self.tr_ui("history_empty"), "muted")
        self.history_empty_label.setWordWrap(True)
        side.addWidget(self.history_empty_label)
        line = QFrame(); line.setObjectName("divider"); side.addWidget(line)
        self.model_status = self._label("", "metadata")
        self.model_status.setWordWrap(True)
        side.addWidget(self.model_status)
        side.addWidget(self._label("Built with PLaMo", "muted"))
        self.settings_button = self._button(self.tr_ui("settings"), self._show_settings_dialog, "settings")
        self.settings_button.setObjectName("ghost")
        side.addWidget(self.settings_button)
        outer.addWidget(self.sidebar)
        self.workspace = QWidget(); self.workspace.setObjectName("workspace")
        work = QVBoxLayout(self.workspace)
        work.setContentsMargins(30, 20, 30, 18)
        work.setSpacing(15)
        toolbar = QHBoxLayout()
        self.sidebar_button = self._button("", lambda: self.sidebar.setVisible(not self.sidebar.isVisible()), "sidebar")
        self.sidebar_button.setFixedWidth(36)
        self.sidebar_button.setObjectName("ghost")
        toolbar.addWidget(self.sidebar_button)
        self.source_language_label = self._label(self.tr_ui("auto_detect"), "metadata")
        toolbar.addWidget(self.source_language_label)
        toolbar.addWidget(self._label("→"))
        self.target_combo = QComboBox()
        for code in SUPPORTED_APP_LANGUAGES:
            self.target_combo.addItem(get_language_name(code), code)
        self.target_combo.setCurrentIndex(self.target_combo.findData(self.settings_manager.get_target_language()))
        self.target_combo.currentIndexChanged.connect(self._target_changed)
        toolbar.addWidget(self.target_combo)
        toolbar.addStretch()
        self.capture_button = self._button(self.tr_ui("capture"), self.start_capture, "capture", True)
        toolbar.addWidget(self.capture_button)
        work.addLayout(toolbar)
        divider = QFrame(); divider.setObjectName("divider"); work.addWidget(divider)
        self.mode_label = self._label("", "metadata"); work.addWidget(self.mode_label)
        self.result_splitter = QSplitter(Qt.Vertical)
        translation_panel = QWidget()
        translation_layout = QVBoxLayout(translation_panel)
        translation_layout.setContentsMargins(5, 10, 5, 4)
        translation_layout.setSpacing(17)
        result_header = QHBoxLayout()
        self.result_heading = self._label(self.tr_ui("result"), "sectionTitle")
        result_header.addWidget(self.result_heading)
        result_header.addStretch()
        self.copy_translation_button = self._button(self.tr_ui("copy_button"), self._copy_translation_text, "copy")
        self.copy_translation_button.setObjectName("ghost")
        result_header.addWidget(self.copy_translation_button)
        translation_layout.addLayout(result_header)
        self.translation_text_edit = QTextEdit()
        self.translation_text_edit.setObjectName("translation")
        self.translation_text_edit.setReadOnly(True)
        self.translation_text_edit.setAcceptRichText(False)
        self.translation_text_edit.setPlaceholderText(self.tr_ui("empty_result"))
        translation_layout.addWidget(self.translation_text_edit, 1)
        self.metadata_label = self._label("", "metadata")
        self.metadata_label.setWordWrap(True)
        translation_layout.addWidget(self.metadata_label)
        self.result_splitter.addWidget(translation_panel)
        self.original_widget = QWidget(); self.original_widget.setObjectName("originalPanel")
        original = QVBoxLayout(self.original_widget)
        original.setContentsMargins(18, 14, 18, 12)
        original_header = QHBoxLayout()
        self.source_heading = self._label(self.tr_ui("source"), "sectionTitle")
        original_header.addWidget(self.source_heading)
        original_header.addStretch()
        self.copy_original_button = self._button(self.tr_ui("copy_button"), self._copy_original_text, "copy")
        self.copy_original_button.setObjectName("ghost")
        original_header.addWidget(self.copy_original_button)
        original.addLayout(original_header)
        self.original_text_edit = QTextEdit()
        self.original_text_edit.setObjectName("original")
        self.original_text_edit.setReadOnly(True)
        self.original_text_edit.setAcceptRichText(False)
        self.original_text_edit.setPlaceholderText(self.tr_ui("empty_source"))
        original.addWidget(self.original_text_edit, 1)
        self.result_splitter.addWidget(self.original_widget)
        self.result_splitter.setSizes([430, 215])
        self.result_splitter.setChildrenCollapsible(False)
        self.result_splitter.setStretchFactor(0, 2)
        self.result_splitter.setStretchFactor(1, 1)
        work.addWidget(self.result_splitter, 1)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        work.addWidget(self.progress_bar)
        footer = QHBoxLayout()
        self.hint_label = self._label("", "muted")
        self.hint_label.setWordWrap(True)
        footer.addWidget(self.hint_label, 1)
        self.paste_button = self._button(self.tr_ui("paste_translate"), self._translate_clipboard)
        footer.addWidget(self.paste_button)
        work.addLayout(footer)
        self.notice_label = self._label("", "notice"); self.notice_label.setWordWrap(True)
        work.addWidget(self.notice_label)
        self.message_label = self._label("", "metadata"); self.message_label.setWordWrap(True)
        work.addWidget(self.message_label)
        outer.addWidget(self.workspace, 1)
        self.setCentralWidget(central)
        self._apply_texts()
        self._apply_theme()
        self._set_busy(False)

    def _apply_theme(self):
        theme = self.settings_manager.get_setting("ui", "theme", "system")
        dark = theme == "dark" or (theme == "system" and QApplication.palette().window().color().lightness() < 128)
        self.setStyleSheet(stylesheet(dark))

    def _apply_texts(self):
        for button, key in ((self.new_button,"new_translation"), (self.settings_button,"settings"),
                            (self.capture_button,"capture"), (self.paste_button,"paste_translate"),
                            (self.copy_original_button,"copy_button"), (self.copy_translation_button,"copy_button")):
            button.setText(self.tr_ui(key))
        self.history_search.setPlaceholderText(self.tr_ui("search_history"))
        self.result_heading.setText(self.tr_ui("result"))
        self.source_heading.setText(self.tr_ui("source"))
        self.translation_text_edit.setPlaceholderText(self.tr_ui("empty_result"))
        self.original_text_edit.setPlaceholderText(self.tr_ui("empty_source"))
        self.hint_label.setText(self.tr_ui("shortcut_hint", shortcut=self.settings_manager.get_setting("shortcuts", "selection")))
        self.capture_button.setToolTip(self.settings_manager.get_setting("shortcuts", "capture"))
        local = self.settings_manager.get_translation_provider() == "plamo"
        self.mode_label.setText(self.tr_ui("provider_local" if local else "provider_cloud"))
        self.notice_label.setText(self.tr_ui("local_notice" if local else "cloud_notice"))
        self.source_language_label.setText(self.tr_ui("auto_detect"))

    def _notify(self, message):
        self.message_label.setText(message)

    def _set_busy(self, busy):
        local = self.settings_manager.get_translation_provider() == "plamo"
        available = not local or self.runtime.ready
        self.capture_button.setEnabled(not busy and available and not self._model_loading)
        self.paste_button.setEnabled(not busy and available and not self._model_loading)
        for widget in (self.new_button, self.settings_button, self.target_combo, self.history_list):
            widget.setEnabled(not busy and not self._selection_pending)
        self.settings_button.setEnabled(not busy and not self._selection_pending and not self._model_loading)
        self.progress_bar.setVisible(busy)
        self.copy_original_button.setEnabled(bool(self.extracted_text))
        self.copy_translation_button.setEnabled(bool(self.translated_text))

    def _load_local_model(self):
        if self.settings_manager.get_translation_provider() == "gemini":
            self.model_status.setText("● " + self.tr_ui("cloud_ready"))
            self._set_busy(False)
            return
        self._model_loading = True
        self.model_status.setText("◌ " + self.tr_ui("loading"))
        self.settings_button.setEnabled(False)
        self._set_busy(False)
        self.settings_button.setEnabled(False)
        runtime = self.runtime
        def load():
            error = ""
            try:
                runtime.start()
            except Exception as exc:
                runtime.close()
                error = sanitize_sensitive_data(str(exc))
            if not self._closing:
                self.bridge.model_ready.emit(error)
        threading.Thread(target=load, daemon=True, name="plamo-loader").start()

    def _handle_model_ready(self, error):
        if self._closing:
            return
        self._model_loading = False
        self.model_status.setText(("○ " + self.tr_ui("not_ready")) if error else ("● " + self.tr_ui("local_ready") + " · " + self.runtime.device_used))
        self._notify(error or getattr(self.runtime, "fallback_reason", "") or " / ".join(self._hotkey_warnings))
        self._set_busy(False)

    def _can_translate(self):
        if self.worker_thread is not None or self._selection_pending or self._model_loading or QApplication.activeModalWidget() is not None:
            return False
        if self.capture_window is not None:
            return False
        local = self.settings_manager.get_translation_provider() == "plamo"
        if local and not self.runtime.ready:
            self._notify(self.tr_ui("model_not_ready"))
            return False
        if not local and not self.settings_manager.get_api_key():
            self._notify(self.tr_ui("api_required"))
            return False
        return True

    def _target_changed(self):
        previous = self.settings_manager.get_target_language()
        self.settings_manager.set_target_language(self.target_combo.currentData())
        if not self.settings_manager.save_settings():
            self.settings_manager.set_target_language(previous)
            self.target_combo.blockSignals(True)
            self.target_combo.setCurrentIndex(self.target_combo.findData(previous))
            self.target_combo.blockSignals(False)
            self._notify(self.tr_ui("save_failed"))

    def _new_translation(self):
        if self.worker_thread is not None:
            return
        self._current_history_id = None
        self._current_result = None
        self.extracted_text = self.translated_text = ""
        self.translation_text_edit.clear(); self.original_text_edit.clear()
        self.metadata_label.clear(); self.history_list.clearSelection()
        self.source_language_label.setText(self.tr_ui("auto_detect"))
        self._set_busy(False)
        self._notify("")

    def _load_history(self):
        self.history_list.clear()
        query = self.history_search.text().strip()
        try:
            rows = self.history_store.search(query, self.settings_manager.get_setting("history", "limit", 500))
        except Exception as exc:
            self._notify(str(exc)); rows = []
        self.history_empty_label.setVisible(not rows)
        self.history_empty_label.setText(self.tr_ui("no_matches" if query else "history_empty"))
        group = None
        for record in rows:
            dt = datetime.fromisoformat(record["created_at"]).astimezone()
            category = "today" if dt.date() == date.today() else "yesterday" if dt.date() == date.today()-timedelta(days=1) else "earlier"
            if category != group:
                heading = QListWidgetItem(self.tr_ui(category))
                heading.setFlags(Qt.NoItemFlags)
                heading.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
                self.history_list.addItem(heading)
                group = category
            title = (record["original"] or record["translated"]).replace("\n", " ").strip()
            title = title[:23] + ("…" if len(title) > 23 else "")
            metadata = f"{get_language_name(record['target_lang'])} · {dt.strftime('%H:%M')} · {'PLaMo' if record['provider']=='plamo' else 'Gemini'}"
            item = QListWidgetItem(title + "\n" + metadata)
            item.setData(Qt.UserRole, record["id"])
            item.setToolTip((record["original"] or record["translated"])[:200])
            self.history_list.addItem(item)
            if record["id"] == self._current_history_id:
                item.setSelected(True)

    def _open_history(self, item):
        if self.worker_thread is not None or not item.data(Qt.UserRole):
            return
        record = self.history_store.get(item.data(Qt.UserRole))
        if not record:
            self._load_history(); return
        self._current_history_id = record["id"]
        result = {"extracted_text": record["original"], "translated_text": record["translated"],
                  "source_language": record["source_lang"], "last_used_model": record["model"],
                  "provider": record["provider"], "created_at": record["created_at"], "target_lang": record["target_lang"]}
        self._display_result(result)
        self._notify("")

    def _history_menu(self, position):
        item = self.history_list.itemAt(position)
        if item is None or not item.data(Qt.UserRole) or self.worker_thread is not None:
            return
        menu = QMenu(self)
        action = menu.addAction(self.tr_ui("delete_history"))
        if menu.exec_(self.history_list.mapToGlobal(position)) == action:
            if QMessageBox.question(self, self.tr_ui("history"), self.tr_ui("delete_confirm"), QMessageBox.Yes|QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
                record_id = item.data(Qt.UserRole)
                self.history_store.delete(record_id)
                if record_id == self._current_history_id:
                    self._new_translation()
                self._load_history()

    def _display_result(self, result):
        self._current_result = dict(result)
        self.extracted_text = result.get("extracted_text", "")
        self.translated_text = result.get("translated_text", "")
        self.translation_text_edit.setPlainText(self.translated_text)
        cursor = self.translation_text_edit.textCursor()
        cursor.select(QTextCursor.Document)
        block = QTextBlockFormat(); block.setLineHeight(160, QTextBlockFormat.ProportionalHeight)
        cursor.mergeBlockFormat(block)
        cursor.clearSelection(); cursor.movePosition(QTextCursor.Start)
        self.translation_text_edit.setTextCursor(cursor)
        self.original_text_edit.setPlainText(self.extracted_text)
        lang = result.get("source_language", "auto")
        self.source_language_label.setText(get_language_name(lang) if lang in SUPPORTED_APP_LANGUAGES else self.tr_ui("auto_detect"))
        target = get_language_name(result.get("target_lang", self.settings_manager.get_target_language()))
        when = datetime.fromisoformat(result["created_at"]).astimezone().strftime("%m/%d %H:%M") if result.get("created_at") else datetime.now().strftime("%H:%M")
        self.metadata_label.setText(f"{target} · {when} · {result.get('last_used_model') or ''}")
        self._set_busy(False)

    def start_capture(self):
        if not self._can_translate() or self.capture_window is not None:
            return
        if not self.settings_manager.get_api_key():
            self._notify(self.tr_ui("api_required")); return
        self._captured = False
        self.hide()
        QApplication.processEvents()
        self.capture_window = ScreenCaptureWindow()
        self.capture_window.setAttribute(Qt.WA_DeleteOnClose)
        self.capture_window.region_selected.connect(self._on_capture_complete)
        self.capture_window.destroyed.connect(self._capture_closed)
        self.capture_window.show()

    def _capture_closed(self):
        self.capture_window = None
        if not self._closing:
            self.show()

    def _on_capture_complete(self, pixmap):
        if not pixmap or pixmap.isNull():
            return
        buffer = QBuffer(); buffer.open(QIODevice.ReadWrite)
        pixmap.save(buffer, "PNG")
        image_bytes = bytes(buffer.data()); buffer.close()
        self._captured = True
        self.show()
        self._start_job(image_bytes=image_bytes)

    def _translate_clipboard(self):
        if not self._can_translate():
            return
        text = QApplication.clipboard().text()
        if not text.strip():
            self._notify(self.tr_ui("selection_empty")); return
        self._start_job(text=text)

    def _start_job(self, image_bytes=None, text=None):
        provider = self.settings_manager.get_translation_provider()
        target = self.settings_manager.get_target_language()
        self._active_job = {"provider": provider, "target_lang": target, "kind": "image" if image_bytes else "text"}
        self._notify(self.tr_ui("busy"))
        self._set_busy(True)
        self.worker_thread = threading.Thread(target=self._run_job, args=(image_bytes,text,dict(self._active_job)), daemon=True, name="translation-worker")
        self.worker_thread.start()

    def _run_job(self, image_bytes, text, job):
        result = {"extracted_text": text or "", "error_message": None}
        try:
            if job["provider"] == "plamo" and text is not None:
                result["translated_text"] = self.runtime.translate(text, job["target_lang"])
                result["last_used_model"] = self.runtime.model_name
            else:
                payload = {"provider": job["provider"], "target_lang": job["target_lang"], "text": text,
                           "image_bytes_b64": base64.b64encode(image_bytes or b"").decode("ascii")}
                with tempfile.TemporaryDirectory(prefix="ocr-job-", dir=self.settings_manager.config_dir) as folder:
                    input_path, output_path = Path(folder)/"input.json", Path(folder)/"output.json"
                    input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                    command = [sys.executable,"--translation-worker"] if getattr(sys,"frozen",False) else [sys.executable,"-m","src.translator.translation_job_runner"]
                    process = subprocess.run(command + ["--input-json",str(input_path),"--output-json",str(output_path)],
                                             cwd=str(Path(__file__).resolve().parents[2]), capture_output=True,
                                             timeout=self.settings_manager.get_timeout()+30,
                                             creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
                    if process.returncode != 0 or not output_path.is_file():
                        raise RuntimeError("処理を完了できませんでした。API設定と通信状態を確認してください。")
                    result = json.loads(output_path.read_text(encoding="utf-8"))
                if job["provider"] == "plamo" and not result.get("error_message"):
                    if not result.get("extracted_text"):
                        raise RuntimeError("画像から文字を読み取れませんでした。")
                    result["translated_text"] = self.runtime.translate(result["extracted_text"], job["target_lang"])
                    result["last_used_model"] = self.runtime.model_name
            if not result.get("translated_text") and not result.get("error_message"):
                raise RuntimeError("翻訳結果がありません。")
        except Exception as exc:
            result["error_message"] = sanitize_sensitive_data(str(exc))
        result.update(job)
        self.bridge.result_ready.emit(result)

    def _handle_translation_result(self, result):
        self.worker_thread = None
        self._active_job = None
        self._set_busy(False)
        if result.get("error_message"):
            self._notify(result["error_message"])
            return
        self._current_history_id = None
        self._display_result(result)
        if self.settings_manager.get_setting("history", "enabled", True):
            try:
                self._current_history_id = self.history_store.add(result, result["target_lang"], result["provider"], result["kind"], self.settings_manager.get_setting("history","limit",500))
                self._load_history()
            except Exception as exc:
                self._notify(self.tr_ui("done") + " / " + str(exc))
                return
        self._notify(self.tr_ui("done"))
        self.show(); self.raise_(); self.activateWindow()

    def _copy_original_text(self):
        QApplication.clipboard().setText(self.original_text_edit.toPlainText())
        self._notify(self.tr_ui("copy_done"))

    def _copy_translation_text(self):
        QApplication.clipboard().setText(self.translation_text_edit.toPlainText())
        self._notify(self.tr_ui("copy_done"))

    def _show_settings_dialog(self):
        if self.worker_thread is not None or self._selection_pending or self._model_loading:
            return
        old_local = dict(self.settings_manager.settings["local_model"])
        old_provider = self.settings_manager.get_translation_provider()
        dialog = SettingsDialog(self)
        accepted = dialog.exec_()
        # Clearing history is immediate, even if other settings were cancelled.
        self._load_history()
        if self._current_history_id and not self.history_store.get(self._current_history_id):
            self._new_translation()
        if not accepted:
            dialog.deleteLater(); return
        self.settings_manager.reload_settings()
        self._apply_theme(); self._apply_texts()
        self.target_combo.blockSignals(True)
        self.target_combo.setCurrentIndex(self.target_combo.findData(self.settings_manager.get_target_language()))
        self.target_combo.blockSignals(False)
        self.history_store.trim(self.settings_manager.get_setting("history","limit",500))
        self._load_history()
        self._unregister_global_hotkey(); self._register_global_hotkey()
        if old_local != self.settings_manager.settings["local_model"] or old_provider != self.settings_manager.get_translation_provider() or getattr(dialog,"force_reload",False):
            self.runtime.close()
            self.runtime = PlamoRuntime(self.settings_manager)
            self._load_local_model()
        self._set_busy(False)
        dialog.deleteLater()

    def _register_global_hotkey(self):
        self._hotkey_warnings = []
        for hotkey_id, name in ((1,"capture"),(2,"selection")):
            sequence = self.settings_manager.get_setting("shortcuts",name)
            try:
                modifiers, key = parse_shortcut(sequence)
                if not ctypes.windll.user32.RegisterHotKey(wintypes.HWND(int(self.winId())), hotkey_id, modifiers|MOD_NOREPEAT, key):
                    raise RuntimeError(sequence)
                self._registered_hotkeys.append(hotkey_id)
            except Exception:
                self._hotkey_warnings.append(self.tr_ui("shortcut_conflict", shortcut=sequence))
        if self._hotkey_warnings:
            self._notify(" / ".join(self._hotkey_warnings))

    def _unregister_global_hotkey(self):
        for hotkey_id in self._registered_hotkeys:
            ctypes.windll.user32.UnregisterHotKey(wintypes.HWND(int(self.winId())),hotkey_id)
        self._registered_hotkeys.clear()

    def nativeEvent(self,event_type,message):
        if event_type == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam in (1,2):
                self.translate_selection() if msg.wParam == 2 else self.start_capture()
                return True,0
        return super().nativeEvent(event_type,message)

    def translate_selection(self):
        if not self._can_translate():
            return
        self._selection_pending = True
        self._selection_deadline = time.monotonic()+3
        self._selection_foreground = ctypes.windll.user32.GetForegroundWindow()
        self._set_busy(False)
        self._wait_for_hotkey_release()

    def _end_selection(self):
        self._selection_pending = False
        self._set_busy(False)

    def _wait_for_hotkey_release(self):
        if self._closing:
            return
        user32 = ctypes.windll.user32
        if user32.GetForegroundWindow() != self._selection_foreground:
            self._end_selection(); return
        _, selection_key = parse_shortcut(self.settings_manager.get_setting("shortcuts","selection"))
        if any(user32.GetAsyncKeyState(key)&0x8000 for key in (0x10,0x11,0x12,selection_key)):
            if time.monotonic()<self._selection_deadline:
                QTimer.singleShot(30,self._wait_for_hotkey_release)
            else:
                self._end_selection()
            return
        clipboard = QApplication.clipboard()
        saved = QMimeData()
        mime = clipboard.mimeData()
        if mime is not None:
            for fmt in mime.formats():
                saved.setData(fmt,mime.data(fmt))
        self._saved_clipboard = saved
        self._clipboard_sequence = user32.GetClipboardSequenceNumber()
        from pynput.keyboard import Controller,Key
        keyboard = Controller()
        try:
            with keyboard.pressed(Key.ctrl):
                keyboard.press("c"); keyboard.release("c")
        except Exception:
            self._end_selection(); self._saved_clipboard = None
            self._notify(self.tr_ui("selection_empty")); return
        self._selection_deadline = time.monotonic()+2
        QTimer.singleShot(50,self._read_selection)

    def _read_selection(self):
        if self._closing:
            return
        user32 = ctypes.windll.user32
        sequence = user32.GetClipboardSequenceNumber()
        if sequence == self._clipboard_sequence:
            if time.monotonic()<self._selection_deadline:
                QTimer.singleShot(50,self._read_selection); return
            self._end_selection(); self._saved_clipboard = None
            self._notify(self.tr_ui("selection_empty")); return
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if user32.GetClipboardSequenceNumber() == sequence:
            clipboard.setMimeData(self._saved_clipboard)
        self._saved_clipboard = None
        self._end_selection()
        if not text.strip():
            self._notify(self.tr_ui("selection_empty")); return
        self._start_job(text=text)

    def closeEvent(self,event):
        if self.worker_thread is not None:
            self._notify(self.tr_ui("status_processing_locked")); event.ignore(); return
        self._closing = True
        self._unregister_global_hotkey()
        self.runtime.close()
        if self.capture_window is not None:
            self.capture_window.close()
        event.accept()
        QApplication.instance().quit()
