"""Offline Windows OCR. Never falls back to a network service."""
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile

from PIL import Image
from ..utils.settings_manager import SettingsManager
from ..translator.plamo_runtime import resource_root


class LocalOCRService:
    def extract_text(self, image_bytes):
        if os.name != 'nt':
            raise RuntimeError('ローカルOCRにはWindows 10/11が必要です。')
        settings = SettingsManager()
        language = settings.get_setting('ocr', 'language', 'en')
        if language not in ('auto', 'en', 'zh-Hans', 'zh-Hant', 'ja', 'ko'):
            raise ValueError('OCRの言語設定が不正です。')
        if len(image_bytes) > 32 * 1024 * 1024:
            raise ValueError('画像が大きすぎます。範囲を小さくして取り込んでください。')
        with tempfile.TemporaryDirectory(prefix='local-ocr-', dir=settings.config_dir) as folder:
            image_path = Path(folder) / 'image.png'
            with Image.open(io.BytesIO(image_bytes)) as image:
                if image.width * image.height > 40_000_000:
                    raise ValueError('画像が大きすぎます。')
                image = image.convert('RGB')
                image.thumbnail((2500, 2500))
                image.save(image_path)
            powershell = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
            script = resource_root() / 'src/ocr/windows_ocr.ps1'
            # Execute our bundled code as a command, without changing execution policy.
            # User-controlled paths/language are values in a child-only environment, never code.
            command = '& { ' + script.read_text(encoding='utf-8') + ' } -ImagePath $env:TARU_OCR_IMAGE -Language $env:TARU_OCR_LANGUAGE'
            environment = dict(os.environ, TARU_OCR_IMAGE=str(image_path), TARU_OCR_LANGUAGE=language)
            process = subprocess.run(
                [str(powershell), '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', command],
                env=environment, capture_output=True, timeout=45, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            try:
                result = json.loads(process.stdout.decode('utf-8-sig'))
            except (ValueError, UnicodeError):
                raise RuntimeError('Windows OCRを起動できません。Windowsの実行ポリシー・OCR機能を確認してください。') from None
            if result.get('error') == 'language_missing':
                raise RuntimeError('指定言語のWindows OCRがありません。Windowsの「言語と地域」で該当言語のOCR機能を追加し、設定の「OCR言語」を選んでください。自動的なクラウド送信は行いません。')
            if process.returncode or result.get('error'):
                raise RuntimeError('Windows OCRで文字を読み取れませんでした。画像範囲とOCR言語を確認してください。')
            return result.get('text', '')
