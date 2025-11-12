"""
Translator that uses the OpenAI API (Responses API only).
- Always calls /v1/responses to avoid 400 with GPT-5 family.
- Logs endpoint/model at runtime for easy diagnostics.
"""
import logging
from typing import Optional

from openai import OpenAI, AuthenticationError, APIConnectionError, APIStatusError

from ..utils.openai_responses import (
    build_reasoning_config,
    build_text_config,
    describe_api_status_error,
    extract_output_text,
    supports_temperature,
)
from ..utils.settings_manager import SettingsManager
from ..utils.utils import handle_exception
from .translator_service import TranslatorService

logger = logging.getLogger("ocr_translator")


class OpenAITranslator(TranslatorService):
    """OpenAI API を利用した翻訳サービス（Responses API専用）"""

    def __init__(self) -> None:
        self.settings_manager = SettingsManager()
        self._api_key: Optional[str] = None
        self.client: Optional[OpenAI] = None
        logger.info("OpenAITranslator(Responses専用) を初期化しました")

    # ---------- 内部：クライアント更新 ----------
    def _refresh_client(self) -> None:
        """設定を反映してクライアントを更新"""
        current_key = self.settings_manager.get_api_key("openai")
        if current_key != self._api_key:
            self._api_key = current_key
            if not self._api_key:
                self.client = None
                logger.warning("OpenAI APIキー未設定のためクライアントを解放しました")
                return
            # base_url が設定マネージャにある場合はここで渡す
            self.client = OpenAI(api_key=self._api_key)
            logger.info("OpenAI クライアントを更新しました")

    # ---------- 公開：翻訳 ----------
    def translate(self, text, source_lang=None, target_lang=None) -> str:
        """OpenAI Responses API でテキストを翻訳"""
        self._refresh_client()

        if not text:
            logger.warning("翻訳するテキストが空です")
            return ""

        if not self._api_key or not self.client:
            logger.error("OpenAI APIキーが設定されていません")
            return "エラー: OpenAI APIキーが設定されていません。設定画面でAPIキーを設定してください。"

        # 設定上のモデル名（空なら gpt-5-nano を既定）
        configured_model = (self.settings_manager.get_model() or "gpt-5-nano").strip()
        model_name = self._normalize_model_id(configured_model)

        try:
            if not target_lang:
                target_lang = self.settings_manager.get_target_language()

            language_names = {
                "ja": "日本語", "en": "英語", "zh": "中国語", "ko": "韓国語",
                "fr": "フランス語", "de": "ドイツ語", "es": "スペイン語",
                "it": "イタリア語", "pt": "ポルトガル語", "ru": "ロシア語",
            }
            target_language_name = language_names.get(target_lang, target_lang or "指定言語")

            # 翻訳プロンプト（出力のみ要求）
            if source_lang:
                prompt = (
                    f"Translate the following {source_lang} text into {target_language_name}. "
                    "Output only the translation with no explanations:\n\n"
                    f"{text}"
                )
            else:
                prompt = (
                    f"Translate the following text into {target_language_name}. "
                    "Output only the translation with no explanations:\n\n"
                    f"{text}"
                )

            logger.info(
                "OpenAI 翻訳を実行: endpoint=responses, model=%s, target=%s",
                model_name, target_language_name
            )

            return self._translate_with_responses(prompt, model_name)

        except (AuthenticationError, APIConnectionError, APIStatusError) as exc:
            # API系エラーは詳細を吐く
            error_msg = self._format_api_error(exc)
            logger.error("OpenAI APIからエラー応答: %s", error_msg)
            return f"エラー: {error_msg}"
        except Exception as exc:
            error_msg = handle_exception(logger, exc, "OpenAI APIでの翻訳")
            return f"エラー: {error_msg}"

    # ---------- 内部：Responses API ----------
    def _translate_with_responses(self, prompt: str, model_name: str) -> str:

        """Responses API を用いた翻訳実行（常用）"""

        # 設定から取得するが、未対応のパラメータは送らない
        max_output_tokens = self.settings_manager.get_openai_max_output_tokens()
        timeout = self.settings_manager.get_timeout()
        temperature = getattr(self.settings_manager, "get_temperature", lambda: 0.3)()
        if not supports_temperature(model_name):
            temperature = None

        reasoning_config = build_reasoning_config(self.settings_manager.get_openai_reasoning_effort())
        text_config = build_text_config(self.settings_manager.get_openai_verbosity())

        # system 相当の instructions に置き換え
        system_prompt = (
            "You are a professional translation assistant. Translate any provided text into the requested language. "
            "Output only the translation."
        )

        responses_kwargs = {
            "model": model_name,
            "instructions": system_prompt,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                    ],
                }
            ],
            "max_output_tokens": (
                max_output_tokens if isinstance(max_output_tokens, int) and max_output_tokens > 0 else None
            ),
            "timeout": timeout,
            "text": text_config,
        }

        if temperature is not None:
            responses_kwargs["temperature"] = temperature
        if reasoning_config:
            responses_kwargs["reasoning"] = reasoning_config

        resp = self.client.responses.create(**responses_kwargs)

        return extract_output_text(resp)

    # ---------- 内部：エラー整形 ----------
    @staticmethod
    def _format_api_error(exc: APIStatusError) -> str:

        """APIStatusError から詳細メッセージを抽出"""

        return describe_api_status_error(exc)


    # ---------- 内部：ユーティリティ ----------
    @staticmethod
    def _normalize_model_id(model_name: str) -> str:
        """設定上のモデル名をそのまま使用（必要ならここで変換）"""
        return (model_name or "").strip()

    # ---------- 公開：利用可否 ----------
    def is_available(self):
        """OpenAI APIキーが設定されているか"""
        return bool(self.settings_manager.get_api_key("openai"))

    # ---------- 公開：APIキー検証 ----------
    def verify_api_key(self, api_key):
        """
        APIキーが有効か検証する
        成功: (True, "")
        失敗: (False, "理由")
        """
        try:
            if not api_key:
                return False, "APIキーが入力されていません。"

            client = OpenAI(api_key=api_key)
            # 軽量操作で権限チェック
            _ = list(client.models.list())
            logger.info("OpenAI APIキーの検証に成功しました")
            return True, ""
        except AuthenticationError:
            logger.error("OpenAI APIキーの認証に失敗しました。")
            return False, "APIキーが無効です。認証情報を確認してください。"
        except APIConnectionError as exc:
            logger.error("OpenAI APIへの接続に失敗しました: %s", exc)
            return False, f"APIへの接続エラー: {exc} (タイムアウトの可能性あり)"
        except APIStatusError as exc:
            return False, OpenAITranslator._format_api_error(exc)
        except Exception as exc:
            logger.error("OpenAI APIキー検証中に予期せぬエラー: %s", exc)
            return False, f"予期せぬエラー: {exc}"
