"""
設定管理モジュール
"""
import os
import json
import logging
from ..utils.utils import get_config_dir

logger = logging.getLogger('ocr_translator')

class SettingsManager:
    """アプリケーション設定の管理クラス"""
    
    def __init__(self):
        self.config_dir = get_config_dir()
        self.config_file = os.path.join(self.config_dir, 'settings.json')
        self.settings = self._load_settings()
    
    def _load_settings(self):
        """設定ファイルから設定を読み込む"""
        default_settings = {
            'api': {
                'selected_api': 'openai',  # 'openai' または 'gemini'
                'openai_api_key': '',
                'gemini_api_key': ''
            },
            'language': {
                'target_language': 'ja',  # デフォルトは日本語
                'ocr_languages': ['jpn', 'eng']  # Tesseract言語コード
            },
            'ui': {
                'theme': 'system',
                'start_minimized': False
            }
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    # デフォルト設定をロードした設定で更新
                    self._update_nested_dict(default_settings, loaded_settings)
            return default_settings
        except Exception as e:
            logger.error(f"設定の読み込み中にエラーが発生しました: {str(e)}")
            return default_settings
    
    def _update_nested_dict(self, d, u):
        """ネストされた辞書を更新する"""
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                self._update_nested_dict(d[k], v)
            else:
                d[k] = v
    
    def save_settings(self):
        """設定をファイルに保存する"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            logger.info("設定を保存しました")
            return True
        except Exception as e:
            logger.error(f"設定の保存中にエラーが発生しました: {str(e)}")
            return False
    
    def get_setting(self, category, key, default=None):
        """指定されたカテゴリと鍵の設定値を取得する"""
        try:
            return self.settings[category][key]
        except KeyError:
            logger.warning(f"設定が見つかりません: {category}.{key}。デフォルト値 {default} を使用します。")
            return default
    
    def set_setting(self, category, key, value):
        """指定されたカテゴリと鍵の設定値を設定する"""
        try:
            self.settings[category][key] = value
            return True
        except KeyError:
            logger.warning(f"設定カテゴリが見つかりません: {category}")
            return False
    
    def get_api_key(self, api_type):
        """指定されたAPI種類のAPIキーを取得する"""
        if api_type.lower() == 'openai':
            return self.get_setting('api', 'openai_api_key')
        elif api_type.lower() == 'gemini':
            return self.get_setting('api', 'gemini_api_key')
        else:
            logger.warning(f"不明なAPI種類: {api_type}")
            return None
    
    def set_api_key(self, api_type, api_key):
        """指定されたAPI種類のAPIキーを設定する"""
        if api_type.lower() == 'openai':
            return self.set_setting('api', 'openai_api_key', api_key)
        elif api_type.lower() == 'gemini':
            return self.set_setting('api', 'gemini_api_key', api_key)
        else:
            logger.warning(f"不明なAPI種類: {api_type}")
            return False
    
    def get_target_language(self):
        """翻訳先言語を取得する"""
        return self.get_setting('language', 'target_language')
    
    def set_target_language(self, language_code):
        """翻訳先言語を設定する"""
        return self.set_setting('language', 'target_language', language_code)
    
    def get_ocr_languages(self):
        """OCR言語リストを取得する"""
        return self.get_setting('language', 'ocr_languages')
    
    def set_ocr_languages(self, language_codes):
        """OCR言語リストを設定する"""
        return self.set_setting('language', 'ocr_languages', language_codes)
    
    def get_selected_api(self):
        """選択されているAPIを取得する"""
        return self.get_setting('api', 'selected_api')
    
    def set_selected_api(self, api_type):
        """使用するAPIを設定する"""
        if api_type.lower() in ['openai', 'gemini']:
            return self.set_setting('api', 'selected_api', api_type.lower())
        else:
            logger.warning(f"不明なAPI種類: {api_type}")
            return False
