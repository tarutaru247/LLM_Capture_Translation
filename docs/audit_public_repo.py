"""Read-only credential-pattern audit; never prints matched secret values."""
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    'google_api_key': re.compile(rb'AIza[0-9A-Za-z_-]{30,}'),
    'provider_key': re.compile(rb'(?<![A-Za-z0-9])(?:sk-(?:proj-|ant-)?|gsk_|xai-)[A-Za-z0-9_-]{20,}'),
    'github_token': re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})'),
    'private_key': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'credential_literal': re.compile(rb'''(?im)["']?(?:api_key|password|access_token|secret_key)["']?\s*[:=]\s*["']([^\r\n"']{12,})["']'''),
}


def audit():
    objects = subprocess.check_output(['git', 'rev-list', '--objects', '--all'], cwd=ROOT).splitlines()
    entries = {}
    for line in objects:
        sha, _, path = line.partition(b' ')
        entries.setdefault(sha, path.decode('utf-8', errors='replace'))
    info = subprocess.check_output(['git', 'cat-file', '--batch-check=%(objectname) %(objecttype) %(objectsize)'],
                                   input=b'\n'.join(entries) + b'\n', cwd=ROOT).splitlines()
    blobs = [(sha, int(size)) for sha, kind, size in (line.split() for line in info) if kind == b'blob']
    findings, binary, large = [], [], []
    for sha, size in blobs:
        path = entries[sha]
        if size > 10 * 1024 * 1024:
            large.append({'path': path, 'sha': sha.decode(), 'size': size})
            continue
        data = subprocess.check_output(['git', 'cat-file', 'blob', sha.decode()], cwd=ROOT)
        if b'\x00' in data:
            binary.append({'path': path, 'sha': sha.decode(), 'size': size})
            continue
        for kind, pattern in PATTERNS.items():
            for match in pattern.finditer(data):
                findings.append({'kind': kind, 'path': path, 'sha': sha.decode(),
                                 'line': data[:match.start()].count(b'\n') + 1})
    report = {'scope': 'local git --all reachable objects; not GitHub dangling objects, LFS or release binaries',
              'commits': len(subprocess.check_output(['git', 'rev-list', '--all'], cwd=ROOT).splitlines()),
              'blobs': len(blobs), 'findings': findings, 'binary_not_inspected': binary, 'large_not_inspected': large}
    out = ROOT / 'runtime/public-repo-audit.json'
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    audit()
