"""The two supported local models; weights are downloaded separately."""
from pathlib import Path
import hashlib
import urllib.request

MODELS = {
    "lightweight": {
        "name": "PLaMo 3 Translate 0.8B", "size": 573123200,
        "filename": "plamo-3-translate-0.8b-Q4_K_M.gguf",
        "repo": "pfnet/plamo-3-translate-0.8b-GGUF",
        "revision": "dbeb0856cb0b004b484f190bb71dd65876297013",
        "sha256": "923b2f28a9856de1b8b3b610a7e59ded0b14d007466fd5dd526e6a9ecaadafdd",
    },
    "quality": {
        "name": "PLaMo 3 Translate 2B", "size": 1807199392,
        "filename": "plamo-3-translate-2b-Q4_K_M.gguf",
        "repo": "pfnet/plamo-3-translate-2b-GGUF",
        "revision": "232fbd7916519edecddfdae0beae7e76fe70453f",
        "sha256": "f36d0813dd95573a852ab5d76e374c543632d9e292929e922bcdbf7e53b494e0",
    },
}


def download_model(profile, destination, progress=lambda received, total: None, cancelled=lambda: False):
    model = MODELS[profile]
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".download")
    url = f"https://huggingface.co/{model['repo']}/resolve/{model['revision']}/{model['filename']}"
    digest = hashlib.sha256()
    received = 0
    try:
        with urllib.request.urlopen(url, timeout=30) as response, partial.open("wb") as output:
            while True:
                if cancelled():
                    raise RuntimeError("ダウンロードを中止しました。")
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                digest.update(chunk)
                received += len(chunk)
                progress(received, model["size"])
        if received != model["size"] or digest.hexdigest() != model["sha256"]:
            raise RuntimeError("ファイルの検証に失敗しました。再ダウンロードしてください。")
        partial.replace(path)
    finally:
        if partial.exists():
            partial.unlink()
    return path
