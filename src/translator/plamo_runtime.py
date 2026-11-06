"""Own one local inference process for the lifetime of the application."""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request


def resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


def build_prompt(text: str, target_lang: str, source_lang: str | None = None) -> str:
    # PFML3 delimiters in source documents must not become instructions.
    text = text.replace("<|plamo:", "＜|plamo:")
    language = {"zh": "zh-hans"}.get(target_lang, target_lang)
    if language not in ("ja", "en", "zh-hans", "ko"):
        raise ValueError("未対応の翻訳先言語です。")
    return (
        "<|plamo:tag|>dataset<|plamo:msg|>translation"
        "<|plamo:tag|>input<|plamo:msg|>" + text
        + "<|plamo:tag|>output<|plamo:key|>lang<|plamo:val|>"
        + language + "<|plamo:msg|>"
    )


class PlamoRuntime:
    def __init__(self, settings):
        self.settings = settings
        self.process = None
        self.url = ""
        self.key = secrets.token_urlsafe(32)
        self.ready = False
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.log_path = Path(settings.config_dir) / "plamo-runtime.log"

    @property
    def model_name(self):
        return "PLaMo 3 Translate 0.8B / " + self.settings.get_setting("local_model", "backend").upper()

    def start(self):
        with self._lock:
            if self._stop.is_set():
                return
            backend = self.settings.get_setting("local_model", "backend")
            model = Path(self.settings.get_setting("local_model", backend + "_path"))
            if not model.exists():
                raise FileNotFoundError(f"モデルが見つかりません: {model}")
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            self.url = f"http://127.0.0.1:{port}"
            if backend == "gguf":
                executable = self.settings.get_setting("local_model", "llama_server_path", "")
                server = Path(executable) if executable else resource_root() / "runtime/llama/llama-server.exe"
                if not server.is_file():
                    raise FileNotFoundError("llama-server.exe がありません。python setup_local_runtime.py を実行してください。")
                command = [str(server), "-m", str(model), "--host", "127.0.0.1", "--port", str(port),
                           "-c", "8192", "-np", "1", "-ngl", "auto", "--api-key", self.key,
                           "--no-webui"]
            elif backend == "bf16":
                interpreter = self.settings.get_setting("local_model", "python_path", "")
                if not interpreter and getattr(sys, "frozen", False):
                    raise RuntimeError("BF16用のPythonを設定画面で指定してください。")
                command = [interpreter or sys.executable, str(resource_root() / "src/translator/bf16_server.py"),
                           "--model", str(model), "--port", str(port)]
            else:
                raise ValueError("モデル形式はGGUFまたはBF16を指定してください。")
            env = dict(os.environ, PLAMO_LOCAL_KEY=self.key, HF_HUB_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
            with self.log_path.open("wb") as log:
                self.process = subprocess.Popen(command, stdout=log, stderr=log, env=env,
                                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        deadline = time.monotonic() + 300
        while not self._stop.is_set() and time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"モデルの読み込みに失敗しました。ログ: {self.log_path}")
            try:
                request = urllib.request.Request(self.url + "/health", headers={"Authorization": "Bearer " + self.key})
                with self._http.open(request, timeout=1) as response:
                    if response.status == 200:
                        self.ready = True
                        return
            except (OSError, urllib.error.URLError):
                pass
            self._stop.wait(0.2)
        self.close()
        raise RuntimeError("モデルの読み込みが中断されたか、時間切れになりました。")

    def translate(self, text: str, target_lang: str) -> str:
        if not self.ready or self.process is None or self.process.poll() is not None:
            raise RuntimeError("PLaMoが読み込まれていません。設定とモデルを確認してください。")
        payload = {"prompt": build_prompt(text, target_lang), "n_predict": 2048,
                   "temperature": 0, "stop": ["<|plamo:tag|>", "<|plamo:bos|>"], "stream": False}
        request = urllib.request.Request(self.url + "/completion", data=json.dumps(payload).encode("utf-8"),
                                         headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.key})
        try:
            with self._http.open(request, timeout=max(120, self.settings.get_timeout())) as response:
                result = json.load(response)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"ローカル翻訳に失敗しました: {detail[:300]}") from exc
        except (OSError, urllib.error.URLError) as exc:
            self.close()
            raise RuntimeError("ローカルモデルとの通信が中断されました。設定メニューからモデルを再読み込みしてください。") from exc
        if result.get("truncated") or result.get("stopped_limit"):
            raise RuntimeError("文章が長すぎるか、翻訳の出力上限に達しました。短く分けて翻訳してください。")
        output = result.get("content", "").strip()
        if not output:
            raise RuntimeError("モデルから翻訳結果が返りませんでした。")
        return output

    def close(self):
        self._stop.set()
        self.ready = False
        with self._lock:
            process, self.process = self.process, None
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
