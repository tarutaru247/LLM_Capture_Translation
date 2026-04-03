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
from ..utils.localization import get_language_name
from ..utils.settings_manager import SettingsManager
from ..utils.utils import handle_exception, sanitize_sensitive_data
from .translator_service import TranslatorService

logger = logging.getLogger("ocr_translator")


class CombinedVisionTranslator(TranslatorService):
    """
    Google AI を使用して画像からテキストを抽出し、同時に翻訳するサービス。
    """

    def __init__(self):
        self.settings_manager = SettingsManager()
        logger.info("CombinedVisionTranslatorを初期化しました")

    def translate(self, text: str, source_lang: str = None, target_lang: str = None) -> str:
        raise NotImplementedError("CombinedVisionTranslator does not implement 'translate'. Use 'translate_image' instead.")

    def is_available(self) -> bool:
        api_key = self.settings_manager.get_api_key("gemini")
        if not api_key:
            logger.warning("Combined Vision Translator のGoogle APIキーが設定されていません。")
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
                    logger.warning("Vision一括翻訳でモデルを %s にフォールバックしました。", model_name)
                return response, model_name
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Vision一括翻訳モデル %s の呼び出しに失敗しました: %s",
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

    def translate_image(self, pixmap: QPixmap | QImage | bytes, target_lang: str = None) -> str:
        """画像からテキストを抽出し、指定された言語に翻訳します。"""
        if not self.is_available():
            return "エラー: 一括翻訳サービスが利用できません。Google APIキーを確認してください。"

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

            if not target_lang:
                target_lang = self.settings_manager.get_app_language()

            target_language_name = get_language_name(target_lang)

            prompt_text = (
                "あなたの仕事は画像内の文字を読み取り、翻訳後の文章だけを返すことです。"
                f"画像に写っているテキストを正確に読み取り、必ず{target_language_name}に翻訳してください。"
                f"出力は翻訳後の{target_language_name}の文章だけにしてください。"
                "読み取った元の文字列、OCR結果、説明、注釈、見出し、引用符、"
                "\"翻訳:\" や \"原文:\" のような前置きは絶対に出力しないでください。"
                "複数行の画像なら、意味の対応を保ちながら自然な改行で翻訳してください。"
                f"画像内テキストがすでに{target_language_name}でも、本文だけを返してください。"
            )

            logger.info(
                "Google AI Vision一括翻訳を実行します。モデル候補: %s",
                format_model_chain(get_google_model_candidates(self.settings_manager)),
            )
            response, model_name = self._generate_with_model_fallback(prompt_text, pil_image, timeout)
            translated_text = (response.text or "").strip()
            logger.info("Google AI Vision 一括翻訳処理が完了しました（%s文字, model=%s）", len(translated_text), model_name)
            return translated_text
        except Exception as e:
            handle_exception(logger, e, "Google AI Vision 一括翻訳処理")
            safe_exc = sanitize_sensitive_data(str(e))
            return f"エラー: Google AI Vision 一括翻訳処理に失敗しました: {safe_exc}"
