"""Reproduce the English/Chinese -> Japanese comparison with the app runtime."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.translator.plamo_runtime import PlamoRuntime


class ComparisonSettings:
    def __init__(self, backend, directory):
        self.backend = backend
        self.config_dir = str(directory)
        directory.mkdir(parents=True, exist_ok=True)

    def get_setting(self, category, key, default=None):
        return {
            "backend": self.backend,
            "gguf_path": r"D:\LocalLLM\models\plamo-3-translate-0.8b-Q4_K_M.gguf",
            "bf16_path": r"D:\LocalLLM\models\plamo-3-translate-0.8b-bf16",
        }.get(key, default)

    def get_timeout(self):
        return 180


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["gguf", "bf16"], required=True)
    args = parser.parse_args()
    directory = Path(__file__).resolve().parent
    samples = json.loads((directory / "samples.json").read_text(encoding="utf-8"))
    settings = ComparisonSettings(args.backend, ROOT / "runtime/comparison" / args.backend)
    runtime = PlamoRuntime(settings)
    model_file = Path(settings.get_setting("local_model", args.backend + "_path"))
    if args.backend == "bf16":
        model_file /= "model.safetensors"
    with model_file.open("rb") as file:
        digest = hashlib.file_digest(file, "sha256").hexdigest()
    report = {
        "backend": args.backend, "target_language": "ja", "source_language": "auto",
        "temperature": 0, "max_output_tokens": 2048, "context_size": 8192,
        "model_sha256": digest, "python": platform.python_version(),
        "model_file": str(model_file), "results": [],
    }
    if args.backend == "bf16":
        import torch
        report.update(torch=torch.__version__, transformers=importlib.metadata.version("transformers"),
                      device=torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu")
    else:
        report.update(runtime="llama.cpp b12140", device="CPU (official win-cpu-x64 runtime)")
    output = directory / (args.backend + "_results.json")
    try:
        start = time.perf_counter()
        runtime.start()
        report["load_seconds"] = round(time.perf_counter() - start, 3)
        print(f"{args.backend}: loaded ({report['load_seconds']} s)", flush=True)
        for sample in samples:
            start = time.perf_counter()
            text = runtime.translate(sample["source"], "ja")
            row = {"id": sample["id"], "output": text, "seconds": round(time.perf_counter() - start, 3)}
            report["results"].append(row)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"{args.backend}: {sample['id']} OK ({row['seconds']} s)", flush=True)
    finally:
        runtime.close()
    print(f"Saved {output}", flush=True)


if __name__ == "__main__":
    main()
