"""
Settings manager module.
"""
import json
import logging
import os
from typing import Any, Dict

from ..utils.utils import get_config_dir

logger = logging.getLogger("ocr_translator")


class SettingsManager:
    """Manage reading and writing application settings."""

    def __init__(self) -> None:
        self.config_dir = get_config_dir()
        self.config_file = os.path.join(self.config_dir, "settings.json")
        self._last_loaded_mtime: float | None = None
        self.settings = self._load_settings()

    def _default_settings(self) -> Dict[str, Any]:
        return {
            "api": {
                "selected_api": "openai",  # 'openai' or 'gemini' (used for combined OCR as well)
                "openai_api_key": "",
                "gemini_api_key": "",
                "model": "gemini-flash-latest",  # default model for OCR/translation
                "timeout": 60,  # API timeout in seconds
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
        return settings

    def _ensure_latest_settings(self) -> None:
        """Reload settings if the underlying file changed."""
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

    def save_settings(self) -> bool:
        """Persist current settings to disk."""
        try:
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
            return self.get_setting("api", "openai_api_key")
        if api_type_lower == "gemini":
            return self.get_setting("api", "gemini_api_key")
        logger.warning("不明なAPI種別が指定されました: %s", api_type)
        return None

    def set_api_key(self, api_type: str, api_key: str) -> bool:
        """Store API key for the requested provider."""
        api_type_lower = api_type.lower()
        if api_type_lower == "openai":
            return self.set_setting("api", "openai_api_key", api_key)
        if api_type_lower == "gemini":
            return self.set_setting("api", "gemini_api_key", api_key)
        logger.warning("不明なAPI種別が指定されました: %s", api_type)
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
        if api_type_lower in ["openai", "gemini"]:
            return self.set_setting("api", "selected_api", api_type_lower)
        logger.warning("不明なAPI種別が指定されました: %s", api_type)
        return False

    def get_model(self) -> str:
        """Return selected model name."""
        return self.get_setting("api", "model")

    def set_model(self, model_name: str) -> bool:
        """Persist model name."""
        return self.set_setting("api", "model", model_name)

    def get_timeout(self) -> int:
        """Return configured API timeout in seconds."""
        return self.get_setting("api", "timeout")

    def set_timeout(self, timeout: int) -> bool:
        """Persist API timeout value."""
        return self.set_setting("api", "timeout", timeout)

    def get_transcribe_original_text(self) -> bool:
        """Return transcription flag."""
        return self.get_setting("ui", "transcribe_original_text", False)

    def set_transcribe_original_text(self, value: bool) -> bool:
        """Persist transcription flag."""
        return self.set_setting("ui", "transcribe_original_text", value)
