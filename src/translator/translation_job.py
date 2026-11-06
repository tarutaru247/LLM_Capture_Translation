"""
Background translation job helpers isolated from the Qt UI process.
"""
from __future__ import annotations

import logging

from ..ocr.vision_ocr_service import VisionOCRService
from .translation_manager import TranslationManager

logger = logging.getLogger("ocr_translator")


def run_translation_job(image_bytes: bytes, target_lang: str, transcribe_original: bool) -> dict:
    """Run OCR / translation and return a serializable result payload."""
    logger.info("バックグラウンド翻訳ジョブを実行します。")
    result = {
        "translated_text": None,
        "extracted_text": "",
        "error_message": None,
        "last_used_model": None,
    }

    try:
        if transcribe_original:
            ocr_service = VisionOCRService()
            translation_manager = TranslationManager()
            extracted_text = ocr_service.extract_text(image_bytes)
            if extracted_text and not extracted_text.startswith("エラー:"):
                result["extracted_text"] = extracted_text
                translated_text = translation_manager.translate(extracted_text, target_lang=target_lang)
                result["translated_text"] = translated_text
                result["last_used_model"] = translation_manager.get_last_used_image_model()
            else:
                result["error_message"] = extracted_text or "テキストの抽出に失敗しました。"
        else:
            translation_manager = TranslationManager()
            translated_text = translation_manager.translate_image(image_bytes, target_lang)
            result["translated_text"] = translated_text
            result["last_used_model"] = translation_manager.get_last_used_image_model()
    except Exception as exc:
        logger.exception("バックグラウンド翻訳処理で予期せぬエラーが発生しました")
        result["error_message"] = str(exc)

    return result


def run_translation_job_process(
    image_bytes: bytes,
    target_lang: str,
    transcribe_original: bool,
    result_queue,
) -> None:
    """Process entrypoint that puts the result into a multiprocessing queue."""
    result = run_translation_job(image_bytes, target_lang, transcribe_original)
    result_queue.put(result)
