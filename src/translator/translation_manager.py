"""
翻訳マネージャーモジュール
"""
import logging
from ..utils.settings_manager import SettingsManager
from PyQt5.QtGui import QPixmap, QImage # 追加
from .openai_translator import OpenAITranslator
from .gemini_translator import GeminiTranslator
from .combined_vision_translator import CombinedVisionTranslator # 追加

logger = logging.getLogger('ocr_translator')

class TranslationManager:
    """翻訳サービスを管理するクラス"""
    
    def __init__(self):
        self.settings_manager = SettingsManager()
        self.openai_translator = OpenAITranslator()
        self.gemini_translator = GeminiTranslator()
        self.combined_vision_translator = CombinedVisionTranslator() # 追加
        logger.info("TranslationManagerを初期化しました")
    
    def translate(self, text, source_lang=None, target_lang=None):
        """テキストを翻訳する
        
        Args:
            text (str): 翻訳するテキスト
            source_lang (str, optional): 元の言語コード。Noneの場合は自動検出
            target_lang (str, optional): 翻訳先の言語コード。Noneの場合はデフォルト言語
            
        Returns:
            str: 翻訳されたテキスト
        """
        if not text:
            logger.warning("翻訳するテキストがありません")
            return ""
        
        # 使用するAPIの選択
        selected_api = self.settings_manager.get_selected_api()
        
        logger.info(f"選択されたAPI: {selected_api}")
        
        if selected_api == 'openai':
            if self.openai_translator.is_available():
                return self.openai_translator.translate(text, source_lang, target_lang)
            return "エラー: OpenAI APIキーが設定されていません。設定画面でAPIキーを設定してください。"
        else:  # gemini
            if self.gemini_translator.is_available():
                return self.gemini_translator.translate(text, source_lang, target_lang)
            return "エラー: Gemini APIキーが設定されていません。設定画面でAPIキーを設定してください。"
    
    def translate_image(self, pixmap: QPixmap | QImage, target_lang: str = None) -> str: # 追加
        """
        画像からテキストを抽出し、指定された言語に翻訳します（一括処理）。

        Args:
            pixmap (QPixmap): 処理する画像。
            target_lang (str, optional): 翻訳先の言語コード。Noneの場合はデフォルト言語。

        Returns:
            str: 抽出・翻訳されたテキスト。
        """
        if not self.combined_vision_translator.is_available():
            return "エラー: 一括翻訳サービスが利用できません。APIキーを確認してください。"
        
        return self.combined_vision_translator.translate_image(pixmap, target_lang)

    def is_any_api_available(self):
        """いずれかのAPIが利用可能かどうかを確認する
        
        Returns:
            bool: 利用可能な場合はTrue、そうでない場合はFalse
        """
        return (self.openai_translator.is_available() or 
                self.gemini_translator.is_available() or
                self.combined_vision_translator.is_available()) # 変更

    def get_translator_service(self, api_type):
        """指定されたAPIタイプの翻訳サービスインスタンスを返す

        Args:
            api_type (str): 'openai' または 'gemini'

        Returns:
            TranslatorService: 対応する翻訳サービスインスタンス、またはNone
        """
        if api_type == 'openai':
            return self.openai_translator
        elif api_type == 'gemini':
            return self.gemini_translator
        else:
            logger.warning(f"不明なAPIタイプが指定されました: {api_type}")
            return None
