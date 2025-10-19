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

        model_name = self.settings_manager.get_model() or "gpt-4o-mini"

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

            logger.info("OpenAI APIによる翻訳を実行します（対象言語: %s）", target_language_name)

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

            translated_text = response.choices[0].message.content.strip()
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
                        f"エラー: 指定したモデル '{model_name}' は利用できません。"
                        "設定画面で有効なモデル名に変更してください。"
                    )
            else:
                detail_msg = str(exc.response)
            return f"エラー: OpenAI APIからエラー応答が返されました ({exc.status_code}): {detail_msg}"
        except Exception as exc:
            error_msg = handle_exception(logger, exc, "OpenAI APIでの翻訳")
            return f"エラー: {error_msg}"

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
