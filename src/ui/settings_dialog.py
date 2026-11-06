"""Category-based settings for translation, models and local history."""
import copy
from pathlib import Path
import re
import threading

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QFrame, QHBoxLayout,
    QKeySequenceEdit, QLabel, QLineEdit, QListWidget, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QSpinBox, QStackedWidget, QTextBrowser, QVBoxLayout, QWidget,
)
from ..utils.history_store import HistoryStore
from ..utils.localization import SUPPORTED_APP_LANGUAGES, get_language_name, get_ui_string
from ..utils.model_catalog import MODELS, download_model
from ..utils.settings_manager import SettingsManager
from ..translator.plamo_runtime import resource_root


def parse_shortcut(sequence):
    parts = sequence.upper().replace("CONTROL", "CTRL").split("+")
    if len(parts) < 2 or not re.fullmatch(r"[A-Z0-9]", parts[-1]):
        raise ValueError("invalid shortcut")
    modifiers = parts[:-1]
    if len(set(modifiers)) != len(modifiers) or any(p not in ("CTRL", "ALT", "SHIFT") for p in modifiers):
        raise ValueError("invalid modifiers")
    return sum({"CTRL": 2, "ALT": 1, "SHIFT": 4}[p] for p in modifiers), ord(parts[-1])


class DownloadBridge(QObject):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_manager = SettingsManager()
        self.app_language = self.settings_manager.get_app_language()
        self._downloading = False
        self._cancel_download = threading.Event()
        self._close_after_download = False
        self.bridge = DownloadBridge(self)
        self.bridge.progress.connect(self._download_progress)
        self.bridge.finished.connect(self._download_finished)
        self.setWindowTitle(self.tr_ui("settings"))
        self.resize(900, 700)
        self.setMinimumSize(760, 540)
        self.setStyleSheet(parent.styleSheet() if parent else self._default_style())
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        body = QHBoxLayout()
        body.setSpacing(0)
        self.nav = QListWidget()
        self.nav.setObjectName("settingsNav")
        self.nav.setFixedWidth(205)
        for key in ("general", "translation_method", "cloud_ocr", "shortcuts", "history", "about"):
            self.nav.addItem(self.tr_ui(key))
        body.addWidget(self.nav)
        self.pages = QStackedWidget()
        body.addWidget(self.pages, 1)
        outer.addLayout(body, 1)
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self._general_page()
        self._translation_page()
        self._cloud_page()
        self._shortcuts_page()
        self._history_page()
        self._about_page()
        footer = QFrame()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 15, 24, 15)
        footer_layout.addStretch()
        self.cancel_button = QPushButton(self.tr_ui("cancel"))
        self.cancel_button.clicked.connect(self.reject)
        self.save_button = QPushButton(self.tr_ui("save"))
        self.save_button.setObjectName("primary")
        self.save_button.clicked.connect(self._save_settings)
        footer_layout.addWidget(self.cancel_button)
        footer_layout.addWidget(self.save_button)
        outer.addWidget(footer)
        self.nav.setCurrentRow(0)
        self._load_settings()

    def _default_style(self):
        from .theme import stylesheet
        return stylesheet()

    def tr_ui(self, key, **kwargs):
        return get_ui_string(self.app_language, key, **kwargs)

    def _page(self, key):
        page = QWidget()
        page.setObjectName("settingsContent")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(34, 28, 34, 28)
        layout.setSpacing(18)
        heading = QLabel(self.tr_ui(key))
        heading.setObjectName("heading")
        layout.addWidget(heading)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        self.pages.addWidget(scroll)
        return layout

    def _note(self, layout, text):
        label = QLabel(text)
        label.setWordWrap(True)
        label.setObjectName("muted")
        layout.addWidget(label)
        return label

    def _combo(self, options):
        combo = QComboBox()
        for label, value in options:
            combo.addItem(label, value)
        return combo

    def _general_page(self):
        layout = self._page("general")
        form = QFormLayout()
        form.setSpacing(18)
        languages = [(get_language_name(code), code) for code in SUPPORTED_APP_LANGUAGES]
        self.app_language_combo = self._combo(languages)
        self.target_language_combo = self._combo(languages)
        self.theme_combo = self._combo([(self.tr_ui("theme_" + k), k) for k in ("system", "light", "dark")])
        form.addRow(self.tr_ui("ui_language"), self.app_language_combo)
        form.addRow(self.tr_ui("target_language"), self.target_language_combo)
        form.addRow(self.tr_ui("appearance"), self.theme_combo)
        layout.addLayout(form)
        layout.addStretch()

    def _translation_page(self):
        layout = self._page("translation_method")
        self.provider_combo = self._combo([(self.tr_ui("provider_local"), "plamo"), (self.tr_ui("provider_cloud"), "gemini")])
        self.provider_combo.hide()
        self.provider_buttons = []
        provider_row = QHBoxLayout()
        self.provider_group = QButtonGroup(self)
        self.provider_group.setExclusive(True)
        for index, key in enumerate(("provider_local", "provider_cloud")):
            button = QPushButton(self.tr_ui(key))
            button.setObjectName("providerChoice")
            button.setMinimumHeight(58)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, i=index: self.provider_combo.setCurrentIndex(i))
            self.provider_group.addButton(button, index)
            self.provider_buttons.append(button)
            provider_row.addWidget(button, 1)
        layout.addLayout(provider_row)
        self._note(layout, self.tr_ui("provider_note"))
        self.local_group = QWidget()
        local = QVBoxLayout(self.local_group)
        local.setContentsMargins(0, 8, 0, 0)
        local.setSpacing(14)
        self.profile_combo = self._combo([(self.tr_ui("profile_light"), "lightweight"), (self.tr_ui("profile_quality"), "quality")])
        self.device_combo = self._combo([(self.tr_ui("device_" + key), key) for key in ("auto", "cpu", "gpu")])
        form = QFormLayout()
        form.setSpacing(16)
        form.addRow(self.tr_ui("local_model_choice"), self.profile_combo)
        form.addRow(self.tr_ui("device"), self.device_combo)
        local.addLayout(form)
        self._note(local, self.tr_ui("device_note"))
        local.addWidget(QLabel(self.tr_ui("model_location")))
        self.model_path_edit = QLineEdit()
        browse = QPushButton(self.tr_ui("browse"))
        self.browse_button = browse
        browse.clicked.connect(self._browse_model)
        row = QHBoxLayout()
        row.addWidget(self.model_path_edit, 1)
        row.addWidget(browse)
        local.addLayout(row)
        self.download_button = QPushButton(self.tr_ui("download"))
        self.download_button.clicked.connect(self._download_model)
        local.addWidget(self.download_button)
        self._note(local, self.tr_ui("download_note"))
        self.download_progress = QProgressBar()
        self.download_progress.setRange(0, 100)
        self.download_progress.hide()
        local.addWidget(self.download_progress)
        self.download_status = self._note(local, "")
        runtime = getattr(self.parent(), "runtime", None)
        status = runtime.model_name if runtime is not None and runtime.ready else self.tr_ui("not_ready")
        self._note(local, status)
        self.reload_button = QPushButton(self.tr_ui("reload"))
        self.reload_button.clicked.connect(self._save_and_reload)
        local.addWidget(self.reload_button)
        self.advanced_button = QPushButton("▸ " + self.tr_ui("advanced"))
        self.advanced_button.setObjectName("ghost")
        self.advanced_button.setCheckable(True)
        self.advanced_widget = QWidget()
        advanced = QFormLayout(self.advanced_widget)
        self.cpu_runtime_edit = QLineEdit()
        self.gpu_runtime_edit = QLineEdit()
        advanced.addRow(self.tr_ui("cpu_runtime"), self.cpu_runtime_edit)
        advanced.addRow(self.tr_ui("gpu_runtime"), self.gpu_runtime_edit)
        note = QLabel(self.tr_ui("format_note"))
        note.setWordWrap(True)
        advanced.addRow(note)
        self.advanced_widget.hide()
        self.advanced_button.toggled.connect(self.advanced_widget.setVisible)
        local.addWidget(self.advanced_button)
        local.addWidget(self.advanced_widget)
        layout.addWidget(self.local_group)
        self._note(layout, self.tr_ui("save_reload_note"))
        layout.addStretch()
        self.provider_combo.currentIndexChanged.connect(self._provider_changed)
        self.profile_combo.currentIndexChanged.connect(self._profile_changed)

    def _cloud_page(self):
        layout = self._page("cloud_ocr")
        self._note(layout, self.tr_ui("api_note"))
        form = QFormLayout()
        form.setSpacing(18)
        self.gemini_api_key_edit = QLineEdit()
        self.gemini_api_key_edit.setEchoMode(QLineEdit.Password)
        self.llm_mode_combo = self._combo([(self.tr_ui("llm_auto"), "auto"), (self.tr_ui("llm_custom"), "custom")])
        self.custom_model_edit = QLineEdit()
        self.custom_model_edit.setPlaceholderText("gemini-3.5-flash-lite")
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(10, 300)
        self.timeout_spin.setSuffix(" s")
        form.addRow(self.tr_ui("google_api_key"), self.gemini_api_key_edit)
        form.addRow(self.tr_ui("llm_setting"), self.llm_mode_combo)
        form.addRow(self.tr_ui("model_name"), self.custom_model_edit)
        form.addRow(self.tr_ui("timeout"), self.timeout_spin)
        self.llm_mode_combo.currentIndexChanged.connect(lambda: self.custom_model_edit.setEnabled(self.llm_mode_combo.currentData() == "custom"))
        layout.addLayout(form)
        self._note(layout, self.tr_ui("auto_model_note"))
        layout.addStretch()

    def _shortcuts_page(self):
        layout = self._page("shortcuts")
        self.capture_shortcut = QKeySequenceEdit()
        self.selection_shortcut = QKeySequenceEdit()
        form = QFormLayout()
        form.setSpacing(18)
        form.addRow(self.tr_ui("shortcut_capture"), self.capture_shortcut)
        form.addRow(self.tr_ui("shortcut_selection"), self.selection_shortcut)
        layout.addLayout(form)
        self._note(layout, self.tr_ui("shortcut_note"))
        layout.addStretch()

    def _history_page(self):
        layout = self._page("history")
        self.history_enabled = QCheckBox(self.tr_ui("save_history"))
        self.history_limit = QSpinBox()
        self.history_limit.setRange(10, 5000)
        layout.addWidget(self.history_enabled)
        form = QFormLayout()
        form.addRow(self.tr_ui("history_limit"), self.history_limit)
        layout.addLayout(form)
        self._note(layout, self.tr_ui("history_note"))
        self.clear_button = QPushButton(self.tr_ui("clear_history"))
        self.clear_button.setObjectName("danger")
        self.clear_button.clicked.connect(self._clear_history)
        layout.addWidget(self.clear_button)
        layout.addStretch()

    def _about_page(self):
        layout = self._page("about")
        layout.addWidget(QLabel("スクショAI翻訳  ·  Built with PLaMo"))
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        notice = resource_root() / "docs/THIRD_PARTY_NOTICES.md"
        license_path = resource_root() / "docs/licenses/PLaMo-ja.txt"
        browser.setPlainText(notice.read_text(encoding="utf-8") + "\n\n" + license_path.read_text(encoding="utf-8"))
        layout.addWidget(browser, 1)

    def _set_combo(self, combo, value):
        combo.blockSignals(True)
        combo.setCurrentIndex(max(0, combo.findData(value)))
        combo.blockSignals(False)

    def _load_settings(self):
        settings = self.settings_manager
        self._paths = {p: settings.get_setting("local_model", p + "_path") for p in MODELS}
        self._current_profile = settings.get_local_profile()
        for combo, value in [(self.app_language_combo, settings.get_app_language()),
                             (self.target_language_combo, settings.get_target_language()),
                             (self.theme_combo, settings.get_setting("ui", "theme", "system")),
                             (self.provider_combo, settings.get_translation_provider()),
                             (self.profile_combo, self._current_profile),
                             (self.device_combo, settings.get_setting("local_model", "device", "auto")),
                             (self.llm_mode_combo, settings.get_llm_mode())]:
            self._set_combo(combo, value)
        self.model_path_edit.setText(self._paths[self._current_profile])
        self.cpu_runtime_edit.setText(settings.get_setting("local_model", "llama_server_path", ""))
        self.gpu_runtime_edit.setText(settings.get_setting("local_model", "gpu_server_path", ""))
        self.gemini_api_key_edit.setText(settings.get_api_key() or "")
        self.custom_model_edit.setText(settings.get_custom_model())
        self.custom_model_edit.setEnabled(settings.get_llm_mode() == "custom")
        self.timeout_spin.setValue(settings.get_timeout())
        self.capture_shortcut.setKeySequence(QKeySequence(settings.get_setting("shortcuts", "capture")))
        self.selection_shortcut.setKeySequence(QKeySequence(settings.get_setting("shortcuts", "selection")))
        self.history_enabled.setChecked(settings.get_setting("history", "enabled", True))
        self.history_limit.setValue(settings.get_setting("history", "limit", 500))
        self._provider_changed()

    def _provider_changed(self):
        self.local_group.setVisible(self.provider_combo.currentData() == "plamo")
        self.provider_buttons[self.provider_combo.currentIndex()].setChecked(True)

    def _profile_changed(self):
        if not hasattr(self, "_paths"):
            return
        self._paths[self._current_profile] = self.model_path_edit.text().strip()
        self._current_profile = self.profile_combo.currentData()
        self.model_path_edit.setText(self._paths[self._current_profile])

    def _browse_model(self):
        path, _ = QFileDialog.getOpenFileName(self, self.tr_ui("model_location"), self.model_path_edit.text(), "GGUF (*.gguf)")
        if path:
            self.model_path_edit.setText(path)

    def _download_model(self):
        if self._downloading:
            return
        path = self.model_path_edit.text().strip()
        if not path:
            self._browse_model()
            path = self.model_path_edit.text().strip()
            if not path:
                return
        self._downloading = True
        self._cancel_download.clear()
        self._lock_download_ui(True)
        self.download_progress.show()
        self.download_progress.setValue(0)
        profile = self._current_profile
        def run():
            error = ""
            try:
                if Path(path).is_file():
                    import hashlib
                    with Path(path).open("rb") as file:
                        digest = hashlib.file_digest(file, "sha256").hexdigest()
                    if digest != MODELS[profile]["sha256"]:
                        raise RuntimeError(self.tr_ui("invalid_model_path"))
                else:
                    download_model(profile, path, lambda received,total: self.bridge.progress.emit(int(received * 100 / total)), self._cancel_download.is_set)
            except Exception as exc:
                error = str(exc)
            self.bridge.finished.emit(error)
        threading.Thread(target=run, daemon=True, name="model-download").start()

    def _lock_download_ui(self, locked):
        for widget in (self.nav, self.provider_combo, self.profile_combo, self.device_combo,
                       self.model_path_edit, self.browse_button, self.download_button, self.reload_button, self.save_button):
            widget.setEnabled(not locked)
        for button in self.provider_buttons:
            button.setEnabled(not locked)

    def _download_progress(self, percent):
        self.download_progress.setValue(percent)
        self.download_status.setText(f"{percent}%")

    def _download_finished(self, error):
        self._downloading = False
        self._lock_download_ui(False)
        self.download_progress.hide()
        self.download_status.setText(error or self.tr_ui("downloaded"))
        if self._close_after_download:
            super().reject()

    def _save_and_reload(self):
        self.force_reload = True
        self._save_settings()

    def _save_settings(self):
        capture = self.capture_shortcut.keySequence().toString(QKeySequence.PortableText)
        selection = self.selection_shortcut.keySequence().toString(QKeySequence.PortableText)
        try:
            first, second = parse_shortcut(capture), parse_shortcut(selection)
            if first == second:
                raise ValueError("duplicate")
        except ValueError:
            QMessageBox.warning(self, self.tr_ui("settings"), self.tr_ui("shortcut_invalid"))
            return
        if self.llm_mode_combo.currentData() == "custom" and not self.custom_model_edit.text().strip():
            QMessageBox.warning(self, self.tr_ui("settings"), self.tr_ui("validation_custom_model"))
            return
        if self.provider_combo.currentData() == "gemini" and not self.gemini_api_key_edit.text().strip():
            QMessageBox.warning(self, self.tr_ui("settings"), self.tr_ui("api_required"))
            return
        settings = self.settings_manager
        before = copy.deepcopy(settings.settings)
        self._paths[self._current_profile] = self.model_path_edit.text().strip()
        for category, values in {
            "translation": {"provider": self.provider_combo.currentData()},
            "local_model": {"profile": self._current_profile, "device": self.device_combo.currentData(),
                            "lightweight_path": self._paths["lightweight"], "quality_path": self._paths["quality"],
                            "llama_server_path": self.cpu_runtime_edit.text().strip(), "gpu_server_path": self.gpu_runtime_edit.text().strip()},
            "history": {"enabled": self.history_enabled.isChecked(), "limit": self.history_limit.value()},
            "shortcuts": {"capture": capture, "selection": selection},
            "ui": {"theme": self.theme_combo.currentData()},
        }.items():
            for key, value in values.items():
                settings.set_setting(category, key, value)
        settings.set_app_language(self.app_language_combo.currentData())
        settings.set_target_language(self.target_language_combo.currentData())
        settings.set_api_key("gemini", self.gemini_api_key_edit.text().strip())
        settings.set_custom_model(self.custom_model_edit.text().strip())
        settings.set_llm_mode(self.llm_mode_combo.currentData())
        settings.set_timeout(self.timeout_spin.value())
        if settings.save_settings():
            self.accept()
        else:
            settings.settings = before
            QMessageBox.warning(self, self.tr_ui("settings"), self.tr_ui("save_failed"))

    def _clear_history(self):
        if QMessageBox.question(self, self.tr_ui("history"), self.tr_ui("clear_confirm"), QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            HistoryStore(self.settings_manager.config_dir).clear()
            self.clear_button.setEnabled(False)

    def reject(self):
        if self._downloading:
            self._close_after_download = True
            self._cancel_download.set()
            self.cancel_button.setEnabled(False)
            return
        super().reject()

    def closeEvent(self, event):
        if self._downloading:
            self.reject()
            event.ignore()
        else:
            super().closeEvent(event)
