"""
設定ダイアログモジュール
"""
import logging
from PyQt5.QtWidgets import (QDialog, QTabWidget, QVBoxLayout, QHBoxLayout, 
                           QLabel, QLineEdit, QRadioButton, QCheckBox, 
                           QPushButton, QGroupBox, QComboBox, QMessageBox, QWidget)
from PyQt5.QtGui import QIntValidator
from PyQt5.QtCore import Qt

from ..utils.settings_manager import SettingsManager
from ..translator.translation_manager import TranslationManager # 追加

logger = logging.getLogger('ocr_translator')

class SettingsDialog(QDialog):
    """アプリケーション設定ダイアログ"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.settings_manager = SettingsManager()
        self.translation_manager = TranslationManager() # 追加
        
        self._init_ui()
        self._load_settings()
        
        logger.info("設定ダイアログを初期化しました")
    
    def _init_ui(self):
        """UIの初期化"""
        self.setWindowTitle("設定")
        self.setMinimumWidth(500)

        # スタイルシートの適用
        self.setStyleSheet("""
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
            QLineEdit {
                font-family: "Yu Gothic UI", "Meiryo UI", sans-serif;
                font-size: 14px;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 5px;
                background-color: white;
            }
            QComboBox {
                font-family: "Yu Gothic UI", "Meiryo UI", sans-serif;
                font-size: 14px;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 5px;
                background-color: white;
            }
            QTabWidget::pane {
                border: 1px solid #cccccc;
                background-color: white;
            }
            QTabBar::tab {
                background: #e0e0e0;
                border: 1px solid #cccccc;
                border-bottom-color: #e0e0e0;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                min-width: 8ex;
                padding: 8px;
                font-family: "Yu Gothic UI", "Meiryo UI", sans-serif;
                font-size: 14px;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom-color: white;
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
            QRadioButton {
                font-family: "Yu Gothic UI", "Meiryo UI", sans-serif;
                font-size: 14px;
            }
            QCheckBox {
                font-family: "Yu Gothic UI", "Meiryo UI", sans-serif;
                font-size: 14px;
            }
        """)
        
        # メインレイアウト
        main_layout = QVBoxLayout(self)
        
        # タブウィジェット
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # API設定タブ
        self._create_api_settings_tab()
        
        # 言語設定タブ
        self._create_language_settings_tab()
        
        # 一般設定タブ
        self._create_general_settings_tab()
        
        # ボタンレイアウト
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
    
    def _create_api_settings_tab(self):
        """API設定タブの作成"""
        api_tab = QWidget()
        api_layout = QVBoxLayout(api_tab)
        
        # OpenAI API設定
        openai_group = QGroupBox("OpenAI API設定")
        openai_layout = QVBoxLayout(openai_group)
        openai_layout.setContentsMargins(10, 20, 10, 10) # 余白を調整
        openai_layout.setSpacing(10) # ウィジェット間のスペースを調整
        
        openai_key_layout = QHBoxLayout()
        openai_key_layout.addWidget(QLabel("APIキー:"))
        
        self.openai_api_key_edit = QLineEdit()
        self.openai_api_key_edit.setEchoMode(QLineEdit.Password)
        self.openai_api_key_edit.setPlaceholderText("OpenAI APIキーを入力")
        openai_key_layout.addWidget(self.openai_api_key_edit)
        
        openai_layout.addLayout(openai_key_layout)
        api_layout.addWidget(openai_group)
        
        # Gemini API設定
        gemini_group = QGroupBox("Google Gemini API設定")
        gemini_layout = QVBoxLayout(gemini_group)
        gemini_layout.setContentsMargins(10, 20, 10, 10) # 余白を調整
        gemini_layout.setSpacing(10) # ウィジェット間のスペースを調整
        
        gemini_key_layout = QHBoxLayout()
        gemini_key_layout.addWidget(QLabel("APIキー:"))
        
        self.gemini_api_key_edit = QLineEdit()
        self.gemini_api_key_edit.setEchoMode(QLineEdit.Password)
        self.gemini_api_key_edit.setPlaceholderText("Gemini APIキーを入力")
        gemini_key_layout.addWidget(self.gemini_api_key_edit)
        
        gemini_layout.addLayout(gemini_key_layout)
        api_layout.addWidget(gemini_group)
        
        # API選択
        api_selection_group = QGroupBox("使用するAPI")
        api_selection_layout = QVBoxLayout(api_selection_group)
        api_selection_layout.setContentsMargins(10, 20, 10, 10) # 余白を調整
        api_selection_layout.setSpacing(10) # ウィジェット間のスペースを調整
        
        self.openai_radio = QRadioButton("OpenAI API")
        api_selection_layout.addWidget(self.openai_radio)
        
        self.gemini_radio = QRadioButton("Google Gemini API")
        api_selection_layout.addWidget(self.gemini_radio)
        
        api_layout.addWidget(api_selection_group)
        
        # APIキー検証ボタン
        verify_layout = QHBoxLayout()
        verify_layout.addStretch()
        
        self.verify_button = QPushButton("APIキーを検証")
        self.verify_button.clicked.connect(self._verify_api_keys)
        verify_layout.addWidget(self.verify_button)
        
        api_layout.addLayout(verify_layout)
        api_layout.addStretch()
        
        # 共通モデル設定
        model_settings_group = QGroupBox("モデル設定")
        model_settings_layout = QVBoxLayout(model_settings_group)
        model_settings_layout.setContentsMargins(10, 20, 10, 10) # 余白を調整
        model_settings_layout.setSpacing(10) # ウィジェット間のスペースを調整

        model_label = QLabel("モデル名:")
        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("例: gemini-2.5-flash-latest, gpt-5-nano")
        model_settings_layout.addWidget(model_label)
        model_settings_layout.addWidget(self.model_edit)

        recommend_label = QLabel("推奨: gemini-flash-latest")
        recommend_label.setStyleSheet("font-size: 12px; color: #666666;")
        model_settings_layout.addWidget(recommend_label)

        timeout_label = QLabel("APIタイムアウト (秒):")
        self.timeout_edit = QLineEdit()
        self.timeout_edit.setPlaceholderText("例: 60")
        self.timeout_edit.setValidator(QIntValidator(1, 300)) # 1秒から300秒
        model_settings_layout.addWidget(timeout_label)
        model_settings_layout.addWidget(self.timeout_edit)

        reasoning_label = QLabel("GPT-5 推論モード:")
        self.reasoning_combo = QComboBox()
        self.reasoning_combo.addItem("最小", "minimal")
        self.reasoning_combo.addItem("低", "low")
        self.reasoning_combo.addItem("中 (推奨)", "medium")
        self.reasoning_combo.addItem("高", "high")
        model_settings_layout.addWidget(reasoning_label)
        model_settings_layout.addWidget(self.reasoning_combo)

        verbosity_label = QLabel("GPT-5 出力の詳細度:")
        self.verbosity_combo = QComboBox()
        self.verbosity_combo.addItem("低", "low")
        self.verbosity_combo.addItem("中 (推奨)", "medium")
        self.verbosity_combo.addItem("高", "high")
        model_settings_layout.addWidget(verbosity_label)
        model_settings_layout.addWidget(self.verbosity_combo)

        max_tokens_label = QLabel("GPT-5 最大出力トークン:")
        self.max_output_tokens_edit = QLineEdit()
        self.max_output_tokens_edit.setPlaceholderText("例: 1024")
        self.max_output_tokens_edit.setValidator(QIntValidator(1, 32768))
        model_settings_layout.addWidget(max_tokens_label)
        model_settings_layout.addWidget(self.max_output_tokens_edit)

        api_layout.addWidget(model_settings_group)
        
        self.tab_widget.addTab(api_tab, "API設定")
    
    def _create_language_settings_tab(self):
        """言語設定タブの作成"""
        language_tab = QWidget()
        language_layout = QVBoxLayout(language_tab)
        
        # 翻訳先言語設定
        target_lang_group = QGroupBox("翻訳先言語")
        target_lang_layout = QVBoxLayout(target_lang_group)
        target_lang_layout.setContentsMargins(10, 20, 10, 10) # 余白を調整
        target_lang_layout.setSpacing(10) # ウィジェット間のスペースを調整
        
        self.target_language_combo = QComboBox()
        self.target_language_combo.addItem("日本語", "ja")
        self.target_language_combo.addItem("英語", "en")
        self.target_language_combo.addItem("中国語", "zh")
        self.target_language_combo.addItem("韓国語", "ko")
        self.target_language_combo.addItem("フランス語", "fr")
        self.target_language_combo.addItem("ドイツ語", "de")
        target_lang_layout.addWidget(self.target_language_combo)
        
        language_layout.addWidget(target_lang_group)
        language_layout.addStretch()
        
        self.tab_widget.addTab(language_tab, "言語設定")
    
    def _create_general_settings_tab(self):
        """一般設定タブの作成"""
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        
        # 起動設定
        startup_group = QGroupBox("起動設定")
        startup_layout = QVBoxLayout(startup_group)
        startup_layout.setContentsMargins(10, 20, 10, 10) # 余白を調整
        startup_layout.setSpacing(10) # ウィジェット間のスペースを調整
        
        self.start_minimized_checkbox = QCheckBox("最小化状態で起動")
        startup_layout.addWidget(self.start_minimized_checkbox)
        
        general_layout.addWidget(startup_group)

        # OCR/翻訳設定
        ocr_translation_group = QGroupBox("OCR/翻訳設定")
        ocr_translation_layout = QVBoxLayout(ocr_translation_group)
        ocr_translation_layout.setContentsMargins(10, 20, 10, 10)
        ocr_translation_layout.setSpacing(10)

        self.transcribe_original_text_checkbox = QCheckBox("原文を文字起こしする (一括翻訳を無効化)")
        ocr_translation_layout.addWidget(self.transcribe_original_text_checkbox)
        
        general_layout.addWidget(ocr_translation_group) # 追加
        general_layout.addStretch()
        
        self.tab_widget.addTab(general_tab, "一般設定")
    
    def _load_settings(self):
        """設定を読み込んでUIに反映"""
        # API設定
        openai_api_key = self.settings_manager.get_api_key('openai')
        gemini_api_key = self.settings_manager.get_api_key('gemini')
        selected_api = self.settings_manager.get_selected_api()
        model = self.settings_manager.get_model()
        timeout = self.settings_manager.get_timeout()
        reasoning_effort = self.settings_manager.get_openai_reasoning_effort()
        verbosity = self.settings_manager.get_openai_verbosity()
        max_output_tokens = self.settings_manager.get_openai_max_output_tokens()
        
        self.openai_api_key_edit.setText(openai_api_key if openai_api_key else "")
        self.gemini_api_key_edit.setText(gemini_api_key if gemini_api_key else "")
        
        if selected_api == 'gemini':
            self.gemini_radio.setChecked(True)
        else:
            self.openai_radio.setChecked(True)

        self.model_edit.setText(model if model else "")
        self.timeout_edit.setText(str(timeout) if timeout else "")

        reasoning_index = self.reasoning_combo.findData(reasoning_effort)
        if reasoning_index >= 0:
            self.reasoning_combo.setCurrentIndex(reasoning_index)

        verbosity_index = self.verbosity_combo.findData(verbosity)
        if verbosity_index >= 0:
            self.verbosity_combo.setCurrentIndex(verbosity_index)

        self.max_output_tokens_edit.setText(str(max_output_tokens) if max_output_tokens else "")
        
        # 言語設定
        target_language = self.settings_manager.get_target_language()
        
        # 翻訳先言語の設定
        index = self.target_language_combo.findData(target_language)
        if index >= 0:
            self.target_language_combo.setCurrentIndex(index)
        
        # 一般設定
        start_minimized = self.settings_manager.get_setting('ui', 'start_minimized', False)
        self.start_minimized_checkbox.setChecked(start_minimized)

        transcribe_original_text = self.settings_manager.get_transcribe_original_text() # 追加
        self.transcribe_original_text_checkbox.setChecked(transcribe_original_text) # 追加
    
    def _save_settings(self):
        """UIの設定を保存"""
        try:
            # API設定
            openai_api_key = self.openai_api_key_edit.text()
            gemini_api_key = self.gemini_api_key_edit.text()
            selected_api = 'gemini' if self.gemini_radio.isChecked() else 'openai'
            model = self.model_edit.text()
            timeout = int(self.timeout_edit.text()) if self.timeout_edit.text().isdigit() else 60
            reasoning_effort = self.reasoning_combo.currentData()
            verbosity = self.verbosity_combo.currentData()
            max_output_tokens_text = self.max_output_tokens_edit.text()
            max_output_tokens = int(max_output_tokens_text) if max_output_tokens_text.isdigit() else 1024
            
            self.settings_manager.set_api_key('openai', openai_api_key)
            self.settings_manager.set_api_key('gemini', gemini_api_key)
            self.settings_manager.set_selected_api(selected_api)
            self.settings_manager.set_model(model)
            self.settings_manager.set_timeout(timeout)
            self.settings_manager.set_openai_reasoning_effort(reasoning_effort)
            self.settings_manager.set_openai_verbosity(verbosity)
            self.settings_manager.set_openai_max_output_tokens(max_output_tokens)
            
            # 言語設定
            target_language = self.target_language_combo.currentData()
            self.settings_manager.set_target_language(target_language)
            
            # 一般設定
            start_minimized = self.start_minimized_checkbox.isChecked()
            self.settings_manager.set_setting('ui', 'start_minimized', start_minimized)

            transcribe_original_text = self.transcribe_original_text_checkbox.isChecked() # 追加
            self.settings_manager.set_transcribe_original_text(transcribe_original_text) # 追加
            
            # 設定を保存
            if self.settings_manager.save_settings():
                logger.info("設定を保存しました")
                self.accept()
            else:
                QMessageBox.critical(self, "エラー", "設定の保存に失敗しました")
        except Exception as e:
            logger.error(f"設定の保存中にエラーが発生しました: {str(e)}")
            QMessageBox.critical(self, "エラー", f"設定の保存中にエラーが発生しました: {str(e)}")
    
    def _verify_api_keys(self):
        """APIキーの検証"""
        selected_api = 'gemini' if self.gemini_radio.isChecked() else 'openai'
        
        if selected_api == 'openai':
            api_key = self.openai_api_key_edit.text()
            translator_service = self.translation_manager.get_translator_service('openai')
        else: # gemini
            api_key = self.gemini_api_key_edit.text()
            translator_service = self.translation_manager.get_translator_service('gemini')
        
        if translator_service:
            is_valid, message = translator_service.verify_api_key(api_key)
            if is_valid:
                QMessageBox.information(self, "APIキー検証", "APIキーは有効です。")
            else:
                QMessageBox.warning(self, "APIキー検証", f"APIキーが無効です: {message}")
        else:
            QMessageBox.critical(self, "エラー", "選択されたAPIの翻訳サービスが見つかりません。")
