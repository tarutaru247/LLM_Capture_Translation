"""Versioned local records: no network access and no acceptance by migration."""
from datetime import datetime, timezone
import hashlib
from ..translator.plamo_runtime import resource_root

TERMS_VERSION = '2026-11-10.1'


def terms_fingerprint():
    root = resource_root()
    digest = hashlib.sha256()
    for file in ('docs/TERMS-ja.md', 'LICENSE', 'docs/licenses/PLaMo-ja.txt', 'docs/licenses/PLaMo-en.txt'):
        digest.update((root / file).read_bytes())
    return TERMS_VERSION + ':' + digest.hexdigest()


def has_terms_consent(settings):
    return settings.get_setting('onboarding', 'terms_version', '') == terms_fingerprint()


def record_terms_consent(settings):
    before = dict(settings.settings['onboarding'])
    settings.set_setting('onboarding', 'terms_version', terms_fingerprint())
    settings.set_setting('onboarding', 'accepted_at', datetime.now(timezone.utc).isoformat())
    if not settings.save_settings():
        settings.settings['onboarding'] = before
        raise RuntimeError('同意内容を保存できませんでした。ダウンロードを開始しません。')
