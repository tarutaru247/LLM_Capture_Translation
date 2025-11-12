"""
Utility helpers for working with the OpenAI Responses API.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from openai import APIStatusError

_ALLOWED_REASONING_EFFORTS = {"minimal", "low", "medium", "high"}
_ALLOWED_VERBOSITY = {"low", "medium", "high"}
_VISION_KEYWORDS = ("gpt-5",)
_NO_TEMPERATURE_PREFIXES = ("gpt-5",)


def build_reasoning_config(effort: Optional[str]) -> Optional[Dict[str, str]]:
    """
    Normalize the configured reasoning effort into the shape expected by the API.
    """
    if not effort:
        return None
    normalized = effort.strip().lower()
    if normalized not in _ALLOWED_REASONING_EFFORTS:
        return None
    return {"effort": normalized}


def build_text_config(verbosity: Optional[str]) -> Dict[str, Any]:
    """
    Build the text configuration block. Verbosity is optional but the format hint
    keeps outputs consistently textual even when tools are involved.
    """
    config: Dict[str, Any] = {"format": {"type": "text"}}
    if verbosity:
        normalized = verbosity.strip().lower()
        if normalized in _ALLOWED_VERBOSITY:
            config["verbosity"] = normalized
    return config


def build_user_turn(text: Optional[str] = None, *, images: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """
    Build a user role turn following the official Responses API format.
    Images must be provided as {"url": "...", "detail": "high|low|auto"} dictionaries.
    """
    contents: List[Dict[str, Any]] = []
    if text:
        contents.append({"type": "input_text", "text": text})
    if images:
        for image in images:
            contents.append(
                {
                    "type": "input_image",
                    "image_url": image["url"],
                    "detail": image.get("detail", "auto"),
                }
            )
    return {"role": "user", "content": contents}


def extract_output_text(response: Any) -> str:
    """
    Extract plain text from a Responses API payload, handling both the helper
    attribute (output_text) and the low-level array form.
    """
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()

    try:
        output = getattr(response, "output", None) or []
        if output and isinstance(output, list):
            first = output[0]
            content = first.get("content") if isinstance(first, dict) else None
            if content and isinstance(content, list):
                item = content[0]
                if isinstance(item, dict) and item.get("type") in {"output_text", "text"}:
                    raw_text = item.get("text") or ""
                    return raw_text.strip()
    except Exception:
        pass

    return ""


def is_openai_vision_model(model_name: Optional[str]) -> bool:
    """
    GPT-5 ファミリーのみを想定し、モデルIDに gpt-5 が含まれていれば画像入力対応とみなす。
    """
    if not model_name:
        return False
    lowered = model_name.lower()
    return lowered.startswith(_VISION_KEYWORDS[0])


def describe_api_status_error(exc: APIStatusError) -> str:
    """
    Extract readable error information from APIStatusError.
    """
    try:
        if exc.response is not None:
            try:
                payload = exc.response.json()
            except Exception:
                payload = None
            if payload:
                message = (
                    payload.get("error", {}).get("message")
                    or payload.get("message")
                    or ""
                )
                if message:
                    return f"{exc.status_code} - {message}"
            text = getattr(exc.response, "text", "") or ""
            if text:
                return f"{exc.status_code} - {text}"
        return f"{getattr(exc, 'status_code', '400')} - <Response [Bad Request]>"
    except Exception:
        return "不明なAPIエラーが発生しました"


def supports_temperature(model_name: Optional[str]) -> bool:
    """
    Some GPT-5 models reject the temperature parameter. Skip it for those models.
    """
    if not model_name:
        return True
    lowered = model_name.lower()
    return not any(lowered.startswith(prefix) for prefix in _NO_TEMPERATURE_PREFIXES)
