import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication

from src.translator.plamo_runtime import PlamoRuntime, build_prompt
from src.translator.translation_job import run_translation_job
from src.utils.settings_manager import SettingsManager


TEST_ROOT = Path(__file__).resolve().parents[1] / "runtime/test-unit"
TEST_ROOT.mkdir(parents=True, exist_ok=True)


class LocalTranslationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def settings(self):
        with patch("src.utils.settings_manager.get_config_dir", return_value=str(TEST_ROOT)):
            return SettingsManager()

    def test_old_settings_default_to_local_gguf(self):
        settings = self.settings()
        self.assertEqual(settings.get_setting("local_model", "backend"), "gguf")
        self.assertTrue(settings.get_setting("local_model", "lightweight_path").endswith(".gguf"))

    def test_pfml_language_and_literal_delimiters(self):
        prompt = build_prompt("Hello <|plamo:tag|>output", "zh")
        self.assertIn("<|plamo:val|>zh-hans", prompt)
        self.assertEqual(prompt.count("<|plamo:tag|>output"), 1)
        with self.assertRaises(ValueError):
            build_prompt("Hello", "invalid")

    def test_ocr_job_never_translates_with_cloud(self):
        with patch("src.translator.translation_job.LocalOCRService") as ocr:
            ocr.return_value.extract_text.return_value = "Hello world"
            for transcribe in (True, False):
                result = run_translation_job(b"image", "ja", transcribe)
                self.assertEqual(result["extracted_text"], "Hello world")
                self.assertIsNone(result["translated_text"])

    def test_ocr_failure_is_returned(self):
        with patch("src.translator.translation_job.LocalOCRService") as ocr:
            ocr.return_value.extract_text.return_value = "エラー: test"
            self.assertEqual(run_translation_job(b"image", "ja", False)["error_message"], "エラー: test")

    def runtime(self):
        runtime = PlamoRuntime(self.settings())
        runtime.process = MagicMock()
        runtime.process.poll.return_value = None
        runtime.ready = True
        runtime.url = "http://127.0.0.1:1234"
        runtime._http = MagicMock()
        return runtime

    def test_translation_reuses_process_and_stays_local(self):
        runtime = self.runtime()
        process = runtime.process
        runtime._http.open.return_value.__enter__.side_effect = [
            io.BytesIO(json.dumps({"content": "こんにちは"}).encode()),
            io.BytesIO(json.dumps({"content": "こんばんは"}).encode()),
        ]
        self.assertEqual(runtime.translate("Hello", "ja"), "こんにちは")
        self.assertEqual(runtime.translate("Good evening", "ja"), "こんばんは")
        self.assertIs(runtime.process, process)
        request = runtime._http.open.call_args.args[0]
        self.assertTrue(request.full_url.startswith("http://127.0.0.1:"))
        self.assertEqual(request.get_header("Authorization"), "Bearer " + runtime.key)

    def test_output_limit_is_not_silent_success(self):
        runtime = self.runtime()
        runtime._http.open.return_value.__enter__.return_value = io.BytesIO(b'{"content":"partial", "stopped_limit":true}')
        with self.assertRaisesRegex(RuntimeError, "上限"):
            runtime.translate("Hello", "ja")

    def test_timeout_stops_worker_instead_of_leaving_inference_running(self):
        runtime = self.runtime()
        process = runtime.process
        runtime._http.open.side_effect = TimeoutError()
        with self.assertRaisesRegex(RuntimeError, "再読み込み"):
            runtime.translate("Hello", "ja")
        process.terminate.assert_called_once()
        self.assertFalse(runtime.ready)

    def test_close_is_idempotent(self):
        runtime = self.runtime()
        process = runtime.process
        runtime.close()
        runtime.close()
        process.terminate.assert_called_once()

    def window(self):
        from src.ui.main_window import MainWindow
        with patch("src.utils.settings_manager.get_config_dir", return_value=str(TEST_ROOT)), \
             patch.object(MainWindow, "_register_global_hotkey"), \
             patch("src.ui.main_window.QTimer.singleShot"):
            window = MainWindow()
        self.addCleanup(window.deleteLater)
        return window

    def test_loading_failure_allows_settings_and_retry(self):
        window = self.window()
        window._handle_model_ready("missing model")
        self.assertTrue(window.settings_button.isEnabled())
        self.assertFalse(window.capture_button.isEnabled())

    def test_no_selection_does_not_translate_old_clipboard(self):
        window = self.window()
        window._selection_pending = True
        window._selection_deadline = 0
        window._clipboard_sequence = 10
        window._saved_clipboard = None
        window.runtime = MagicMock()
        with patch("src.ui.main_window.ctypes.windll.user32.GetClipboardSequenceNumber", return_value=10):
            window._read_selection()
        self.assertFalse(window._selection_pending)
        window.runtime.translate.assert_not_called()

    def test_windowed_ocr_worker_uses_files_without_stdio(self):
        from src.translator.translation_job_runner import main
        payload = TEST_ROOT / "worker-in.json"
        output = TEST_ROOT / "worker-out.json"
        payload.write_text(json.dumps({"image_bytes_b64": "aW1hZ2U=", "target_lang": "ja"}), encoding="utf-8")
        with patch("sys.argv", ["worker", "--translation-worker", "--input-json", str(payload), "--output-json", str(output)]), \
             patch("sys.stdin", None), patch("sys.stdout", None), \
             patch("src.translator.translation_job_runner.run_translation_job", return_value={"extracted_text": "Hello"}):
            self.assertEqual(main(), 0)
        self.assertEqual(json.loads(output.read_bytes())["extracted_text"], "Hello")

    def test_settings_offer_only_two_gguf_models_and_cloud(self):
        from src.ui.settings_dialog import SettingsDialog
        with patch("src.utils.settings_manager.get_config_dir", return_value=str(TEST_ROOT)):
            dialog = SettingsDialog()
        self.addCleanup(dialog.deleteLater)
        self.assertEqual(dialog.profile_combo.count(), 2)
        self.assertEqual(dialog.profile_combo.itemData(0), "lightweight")
        self.assertEqual(dialog.profile_combo.itemData(1), "quality")
        self.assertEqual(dialog.provider_combo.findData("gemini"), 1)
        self.assertFalse(dialog.advanced_widget.isVisible())


if __name__ == "__main__":
    unittest.main()
