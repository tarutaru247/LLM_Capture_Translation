import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication, QMessageBox
from src.utils.settings_manager import SettingsManager
from src.utils.providers import PROVIDERS, validate_endpoint
from src.utils.consent import has_terms_consent, record_terms_consent
from src.utils import secure_storage
from src.translator.translation_job import run_translation_job
from src.translator.api_translator import APITranslator, NoRedirect
from src.ui.onboarding import TermsDialog, ModelSetupDialog
from src.ui.settings_dialog import SettingsDialog

ROOT = Path(__file__).resolve().parents[1] / 'runtime/test-distribution'
ROOT.mkdir(parents=True, exist_ok=True)


class DistributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        patcher = patch('src.utils.settings_manager.get_config_dir', return_value=self.temp.name)
        patcher.start(); self.addCleanup(patcher.stop)
        self.settings = SettingsManager()

    def enable(self, provider='openai'):
        self.settings.set_setting('privacy', 'cloud_enabled', True)
        self.settings.set_setting('privacy', 'cloud_consent_version', '1')
        self.settings.set_setting('translation', 'provider', provider)
        self.settings.set_setting('cloud_accounts', provider, {'model': 'fixture-model', 'api_key': '', 'base_url': 'https://example.org/v1'})

    def test_cloud_migration_requires_new_explicit_consent(self):
        self.settings.set_setting('translation', 'provider', 'gemini')
        self.settings.save_settings()
        loaded = SettingsManager()
        self.assertFalse(loaded.cloud_allowed())
        self.assertEqual(loaded.get_translation_provider(), 'plamo')
        with patch('src.utils.google_ai.genai.Client') as client:
            from src.utils.google_ai import create_google_client
            with self.assertRaises(PermissionError): create_google_client('unused')
            client.assert_not_called()

    def test_all_cloud_worker_routes_blocked_while_off(self):
        with patch('src.translator.translation_job.GeminiTranslator') as gemini, \
             patch('src.translator.translation_job.CombinedVisionTranslator') as vision, \
             patch('src.translator.translation_job.APITranslator') as api:
            for provider in PROVIDERS:
                self.assertTrue(run_translation_job(b'image', 'ja', provider=provider)['error_message'])
            gemini.assert_not_called(); vision.assert_not_called(); api.assert_not_called()

    def test_local_image_never_uses_cloud_or_requires_api_key(self):
        with patch('src.translator.translation_job.LocalOCRService') as ocr, \
             patch('src.translator.translation_job.CombinedVisionTranslator') as cloud:
            ocr.return_value.extract_text.return_value = 'source'
            result = run_translation_job(b'fixture', 'ja')
            self.assertEqual(result['extracted_text'], 'source')
            cloud.assert_not_called()

    def test_ocr_error_does_not_fall_back_to_cloud(self):
        with patch('src.translator.translation_job.LocalOCRService') as ocr, \
             patch('src.translator.translation_job.CombinedVisionTranslator') as cloud:
            ocr.return_value.extract_text.side_effect = RuntimeError('missing language')
            self.assertTrue(run_translation_job(b'fixture', 'ja')['error_message'])
            cloud.assert_not_called()

    def test_local_urls_are_numeric_loopback_and_credentials_never_in_url(self):
        self.assertEqual(validate_endpoint('http://localhost:1234/v1/', local=True), 'http://127.0.0.1:1234/v1')
        self.assertEqual(validate_endpoint('http://[::1]:1234/v1', local=True), 'http://[::1]:1234/v1')
        for url in ('https://example.org/v1', 'http://192.168.1.1/v1', 'http://127.0.0.1.evil/v1',
                    'http://user:password@127.0.0.1/v1', 'http://127.0.0.1/v1?key=value',
                    'http://127.0.0.1/v1#fragment', 'http://127.0.0.1/\n', 'file:///test'):
            with self.assertRaises(ValueError, msg=url): validate_endpoint(url, local=True)
        with self.assertRaises(ValueError): validate_endpoint('http://example.org/v1')

    def test_no_redirect_can_forward_credentials(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, '', {}, 'https://evil.invalid'))

    def test_encrypt_failure_never_returns_plaintext(self):
        with patch('src.utils.secure_storage._protect_via_dpapi', return_value=None):
            with self.assertRaises(RuntimeError): secure_storage.protect_secret('synthetic-test-value')

    def test_dpapi_round_trip_and_storage_has_no_plain_secret(self):
        value = secure_storage.protect_secret('synthetic-test-value')
        self.assertTrue(value.startswith('dpapi:'))
        self.assertNotIn('synthetic-test-value', value)
        self.assertEqual(secure_storage.unprotect_secret(value), 'synthetic-test-value')

    def test_terms_unchecked_and_acceptance_must_be_saved(self):
        dialog = TermsDialog(self.settings); self.addCleanup(dialog.deleteLater)
        self.assertFalse(dialog.continue_button.isEnabled())
        dialog.software_agree.setChecked(True)
        self.assertFalse(dialog.continue_button.isEnabled())
        dialog.plamo_agree.setChecked(True)
        self.assertTrue(dialog.continue_button.isEnabled())
        self.assertFalse(has_terms_consent(self.settings))
        dialog._accept_terms()
        self.assertTrue(has_terms_consent(SettingsManager()))

    def test_failed_consent_save_rolls_back_and_download_is_unreachable(self):
        with patch.object(self.settings, 'save_settings', return_value=False):
            with self.assertRaises(RuntimeError): record_terms_consent(self.settings)
        dialog = ModelSetupDialog(self.settings); self.addCleanup(dialog.deleteLater)
        with patch('src.ui.onboarding.download_model') as download:
            dialog._run()
            download.assert_not_called()
        self.assertFalse(dialog.running)

    def test_cloud_warning_defaults_to_no_and_cancel_does_not_save(self):
        dialog = SettingsDialog(); self.addCleanup(dialog.deleteLater)
        self.assertFalse(dialog.cloud_enabled.isChecked())
        self.assertFalse(dialog.provider_buttons[1].isEnabled())
        with patch('src.ui.settings_dialog.QMessageBox.warning', return_value=QMessageBox.No) as warning:
            dialog.cloud_enabled.setChecked(True)
        self.assertFalse(dialog.cloud_enabled.isChecked())
        self.assertEqual(warning.call_args.args[-1], QMessageBox.No)
        with patch('src.ui.settings_dialog.QMessageBox.warning', return_value=QMessageBox.Yes):
            dialog.cloud_enabled.setChecked(True)
        self.assertTrue(dialog.provider_buttons[1].isEnabled())
        dialog.reject()
        self.assertFalse(SettingsManager().cloud_allowed())

    def test_provider_switch_does_not_reuse_keys(self):
        dialog = SettingsDialog(); self.addCleanup(dialog.deleteLater)
        dialog.cloud_service_combo.setCurrentIndex(dialog.cloud_service_combo.findData('openai'))
        dialog.other_api_key_edit.setText('synthetic-openai-value')
        dialog.cloud_service_combo.setCurrentIndex(dialog.cloud_service_combo.findData('anthropic'))
        self.assertEqual(dialog.other_api_key_edit.text(), '')
        dialog.cloud_service_combo.setCurrentIndex(dialog.cloud_service_combo.findData('openai'))
        self.assertEqual(dialog.other_api_key_edit.text(), 'synthetic-openai-value')

    def api_response(self, body, protocol='openai'):
        self.enable(protocol)
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value = io.BytesIO(json.dumps(body).encode())
        return opener

    def test_openai_uses_stateless_responses_and_text_only(self):
        opener = self.api_response({'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': '訳文'}]}]})
        with patch.object(self.settings, 'get_cloud_api_key', return_value='synthetic-value'), \
             patch('src.translator.api_translator.urllib.request.build_opener', return_value=opener):
            self.assertEqual(APITranslator(self.settings).translate('source'), '訳文')
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, 'https://api.openai.com/v1/responses')
        payload = json.loads(request.data)
        self.assertFalse(payload['store']); self.assertEqual(payload['input'], 'source')

    def test_claude_and_compatible_protocols_parse_complete_only(self):
        for provider in ('anthropic', 'deepseek', 'xai', 'groq', 'mistral', 'openrouter', 'custom'):
            body = {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': '訳文'}]} if provider == 'anthropic' else {
                'choices': [{'finish_reason': 'stop', 'message': {'content': '訳文'}}]}
            opener = self.api_response(body, provider)
            with patch.object(self.settings, 'get_cloud_api_key', return_value='synthetic-value'), \
                 patch('src.translator.api_translator.urllib.request.build_opener', return_value=opener):
                self.assertEqual(APITranslator(self.settings).translate('source'), '訳文')

    def test_truncated_response_is_not_accepted_as_translation(self):
        opener = self.api_response({'choices': [{'finish_reason': 'length', 'message': {'content': 'partial'}}]}, 'deepseek')
        with patch.object(self.settings, 'get_cloud_api_key', return_value='synthetic-value'), \
             patch('src.translator.api_translator.urllib.request.build_opener', return_value=opener):
            with self.assertRaises(RuntimeError): APITranslator(self.settings).translate('source')

    def test_custom_local_api_sends_no_cloud_credentials(self):
        self.settings.set_setting('local_api', 'model', 'local-fixture')
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value = io.BytesIO(b'{"choices":[{"finish_reason":"stop","message":{"content":"ok"}}]}')
        with patch('src.translator.api_translator.urllib.request.build_opener', return_value=opener):
            self.assertEqual(APITranslator(self.settings).translate('source', local=True), 'ok')
        request = opener.open.call_args.args[0]
        self.assertTrue(request.full_url.startswith('http://127.0.0.1:'))
        self.assertIsNone(request.get_header('Authorization'))


if __name__ == '__main__': unittest.main()
