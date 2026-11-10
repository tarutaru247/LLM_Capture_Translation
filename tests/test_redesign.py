import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from src.utils.history_store import HistoryStore
from src.utils.settings_manager import SettingsManager
from src.translator.plamo_runtime import PlamoRuntime
from src.translator.translation_job import run_translation_job
from src.ui.settings_dialog import SettingsDialog, parse_shortcut
from src.utils.model_catalog import download_model

ROOT = Path(__file__).resolve().parents[1] / "runtime/test-redesign"
ROOT.mkdir(parents=True, exist_ok=True)


class RedesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.folder = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def settings(self):
        with patch("src.utils.settings_manager.get_config_dir", return_value=str(self.folder)):
            return SettingsManager()

    def test_migration_removes_bf16_keeps_old_path_and_api_settings(self):
        (self.folder / "settings.json").write_text(json.dumps({
            "local_model": {"backend":"bf16", "gguf_path":"C:/models/old.gguf", "bf16_path":"old"},
            "api": {"llm_mode":"custom", "custom_model":"my-model"}}), encoding="utf-8")
        settings = self.settings()
        self.assertEqual(settings.get_local_model_path(), "C:/models/old.gguf")
        self.assertNotIn("bf16_path", settings.settings["local_model"])
        self.assertEqual(settings.get_model(), "my-model")
        self.assertEqual(settings.get_local_profile(), "lightweight")

    def test_target_language_is_independent_and_persists(self):
        settings = self.settings()
        settings.set_app_language("ja")
        settings.set_target_language("en")
        self.assertTrue(settings.save_settings())
        loaded = self.settings()
        self.assertEqual(loaded.get_app_language(), "ja")
        self.assertEqual(loaded.get_target_language(), "en")

    def test_history_persists_searches_full_text_and_limits_entries(self):
        store = HistoryStore(self.folder)
        result = {"extracted_text":"original 100%_text", "translated_text":"訳文"}
        first = store.add(result,"ja","plamo","text",limit=2)
        reopened = HistoryStore(self.folder)
        self.assertEqual(reopened.get(first)["translated"],"訳文")
        self.assertEqual(len(reopened.search("100%_text")),1)
        self.assertEqual(len(reopened.search("%missing")),0)
        second = reopened.add({"translated_text":"two"},"ja","gemini","image",limit=2)
        reopened.add({"translated_text":"three"},"ja","plamo","text",limit=2)
        self.assertIsNone(reopened.get(first))
        reopened.delete(second)
        self.assertEqual(len(reopened.search()),1)
        reopened.clear()
        self.assertEqual(reopened.search(),[])

    def test_cloud_image_is_one_direct_request_without_separate_ocr(self):
        with patch("src.translator.translation_job.SettingsManager") as sm, patch("src.translator.translation_job.CombinedVisionTranslator") as cloud, patch("src.translator.translation_job.LocalOCRService") as ocr:
            sm.return_value.get_translation_provider.return_value = "gemini"
            cloud.return_value.translate_image_result.return_value = {"translated_text":"result","extracted_text":"source"}
            result = run_translation_job(b"image","ja",provider="gemini")
            self.assertEqual(result["translated_text"],"result")
            cloud.return_value.translate_image_result.assert_called_once_with(b"image","ja")
            ocr.assert_not_called()

    def test_cloud_text_uses_text_translator(self):
        with patch("src.translator.translation_job.SettingsManager") as sm, patch("src.translator.translation_job.GeminiTranslator") as cloud, patch("src.translator.translation_job.LocalOCRService") as ocr:
            sm.return_value.get_translation_provider.return_value = "gemini"
            cloud.return_value.translate.return_value = "result"
            result = run_translation_job(b"","ja",provider="gemini",text="source")
            self.assertEqual(result["extracted_text"],"source")
            cloud.return_value.translate.assert_called_once_with("source",target_lang="ja")
            ocr.assert_not_called()

    def test_cloud_image_response_keeps_both_full_texts(self):
        from src.translator.combined_vision_translator import CombinedVisionTranslator
        from types import SimpleNamespace
        payload = {"original_text":"line one\nline two", "translated_text":"一行目\n二行目", "source_language":"en"}
        with patch("src.utils.settings_manager.get_config_dir",return_value=str(self.folder)):
            translator = CombinedVisionTranslator()
        with patch.object(translator,"is_available",return_value=True), patch("src.translator.combined_vision_translator.Image.open"), patch.object(translator,"_generate_with_model_fallback",return_value=(SimpleNamespace(text=json.dumps(payload)),"gemini-test")) as generate:
            result = translator.translate_image_result(b"image","ja")
        self.assertEqual(result["extracted_text"],payload["original_text"])
        self.assertEqual(result["translated_text"],payload["translated_text"])
        self.assertTrue(generate.call_args.kwargs["json_output"])

    def test_success_saves_history_and_can_reopen_without_new_request(self):
        from src.ui.main_window import MainWindow
        with patch("src.utils.settings_manager.get_config_dir",return_value=str(self.folder)), patch.object(MainWindow,"_register_global_hotkey"), patch("src.ui.main_window.QTimer.singleShot"):
            window = MainWindow()
        self.addCleanup(window.deleteLater)
        window.runtime = MagicMock()
        window.runtime.ready = True
        with patch.object(window,"show"), patch.object(window,"raise_"), patch.object(window,"activateWindow"):
            window._handle_translation_result({"extracted_text":"source", "translated_text":"translation", "provider":"plamo", "kind":"text", "target_lang":"ja"})
        records = window.history_store.search()
        self.assertEqual(len(records),1)
        window._new_translation()
        self.assertEqual(window.translation_text_edit.toPlainText(),"")
        for index in range(window.history_list.count()):
            item = window.history_list.item(index)
            if item.data(256) == records[0]["id"]:
                window._open_history(item)
                break
        self.assertEqual(window.translation_text_edit.toPlainText(),"translation")
        self.assertEqual(window.original_text_edit.toPlainText(),"source")
        window.runtime.translate.assert_not_called()

    def test_invalid_provider_never_sends_to_cloud(self):
        with patch("src.translator.translation_job.CombinedVisionTranslator") as cloud:
            result = run_translation_job(b"image","ja",provider="unknown")
            self.assertTrue(result["error_message"])
            cloud.assert_not_called()

    def test_auto_device_falls_back_to_cpu_without_changing_model(self):
        settings = self.settings()
        model = self.folder / "model.gguf"; model.write_bytes(b"fake")
        settings.set_setting("local_model","lightweight_path",str(model))
        runtime = PlamoRuntime(settings)
        with patch.object(runtime,"_gpu_available",return_value=True), patch.object(runtime,"_launch",side_effect=[RuntimeError("GPU memory"),None]) as launch:
            runtime.start()
        self.assertEqual(launch.call_args_list[0].args,(model,True))
        self.assertEqual(launch.call_args_list[1].args,(model,False))
        self.assertTrue(runtime.fallback_reason)

    def test_explicit_gpu_does_not_silently_switch_to_cpu(self):
        settings = self.settings()
        model = self.folder / "model.gguf"; model.write_bytes(b"fake")
        settings.set_setting("local_model","lightweight_path",str(model))
        settings.set_setting("local_model","device","gpu")
        runtime = PlamoRuntime(settings)
        with patch.object(runtime,"_gpu_available",return_value=False), patch.object(runtime,"_launch") as launch:
            with self.assertRaises(RuntimeError): runtime.start()
            launch.assert_not_called()

    def test_download_verifies_hash_and_does_not_install_corrupt_file(self):
        data = b"test weights"
        model = {"size":len(data),"repo":"repo","revision":"revision","filename":"model.gguf","sha256":hashlib.sha256(data).hexdigest()}
        path = self.folder / "model.gguf"
        with patch("src.utils.model_catalog.MODELS",{"test":model}), patch("src.utils.model_catalog.urllib.request.urlopen",return_value=io.BytesIO(data)):
            download_model("test",path)
        self.assertEqual(path.read_bytes(),data)
        path.unlink()
        with patch("src.utils.model_catalog.MODELS",{"test":model}), patch("src.utils.model_catalog.urllib.request.urlopen",return_value=io.BytesIO(b"corrupt")):
            with self.assertRaises(RuntimeError): download_model("test",path)
        self.assertFalse(path.exists())
        self.assertFalse(path.with_name(path.name+".download").exists())

    def test_shortcut_validation(self):
        self.assertEqual(parse_shortcut("Ctrl+Shift+C"),(6,67))
        for invalid in ("C","Ctrl+C, Ctrl+V","Meta+C","Ctrl+Ctrl+C"):
            with self.assertRaises(ValueError): parse_shortcut(invalid)

    def test_settings_load_quality_path_without_overwriting_it(self):
        settings = self.settings()
        settings.set_setting("local_model","profile","quality")
        settings.set_setting("local_model","quality_path","C:/models/quality.gguf")
        settings.save_settings()
        with patch("src.utils.settings_manager.get_config_dir", return_value=str(self.folder)):
            dialog = SettingsDialog()
        self.addCleanup(dialog.deleteLater)
        self.assertEqual(dialog.model_path_edit.text(),"C:/models/quality.gguf")
        self.assertEqual(dialog.profile_combo.currentData(),"quality")


if __name__ == "__main__": unittest.main()
