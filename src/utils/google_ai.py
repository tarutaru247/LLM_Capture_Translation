"""
Google AI model selection helpers.
"""
from __future__ import annotations

from typing import Iterable

from google import genai
from google.genai import types

from .settings_manager import SettingsManager
from .utils import sanitize_sensitive_data

RETRYABLE_MODEL_ERROR_KEYWORDS = (
    "429",
    "rate limit",
    "resource exhausted",
    "quota",
    "503",
    "service unavailable",
    "unavailable",
    "overloaded",
    "temporarily unavailable",
)


def get_google_model_candidates(settings_manager: SettingsManager) -> list[str]:
    """Return model names in priority order."""
    return settings_manager.get_model_candidates()


def should_retry_with_fallback(exc: Exception) -> bool:
    """Return True when the error suggests temporary unavailability."""
    message = sanitize_sensitive_data(str(exc)).lower()
    return any(keyword in message for keyword in RETRYABLE_MODEL_ERROR_KEYWORDS)


def format_model_chain(models: Iterable[str]) -> str:
    """Format model names for logging or UI."""
    return " -> ".join(model for model in models if model)


def supports_minimal_thinking(model_name: str | None) -> bool:
    """Return True when the target model supports minimal thinking config."""
    lowered = (model_name or "").strip().lower()
    return lowered.startswith("gemini-3.1-flash-lite")


def build_generation_config_for_model(model_name: str | None):
    """Build per-model config. Thinking is only enabled on supported Gemini models."""
    if supports_minimal_thinking(model_name):
        return types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level="minimal")
        )
    return None


def create_google_client(api_key: str) -> genai.Client:
    """Create a Google GenAI client for Gemini API."""
    return genai.Client(api_key=api_key)
