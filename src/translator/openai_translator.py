"""
Translator that uses the OpenAI API.
"""
import logging
from typing import Optional

from openai import APIConnectionError, APIStatusError, AuthenticationError, OpenAI

from ..utils.settings_manager import SettingsManager
from ..utils.utils import handle_exception
from .translator_service import TranslatorService

logger = logging.getLogger("ocr_translator")


class OpenAITranslator(TranslatorService):
    """OpenAI API を利用した翻訳サービス."""

    def __init__(self) -> None:
        self.settings_manager = SettingsManager()
        self._api_key: Optional[str] = None
        self.client: Optional[OpenAI] = None
        logger.info("OpenAITranslatorを初期化しました")

    def _refresh_client(self) -> None:
        """設定ファイルの変更を反映してクライアントを更新する."""
        current_key = self.settings_manager.get_api_key("openai")
        if current_key != self._api_key:
            self._api_key = current_key
            self.client = OpenAI(api_key=self._api_key) if self._api_key else None

    def translate(self, text, source_lang=None, target_lang=None):
        """OpenAI API を使用してテキストを翻訳する."""
        self._refresh_client()

        if not text:
            logger.warning("翻訳するテキストがありません")
            return ""

        if not self._api_key or not self.client:
            logger.error("OpenAI APIキーが設定されていません")
            return "エラー: OpenAI APIキーが設定されていません。設定画面でAPIキーを設定してください。"

        configured_model = (self.settings_manager.get_model() or "gpt-5-nano").strip()
        if not configured_model:
            configured_model = "gpt-5-nano"
        # Unicodeハイフン等をASCIIに正規化して判定用IDを作る
        model_name = self._normalize_model_id(configured_model)

        try:
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

            logger.info("OpenAI APIによる翻訳を実行します（対象言語: %s, モデル: %s）", target_language_name, configured_model)

            if self._is_gpt5_model(model_name):
                translated_text = self._translate_with_responses(prompt, model_name)
            else:
                translated_text = self._translate_with_chat(prompt, model_name)

            logger.info("翻訳が完了しました")
            return translated_text

        except AuthenticationError:
            logger.error("OpenAI APIキーの認証に失敗しました。")
            return "エラー: OpenAI APIキーが無効です。認証情報を確認してください。"
        except APIConnectionError as exc:
            logger.error("OpenAI APIへの接続に失敗しました: %s", exc)
            return f"エラー: APIへの接続に失敗しました ({exc})."
        except APIStatusError as exc:
            error_detail = ""
            try:
                if exc.response is not None:
                    payload = exc.response.json()
                    error_detail = payload.get("error", {}).get("message") or exc.response.text
            except Exception:
                error_detail = exc.response.text if exc.response is not None else ""

            logger.error(
                "OpenAI APIからエラーが返されました: %s - %s - %s",
                exc.status_code,
                exc.response,
                error_detail,
            )
            if error_detail:
                detail_msg = error_detail
                if "does not exist" in error_detail.lower() or "unsupported" in error_detail.lower():
                    return (
                        f"エラー: 指定したモデル '{configured_model}' は利用できません。"
                        "設定画面で有効なモデル名に変更してください。"
                    )
            else:
                detail_msg = str(exc.response)
            return f"エラー: OpenAI APIからエラー応答が返されました ({exc.status_code}): {detail_msg}"
        except Exception as exc:
            error_msg = handle_exception(logger, exc, "OpenAI APIでの翻訳")
            return f"エラー: {error_msg}"

    def _translate_with_chat(self, prompt: str, model_name: str) -> str:
        """既存のChat Completions APIで翻訳する."""
        # 安全ガード：万一ここに来ても GPT-5 系なら Responses へ誘導
        if self._is_gpt5_model(model_name):
            raise RuntimeError("gpt-5 系モデルは Chat Completions 非対応です。Responses API を使用してください。")
        response = self.client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": "あなたは翻訳アシスタントです。与えられたテキストを指定言語に翻訳してください。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=1024,
            timeout=self.settings_manager.get_timeout(),
        )
        return response.choices[0].message.content.strip()

    def _translate_with_responses(self, prompt: str, model_name: str) -> str:
        """GPT-5 系モデル向けに Responses API を利用して翻訳する."""
        reasoning_effort = self.settings_manager.get_openai_reasoning_effort()
        verbosity = self.settings_manager.get_openai_verbosity()
        max_output_tokens = self.settings_manager.get_openai_max_output_tokens()

        verbosity_tips = {
            "low": "Keep the translation as concise as possible.",
            "medium": "Provide a natural translation without extra commentary.",
            "high": "Include any nuances needed for an accurate translation, but avoid unrelated commentary.",
        }
        system_prompt = (
            "You are a professional translation assistant. Translate any provided text into the requested language. "
            "Output only the translation."
        )
        if verbosity in verbosity_tips:
            system_prompt = f"{system_prompt} {verbosity_tips[verbosity]}"

        # Responses API expects explicit content type metadata for each part.
        request_params = {
            "model": model_name,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {"type": "text", "text": system_prompt},
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                    ],
                },
            ],
            "temperature": 0.3,
        }

        if reasoning_effort:
            request_params["reasoning_effort"] = reasoning_effort
        if verbosity:
            request_params["verbosity"] = verbosity
        if isinstance(max_output_tokens, int) and max_output_tokens > 0:
            request_params["max_output_tokens"] = max_output_tokens

        response = self.client.responses.create(
            timeout=self.settings_manager.get_timeout(),
            **request_params,
        )

        if getattr(response, "output_text", None):
            return response.output_text.strip()

        # Fallback: extract first text segment manually
        try:
            for item in response.output:
                if item.type == "message":
                    for content_part in getattr(item, "content", []):
                        if content_part.type == "output_text":
                            text_value = getattr(content_part, "text", "")
                            if text_value:
                                return text_value.strip()
        except AttributeError:
            pass

        raise RuntimeError("GPT-5 応答から翻訳結果を取得できませんでした。")

    @staticmethod
    def _is_gpt5_model(model_name: str) -> bool:
        # gpt-5 / gpt-5 / gpt–5 / gpt＿5 / gpt 5 なども許容
        import re
        return bool(re.match(r'^gpt[\-\u2010-\u2015\u2212\uFE63\uFF0D_ ]?5', (model_name or '').lower()))

    @staticmethod
    def _normalize_model_id(model_name: str) -> str:
        # 判定用に、よく混入する「ハイフンもどき」をASCIIの '-' に統一
        table = dict.fromkeys(map(ord, "‐-‒–—−﹣－"), ord('-'))
        return (model_name or "").translate(table).lower()

    def is_available(self):
        """OpenAI API が利用可能かどうかを確認する."""
        self._refresh_client()
        return bool(self._api_key)

    def verify_api_key(self, api_key):
        """指定された API キーが OpenAI で有効かどうかを検証する."""
        if not api_key:
            return False, "APIキーが入力されていません。"

        try:
            client = OpenAI(api_key=api_key, timeout=5.0)
            list(client.models.list())
            logger.info("OpenAI APIキーの検証に成功しました。")
            return True, ""
        except AuthenticationError:
            logger.error("OpenAI APIキーの認証に失敗しました。")
            return False, "APIキーが無効です。認証情報を確認してください。"
        except APIConnectionError as exc:
            logger.error("OpenAI APIへの接続に失敗しました: %s", exc)
            return False, f"APIへの接続エラー: {exc} (タイムアウトの可能性あり)"
        except APIStatusError as exc:
            detail = ""
            try:
                if exc.response is not None:
                    payload = exc.response.json()
                    detail = payload.get("error", {}).get("message") or exc.response.text
            except Exception:
                detail = exc.response.text if exc.response is not None else ""
            logger.error("OpenAI APIからエラーが返されました: %s - %s - %s", exc.status_code, exc.response, detail)
            if detail:
                return False, f"APIエラーが発生しました: {detail}"
            return False, f"APIエラーが発生しました: {exc.status_code} - {exc.response}"
        except Exception as exc:
            error_msg = f"OpenAI APIキーの検証中に予期しないエラーが発生しました: {exc}"
            logger.error(error_msg)
            return False, error_msg
