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

from ..utils.model_catalog import MODELS
from ..utils.providers import NoRedirect


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
        self._http = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        self.log_path = Path(settings.config_dir) / "plamo-runtime.log"

    @property
    def model_name(self):
        profile = self.settings.get_setting("local_model", "profile", "lightweight")
        return MODELS[profile]["name"] + " / " + getattr(self, "device_used", "CPU")

    def _server(self, gpu=False):
        key = "gpu_server_path" if gpu else "llama_server_path"
        configured = self.settings.get_setting("local_model", key, "")
        folder = "llama-vulkan" if gpu else "llama"
        return Path(configured).expanduser() if configured else resource_root() / "runtime" / folder / "llama-server.exe"

    def _gpu_available(self, server):
        if not server.is_file():
            return False
        try:
            probe = subprocess.run([str(server), "--list-devices"], capture_output=True,
                                   timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            import re
            return probe.returncode == 0 and bool(re.search(r"(?:Vulkan|CUDA|SYCL|HIP)\d+:",
                (probe.stdout + probe.stderr).decode("utf-8", errors="replace")))
        except (OSError, subprocess.TimeoutExpired):
            return False

    def start(self):
        profile = self.settings.get_setting("local_model", "profile", "lightweight")
        if profile not in MODELS:
            raise ValueError("ローカルモデルを選び直してください。")
        # Keep compatibility with the comparison runner's lightweight-only path.
        model_path = self.settings.get_setting("local_model", profile + "_path", "")
        if not model_path and profile == "lightweight":
            model_path = self.settings.get_setting("local_model", "gguf_path", "")
        model = Path(model_path).expanduser()
        if not model_path or not model.is_file():
            raise FileNotFoundError("モデルがありません。設定の『翻訳方式』からダウンロードするか、保存先を指定してください。")
        device = self.settings.get_setting("local_model", "device", "auto")
        gpu = device != "cpu" and self._gpu_available(self._server(gpu=True))
        self.fallback_reason = ""
        if device == "gpu" and not gpu:
            raise RuntimeError("GPUを利用できません。GPU対応ランタイムとドライバーを確認するか、実行先を自動／CPUにしてください。")
        try:
            self._launch(model, gpu)
        except Exception:
            self._terminate_process()
            if device != "auto" or not gpu or self._stop.is_set():
                raise
            self.fallback_reason = "GPUでの読み込みに失敗したためCPUを使用しています。"
            self._launch(model, False)

    def _launch(self, model, gpu):
        server = self._server(gpu)
        if not server.is_file():
            raise FileNotFoundError("実行ランタイムがありません。python setup_local_runtime.py を実行してください。")
        with self._lock:
            if self._stop.is_set():
                raise RuntimeError("モデルの読み込みを中断しました。")
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            self.url = f"http://127.0.0.1:{port}"
            command = [str(server), "-m", str(model), "--host", "127.0.0.1", "--port", str(port),
                       "-c", "8192", "-np", "1", "-ngl", "all" if gpu else "0",
                       "--api-key", self.key, "--no-webui", "--log-verbosity", "0"]
            if not gpu:
                command += ["--device", "none"]
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("ab") as log:
                log.write((f"\nPLaMo runtime: {'GPU' if gpu else 'CPU'} / {model.name}\n").encode("utf-8"))
                log.flush()
                self.process = subprocess.Popen(command, stdout=log, stderr=log,
                                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            process = self.process
        deadline = time.monotonic() + 180
        while not self._stop.is_set() and time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"モデルの読み込みに失敗しました。ログ: {self.log_path}")
            try:
                request = urllib.request.Request(self.url + "/health", headers={"Authorization": "Bearer " + self.key})
                with self._http.open(request, timeout=1) as response:
                    if response.status == 200 and not self._stop.is_set():
                        self.device_used = "GPU" if gpu else "CPU"
                        self.ready = True
                        return
            except (OSError, urllib.error.URLError) as exc:
                reason = getattr(exc, 'reason', exc)
                if getattr(reason, 'winerror', None) == 10013:
                    raise RuntimeError('Windowsまたは実行環境がPC内モデルへの接続を拒否しました。アプリのネットワーク権限を確認してください。') from None
            self._stop.wait(0.2)
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
                body = response.read(4 * 1024 * 1024 + 1)
                if len(body) > 4 * 1024 * 1024:
                    raise RuntimeError('ローカルモデルの応答が大きすぎます。')
                result = json.loads(body)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"ローカル翻訳に失敗しました（HTTP {exc.code}）。モデルを再読み込みしてください。") from None
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
        self._terminate_process()

    def _terminate_process(self):
        with self._lock:
            process, self.process = self.process, None
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
