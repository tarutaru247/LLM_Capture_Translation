"""
Google Gemini APIを使用した翻訳サービス
"""
import logging
import google.generativeai as genai
from ..utils.utils import handle_exception
from ..utils.settings_manager import SettingsManager
from .translator_service import TranslatorService

logger = logging.getLogger('ocr_translator')

class GeminiTranslator(TranslatorService):
    """Google Gemini APIを使用した翻訳サービス"""
    
    def __init__(self):
        self.settings_manager = SettingsManager()
        self.api_key = self.settings_manager.get_api_key('gemini')
        logger.info("GeminiTranslatorを初期化しました")
    
    def translate(self, text, source_lang=None, target_lang=None):
        """Gemini APIを使用してテキストを翻訳する
        
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
        
        if not self.api_key:
            logger.error("Gemini APIキーが設定されていません")
            return "エラー: Gemini APIキーが設定されていません。設定画面でAPIキーを設定してください。"
        
        try:
            # APIキーの設定
            genai.configure(api_key=self.api_key)
            
            # 翻訳先言語の取得
            if not target_lang:
                target_lang = self.settings_manager.get_target_language()
            
            # 言語名のマッピング
            language_names = {
                'ja': '日本語',
                'en': '英語',
                'zh': '中国語',
                'ko': '韓国語',
                'fr': 'フランス語',
                'de': 'ドイツ語'
            }
            
            target_language_name = language_names.get(target_lang, target_lang)
            
            # 翻訳プロンプトの作成
            prompt = f"以下のテキストを{target_language_name}に翻訳してください。翻訳のみを出力し、余計な説明は不要です。\n\n{text}"
            
            logger.info(f"Gemini APIを使用して翻訳を実行中... (対象言語: {target_language_name})")
            
            # Gemini APIを使用して翻訳
            model = genai.GenerativeModel('gemini-2.0-flash-lite')
            response = model.generate_content(prompt)
            
            # 翻訳結果の取得
            translated_text = response.text.strip()
            
            logger.info("翻訳が完了しました")
            return translated_text
            
        except Exception as e:
            error_msg = handle_exception(logger, e, "Gemini APIによる翻訳")
            return f"翻訳エラー: {error_msg}"
    
    def is_available(self):
        """Gemini APIが利用可能かどうかを確認する
        
        Returns:
            bool: 利用可能な場合はTrue、そうでない場合はFalse
        """
        return bool(self.api_key)
