"""
Translator that uses the Google Gemini API.
"""
import logging
from typing import Optional

import google.generativeai as genai

from ..utils.settings_manager import SettingsManager
from ..utils.utils import handle_exception, sanitize_sensitive_data
from .translator_service import TranslatorService

logger = logging.getLogger("ocr_translator")


class GeminiTranslator(TranslatorService):
    """Google Gemini API を利用した翻訳サービス."""

    def __init__(self) -> None:
        self.settings_manager = SettingsManager()
        self._api_key: Optional[str] = None
        logger.info("GeminiTranslatorを初期化しました")

    def _refresh_api_key(self) -> None:
        """設定ファイルから最新の API キーを取得する."""
        self._api_key = self.settings_manager.get_api_key("gemini")

    def translate(self, text, source_lang=None, target_lang=None):
        """Gemini API を使用してテキストを翻訳する."""
        self._refresh_api_key()

        if not text:
            logger.warning("翻訳するテキストがありません")
            return ""

        if not self._api_key:
            logger.error("Gemini APIキーが設定されていません")
            return "エラー: Gemini APIキーが設定されていません。設定画面でAPIキーを設定してください。"

        model_name = self._resolve_model_name()

        try:
            genai.configure(api_key=self._api_key)

            if not target_lang:
                target_lang = self.settings_manager.get_target_language()

            language_names = {
                "ja": "日本語",
                "en": "英語",
                "zh": "中国語",
                "ko": "韓国語",
                "fr": "フランス語",
                "de": "ドイツ語",
            }
            target_language_name = language_names.get(target_lang, target_lang)

            prompt = (
                f"次のテキストを{target_language_name}に翻訳してください。"
                "翻訳のみを出力し、不必要な説明は省いてください。\n\n"
                f"{text}"
            )

            logger.info("Gemini APIによる翻訳を実行します（対象言語: %s）", target_language_name)

            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt, request_options={"timeout": self.settings_manager.get_timeout()})

            translated_text = response.text.strip()
            logger.info("翻訳が完了しました")
            return translated_text

        except Exception as exc:
            error_msg = handle_exception(logger, exc, "Gemini APIでの翻訳")
            return f"エラー: {error_msg}"

    def is_available(self):
        """Gemini API が利用可能かどうかを確認する."""
        self._refresh_api_key()
        return bool(self._api_key)

    def verify_api_key(self, api_key):
        """指定された API キーが Gemini で有効かどうかを検証する."""
        if not api_key:
            return False, "APIキーが入力されていません。"

        try:
            genai.configure(api_key=api_key)
            model_name = self._resolve_model_name()
            model = genai.GenerativeModel(model_name)
            model.generate_content("test", request_options={"timeout": 5})
            logger.info("Google Gemini APIキーの検証に成功しました。")
            return True, ""
        except Exception as exc:
            safe_exc = sanitize_sensitive_data(str(exc))
            error_msg = f"Google Gemini APIキーの検証中にエラーが発生しました: {safe_exc}"
            logger.error(error_msg)
            if "timeout" in safe_exc.lower():
                return False, f"APIへの接続エラー: {safe_exc} (タイムアウトの可能性あり)"
            return False, error_msg

    def _resolve_model_name(self) -> str:
        """Return a Gemini-compatible model name, falling back to default if necessary."""
        configured_model = self.settings_manager.get_model_for_api("gemini")
        if configured_model and configured_model.lower().startswith("gemini"):
            return configured_model
        # Fallback to a safe default Gemini model if the configured one is meant for OpenAI (e.g., GPT-5).
        logger.warning(
            "Geminiモデル以外 (%s) が設定されていたため、Geminiデフォルトモデルを使用します。",
            configured_model,
        )
        return "gemini-pro"
