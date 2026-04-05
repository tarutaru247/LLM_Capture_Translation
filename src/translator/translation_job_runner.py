"""
CLI entrypoint for isolated translation subprocess execution.
"""
from __future__ import annotations

import base64
import json
import sys

from .translation_job import run_translation_job


def main() -> int:
    payload = json.load(sys.stdin)
    image_bytes = base64.b64decode(payload["image_bytes_b64"])
    target_lang = payload.get("target_lang")
    transcribe_original = bool(payload.get("transcribe_original"))
    result = run_translation_job(image_bytes, target_lang, transcribe_original)
    json.dump(result, sys.stdout, ensure_ascii=False)
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
