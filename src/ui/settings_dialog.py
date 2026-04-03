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
from ..utils.settings_manager import SettingsManager

logger = logging.getLogger("ocr_translator")


class SettingsDialog(QDialog):
    """アプリケーション設定ダイアログ"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.settings_manager = SettingsManager()
        self.translation_manager = TranslationManager()

        self._init_ui()
        self._load_settings()

        logger.info("設定ダイアログを初期化しました")

    def _init_ui(self):
        """UIの初期化"""
        self.setWindowTitle("設定")
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

        api_container = QWidget()
        api_layout = QVBoxLayout(api_container)

        api_group = QGroupBox("API設定")
        api_form = QFormLayout(api_group)
        api_form.setContentsMargins(10, 20, 10, 10)
        api_form.setSpacing(12)

        self.gemini_api_key_edit = QLineEdit()
        self.gemini_api_key_edit.setEchoMode(QLineEdit.Password)
        self.gemini_api_key_edit.setPlaceholderText("Google AI Studio の APIキーを入力")
        api_form.addRow("Google APIキー:", self.gemini_api_key_edit)

        self.llm_mode_combo = QComboBox()
        self.llm_mode_combo.addItem("自動", "auto")
        self.llm_mode_combo.addItem("カスタム", "custom")
        self.llm_mode_combo.currentIndexChanged.connect(self._update_custom_model_visibility)
        api_form.addRow("LLM設定:", self.llm_mode_combo)

        self.auto_model_note = QLabel(
            "自動では通常 `gemini-2.5-flash-lite` を使い、混雑や制限時は `gemma-3-27b-it` に自動切替します。"
        )
        self.auto_model_note.setWordWrap(True)
        self.auto_model_note.setStyleSheet("font-size: 12px; color: #666666;")
        api_form.addRow("", self.auto_model_note)

        self.custom_model_label = QLabel("モデル名:")
        self.custom_model_edit = QLineEdit()
        self.custom_model_edit.setPlaceholderText("例: gemini-2.5-pro, gemma-3-27b-it")
        api_form.addRow(self.custom_model_label, self.custom_model_edit)

        self.custom_model_note = QLabel("カスタム選択時のみ、入力したモデル名をそのまま Google API に渡します。")
        self.custom_model_note.setWordWrap(True)
        self.custom_model_note.setStyleSheet("font-size: 12px; color: #666666;")
        api_form.addRow("", self.custom_model_note)

        self.timeout_edit = QLineEdit()
        self.timeout_edit.setPlaceholderText("例: 60")
        self.timeout_edit.setValidator(QIntValidator(1, 300))
        api_form.addRow("APIタイムアウト (秒):", self.timeout_edit)

        api_layout.addWidget(api_group)

        verify_layout = QHBoxLayout()
        verify_layout.addStretch()
        self.verify_button = QPushButton("APIキーを検証")
        self.verify_button.clicked.connect(self._verify_api_keys)
        verify_layout.addWidget(self.verify_button)
        api_layout.addLayout(verify_layout)
        api_layout.addStretch()

        main_layout.addWidget(api_container)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_button = QPushButton("キャンセル")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        self.save_button = QPushButton("保存")
        self.save_button.clicked.connect(self._save_settings)
        self.save_button.setDefault(True)
        button_layout.addWidget(self.save_button)

        main_layout.addLayout(button_layout)

    def _load_settings(self):
        """設定を読み込んでUIに反映"""
        gemini_api_key = self.settings_manager.get_api_key("gemini")
        llm_mode = self.settings_manager.get_llm_mode()
        custom_model = self.settings_manager.get_custom_model()
        timeout = self.settings_manager.get_timeout()

        self.gemini_api_key_edit.setText(gemini_api_key if gemini_api_key else "")

        index = self.llm_mode_combo.findData(llm_mode)
        if index < 0:
            index = self.llm_mode_combo.findData("auto")
        self.llm_mode_combo.setCurrentIndex(index)

        self.custom_model_edit.setText(custom_model)
        self.timeout_edit.setText(str(timeout) if timeout else "")
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

            if llm_mode == "custom" and not custom_model:
                QMessageBox.warning(self, "入力不足", "カスタムを使う場合はモデル名を入力してください。")
                return

            self.settings_manager.set_api_key("gemini", gemini_api_key)
            self.settings_manager.set_llm_mode(llm_mode)
            self.settings_manager.set_custom_model(custom_model if llm_mode == "custom" else "")
            self.settings_manager.set_timeout(timeout)
            self.settings_manager.set_selected_api("gemini")

            if self.settings_manager.save_settings():
                logger.info("設定を保存しました")
                self.accept()
            else:
                QMessageBox.critical(self, "エラー", "設定の保存に失敗しました")
        except Exception as e:
            logger.error("設定の保存中にエラーが発生しました: %s", str(e))
            QMessageBox.critical(self, "エラー", f"設定の保存中にエラーが発生しました: {str(e)}")

    def _verify_api_keys(self):
        """APIキーの検証"""
        api_key = self.gemini_api_key_edit.text().strip()
        translator_service = self.translation_manager.get_translator_service("gemini")

        if not translator_service:
            QMessageBox.critical(self, "エラー", "Google翻訳サービスが見つかりません。")
            return

        llm_mode = self.llm_mode_combo.currentData()
        custom_model = self.custom_model_edit.text().strip()
        translator_service.settings_manager.set_llm_mode(llm_mode)
        translator_service.settings_manager.set_custom_model(custom_model if llm_mode == "custom" else "")

        is_valid, message = translator_service.verify_api_key(api_key)
        if is_valid:
            QMessageBox.information(self, "APIキー検証", "APIキーは有効です。")
        else:
            QMessageBox.warning(self, "APIキー検証", f"APIキーが無効です: {message}")
