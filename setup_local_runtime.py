"""Download the official CPU llama.cpp runtime (no model weights)."""
import hashlib
import io
from pathlib import Path
import urllib.request
import zipfile

VERSION = "b12140"
SHA256 = "cc210fbbe01767d15c4b8efc71af68b14f3260f62ca6def4b1ced935a32ff738"


def main():
    url = f"https://github.com/ggml-org/llama.cpp/releases/download/{VERSION}/llama-{VERSION}-bin-win-cpu-x64.zip"
    print("Downloading official llama.cpp runtime...", flush=True)
    with urllib.request.urlopen(url, timeout=120) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise RuntimeError("Runtime SHA256 mismatch")
    destination = Path(__file__).resolve().parent / "runtime/llama"
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for item in archive.infolist():
            target = (destination / item.filename).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise RuntimeError("Unsafe archive path")
        archive.extractall(destination)
    license_path = Path(__file__).resolve().parent / "docs/licenses/llama.cpp.txt"
    with urllib.request.urlopen(f"https://raw.githubusercontent.com/ggml-org/llama.cpp/{VERSION}/LICENSE", timeout=30) as response:
        license_data = response.read()
    license_path.parent.mkdir(parents=True, exist_ok=True)
    license_path.write_bytes(license_data)
    print(f"Saved to {destination}")


if __name__ == "__main__":
    main()
