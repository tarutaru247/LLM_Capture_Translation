"""
翻訳マネージャーモジュール
"""
import logging
from ..utils.settings_manager import SettingsManager
from .openai_translator import OpenAITranslator
from .gemini_translator import GeminiTranslator

logger = logging.getLogger('ocr_translator')

class TranslationManager:
    """翻訳サービスを管理するクラス"""
    
    def __init__(self):
        self.settings_manager = SettingsManager()
        self.openai_translator = OpenAITranslator()
        self.gemini_translator = GeminiTranslator()
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
            elif self.gemini_translator.is_available():
                logger.warning("OpenAI APIキーが設定されていないため、Gemini APIを使用します")
                return self.gemini_translator.translate(text, source_lang, target_lang)
            else:
                return "エラー: APIキーが設定されていません。設定画面でAPIキーを設定してください。"
        else:  # gemini
            if self.gemini_translator.is_available():
                return self.gemini_translator.translate(text, source_lang, target_lang)
            elif self.openai_translator.is_available():
                logger.warning("Gemini APIキーが設定されていないため、OpenAI APIを使用します")
                return self.openai_translator.translate(text, source_lang, target_lang)
            else:
                return "エラー: APIキーが設定されていません。設定画面でAPIキーを設定してください。"
    
    def is_any_api_available(self):
        """いずれかのAPIが利用可能かどうかを確認する
        
        Returns:
            bool: 利用可能な場合はTrue、そうでない場合はFalse
        """
        return self.openai_translator.is_available() or self.gemini_translator.is_available()
