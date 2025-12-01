"""
Settings manager module.
"""
import json
import logging
import os
import time
from typing import Any, Dict, Optional

from ..utils.utils import get_config_dir
from ..utils import secure_storage

logger = logging.getLogger("ocr_translator")

SUPPORTED_API_TYPES = ("openai", "gemini")
DEFAULT_MODELS_BY_API = {
    "openai": "gpt-5-nano",
    "gemini": "gemini-flash-lite-latest",
}


class SettingsManager:
    """Manage reading and writing application settings."""

    def __init__(self) -> None:
        self.config_dir = get_config_dir()
        self.config_file = os.path.join(self.config_dir, "settings.json")
        self._last_loaded_mtime: float | None = None
        self._last_mtime_check: float | None = None
        self.settings = self._load_settings()

    def _default_settings(self) -> Dict[str, Any]:
        return {
            "api": {
                "selected_api": "openai",  # 'openai' or 'gemini' (used for combined OCR as well)
                "openai_api_key": "",
                "gemini_api_key": "",
                "model": DEFAULT_MODELS_BY_API["openai"],  # legacy field mirrors the selected API model
                "models_by_api": DEFAULT_MODELS_BY_API.copy(),  # remember per-provider models
                "timeout": 60,  # API timeout in seconds
                "reasoning_effort": "medium",
                "verbosity": "medium",
                "max_output_tokens": 1024,
            },
            "language": {
                "target_language": "ja",  # default translation target
            },
            "ui": {
                "theme": "system",
                "start_minimized": False,
                "transcribe_original_text": False,  # flag for transcription-first workflow
            },
        }

    def _load_settings(self) -> Dict[str, Any]:
        """Load settings from disk and merge with defaults."""
        settings = self._default_settings()
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as fh:
                    loaded_settings = json.load(fh)
                self._update_nested_dict(settings, loaded_settings)
                try:
                    self._last_loaded_mtime = os.path.getmtime(self.config_file)
                except OSError:
                    self._last_loaded_mtime = None
            else:
                self._last_loaded_mtime = None
        except Exception as exc:
            logger.error("設定ファイルの読み込みでエラーが発生しました: %s", exc)
            self._last_loaded_mtime = None
        self._normalize_api_key_storage(settings)
        self._ensure_model_map(settings)
        return settings

    def _ensure_latest_settings(self) -> None:
        """Reload settings if the underlying file changed."""
        now = time.monotonic()
        if self._last_mtime_check is not None and (now - self._last_mtime_check) < 2:
            return
        self._last_mtime_check = now
        try:
            current_mtime = os.path.getmtime(self.config_file)
        except OSError:
            current_mtime = None

        if current_mtime is None:
            if self.settings is None:
                self.settings = self._default_settings()
            return

        if self._last_loaded_mtime != current_mtime:
            self.settings = self._load_settings()

    def _update_nested_dict(self, dest: Dict[str, Any], src: Dict[str, Any]) -> None:
        """Recursively merge dictionaries."""
        for key, value in src.items():
            if isinstance(value, dict) and key in dest and isinstance(dest[key], dict):
                self._update_nested_dict(dest[key], value)
            else:
                dest[key] = value

    def _ensure_model_map(self, settings: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """
        Ensure that per-API model values exist and are synchronized with the legacy single model field.
        """
        if settings is None:
            if self.settings is None:
                self.settings = self._default_settings()
            settings = self.settings

        api_settings = settings.setdefault("api", {})
        models = api_settings.get("models_by_api")
        if not isinstance(models, dict):
            models = {}
            api_settings["models_by_api"] = models

        selected_api = (api_settings.get("selected_api") or "openai").lower()
        if selected_api not in SUPPORTED_API_TYPES:
            selected_api = "openai"
            api_settings["selected_api"] = selected_api

        legacy_model = api_settings.get("model")
        if isinstance(legacy_model, str) and legacy_model.strip():
            models.setdefault(selected_api, legacy_model.strip())

        for api_type, default_model in DEFAULT_MODELS_BY_API.items():
            current = models.get(api_type)
            if not isinstance(current, str) or not current.strip():
                models[api_type] = default_model

        api_settings["model"] = models.get(selected_api, DEFAULT_MODELS_BY_API[selected_api])
        return models

    def _normalize_api_key_storage(self, settings: Optional[Dict[str, Any]] = None) -> None:
        """Ensure APIキーがDPAPI形式で保存されるよう整備する。"""
        if settings is None:
            settings = self.settings
        if not settings:
            return
        api_settings = settings.setdefault("api", {})
        for field in ("openai_api_key", "gemini_api_key"):
            value = api_settings.get(field)
            if not value or (isinstance(value, str) and value.startswith("dpapi:")):
                continue
            api_settings[field] = secure_storage.protect_secret(str(value))

    def save_settings(self) -> bool:
        """Persist current settings to disk."""
        try:
            self._ensure_model_map()
            with open(self.config_file, "w", encoding="utf-8") as fh:
                json.dump(self.settings, fh, indent=4, ensure_ascii=False)
            try:
                self._last_loaded_mtime = os.path.getmtime(self.config_file)
            except OSError:
                self._last_loaded_mtime = None
            logger.info("設定を保存しました")
            return True
        except Exception as exc:
            logger.error("設定の保存でエラーが発生しました: %s", exc)
            return False

    def reload_settings(self) -> None:
        """Force reload of settings from disk."""
        self.settings = self._load_settings()

    def get_setting(self, category: str, key: str, default: Any = None) -> Any:
        """Return the requested setting value."""
        self._ensure_latest_settings()
        try:
            return self.settings[category][key]
        except KeyError:
            logger.warning("設定が見つかりません: %s.%s (default=%s)", category, key, default)
            return default

    def set_setting(self, category: str, key: str, value: Any) -> bool:
        """Update a specific setting entry."""
        self._ensure_latest_settings()
        try:
            self.settings[category][key] = value
            return True
        except KeyError:
            logger.warning("設定カテゴリが見つかりません: %s", category)
            return False

    def get_api_key(self, api_type: str) -> str | None:
        """Return API key for the requested provider."""
        api_type_lower = api_type.lower()
        if api_type_lower == "openai":
            stored = self.get_setting("api", "openai_api_key")
            return secure_storage.unprotect_secret(stored)
        if api_type_lower == "gemini":
            stored = self.get_setting("api", "gemini_api_key")
            return secure_storage.unprotect_secret(stored)
        logger.warning("未対応のAPIキーが要求されました: %s", api_type)
        return None

    def set_api_key(self, api_type: str, api_key: str) -> bool:
        """Store API key for the requested provider."""
        api_type_lower = api_type.lower()
        if api_type_lower == "openai":
            protected = secure_storage.protect_secret(api_key or "")
            return self.set_setting("api", "openai_api_key", protected)
        if api_type_lower == "gemini":
            protected = secure_storage.protect_secret(api_key or "")
            return self.set_setting("api", "gemini_api_key", protected)
        logger.warning("未対応のAPIが指定されました: %s", api_type)
        return False
    def get_target_language(self) -> str:
        """Return configured translation target language code."""
        return self.get_setting("language", "target_language")

    def set_target_language(self, language_code: str) -> bool:
        """Persist translation target language code."""
        return self.set_setting("language", "target_language", language_code)

    def get_selected_api(self) -> str:
        """Return the selected API provider name."""
        return self.get_setting("api", "selected_api")

    def set_selected_api(self, api_type: str) -> bool:
        """Persist the selected API provider."""
        api_type_lower = api_type.lower()
        if api_type_lower in SUPPORTED_API_TYPES:
            updated = self.set_setting("api", "selected_api", api_type_lower)
            if updated:
                models = self._ensure_model_map()
                self.settings["api"]["model"] = models.get(
                    api_type_lower, DEFAULT_MODELS_BY_API[api_type_lower]
                )
            return updated
        logger.warning("無効なAPI種別が指定されました: %s", api_type)
        return False

    def get_model(self) -> str:
        """Return selected model name."""
        return self.get_model_for_api()

    def set_model(self, model_name: str) -> bool:
        """Persist model name."""
        return self.set_model_for_api(self.get_selected_api(), model_name)

    def get_model_for_api(self, api_type: str | None = None) -> str:
        """Return the stored model for a specific API (defaults to the currently selected API)."""
        self._ensure_latest_settings()
        models = self._ensure_model_map()
        selected_api = (api_type or self.get_selected_api() or "openai").lower()
        if selected_api not in SUPPORTED_API_TYPES:
            selected_api = "openai"
        model_name = models.get(selected_api)
        if isinstance(model_name, str) and model_name.strip():
            return model_name.strip()
        return DEFAULT_MODELS_BY_API[selected_api]

    def get_default_model_for_api(self, api_type: str) -> str:
        """Return the default model for the specified API."""
        return DEFAULT_MODELS_BY_API.get(api_type.lower(), DEFAULT_MODELS_BY_API["openai"])

    def set_model_for_api(self, api_type: str, model_name: str) -> bool:
        """Persist the model name for a specific API."""
        self._ensure_latest_settings()
        api_type_lower = (api_type or "").lower()
        if api_type_lower not in SUPPORTED_API_TYPES:
            logger.warning("無効なAPI種別が指定されました: %s", api_type)
            return False

        models = self._ensure_model_map()
        sanitized = (model_name or "").strip()
        if not sanitized:
            sanitized = DEFAULT_MODELS_BY_API[api_type_lower]
        models[api_type_lower] = sanitized

        if self.get_selected_api() == api_type_lower:
            self.settings["api"]["model"] = sanitized
        return True

    def get_timeout(self) -> int:
        """Return configured API timeout in seconds."""
        return self.get_setting("api", "timeout")

    def set_timeout(self, timeout: int) -> bool:
        """Persist API timeout value."""
        return self.set_setting("api", "timeout", timeout)

    def get_openai_reasoning_effort(self) -> str:
        """Return configured reasoning effort for OpenAI GPT-5 models."""
        return self.get_setting("api", "reasoning_effort", "medium")

    def set_openai_reasoning_effort(self, effort: str) -> bool:
        """Persist reasoning effort for OpenAI GPT-5 models."""
        return self.set_setting("api", "reasoning_effort", effort)

    def get_openai_verbosity(self) -> str:
        """Return configured verbosity for OpenAI GPT-5 models."""
        return self.get_setting("api", "verbosity", "medium")

    def set_openai_verbosity(self, verbosity: str) -> bool:
        """Persist verbosity for OpenAI GPT-5 models."""
        return self.set_setting("api", "verbosity", verbosity)

    def get_openai_max_output_tokens(self) -> int:
        """Return configured max output tokens for OpenAI GPT-5 models."""
        return self.get_setting("api", "max_output_tokens", 1024)

    def set_openai_max_output_tokens(self, value: int) -> bool:
        """Persist max output tokens for OpenAI GPT-5 models."""
        return self.set_setting("api", "max_output_tokens", value)

    def get_transcribe_original_text(self) -> bool:
        """Return transcription flag."""
        return self.get_setting("ui", "transcribe_original_text", False)

    def set_transcribe_original_text(self, value: bool) -> bool:
        """Persist transcription flag."""
        return self.set_setting("ui", "transcribe_original_text", value)


