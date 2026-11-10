"""
Background translation job helpers isolated from the Qt UI process.
"""
from __future__ import annotations

import logging

from ..ocr.local_ocr_service import LocalOCRService
from ..utils.settings_manager import SettingsManager
from ..utils.providers import PROVIDERS
from .api_translator import APITranslator
from .combined_vision_translator import CombinedVisionTranslator
from .gemini_translator import GeminiTranslator

logger = logging.getLogger("ocr_translator")


def run_translation_job(image_bytes: bytes, target_lang: str, transcribe_original: bool = True,
                        provider: str = "plamo", text: str | None = None) -> dict:
    """Extract text in isolation. Translation runs in the resident local model."""
    logger.info("バックグラウンド翻訳ジョブを実行します。")
    result = {
        "translated_text": None,
        "extracted_text": "",
        "error_message": None,
        "last_used_model": None,
    }

    try:
        if provider not in ("plamo", "local_api", *PROVIDERS):
            raise ValueError("翻訳方式が不正です。")
        settings = SettingsManager()
        if provider in PROVIDERS:
            settings.require_cloud_access()
            if settings.get_translation_provider() != provider:
                raise PermissionError("翻訳先が変更されています。もう一度翻訳してください。")
        if provider == "gemini":
            if text is not None:
                translator = GeminiTranslator()
                translated = translator.translate(text, target_lang=target_lang)
                if not translated or translated.startswith("エラー:"):
                    raise RuntimeError(translated or "翻訳結果がありません。")
                result.update(extracted_text=text, translated_text=translated, last_used_model=translator.last_used_model)
                return result
            return CombinedVisionTranslator().translate_image_result(image_bytes, target_lang)
        if provider != "plamo":
            original = text if text is not None else LocalOCRService().extract_text(image_bytes)
            if not original.strip():
                raise RuntimeError("画像から文字を読み取れませんでした。")
            translator = APITranslator(settings)
            translated = translator.translate(original, target_lang, local=provider == "local_api")
            result.update(extracted_text=original, translated_text=translated, last_used_model=translator.last_used_model)
            return result
        if text is not None:
            result["extracted_text"] = text
            return result
        extracted_text = LocalOCRService().extract_text(image_bytes)
        if extracted_text and not extracted_text.startswith("エラー:"):
            result["extracted_text"] = extracted_text
        else:
            result["error_message"] = extracted_text or "テキストの抽出に失敗しました。"
    except Exception as exc:
        logger.error("バックグラウンド翻訳処理に失敗しました（%s）。", type(exc).__name__)
        from ..utils.utils import sanitize_sensitive_data
        if provider == 'gemini' and not isinstance(exc, PermissionError):
            result['error_message'] = 'Google APIで処理できませんでした。APIキー・モデル設定・利用制限・画像範囲を確認してください。'
        else:
            result["error_message"] = sanitize_sensitive_data(str(exc))

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
