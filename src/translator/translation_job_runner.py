"""
CLI entrypoint for isolated translation subprocess execution.
"""
from __future__ import annotations

import base64
import argparse
import json
from pathlib import Path
import sys

from .translation_job import run_translation_job


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--translation-worker", action="store_true")
    parser.add_argument("--input-json")
    parser.add_argument("--output-json")
    args = parser.parse_args()
    payload = json.loads(Path(args.input_json).read_text(encoding="utf-8")) if args.input_json else json.load(sys.stdin)
    image_bytes = base64.b64decode(payload.get("image_bytes_b64", ""))
    target_lang = payload.get("target_lang")
    transcribe_original = bool(payload.get("transcribe_original"))
    result = run_translation_job(image_bytes, target_lang, transcribe_original,
                                 provider=payload.get("provider", "plamo"), text=payload.get("text"))
    output = json.dumps(result, ensure_ascii=False).encode("utf-8")
    if args.output_json:
        Path(args.output_json).write_bytes(output)
    else:
        sys.stdout.buffer.write(output)
        sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
