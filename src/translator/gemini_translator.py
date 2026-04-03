"""
Translator that uses the Google GenAI SDK.
"""
import logging
from typing import Optional

from ..utils.google_ai import (
    create_google_client,
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
        self._api_key = self.settings_manager.get_api_key("gemini")

    def _generate_content_with_model_fallback(self, prompt: str, timeout: int):
        """Auto mode では一時的な障害時にフォールバックモデルへ切り替える。"""
        model_candidates = get_google_model_candidates(self.settings_manager)
        last_error: Exception | None = None
        client = create_google_client(self._api_key or "")

        for index, model_name in enumerate(model_candidates):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
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
        self._refresh_api_key()

        if not text:
            logger.warning("翻訳するテキストがありません")
            return ""

        if not self._api_key:
            logger.error("Google APIキーが設定されていません")
            return "エラー: Google APIキーが設定されていません。設定画面でAPIキーを設定してください。"

        try:
            if not target_lang:
                target_lang = self.settings_manager.get_app_language()

            target_language_name = get_language_name(target_lang)

            prompt = (
                f"# 今から与えられる文字列を全て{target_language_name}に翻訳してください\n\n"
                "## ルール\n\n"
                "- 出力される文字は翻訳後の文字列のみになります。他の一切の文字が混入することは禁止されています\n\n"
                "- 文章の意味の説明は不要です。翻訳後の文章をそのまま出力してください\n\n"
                "- 固有名詞は無理に意訳せず音訳してください\n\n"
                f"- 入力文字が不明瞭で読めない場合は、推測せず不明瞭で読めないという文を{target_language_name}で出力してください。この時のみ例外的に翻訳後文章以外の出力が許可されます\n\n"
                "## 例\n"
                "出力先言語 : 日本語\n"
                "入力文章 : Hello, how are you doing?\n"
                "出力 : こんにちは、調子はどうですか？\n\n"
                "出力先言語 : 英語\n"
                "入力文章 : 今日は雨降るらしいから傘持っていった方がいいよ\n"
                "出力 : It's supposed to rain today, so you should take an umbrella.\n\n"
                "## 入力文章\n"
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
        self._refresh_api_key()
        return bool(self._api_key)

    def verify_api_key(self, api_key):
        if not api_key:
            return False, "APIキーが入力されていません。"

        try:
            client = create_google_client(api_key)
            model_name = self.settings_manager.get_model_candidates()[0]
            client.models.generate_content(model=model_name, contents="test")
            logger.info("Google APIキーの検証に成功しました。")
            return True, ""
        except Exception as exc:
            safe_exc = sanitize_sensitive_data(str(exc))
            error_msg = f"Google APIキーの検証中にエラーが発生しました: {safe_exc}"
            logger.error(error_msg)
            if "timeout" in safe_exc.lower():
                return False, f"APIへの接続エラー: {safe_exc} (タイムアウトの可能性あり)"
            return False, error_msg
