"""Build a portable folder with CPU and Vulkan runtimes, without model weights."""
import argparse
from pathlib import Path
import subprocess
import sys
import shutil
import zipfile
import hashlib
import os
import ast

from docs.release_inventory import main as inventory_main


def create_executable():
    parser = argparse.ArgumentParser()
    parser.add_argument('--distpath', default='dist')
    parser.add_argument('--workpath', default='build')
    parser.add_argument('--console', action='store_true', help='Diagnostic build with stderr')
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 12) or sys.version_info[:3] < (3, 12, 16):
        raise RuntimeError('Release candidates require Python 3.12.16+ (3.12 series), including security fixes.')
    root = Path(__file__).resolve().parent
    inventory_main()
    metadata = root / 'runtime/release-metadata'
    subprocess.run([sys.executable, str(root / 'docs/audit_dependencies.py'),
        '--cache', str(root / 'docs/security/dependency-audit-2026-11-10.json')], check=True)
    for folder in ('llama','llama-vulkan'):
        if not (root/'runtime'/folder/'llama-server.exe').is_file():
            raise RuntimeError('Run python setup_local_runtime.py first (CPU and Vulkan runtimes are required).')
    command = [sys.executable,'-m','PyInstaller','--name=tarutaru_translate',
               '--onedir','--console' if args.console else '--windowed','--noconfirm',f'--distpath={args.distpath}',
               f'--workpath={args.workpath}',f'--specpath={root / "runtime"}',
               '--exclude-module=torch','--exclude-module=transformers','--exclude-module=numba',
               '--exclude-module=PyQt5','--exclude-module=PySide2','--exclude-module=PyQt6',
               '--exclude-module=src.translator.bf16_server', '--exclude-module=googleapiclient',
               '--exclude-module=IPython','--exclude-module=matplotlib','--exclude-module=numpy']
    for module in ('QtNetwork','QtWebSockets','QtHttpServer','QtQml','QtQuick','QtQuickWidgets',
                   'QtQuickControls2','QtCore5Compat','QtXml','QtPrintSupport','QtSql','QtTest'):
        command.append('--exclude-module=PySide6.' + module)
    for source, destination in [
        (root/'docs/THIRD_PARTY_NOTICES.md','docs'),
        (root/'docs/licenses','docs/licenses'),
        (root/'docs/TERMS-ja.md','docs'),
        (root/'LICENSE','.'),
        (root/'resources','resources'),
        (root/'src/ocr/windows_ocr.ps1','src/ocr'),
        (metadata/'licenses','docs/dependency-licenses'),
        (root/'src/prompts/vision_translation_prompt.md','src/prompts'),
    ]:
        command.append(f'--add-data={source};{destination}')
    for folder in ('llama','llama-vulkan'):
        for file in (root/'runtime'/folder).iterdir():
            if file.suffix.lower()=='.dll' or file.name=='llama-server.exe':
                command.append(f'--add-binary={file};runtime/{folder}')
            elif file.name.startswith('LICENSE'):
                command.append(f'--add-data={file};runtime/{folder}')
    icon = root/'resources/icon.ico'
    if icon.is_file(): command.append(f'--icon={icon}')
    command.append(str(root/'main.py'))
    # Do not resolve Qt DLLs from unrelated programs injected into the caller's PATH.
    build_env = dict(os.environ)
    system_root = Path(os.environ.get('SystemRoot', r'C:\Windows'))
    build_env['PATH'] = os.pathsep.join(str(p) for p in (Path(sys.base_prefix), Path(sys.base_prefix)/'DLLs',
        root/'.venv/Lib/site-packages/PySide6', root/'.venv/Lib/site-packages/shiboken6', system_root/'System32', system_root))
    build_env['PYINSTALLER_CONFIG_DIR'] = str(root/'runtime/pyinstaller-cache')
    subprocess.run(command,cwd=root,check=True,env=build_env)
    # Fail if collection pulled native code from an unreviewed application/tool cache.
    analysis_file = Path(args.workpath).resolve() / 'tarutaru_translate/Analysis-00.toc'
    analysis = ast.literal_eval(analysis_file.read_text(encoding='utf-8'))
    allowed = (root.resolve(), Path(sys.base_prefix).resolve(), system_root.resolve())
    def inspect_binary_sources(value):
        if not isinstance(value, (list, tuple)): return
        if len(value) == 3 and value[2] in ('BINARY', 'EXTENSION') and isinstance(value[1], str):
            origin = Path(value[1]).resolve()
            if not any(origin.is_relative_to(folder) for folder in allowed):
                raise RuntimeError('Unreviewed native dependency: ' + str(origin))
        for item in value: inspect_binary_sources(item)
    inspect_binary_sources(analysis)
    destination = Path(args.distpath).resolve() / 'tarutaru_translate'
    # Keep only plugins used by this Windows Widgets app (PNG/ICO resources, no network Qt APIs).
    qt_folder = destination / '_internal/PySide6'
    # Qt uses the Windows ICU API. Never shadow it with an unrelated application's ICU DLL.
    for name in ('icuuc.dll', 'icudt78.dll'):
        file = destination / '_internal' / name
        if file.is_file() and file.resolve().is_relative_to(destination): file.unlink()
    # Microsoft CRT is an explicit prerequisite installed by users from Microsoft.
    # Avoid assuming that the publisher owns a Visual Studio redistribution license.
    for file in (destination / '_internal').rglob('*.dll'):
        if file.name.lower().startswith(('vcruntime', 'msvcp', 'concrt', 'vccorlib', 'vcomp', 'vcamp')):
            if not file.resolve().is_relative_to(destination): raise RuntimeError('Unsafe runtime path')
            file.unlink()
    software_gl = qt_folder / 'opengl32sw.dll'
    if software_gl.is_file() and software_gl.resolve().is_relative_to(destination):
        software_gl.unlink()  # This raster Widgets app does not create OpenGL contexts.
    keep_plugins = {'platforms/qwindows.dll', 'platforms/qoffscreen.dll', 'styles/qmodernwindowsstyle.dll',
                    'imageformats/qico.dll', 'imageformats/qjpeg.dll', 'imageformats/qgif.dll'}
    for file in (qt_folder / 'plugins').rglob('*.dll'):
        if file.relative_to(qt_folder / 'plugins').as_posix() not in keep_plugins:
            if not file.resolve().is_relative_to(destination): raise RuntimeError('Unsafe plugin path')
            file.unlink()
    import pefile
    imported = set()
    for file in qt_folder.rglob('*'):
        if file.suffix.lower() not in ('.pyd', '.dll') or file.name in ('Qt6Network.dll', 'Qt6Svg.dll'): continue
        binary = pefile.PE(str(file), fast_load=True)
        binary.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT'],
                                                  pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT']])
        imported.update(entry.dll.decode('ascii').lower() for entry in getattr(binary, 'DIRECTORY_ENTRY_IMPORT', []))
        imported.update(entry.dll.decode('ascii').lower() for entry in getattr(binary, 'DIRECTORY_ENTRY_DELAY_IMPORT', []))
        binary.close()
    for name in ('Qt6Network.dll', 'Qt6Svg.dll'):
        file = qt_folder / name
        if file.exists() and name.lower() not in imported:
            if not file.resolve().is_relative_to(destination): raise RuntimeError('Unsafe library path')
            file.unlink()
    for file in ('LICENSE','README.md'):
        shutil.copyfile(root / file, destination / file)
    for file in ('THIRD_PARTY_NOTICES.md','TERMS-ja.md','DISTRIBUTION.md','requirements-release-lock.txt'):
        shutil.copyfile(root / 'docs' / file, destination / file)
    for file in ('dependencies.json','requirements-lock.txt'):
        shutil.copyfile(metadata / file, destination / file)
    shutil.copyfile(root / 'runtime/dependency-audit.json', destination / 'dependency-audit.json')
    # Complete application sources, explicitly whitelisted. No user state/models/old binaries.
    with zipfile.ZipFile(destination / 'application-source.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for folder in ('src','tests','resources','docs/licenses','docs/security'):
            for file in (root / folder).rglob('*'):
                if file.is_file() and '__pycache__' not in file.parts and file.suffix != '.pyc':
                    archive.write(file, file.relative_to(root))
        for file in ('main.py','build_exe.py','requirements.txt','setup_local_runtime.py','README.md','LICENSE'):
            archive.write(root / file, file)
        for file in ('TERMS-ja.md','DISTRIBUTION.md','THIRD_PARTY_NOTICES.md','requirements-release-lock.txt',
                     'release_inventory.py','audit_dependencies.py','audit_public_repo.py','generate_icon.py','verify_distribution.py'):
            archive.write(root / 'docs' / file, 'docs/' + file)
    manifest = []
    for file in sorted(destination.rglob('*')):
        if file.is_file():
            manifest.append(hashlib.sha256(file.read_bytes()).hexdigest() + '  ' + file.relative_to(destination).as_posix())
    (destination / 'SHA256SUMS.txt').write_text('\n'.join(manifest)+'\n',encoding='utf-8')
    print('Build complete. Review DISTRIBUTION.md before publishing; distribute the whole tarutaru_translate folder.')


if __name__=='__main__': create_executable()
