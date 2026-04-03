"""
翻訳マネージャーモジュール
"""
import logging

from PyQt5.QtGui import QImage, QPixmap

from ..utils.settings_manager import SettingsManager
from .combined_vision_translator import CombinedVisionTranslator
from .gemini_translator import GeminiTranslator

logger = logging.getLogger("ocr_translator")


class TranslationManager:
    """翻訳サービスを管理するクラス"""

    def __init__(self):
        self.settings_manager = SettingsManager()
        self.gemini_translator = GeminiTranslator()
        self.combined_vision_translator = CombinedVisionTranslator()
        logger.info("TranslationManagerを初期化しました")

    def translate(self, text, source_lang=None, target_lang=None):
        """テキストを翻訳する"""
        if not text:
            logger.warning("翻訳するテキストがありません")
            return ""

        if self.gemini_translator.is_available():
            return self.gemini_translator.translate(text, source_lang, target_lang)
        return "エラー: Google APIキーが設定されていません。設定画面でAPIキーを設定してください。"

    def translate_image(self, pixmap: QPixmap | QImage | bytes, target_lang: str = None) -> str:
        """
        画像からテキストを抽出し、指定された言語に翻訳します（一括処理）。
        """
        if not self.combined_vision_translator.is_available():
            return "エラー: 一括翻訳サービスが利用できません。APIキーを確認してください。"

        return self.combined_vision_translator.translate_image(pixmap, target_lang)

    def is_any_api_available(self):
        """APIが利用可能かどうかを確認する"""
        return self.gemini_translator.is_available() or self.combined_vision_translator.is_available()

    def get_translator_service(self, api_type):
        """指定されたAPIタイプの翻訳サービスインスタンスを返す"""
        if api_type == "gemini":
            return self.gemini_translator
        logger.warning("不明なAPIタイプが指定されました: %s", api_type)
        return None
