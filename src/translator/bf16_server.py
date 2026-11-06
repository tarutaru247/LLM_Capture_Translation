"""Standalone BF16 worker; model code is loaded only from the chosen local folder."""
import argparse
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, trust_remote_code=True, local_files_only=True, dtype=torch.bfloat16,
    ).to(device).eval()
    stops = [tokenizer.convert_tokens_to_ids(t) for t in ("<|plamo:tag|>", "<|plamo:bos|>")]
    secret = "Bearer " + os.environ["PLAMO_LOCAL_KEY"]

    class Handler(BaseHTTPRequestHandler):
        def reply(self, code, value):
            body = json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            return hmac.compare_digest(self.headers.get("Authorization", ""), secret)

        def do_GET(self):
            self.reply(200 if self.authorized() and self.path == "/health" else 403, {"status": "ok"})

        def do_POST(self):
            if not self.authorized() or self.path != "/completion":
                self.reply(403, {"error": "Forbidden"})
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                if length <= 0 or length > 1_000_000:
                    raise ValueError("入力サイズが不正です。")
                payload = json.loads(self.rfile.read(length))
                inputs = tokenizer(payload["prompt"], return_tensors="pt").to(device)
                count = inputs["input_ids"].shape[1]
                limit = min(int(payload.get("n_predict", 2048)), 2048)
                if count + limit > 8192:
                    raise ValueError("文章が長すぎます。短く分けて翻訳してください。")
                with torch.inference_mode():
                    output = model.generate(**inputs, do_sample=False, max_new_tokens=limit,
                                            eos_token_id=stops, pad_token_id=tokenizer.pad_token_id)
                generated = output[0, count:]
                self.reply(200, {"content": tokenizer.decode(generated, skip_special_tokens=True),
                                 "stopped_limit": len(generated) >= limit and int(generated[-1]) not in stops})
            except Exception as exc:
                self.reply(400, {"error": str(exc)})

        def log_message(self, fmt, *values):
            pass

    HTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
