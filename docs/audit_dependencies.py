"""Release-specific PyPI advisory check. Fails closed on missing/incomplete results."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import urllib.request

from release_inventory import ROOT, dependencies


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', type=Path, help='Previously retrieved release-specific JSON records')
    parser.add_argument('--output', type=Path, default=ROOT / 'runtime/dependency-audit.json')
    args = parser.parse_args()
    cached = json.loads(args.cache.read_text(encoding='utf-8')) if args.cache else []
    if isinstance(cached, dict): cached = cached.get('packages', [])
    records, failed = [], False
    for name, dist in sorted(dependencies().items()):
        version = dist.version
        url = f'https://pypi.org/pypi/{name}/{version}/json'
        try:
            if args.cache:
                record = next(r for r in cached if r.get('name') == name and r.get('version') == version)
                if not record.get('checked_at') or not isinstance(record.get('vulnerabilities'), list):
                    raise ValueError('Missing advisory data')
                age = datetime.now(timezone.utc) - datetime.fromisoformat(record['checked_at'].replace('Z', '+00:00'))
                if age.total_seconds() < -300 or age.days > 7:
                    raise ValueError('Advisory cache is stale; re-check before building')
            else:
                with urllib.request.urlopen(url, timeout=20) as response:
                    data = json.loads(response.read(8 * 1024 * 1024))
                if data['info']['version'] != version or not isinstance(data['vulnerabilities'], list):
                    raise ValueError('Unexpected release metadata')
                record = {'name': name, 'version': version, 'source': url,
                          'checked_at': datetime.now(timezone.utc).isoformat(),
                          'vulnerabilities': [{k: v.get(k) for k in ('id', 'aliases', 'fixed_in', 'link')}
                              for v in data['vulnerabilities'] if not v.get('withdrawn')]}
            records.append(record)
            if record['vulnerabilities']: failed = True
        except Exception as exc:
            records.append({'name': name, 'version': version, 'source': url, 'error': type(exc).__name__})
            failed = True
    result = {'schema': 1, 'checked_at': datetime.now(timezone.utc).isoformat(),
              'scope': 'release dependency closure, PyPI release-specific advisories; excludes native llama.cpp/Qt/Python/OS advisories',
              'passed': not failed, 'packages': records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"{'PASS' if not failed else 'FAIL'}: {len(records)} dependency releases")
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__': main()
