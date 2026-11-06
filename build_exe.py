"""Build a portable folder with CPU and Vulkan runtimes, without model weights."""
import argparse
from pathlib import Path
import subprocess
import sys


def create_executable():
    parser = argparse.ArgumentParser()
    parser.add_argument('--distpath', default='dist')
    parser.add_argument('--workpath', default='build')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    for folder in ('llama','llama-vulkan'):
        if not (root/'runtime'/folder/'llama-server.exe').is_file():
            raise RuntimeError('Run python setup_local_runtime.py first (CPU and Vulkan runtimes are required).')
    command = [sys.executable,'-m','PyInstaller','--name=ocr_translator',
               '--onedir','--windowed','--noconfirm',f'--distpath={args.distpath}',
               f'--workpath={args.workpath}',f'--specpath={root / "runtime"}',
               '--exclude-module=torch','--exclude-module=transformers','--exclude-module=numba']
    for source, destination in [
        (root/'docs/THIRD_PARTY_NOTICES.md','docs'),
        (root/'docs/licenses','docs/licenses'),
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
    subprocess.run(command,cwd=root,check=True)
    print('Build complete. Distribute the whole ocr_translator folder, not only its exe.')


if __name__=='__main__': create_executable()
