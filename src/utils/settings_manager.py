"""
Settings manager module.
"""
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from ..utils import secure_storage
from ..utils.localization import get_system_default_language, normalize_app_language
from ..utils.utils import get_config_dir

logger = logging.getLogger("ocr_translator")

SUPPORTED_API_TYPES = ("gemini",)
DEFAULT_PRIMARY_MODEL = "gemini-3.5-flash-lite"
DEFAULT_FALLBACK_MODEL = "gemma-4-26b-a4b-it"
DEFAULT_LLM_MODE = "auto"
LEGACY_PRIMARY_MODELS = frozenset(
    {
        "gemini-3.1-flash-lite-preview",
        "gemini-3.1-flash-lite",
    }
)


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
            "local_model": {
                "backend": "gguf",
                "profile": "lightweight",
                "device": "auto",
                "lightweight_path": str(self._model_directory() / "plamo-3-translate-0.8b-Q4_K_M.gguf"),
                "quality_path": str(self._model_directory() / "plamo-3-translate-2b-Q4_K_M.gguf"),
                "llama_server_path": "",
                "gpu_server_path": "",
            },
            "translation": {"provider": "plamo"},
            "history": {"enabled": True, "limit": 500},
            "shortcuts": {"capture": "Ctrl+Shift+X", "selection": "Ctrl+Shift+C"},
            "api": {
                "selected_api": "gemini",
                "gemini_api_key": "",
                "llm_mode": DEFAULT_LLM_MODE,
                "custom_model": "",
                "model": DEFAULT_PRIMARY_MODEL,
                "fallback_model": DEFAULT_FALLBACK_MODEL,
                "timeout": 60,
            },
            "language": {
                "app_language": get_system_default_language(),
                "target_language": "ja",
            },
            "ui": {
                "theme": "system",
                "start_minimized": False,
                "transcribe_original_text": False,
            },
        }

    def _model_directory(self):
        existing = Path(r"D:\LocalLLM\models")
        return existing if existing.is_dir() else Path(self.config_dir) / "models"

    def _load_settings(self) -> Dict[str, Any]:
        """Load settings from disk and merge with defaults."""
        settings = self._default_settings()
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as fh:
                    loaded_settings = json.load(fh)
                self._update_nested_dict(settings, loaded_settings)
                loaded_language = loaded_settings.get("language", {})
                if "target_language" not in loaded_language:
                    settings["language"]["target_language"] = loaded_language.get("app_language", "ja")
                try:
                    self._last_loaded_mtime = os.path.getmtime(self.config_file)
                except OSError:
                    self._last_loaded_mtime = None
            else:
                self._last_loaded_mtime = None
        except Exception as exc:
            logger.error("設定ファイルの読み込みでエラーが発生しました: %s", exc)
            self._last_loaded_mtime = None

        self._migrate_legacy_settings(settings)
        self._normalize_api_key_storage(settings)
        self._sync_active_model(settings)
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

    def _migrate_legacy_settings(self, settings: Optional[Dict[str, Any]] = None) -> None:
        """Translate older OpenAI/Gemini mixed settings into the new Google-only schema."""
        if settings is None:
            settings = self.settings
        if not settings:
            return

        local = settings.setdefault("local_model", {})
        if local.get("gguf_path"):
            local["lightweight_path"] = local.pop("gguf_path")
        local["backend"] = "gguf"
        local.pop("bf16_path", None)
        local.pop("python_path", None)
        if local.get("profile") not in ("lightweight", "quality"):
            local["profile"] = "lightweight"
        if local.get("device") not in ("auto", "cpu", "gpu"):
            local["device"] = "auto"
        translation = settings.setdefault("translation", {})
        if translation.get("provider") not in ("plamo", "gemini"):
            translation["provider"] = "plamo"
        history = settings.setdefault("history", {})
        try:
            history["limit"] = min(5000, max(10, int(history.get("limit", 500))))
        except (TypeError, ValueError):
            history["limit"] = 500

        api_settings = settings.setdefault("api", {})
        api_settings["selected_api"] = "gemini"

        llm_mode = api_settings.get("llm_mode")
        llm_mode_is_legacy = llm_mode not in ("auto", "custom")
        if llm_mode_is_legacy:
            api_settings["llm_mode"] = DEFAULT_LLM_MODE

        custom_model = api_settings.get("custom_model")
        if not isinstance(custom_model, str):
            custom_model = ""
        custom_model = custom_model.strip()
        api_settings["custom_model"] = custom_model

        if llm_mode_is_legacy and not custom_model:
            legacy_candidate = ""
            models_by_api = api_settings.get("models_by_api")
            if isinstance(models_by_api, dict):
                value = models_by_api.get("gemini")
                if isinstance(value, str):
                    legacy_candidate = value.strip()

            if not legacy_candidate:
                legacy_model = api_settings.get("model")
                if isinstance(legacy_model, str):
                    legacy_candidate = legacy_model.strip()

            lowered = legacy_candidate.lower()
            if lowered.startswith("gemini") or lowered.startswith("gemma"):
                if (
                    legacy_candidate != DEFAULT_PRIMARY_MODEL
                    and legacy_candidate != DEFAULT_FALLBACK_MODEL
                    and legacy_candidate not in LEGACY_PRIMARY_MODELS
                ):
                    api_settings["llm_mode"] = "custom"
                    api_settings["custom_model"] = legacy_candidate

        if api_settings["llm_mode"] != "custom":
            api_settings["custom_model"] = ""

        api_settings["fallback_model"] = DEFAULT_FALLBACK_MODEL
        api_settings["models_by_api"] = {"gemini": DEFAULT_PRIMARY_MODEL}
        api_settings.pop("openai_api_key", None)

        language_settings = settings.setdefault("language", {})
        legacy_target = language_settings.get("target_language")
        app_language = language_settings.get("app_language")
        if not isinstance(app_language, str) or not app_language.strip():
            if isinstance(legacy_target, str) and legacy_target.strip():
                language_settings["app_language"] = normalize_app_language(legacy_target)
            else:
                language_settings["app_language"] = get_system_default_language()
        else:
            language_settings["app_language"] = normalize_app_language(app_language)

        vision_ocr_settings = settings.setdefault("vision_ocr", {})
        vision_ocr_settings["provider"] = "gemini"
        vision_ocr_settings["model"] = DEFAULT_PRIMARY_MODEL
        vision_ocr_settings["timeout"] = api_settings.get("timeout", 60)
        vision_ocr_settings.pop("openai_api_key", None)

    def _sync_active_model(self, settings: Optional[Dict[str, Any]] = None) -> None:
        """Mirror the currently active model into the legacy `model` field."""
        if settings is None:
            if self.settings is None:
                self.settings = self._default_settings()
            settings = self.settings

        api_settings = settings.setdefault("api", {})
        llm_mode = api_settings.get("llm_mode", DEFAULT_LLM_MODE)
        custom_model = api_settings.get("custom_model", "")

        active_model = DEFAULT_PRIMARY_MODEL
        if llm_mode == "custom" and isinstance(custom_model, str) and custom_model.strip():
            active_model = custom_model.strip()

        api_settings["model"] = active_model
        api_settings["fallback_model"] = DEFAULT_FALLBACK_MODEL

    def _normalize_api_key_storage(self, settings: Optional[Dict[str, Any]] = None) -> None:
        """Ensure APIキーがDPAPI形式で保存されるよう整備する。"""
        if settings is None:
            settings = self.settings
        if not settings:
            return

        api_settings = settings.setdefault("api", {})
        for field in ("gemini_api_key", "openai_api_key"):
            value = api_settings.get(field)
            if not value or (isinstance(value, str) and value.startswith("dpapi:")):
                continue
            api_settings[field] = secure_storage.protect_secret(str(value))

    def save_settings(self) -> bool:
        """Persist current settings to disk."""
        try:
            self._migrate_legacy_settings()
            self._sync_active_model()
            temporary = self.config_file + ".tmp"
            with open(temporary, "w", encoding="utf-8") as fh:
                json.dump(self.settings, fh, indent=4, ensure_ascii=False)
            os.replace(temporary, self.config_file)
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

    def get_api_key(self, api_type: str = "gemini") -> str | None:
        """Return API key for the requested provider."""
        if (api_type or "gemini").lower() != "gemini":
            logger.warning("未対応のAPIキーが要求されました: %s", api_type)
            return None
        stored = self.get_setting("api", "gemini_api_key")
        return secure_storage.unprotect_secret(stored)

    def set_api_key(self, api_type: str, api_key: str) -> bool:
        """Store API key for the requested provider."""
        if (api_type or "").lower() != "gemini":
            logger.warning("未対応のAPIが指定されました: %s", api_type)
            return False
        protected = secure_storage.protect_secret(api_key or "")
        return self.set_setting("api", "gemini_api_key", protected)

    def get_app_language(self) -> str:
        """Return configured app language code."""
        return normalize_app_language(self.get_setting("language", "app_language", get_system_default_language()))

    def set_app_language(self, language_code: str) -> bool:
        """Persist app language code."""
        return self.set_setting("language", "app_language", normalize_app_language(language_code))

    def get_target_language(self) -> str:
        return normalize_app_language(self.get_setting("language", "target_language", "ja"))

    def set_target_language(self, language_code: str) -> bool:
        return self.set_setting("language", "target_language", normalize_app_language(language_code))

    def get_translation_provider(self):
        return self.get_setting("translation", "provider", "plamo")

    def get_local_profile(self):
        return self.get_setting("local_model", "profile", "lightweight")

    def get_local_model_path(self):
        return self.get_setting("local_model", self.get_local_profile() + "_path", "")

    def get_selected_api(self) -> str:
        """Return the selected API provider name."""
        return "gemini"

    def set_selected_api(self, api_type: str) -> bool:
        """Persist the selected API provider."""
        if (api_type or "").lower() != "gemini":
            logger.warning("Google API専用のため、API種別 %s は利用できません。", api_type)
        return self.set_setting("api", "selected_api", "gemini")

    def get_llm_mode(self) -> str:
        """Return the configured LLM mode."""
        mode = self.get_setting("api", "llm_mode", DEFAULT_LLM_MODE)
        return mode if mode in ("auto", "custom") else DEFAULT_LLM_MODE

    def set_llm_mode(self, mode: str) -> bool:
        """Persist LLM mode."""
        normalized = (mode or DEFAULT_LLM_MODE).strip().lower()
        if normalized not in ("auto", "custom"):
            normalized = DEFAULT_LLM_MODE
        updated = self.set_setting("api", "llm_mode", normalized)
        if updated and normalized != "custom":
            self.set_custom_model("")
        self._sync_active_model()
        return updated

    def get_custom_model(self) -> str:
        """Return the custom model name."""
        value = self.get_setting("api", "custom_model", "")
        return value.strip() if isinstance(value, str) else ""

    def set_custom_model(self, model_name: str) -> bool:
        """Persist custom model name."""
        updated = self.set_setting("api", "custom_model", (model_name or "").strip())
        self._sync_active_model()
        return updated

    def get_model(self) -> str:
        """Return the active model name."""
        if self.get_llm_mode() == "custom":
            custom_model = self.get_custom_model()
            if custom_model:
                return custom_model
        return DEFAULT_PRIMARY_MODEL

    def set_model(self, model_name: str) -> bool:
        """Persist active model as custom when explicitly specified."""
        sanitized = (model_name or "").strip()
        if not sanitized:
            return self.set_llm_mode("auto")
        self.set_custom_model(sanitized)
        return self.set_llm_mode("custom")

    def get_model_for_api(self, api_type: str | None = None) -> str:
        """Compatibility wrapper for legacy callers."""
        return self.get_model()

    def get_default_model_for_api(self, api_type: str) -> str:
        """Return the default Google model."""
        return DEFAULT_PRIMARY_MODEL

    def set_model_for_api(self, api_type: str, model_name: str) -> bool:
        """Compatibility wrapper for legacy callers."""
        if (api_type or "gemini").lower() != "gemini":
            logger.warning("無効なAPI種別が指定されました: %s", api_type)
            return False
        return self.set_model(model_name)

    def get_timeout(self) -> int:
        """Return configured API timeout in seconds."""
        return self.get_setting("api", "timeout")

    def set_timeout(self, timeout: int) -> bool:
        """Persist API timeout value."""
        return self.set_setting("api", "timeout", timeout)

    def get_primary_google_model(self) -> str:
        """Return the built-in primary model for auto mode."""
        return DEFAULT_PRIMARY_MODEL

    def get_fallback_google_model(self) -> str:
        """Return the built-in fallback model for auto mode."""
        return DEFAULT_FALLBACK_MODEL

    def get_model_candidates(self) -> list[str]:
        """Return model names in the order they should be attempted."""
        if self.get_llm_mode() == "custom":
            custom_model = self.get_custom_model()
            return [custom_model] if custom_model else [DEFAULT_PRIMARY_MODEL]
        return [DEFAULT_PRIMARY_MODEL, DEFAULT_FALLBACK_MODEL]

    def is_custom_model_enabled(self) -> bool:
        """Return whether the custom model path is active."""
        return self.get_llm_mode() == "custom" and bool(self.get_custom_model())

    def get_transcribe_original_text(self) -> bool:
        """Return transcription flag."""
        return self.get_setting("ui", "transcribe_original_text", False)

    def set_transcribe_original_text(self, value: bool) -> bool:
        """Persist transcription flag."""
        return self.set_setting("ui", "transcribe_original_text", value)
