"""
設定ダイアログモジュール
"""
import logging

from PyQt5.QtGui import QIntValidator
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..translator.translation_manager import TranslationManager
from ..utils.localization import SUPPORTED_APP_LANGUAGES, get_language_name, get_ui_string
from ..utils.settings_manager import SettingsManager

logger = logging.getLogger("ocr_translator")


class SettingsDialog(QDialog):
    """アプリケーション設定ダイアログ"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.settings_manager = SettingsManager()
        self.translation_manager = TranslationManager()
        self.app_language = self.settings_manager.get_app_language()

        self._init_ui()
        self._load_settings()

        logger.info("設定ダイアログを初期化しました")

    def tr_ui(self, key: str, **kwargs) -> str:
        return get_ui_string(self.app_language, key, **kwargs)

    def _init_ui(self):
        """UIの初期化"""
        self.setMinimumWidth(520)

        self.setStyleSheet(
            """
            QDialog {
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
            QLineEdit, QComboBox {
                font-family: "Yu Gothic UI", "Meiryo UI", sans-serif;
                font-size: 14px;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 5px;
                background-color: white;
            }
            QGroupBox {
                font-family: "Yu Gothic UI", "Meiryo UI", sans-serif;
                font-size: 14px;
                font-weight: bold;
                margin-top: 1ex;
                border: 1px solid #cccccc;
                border-radius: 5px;
                padding-top: 1ex;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 3px;
                background-color: #f0f0f0;
            }
            """
        )

        main_layout = QVBoxLayout(self)

        self.language_group = QGroupBox()
        language_form = QFormLayout(self.language_group)
        language_form.setContentsMargins(10, 20, 10, 10)
        language_form.setSpacing(12)

        self.app_language_label = QLabel()
        self.app_language_combo = QComboBox()
        for language_code in SUPPORTED_APP_LANGUAGES:
            self.app_language_combo.addItem(get_language_name(language_code), language_code)
        self.app_language_combo.currentIndexChanged.connect(self._on_app_language_changed)
        language_form.addRow(self.app_language_label, self.app_language_combo)
        main_layout.addWidget(self.language_group)

        api_container = QWidget()
        api_layout = QVBoxLayout(api_container)

        self.api_group = QGroupBox()
        api_form = QFormLayout(self.api_group)
        api_form.setContentsMargins(10, 20, 10, 10)
        api_form.setSpacing(12)

        self.gemini_api_key_label = QLabel()
        self.gemini_api_key_edit = QLineEdit()
        self.gemini_api_key_edit.setEchoMode(QLineEdit.Password)
        api_form.addRow(self.gemini_api_key_label, self.gemini_api_key_edit)

        self.llm_mode_label = QLabel()
        self.llm_mode_combo = QComboBox()
        self.llm_mode_combo.currentIndexChanged.connect(self._update_custom_model_visibility)
        api_form.addRow(self.llm_mode_label, self.llm_mode_combo)

        self.auto_model_note = QLabel()
        self.auto_model_note.setWordWrap(True)
        self.auto_model_note.setStyleSheet("font-size: 12px; color: #666666;")
        api_form.addRow("", self.auto_model_note)

        self.custom_model_label = QLabel()
        self.custom_model_edit = QLineEdit()
        api_form.addRow(self.custom_model_label, self.custom_model_edit)

        self.custom_model_note = QLabel()
        self.custom_model_note.setWordWrap(True)
        self.custom_model_note.setStyleSheet("font-size: 12px; color: #666666;")
        api_form.addRow("", self.custom_model_note)

        self.timeout_label = QLabel()
        self.timeout_edit = QLineEdit()
        self.timeout_edit.setValidator(QIntValidator(1, 300))
        api_form.addRow(self.timeout_label, self.timeout_edit)

        api_layout.addWidget(self.api_group)

        verify_layout = QHBoxLayout()
        verify_layout.addStretch()
        self.verify_button = QPushButton()
        self.verify_button.clicked.connect(self._verify_api_keys)
        verify_layout.addWidget(self.verify_button)
        api_layout.addLayout(verify_layout)
        api_layout.addStretch()

        main_layout.addWidget(api_container)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_button = QPushButton()
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        self.save_button = QPushButton()
        self.save_button.clicked.connect(self._save_settings)
        self.save_button.setDefault(True)
        button_layout.addWidget(self.save_button)

        main_layout.addLayout(button_layout)
        self._apply_texts()

    def _apply_texts(self):
        """現在のアプリ言語に合わせて文言を反映"""
        self.setWindowTitle(self.tr_ui("settings_dialog_title"))
        self.app_language_label.setText(self.tr_ui("app_language"))

        self.language_group.setTitle(self.tr_ui("settings_language_group"))
        self.api_group.setTitle(self.tr_ui("settings_api_group"))

        self.gemini_api_key_label.setText(self.tr_ui("google_api_key"))
        self.gemini_api_key_edit.setPlaceholderText(self.tr_ui("google_api_key_placeholder"))

        self.llm_mode_label.setText(self.tr_ui("llm_setting"))
        current_mode = self.llm_mode_combo.currentData()
        self.llm_mode_combo.blockSignals(True)
        self.llm_mode_combo.clear()
        self.llm_mode_combo.addItem(self.tr_ui("llm_auto"), "auto")
        self.llm_mode_combo.addItem(self.tr_ui("llm_custom"), "custom")
        mode_index = self.llm_mode_combo.findData(current_mode if current_mode else "auto")
        self.llm_mode_combo.setCurrentIndex(mode_index if mode_index >= 0 else 0)
        self.llm_mode_combo.blockSignals(False)

        self.auto_model_note.setText(self.tr_ui("auto_model_note"))
        self.custom_model_label.setText(self.tr_ui("model_name"))
        self.custom_model_edit.setPlaceholderText(self.tr_ui("custom_model_placeholder"))
        self.custom_model_note.setText(self.tr_ui("custom_model_note"))
        self.timeout_label.setText(self.tr_ui("timeout"))
        self.timeout_edit.setPlaceholderText("60")
        self.verify_button.setText(self.tr_ui("verify_api_key"))
        self.cancel_button.setText(self.tr_ui("cancel"))
        self.save_button.setText(self.tr_ui("save"))

    def _load_settings(self):
        """設定を読み込んでUIに反映"""
        gemini_api_key = self.settings_manager.get_api_key("gemini")
        llm_mode = self.settings_manager.get_llm_mode()
        custom_model = self.settings_manager.get_custom_model()
        timeout = self.settings_manager.get_timeout()
        app_language = self.settings_manager.get_app_language()

        self.gemini_api_key_edit.setText(gemini_api_key if gemini_api_key else "")
        self.custom_model_edit.setText(custom_model)
        self.timeout_edit.setText(str(timeout) if timeout else "")

        lang_index = self.app_language_combo.findData(app_language)
        self.app_language_combo.setCurrentIndex(lang_index if lang_index >= 0 else 0)

        mode_index = self.llm_mode_combo.findData(llm_mode)
        self.llm_mode_combo.setCurrentIndex(mode_index if mode_index >= 0 else 0)
        self._update_custom_model_visibility()

    def _on_app_language_changed(self):
        """言語選択変更時に文言を即時更新"""
        self.app_language = self.app_language_combo.currentData() or self.settings_manager.get_app_language()
        self._apply_texts()
        self._update_custom_model_visibility()

    def _update_custom_model_visibility(self):
        """カスタムモデル入力欄の表示を切り替える"""
        is_custom = self.llm_mode_combo.currentData() == "custom"
        self.custom_model_label.setVisible(is_custom)
        self.custom_model_edit.setVisible(is_custom)
        self.custom_model_note.setVisible(is_custom)
        self.auto_model_note.setVisible(not is_custom)

    def _save_settings(self):
        """UIの設定を保存"""
        try:
            gemini_api_key = self.gemini_api_key_edit.text()
            llm_mode = self.llm_mode_combo.currentData()
            custom_model = self.custom_model_edit.text().strip()
            timeout = int(self.timeout_edit.text()) if self.timeout_edit.text().isdigit() else 60
            app_language = self.app_language_combo.currentData()

            if llm_mode == "custom" and not custom_model:
                QMessageBox.warning(self, self.tr_ui("validation_title"), self.tr_ui("validation_custom_model"))
                return

            self.settings_manager.set_api_key("gemini", gemini_api_key)
            self.settings_manager.set_llm_mode(llm_mode)
            self.settings_manager.set_custom_model(custom_model if llm_mode == "custom" else "")
            self.settings_manager.set_timeout(timeout)
            self.settings_manager.set_app_language(app_language)
            self.settings_manager.set_selected_api("gemini")

            if self.settings_manager.save_settings():
                logger.info("設定を保存しました")
                self.accept()
            else:
                QMessageBox.critical(self, self.tr_ui("error_title"), self.tr_ui("error_title"))
        except Exception as e:
            logger.error("設定の保存中にエラーが発生しました: %s", str(e))
            QMessageBox.critical(self, self.tr_ui("error_title"), str(e))

    def _verify_api_keys(self):
        """APIキーの検証"""
        api_key = self.gemini_api_key_edit.text().strip()
        translator_service = self.translation_manager.get_translator_service("gemini")

        if not translator_service:
            QMessageBox.critical(self, self.tr_ui("error_title"), self.tr_ui("missing_translator"))
            return

        llm_mode = self.llm_mode_combo.currentData()
        custom_model = self.custom_model_edit.text().strip()
        translator_service.settings_manager.set_llm_mode(llm_mode)
        translator_service.settings_manager.set_custom_model(custom_model if llm_mode == "custom" else "")

        is_valid, message = translator_service.verify_api_key(api_key)
        if is_valid:
            QMessageBox.information(self, self.tr_ui("verify_ok_title"), self.tr_ui("verify_ok_message"))
        else:
            QMessageBox.warning(
                self,
                self.tr_ui("verify_ok_title"),
                self.tr_ui("verify_ng_message", message=message),
            )
