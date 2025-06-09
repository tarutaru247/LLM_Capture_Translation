import logging
import base64
from io import BytesIO
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import QBuffer, QIODevice

from openai import OpenAI, APIStatusError, APIConnectionError, AuthenticationError
import google.generativeai as genai
from PIL import Image

from ..utils.settings_manager import SettingsManager
from ..utils.utils import handle_exception
from .translator_service import TranslatorService

logger = logging.getLogger('ocr_translator')

class CombinedVisionTranslator(TranslatorService):
    """
    LLM (Vision API) を使用して画像からテキストを抽出し、同時に翻訳するサービス。
    OpenAI Vision と Gemini Vision の両方に対応。
    """

    def __init__(self):
        self.settings_manager = SettingsManager()
        logger.info("CombinedVisionTranslatorを初期化しました")

    def translate(self, text: str, source_lang: str = None, target_lang: str = None) -> str:
        """
        CombinedVisionTranslatorではこのメソッドは使用されません。
        translate_image メソッドを使用してください。
        """
        raise NotImplementedError("CombinedVisionTranslator does not implement 'translate'. Use 'translate_image' instead.")

    def is_available(self) -> bool:
        """
        Combined Vision Translator サービスが利用可能かどうかを判定します。
        API キーが設定されていることを確認します。
        """
        selected_api = self.settings_manager.get_selected_api()
        api_key = self.settings_manager.get_api_key(selected_api)
        if not api_key:
            logger.warning(f"Combined Vision Translator ({selected_api}) のAPIキーが設定されていません。")
            return False
        return True

    def translate_image(self, pixmap: QPixmap, target_lang: str = None) -> str:
        """
        画像からテキストを抽出し、指定された言語に翻訳します。

        Args:
            pixmap (QPixmap): 処理する画像。
            target_lang (str, optional): 翻訳先の言語コード。Noneの場合はデフォルト言語。

        Returns:
            str: 抽出・翻訳されたテキスト。
        """
        if not self.is_available():
            return "エラー: Combined Vision Translator サービスが利用できません。APIキーを確認してください。"

        if pixmap.isNull():
            logger.error("有効な画像がありません。")
            return ""

        try:
            selected_api = self.settings_manager.get_selected_api()
            api_key = self.settings_manager.get_api_key(selected_api)
            model_name = self.settings_manager.get_model()
            timeout = self.settings_manager.get_timeout()

            # QPixmap を base64 エンコードされた PNG データに変換
            buffer = QBuffer()
            buffer.open(QIODevice.ReadWrite)
            pixmap.save(buffer, "PNG")
            base64_image = base64.b64encode(buffer.data().data()).decode('utf-8')
            buffer.close()

            if selected_api == "openai":
                return self._extract_and_translate_with_openai(base64_image, api_key, model_name, timeout, target_lang)
            elif selected_api == "gemini":
                return self._extract_and_translate_with_gemini(base64_image, api_key, model_name, timeout, target_lang)
            else:
                logger.error(f"未対応のCombined Vision Translatorプロバイダー: {selected_api}")
                return f"エラー: 未対応のCombined Vision Translatorプロバイダー: {selected_api}"

        except Exception as e:
            error_msg = handle_exception(logger, e, "Combined Vision Translator 処理")
            return f"Combined Vision Translator 処理エラー: {error_msg}"

    def _extract_and_translate_with_openai(self, base64_image: str, api_key: str, model_name: str, timeout: int, target_lang: str = None) -> str:
        """
        OpenAI Vision API を使用してテキストを抽出し、翻訳します。
        """
        try:
            client = OpenAI(api_key=api_key, timeout=timeout)

            if not target_lang:
                target_lang = self.settings_manager.get_target_language()

            language_names = {
                'ja': '日本語', 'en': '英語', 'zh': '中国語', 'ko': '韓国語',
                'fr': 'フランス語', 'de': 'ドイツ語'
            }
            target_language_name = language_names.get(target_lang, target_lang)

            prompt_text = (
                f"画像に写っているテキストを抽出し、{target_language_name} に翻訳してください。"
                "抽出・翻訳後のテキストのみを改行を保って出力してください。余計な説明は不要です。"
            )

            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_text},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}",
                                    "detail": "high"
                                },
                            },
                        ],
                    }
                ],
                max_tokens=4096,
            )
            translated_text = response.choices[0].message.content
            logger.info(f"OpenAI Vision 一括翻訳処理が完了しました（{len(translated_text)}文字）")
            return translated_text
        except AuthenticationError:
            logger.error("OpenAI APIキーの認証に失敗しました。")
            return "エラー: OpenAI APIキーが無効です。認証情報を確認してください。"
        except APIConnectionError as e:
            logger.error(f"OpenAI APIへの接続に失敗しました: {e}")
            return f"翻訳エラー: APIへの接続エラーが発生しました: {e}"
        except APIStatusError as e:
            logger.error(f"OpenAI APIからエラー応答: {e.status_code} - {e.response}")
            return f"翻訳エラー: APIエラーが発生しました: {e.status_code} - {e.response}"
        except Exception as e:
            handle_exception(logger, e, "OpenAI Vision 一括翻訳処理")
            return f"OpenAI Vision 一括翻訳エラー: {e}"

    def _extract_and_translate_with_gemini(self, base64_image: str, api_key: str, model_name: str, timeout: int, target_lang: str = None) -> str:
        """
        Gemini Vision API を使用してテキストを抽出し、翻訳します。
        """
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)

            image_data = base64.b64decode(base64_image)
            pil_image = Image.open(BytesIO(image_data))

            if not target_lang:
                target_lang = self.settings_manager.get_target_language()

            language_names = {
                'ja': '日本語', 'en': '英語', 'zh': '中国語', 'ko': '韓国語',
                'fr': 'フランス語', 'de': 'ドイツ語'
            }
            target_language_name = language_names.get(target_lang, target_lang)

            prompt_text = (
                f"画像に写っているテキストを抽出し、{target_language_name} に翻訳してください。"
                "抽出・翻訳後のテキストのみを改行を保って出力してください。余計な説明は不要です。"
            )

            response = model.generate_content([prompt_text, pil_image],
                                              request_options={"timeout": timeout})
            translated_text = response.text
            logger.info(f"Gemini Vision 一括翻訳処理が完了しました（{len(translated_text)}文字）")
            return translated_text
        except Exception as e:
            handle_exception(logger, e, "Gemini Vision 一括翻訳処理")
            return f"Gemini Vision 一括翻訳エラー: {e}"
