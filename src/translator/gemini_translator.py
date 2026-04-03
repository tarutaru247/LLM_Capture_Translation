"""
Translator that uses the Google Gemini API.
"""
import logging
from typing import Optional

import google.generativeai as genai

from ..utils.google_ai import (
    format_model_chain,
    get_google_model_candidates,
    should_retry_with_fallback,
)
from ..utils.localization import get_language_name
from ..utils.settings_manager import SettingsManager
from ..utils.utils import handle_exception, sanitize_sensitive_data
from .translator_service import TranslatorService

logger = logging.getLogger("ocr_translator")


class GeminiTranslator(TranslatorService):
    """Google AI を利用した翻訳サービス."""

    def __init__(self) -> None:
        self.settings_manager = SettingsManager()
        self._api_key: Optional[str] = None
        logger.info("GeminiTranslatorを初期化しました")

    def _refresh_api_key(self) -> None:
        """設定ファイルから最新の API キーを取得する."""
        self._api_key = self.settings_manager.get_api_key("gemini")

    def _generate_content_with_model_fallback(self, prompt, timeout: int):
        """Auto mode では一時的な障害時にフォールバックモデルへ切り替える。"""
        model_candidates = get_google_model_candidates(self.settings_manager)
        last_error: Exception | None = None

        for index, model_name in enumerate(model_candidates):
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt, request_options={"timeout": timeout})
                if index > 0:
                    logger.warning("Google AI モデルを %s にフォールバックしました。", model_name)
                return response, model_name
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Google AI モデル %s の呼び出しに失敗しました: %s",
                    model_name,
                    sanitize_sensitive_data(str(exc)),
                )
                can_retry = (
                    index < len(model_candidates) - 1
                    and self.settings_manager.get_llm_mode() == "auto"
                    and should_retry_with_fallback(exc)
                )
                if not can_retry:
                    raise

        if last_error is not None:
            raise last_error
        raise RuntimeError("利用可能なGoogle AIモデルが見つかりません。")

    def translate(self, text, source_lang=None, target_lang=None):
        """Google AI を使用してテキストを翻訳する."""
        self._refresh_api_key()

        if not text:
            logger.warning("翻訳するテキストがありません")
            return ""

        if not self._api_key:
            logger.error("Google APIキーが設定されていません")
            return "エラー: Google APIキーが設定されていません。設定画面でAPIキーを設定してください。"

        try:
            genai.configure(api_key=self._api_key)

            if not target_lang:
                target_lang = self.settings_manager.get_app_language()

            target_language_name = get_language_name(target_lang)

            prompt = (
                f"あなたの仕事は、入力テキストを必ず{target_language_name}へ翻訳することです。"
                f"出力は翻訳後の{target_language_name}の文章だけにしてください。"
                "元の文章は絶対に出力しないでください。"
                "説明、注釈、見出し、引用符、\"翻訳:\" のような前置きも禁止です。"
                "入力文に複数行がある場合は、意味の対応を保ちながら自然な改行で翻訳してください。"
                f"入力がすでに{target_language_name}でも、余計な説明を付けず本文だけを返してください。\n\n"
                "入力テキスト:\n"
                f"{text}"
            )

            logger.info(
                "Google AIによる翻訳を実行します（対象言語: %s, モデル候補: %s）",
                target_language_name,
                format_model_chain(get_google_model_candidates(self.settings_manager)),
            )

            response, model_name = self._generate_content_with_model_fallback(
                prompt,
                self.settings_manager.get_timeout(),
            )
            translated_text = (response.text or "").strip()
            logger.info("翻訳が完了しました。使用モデル: %s", model_name)
            return translated_text

        except Exception as exc:
            error_msg = handle_exception(logger, exc, "Google AIでの翻訳")
            return f"エラー: {error_msg}"

    def is_available(self):
        """Google API が利用可能かどうかを確認する."""
        self._refresh_api_key()
        return bool(self._api_key)

    def verify_api_key(self, api_key):
        """指定された API キーが Google AI で有効かどうかを検証する."""
        if not api_key:
            return False, "APIキーが入力されていません。"

        try:
            genai.configure(api_key=api_key)
            model_name = self.settings_manager.get_model_candidates()[0]
            model = genai.GenerativeModel(model_name)
            model.generate_content("test", request_options={"timeout": 5})
            logger.info("Google APIキーの検証に成功しました。")
            return True, ""
        except Exception as exc:
            safe_exc = sanitize_sensitive_data(str(exc))
            error_msg = f"Google APIキーの検証中にエラーが発生しました: {safe_exc}"
            logger.error(error_msg)
            if "timeout" in safe_exc.lower():
                return False, f"APIへの接続エラー: {safe_exc} (タイムアウトの可能性あり)"
            return False, error_msg
