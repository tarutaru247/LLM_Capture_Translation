"""
設定ダイアログモジュール
"""
import logging
from PyQt5.QtWidgets import (QDialog, QTabWidget, QVBoxLayout, QHBoxLayout, 
                           QLabel, QLineEdit, QRadioButton, QCheckBox, 
                           QPushButton, QGroupBox, QComboBox, QMessageBox, QWidget)
from PyQt5.QtCore import Qt

from ..utils.settings_manager import SettingsManager

logger = logging.getLogger('ocr_translator')

class SettingsDialog(QDialog):
    """アプリケーション設定ダイアログ"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.settings_manager = SettingsManager()
        
        self._init_ui()
        self._load_settings()
        
        logger.info("設定ダイアログを初期化しました")
    
    def _init_ui(self):
        """UIの初期化"""
        self.setWindowTitle("設定")
        self.setMinimumWidth(500)
        
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
        
        self.tab_widget.addTab(api_tab, "API設定")
    
    def _create_language_settings_tab(self):
        """言語設定タブの作成"""
        language_tab = QWidget()
        language_layout = QVBoxLayout(language_tab)
        
        # 翻訳先言語設定
        target_lang_group = QGroupBox("翻訳先言語")
        target_lang_layout = QVBoxLayout(target_lang_group)
        
        self.target_language_combo = QComboBox()
        self.target_language_combo.addItem("日本語", "ja")
        self.target_language_combo.addItem("英語", "en")
        self.target_language_combo.addItem("中国語", "zh")
        self.target_language_combo.addItem("韓国語", "ko")
        self.target_language_combo.addItem("フランス語", "fr")
        self.target_language_combo.addItem("ドイツ語", "de")
        target_lang_layout.addWidget(self.target_language_combo)
        
        language_layout.addWidget(target_lang_group)
        
        # OCR言語設定
        ocr_lang_group = QGroupBox("OCR言語")
        ocr_lang_layout = QVBoxLayout(ocr_lang_group)
        
        self.jpn_checkbox = QCheckBox("日本語")
        ocr_lang_layout.addWidget(self.jpn_checkbox)
        
        self.eng_checkbox = QCheckBox("英語")
        ocr_lang_layout.addWidget(self.eng_checkbox)
        
        language_layout.addWidget(ocr_lang_group)
        language_layout.addStretch()
        
        self.tab_widget.addTab(language_tab, "言語設定")
    
    def _create_general_settings_tab(self):
        """一般設定タブの作成"""
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        
        # 起動設定
        startup_group = QGroupBox("起動設定")
        startup_layout = QVBoxLayout(startup_group)
        
        self.start_minimized_checkbox = QCheckBox("最小化状態で起動")
        startup_layout.addWidget(self.start_minimized_checkbox)
        
        general_layout.addWidget(startup_group)
        general_layout.addStretch()
        
        self.tab_widget.addTab(general_tab, "一般設定")
    
    def _load_settings(self):
        """設定を読み込んでUIに反映"""
        # API設定
        openai_api_key = self.settings_manager.get_api_key('openai')
        gemini_api_key = self.settings_manager.get_api_key('gemini')
        selected_api = self.settings_manager.get_selected_api()
        
        self.openai_api_key_edit.setText(openai_api_key if openai_api_key else "")
        self.gemini_api_key_edit.setText(gemini_api_key if gemini_api_key else "")
        
        if selected_api == 'gemini':
            self.gemini_radio.setChecked(True)
        else:
            self.openai_radio.setChecked(True)
        
        # 言語設定
        target_language = self.settings_manager.get_target_language()
        ocr_languages = self.settings_manager.get_ocr_languages()
        
        # 翻訳先言語の設定
        index = self.target_language_combo.findData(target_language)
        if index >= 0:
            self.target_language_combo.setCurrentIndex(index)
        
        # OCR言語の設定
        self.jpn_checkbox.setChecked('jpn' in ocr_languages)
        self.eng_checkbox.setChecked('eng' in ocr_languages)
        
        # 一般設定
        start_minimized = self.settings_manager.get_setting('ui', 'start_minimized', False)
        self.start_minimized_checkbox.setChecked(start_minimized)
    
    def _save_settings(self):
        """UIの設定を保存"""
        try:
            # API設定
            openai_api_key = self.openai_api_key_edit.text()
            gemini_api_key = self.gemini_api_key_edit.text()
            selected_api = 'gemini' if self.gemini_radio.isChecked() else 'openai'
            
            self.settings_manager.set_api_key('openai', openai_api_key)
            self.settings_manager.set_api_key('gemini', gemini_api_key)
            self.settings_manager.set_selected_api(selected_api)
            
            # 言語設定
            target_language = self.target_language_combo.currentData()
            self.settings_manager.set_target_language(target_language)
            
            ocr_languages = []
            if self.jpn_checkbox.isChecked():
                ocr_languages.append('jpn')
            if self.eng_checkbox.isChecked():
                ocr_languages.append('eng')
            
            # 少なくとも1つの言語を選択する必要がある
            if not ocr_languages:
                QMessageBox.warning(self, "警告", "OCR言語は少なくとも1つ選択してください")
                return
            
            self.settings_manager.set_ocr_languages(ocr_languages)
            
            # 一般設定
            start_minimized = self.start_minimized_checkbox.isChecked()
            self.settings_manager.set_setting('ui', 'start_minimized', start_minimized)
            
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
        # TODO: 実際のAPI検証を実装
        QMessageBox.information(self, "APIキー検証", "APIキー検証機能は実装中です")
