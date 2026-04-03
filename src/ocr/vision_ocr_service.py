import base64
import logging
from io import BytesIO

import google.generativeai as genai
from PIL import Image
from PyQt5.QtCore import QBuffer, QIODevice
from PyQt5.QtGui import QImage, QPixmap

from ..utils.google_ai import (
    format_model_chain,
    get_google_model_candidates,
    should_retry_with_fallback,
)
from ..utils.settings_manager import SettingsManager
from ..utils.utils import handle_exception, sanitize_sensitive_data
from .ocr_service import OCRService

logger = logging.getLogger("ocr_translator")


class VisionOCRService(OCRService):
    """
    Google AI (Vision) を使用して画像からテキストを抽出するサービス。
    """

    def __init__(self):
        self.settings_manager = SettingsManager()
        logger.info("VisionOCRServiceを初期化しました")

    def is_available(self) -> bool:
        api_key = self.settings_manager.get_api_key("gemini")
        if not api_key:
            logger.warning("Vision OCR のGoogle APIキーが設定されていません。")
            return False
        return True

    def _generate_with_model_fallback(self, prompt_text: str, pil_image: Image.Image, timeout: int):
        """Auto mode では一時的な障害時にフォールバックモデルへ切り替える。"""
        model_candidates = get_google_model_candidates(self.settings_manager)
        last_error: Exception | None = None

        for index, model_name in enumerate(model_candidates):
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content([prompt_text, pil_image], request_options={"timeout": timeout})
                if index > 0:
                    logger.warning("Vision OCR でモデルを %s にフォールバックしました。", model_name)
                return response, model_name
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Vision OCR モデル %s の呼び出しに失敗しました: %s",
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

    def extract_text(self, pixmap: QPixmap | QImage | bytes, lang: str = None) -> str:
        """画像からテキストを抽出します。"""
        if not self.is_available():
            return "エラー: Vision OCR サービスが利用できません。Google APIキーを確認してください。"

        base64_image: str | None = None

        if isinstance(pixmap, (bytes, bytearray)):
            if not pixmap:
                logger.error("有効な画像がありません。")
                return ""
            base64_image = base64.b64encode(pixmap).decode("utf-8")
        else:
            if pixmap.isNull():
                logger.error("有効な画像がありません。")
                return ""

        try:
            api_key = self.settings_manager.get_api_key("gemini")
            timeout = self.settings_manager.get_timeout()

            if base64_image is None:
                buffer = QBuffer()
                buffer.open(QIODevice.ReadWrite)
                pixmap.save(buffer, "PNG")
                base64_image = base64.b64encode(buffer.data().data()).decode("utf-8")
                buffer.close()

            genai.configure(api_key=api_key)
            image_data = base64.b64decode(base64_image)
            pil_image = Image.open(BytesIO(image_data))

            prompt_text = "画像内のテキストを改行を保ったまま抽出してください。OCR のみを行い、余計な説明は不要です。"
            if lang:
                prompt_text += f"テキストの言語は{lang}です。"

            logger.info(
                "Google AI Vision OCR を実行します。モデル候補: %s",
                format_model_chain(get_google_model_candidates(self.settings_manager)),
            )
            response, model_name = self._generate_with_model_fallback(prompt_text, pil_image, timeout)
            extracted_text = (response.text or "").strip()
            logger.info("Google AI Vision OCR 処理が完了しました（%s文字, model=%s）", len(extracted_text), model_name)
            return extracted_text
        except Exception as e:
            handle_exception(logger, e, "Google AI Vision OCR 処理")
            safe_exc = sanitize_sensitive_data(str(e))
            return f"エラー: Google AI Vision OCR 処理に失敗しました: {safe_exc}"
