import os
import logging
import base64
from io import BytesIO
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import QBuffer, QIODevice
from openai import APIStatusError

from ..utils.openai_responses import (
    build_reasoning_config,
    build_text_config,
    describe_api_status_error,
    extract_output_text,
    is_openai_vision_model,
    supports_temperature,
)
from ..utils.settings_manager import SettingsManager
from ..utils.utils import handle_exception, sanitize_sensitive_data
from .ocr_service import OCRService

logger = logging.getLogger('ocr_translator')

class VisionOCRService(OCRService):
    """
    LLM (Vision API) を使用して画像からテキストを抽出するサービス。
    OpenAI Vision と Gemini Vision の両方に対応。
    """

    def __init__(self):
        self.settings_manager = SettingsManager()
        logger.info("VisionOCRServiceを初期化しました")

    def is_available(self) -> bool:
        """
        Vision OCR サービスが利用可能かどうかを判定します。
        API キーが設定されていることを確認します。
        """
        selected_api = self.settings_manager.get_selected_api()
        api_key = self.settings_manager.get_api_key(selected_api)
        if not api_key:
            logger.warning(f"Vision OCR ({selected_api}) のAPIキーが設定されていません。")
            return False
        return True

    def extract_text(self, pixmap: QPixmap | QImage, lang: str = None) -> str:
        """
        画像からテキストを抽出します。

        Args:
            pixmap (QPixmap): 処理する画像。
            lang (str, optional): OCR言語。LLMのプロンプトに含めるために使用。

        Returns:
            str: 抽出されたテキスト。
        """
        if not self.is_available():
            return "エラー: Vision OCR サービスが利用できません。APIキーを確認してください。"

        if pixmap.isNull():
            logger.error("有効な画像がありません。")
            return ""

        try:
            selected_api = self.settings_manager.get_selected_api()
            api_key = self.settings_manager.get_api_key(selected_api)
            model_name = self.settings_manager.get_model_for_api(selected_api) # 共通モデルを使用
            timeout = self.settings_manager.get_timeout() # 共通タイムアウトを使用

            # 画像を base64 エンコードされた PNG データに変換
            buffer = QBuffer()
            buffer.open(QIODevice.ReadWrite)
            pixmap.save(buffer, "PNG")
            base64_image = base64.b64encode(buffer.data().data()).decode('utf-8')
            buffer.close()

            if selected_api == "openai":
                if not is_openai_vision_model(model_name):
                    msg = (
                        f"エラー: 選択されたOpenAIモデル '{model_name or '未設定'}' は画像入力をサポートしていません。"
                        " 設定画面で GPT-5 Vision 対応モデル（例: gpt-5-nano, gpt-5.1-vision）を選択してください。"
                    )
                    logger.error(msg)
                    return msg
                return self._extract_text_with_openai(base64_image, api_key, model_name, timeout, lang)
            elif selected_api == "gemini":
                return self._extract_text_with_gemini(base64_image, api_key, model_name, timeout, lang)
            else:
                logger.error(f"未対応のVision OCRプロバイダー: {selected_api}")
                return f"エラー: 未対応のVision OCRプロバイダー: {selected_api}"

        except Exception as e:
            error_msg = handle_exception(logger, e, "Vision OCR 処理")
            return f"エラー: Vision OCR 処理に失敗しました: {error_msg}"

    def _extract_text_with_openai(self, base64_image: str, api_key: str, model_name: str, timeout: int, lang: str = None) -> str:

        """OpenAI Vision API を使用してテキストを抽出します。"""

        try:

            from openai import OpenAI



            client = OpenAI(api_key=api_key, timeout=timeout)



            prompt_text = "画像内のテキストを改行を保ったまま抽出してください。OCR のみを行い、余計な説明は不要です。"

            if lang:

                prompt_text += f"テキストの言語は {lang} です。"



            instructions = (

                "You are an OCR assistant. Extract every piece of text from the provided image while preserving line breaks. "

                "Return only the extracted text."

            )



            user_turn = build_user_turn(
                prompt_text,
                images=[
                    {
                        "url": f"data:image/png;base64,{base64_image}",
                        "detail": "high",
                    }
                ],
            )


            configured_max = self.settings_manager.get_openai_max_output_tokens()

            if not isinstance(configured_max, int) or configured_max <= 0:

                configured_max = 4096



            temperature = 0.0
            if not supports_temperature(model_name):
                temperature = None

            responses_kwargs = {
                "model": model_name,
                "instructions": instructions,
                "input": [user_turn],

                "timeout": timeout,
                "max_output_tokens": configured_max,
                "text": build_text_config(self.settings_manager.get_openai_verbosity()),
            }

            if temperature is not None:
                responses_kwargs["temperature"] = temperature

            reasoning = build_reasoning_config(self.settings_manager.get_openai_reasoning_effort())
            if reasoning:
                responses_kwargs["reasoning"] = reasoning


            response = client.responses.create(**responses_kwargs)

            extracted_text = extract_output_text(response)

            logger.info("OpenAI Vision OCR 処理が完了しました（%s文字）", len(extracted_text))

            return extracted_text

        except APIStatusError as exc:
            message = describe_api_status_error(exc)
            logger.error("OpenAI APIからエラー応答: %s", message)
            return f"エラー: OpenAI Vision OCR 処理に失敗しました: {message}"
        except Exception as e:
            handle_exception(logger, e, "OpenAI Vision OCR 処理")
            safe_exc = sanitize_sensitive_data(str(e))
            return f"エラー: OpenAI Vision OCR 処理に失敗しました: {safe_exc}"

    def _extract_text_with_gemini(self, base64_image: str, api_key: str, model_name: str, timeout: int, lang: str = None) -> str:
        """
        Gemini Vision API を使用してテキストを抽出します。
        """
        try:
            import google.generativeai as genai
            from PIL import Image

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)

            # base64 を PIL Image に変換
            image_data = base64.b64decode(base64_image)
            pil_image = Image.open(BytesIO(image_data))

            prompt_text = "画像内のテキストを改行を保ったまま抽出してください。OCR のみを行い、余計な説明は不要です。"
            if lang:
                prompt_text += f"テキストの言語は{lang}です。" # LLMに言語ヒントを与える

            response = model.generate_content([prompt_text, pil_image],
                                              request_options={"timeout": timeout})
            extracted_text = response.text
            logger.info(f"Gemini Vision OCR 処理が完了しました（{len(extracted_text)}文字）")
            return extracted_text
        except Exception as e:
            handle_exception(logger, e, "Gemini Vision OCR 処理")
            safe_exc = sanitize_sensitive_data(str(e))
            return f"エラー: Gemini Vision OCR 処理に失敗しました: {safe_exc}"
