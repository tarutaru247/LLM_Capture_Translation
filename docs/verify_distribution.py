"""Verify a candidate without sending content to a cloud or accepting real terms."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont
from release_inventory import ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    folder = args.folder.resolve()
    for line in (folder / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        digest, relative = line.split('  ', 1)
        path = (folder / relative).resolve()
        if not path.is_relative_to(folder): raise RuntimeError('Unsafe manifest path')
        with path.open('rb') as file:
            if hashlib.file_digest(file, 'sha256').hexdigest() != digest: raise RuntimeError('Hash mismatch: ' + relative)
    files = list(folder.rglob('*'))
    assert not any(p.suffix.lower() == '.gguf' for p in files)
    assert not any(p.name.lower() in ('settings.json', 'history.sqlite3') for p in files)
    assert not any(p.suffix.lower() == '.dll' and p.name.lower().startswith(('vcruntime','msvcp','concrt','vcomp','vcamp','vccorlib')) for p in files)
    assert not (folder / '_internal/PySide6/Qt6Network.dll').exists()
    assert not (folder / '_internal/icuuc.dll').exists()
    for file in ('application-source.zip', 'LICENSE', 'TERMS-ja.md', 'DISTRIBUTION.md',
                 '_internal/docs/licenses/PLaMo-ja.txt', '_internal/docs/licenses/Qt-LGPL-3.0-only.txt'):
        assert (folder / file).is_file(), file
    results = {'manifest': 'passed', 'forbidden_payloads': 'none', 'worker': {}, 'runtimes': {}}
    parent = ROOT / 'runtime/package-verification'; parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=parent) as temp:
        temp = Path(temp)
        image = Image.new('RGB', (900, 180), 'white')
        ImageDraw.Draw(image).text((20, 25), 'Hello world 123', fill='black',
            font=ImageFont.truetype(str(Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'Fonts/arial.ttf'), 56))
        import io
        encoded = io.BytesIO(); image.save(encoded, format='PNG')
        environment = dict(os.environ, TARUTARU_TRANSLATE_DATA_DIR=str(temp / 'data'))
        for provider in ('plamo', 'gemini', 'openai', 'anthropic', 'deepseek', 'xai', 'groq', 'mistral', 'openrouter', 'custom'):
            payload = {'provider': provider, 'target_lang': 'ja', 'text': None if provider == 'plamo' else 'synthetic fixture',
                       'image_bytes_b64': base64.b64encode(encoded.getvalue()).decode('ascii') if provider == 'plamo' else ''}
            source, output = temp / 'input.json', temp / 'output.json'
            source.write_text(json.dumps(payload), encoding='utf-8')
            if output.exists(): output.unlink()
            completed = subprocess.run([str(folder / 'tarutaru_translate.exe'), '--translation-worker',
                '--input-json', str(source), '--output-json', str(output)], capture_output=True, env=environment, timeout=30)
            if completed.returncode or not output.exists(): raise RuntimeError('Frozen worker failed: ' + provider)
            result = json.loads(output.read_text(encoding='utf-8'))
            if provider == 'plamo':
                assert not result.get('error_message') and result.get('extracted_text')
                results['worker'][provider] = 'offline OCR succeeded'
            else:
                assert result.get('error_message') and not result.get('translated_text')
                assert 'クラウド翻訳は無効' in result['error_message']
                results['worker'][provider] = 'cloud disabled; request blocked'
    for variant in ('llama', 'llama-vulkan'):
        completed = subprocess.run([str(folder / '_internal/runtime' / variant / 'llama-server.exe'), '--version'],
                                   capture_output=True, timeout=15)
        assert completed.returncode == 0
        results['runtimes'][variant] = 'binary launched; inference socket not covered'
    (ROOT / 'runtime/package-verification.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(results, ensure_ascii=True, indent=2))


if __name__ == '__main__': main()
