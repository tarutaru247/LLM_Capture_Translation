"""Download pinned CPU and Vulkan (NVIDIA/AMD/Intel) runtimes, without models."""
import argparse
import hashlib
import io
from pathlib import Path
import urllib.request
import zipfile

VERSION = "b12140"
SHA256 = "cc210fbbe01767d15c4b8efc71af68b14f3260f62ca6def4b1ced935a32ff738"
GPU_SHA256 = "f23bd9e1cf777762f05e061cdf5095f241863f40441aa70ec892f1bcf75387f8"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cpu-only", action="store_true")
    args = parser.parse_args()
    variants = [("cpu", "llama", SHA256)]
    if not args.cpu_only:
        variants.append(("vulkan", "llama-vulkan", GPU_SHA256))
    for variant, folder, expected in variants:
        url = f"https://github.com/ggml-org/llama.cpp/releases/download/{VERSION}/llama-{VERSION}-bin-win-{variant}-x64.zip"
        print(f"Downloading official llama.cpp {variant} runtime...", flush=True)
        with urllib.request.urlopen(url, timeout=120) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError("Runtime SHA256 mismatch")
        destination = Path(__file__).resolve().parent / "runtime" / folder
        destination.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for item in archive.infolist():
                target = (destination / item.filename).resolve()
                if not target.is_relative_to(destination.resolve()):
                    raise RuntimeError("Unsafe archive path")
                if not item.is_dir() and target.is_file() and target.read_bytes() == archive.read(item):
                    continue
                archive.extract(item, destination)
        print(f"Saved to {destination}", flush=True)
    license_path = Path(__file__).resolve().parent / "docs/licenses/llama.cpp.txt"
    with urllib.request.urlopen(f"https://raw.githubusercontent.com/ggml-org/llama.cpp/{VERSION}/LICENSE", timeout=30) as response:
        license_data = response.read()
    license_path.parent.mkdir(parents=True, exist_ok=True)
    license_path.write_bytes(license_data)


if __name__ == "__main__":
    main()
