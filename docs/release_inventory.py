"""Inventory only the release dependency closure, retaining wheel license files."""
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]
# PyYAML and rsa are optional imports collected by the SDK's import graph.
DIRECT = ('PySide6-Essentials', 'Pillow', 'google-genai', 'pynput', 'pyinstaller', 'PyYAML', 'rsa')


def dependencies():
    pending = [(name, set()) for name in DIRECT]
    seen, result = {}, {}
    while pending:
        name, extras = pending.pop()
        name = canonicalize_name(name)
        if name in seen and extras <= seen[name]: continue
        seen[name] = seen.get(name, set()) | extras
        dist = metadata.distribution(name)
        result[name] = dist
        for value in dist.requires or ():
            req = Requirement(value)
            if req.marker and not any(req.marker.evaluate({'extra': extra}) for extra in ({''} | seen[name])):
                continue
            child = metadata.distribution(req.name)
            if req.specifier and not req.specifier.contains(child.version, prereleases=True):
                raise RuntimeError(f'Incompatible dependency: {req.name} {child.version} for {name}')
            pending.append((req.name, set(req.extras)))
    return result


def main():
    destination = ROOT / 'runtime/release-metadata'
    licenses = destination / 'licenses'
    licenses.mkdir(parents=True, exist_ok=True)
    records = []
    for name, dist in sorted(dependencies().items()):
        copied = []
        for file in dist.files or ():
            if not any(word in str(file).lower() for word in ('license', 'copying', 'notice', 'copyright')):
                continue
            source = Path(dist.locate_file(file))
            if not source.is_file(): continue
            # Retain package-relative paths; metadata path comes from a local installed wheel.
            relative = Path(str(file).replace('\\', '/'))
            if relative.is_absolute() or '..' in relative.parts: continue
            target = licenses / name / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            copied.append(str(target.relative_to(destination)).replace('\\', '/'))
        records.append({'name': name, 'version': dist.version, 'license': dist.metadata.get('License-Expression') or dist.metadata.get('License'),
                        'project_urls': dist.metadata.get_all('Project-URL') or [], 'license_files': copied})
    (destination / 'dependencies.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    (destination / 'requirements-lock.txt').write_text(''.join(f"{r['name']}=={r['version']}\n" for r in records), encoding='utf-8')
    print(json.dumps({r['name']: r['version'] for r in records}, indent=2))


if __name__ == '__main__': main()
