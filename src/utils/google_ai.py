"""
Google AI model selection helpers.
"""
from __future__ import annotations

from typing import Iterable

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
