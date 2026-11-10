"""Network-free quality comparison plus separate warmed-up llama-bench timings."""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from src.translator.plamo_runtime import build_prompt
from src.utils.model_catalog import MODELS


def run(command, timeout=180):
    result = subprocess.run(command,capture_output=True,timeout=timeout,
                            creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8",errors="replace")[-1800:])
    return result


def gpu_used():
    try:
        return int(run(["nvidia-smi","--query-gpu=memory.used","--format=csv,noheader,nounits"],10).stdout.decode().splitlines()[0])
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired):
        return None


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--profile",choices=list(MODELS),required=True)
    args=parser.parse_args()
    directory=Path(__file__).resolve().parent
    work=ROOT/"runtime/size-cli"/args.profile
    work.mkdir(parents=True,exist_ok=True)
    model_info=MODELS[args.profile]
    model=Path(r"D:\LocalLLM\models")/model_info["filename"]
    with model.open("rb") as file: sha=hashlib.file_digest(file,"sha256").hexdigest()
    if sha!=model_info["sha256"]: raise RuntimeError("Model checksum mismatch")
    binary=ROOT/"runtime/llama-vulkan"
    samples=json.loads((directory.parent/"samples.json").read_text(encoding="utf-8"))
    report={"profile":args.profile,"model":model_info["name"],"sha256":sha,"file_bytes":model.stat().st_size,
            "date":datetime.now(timezone(timedelta(hours=9))).isoformat(),
            "runtime":"llama.cpp b12140 / Vulkan / network-free CLI",
            "gpu":run(["nvidia-smi","--query-gpu=name,driver_version","--format=csv,noheader"]).stdout.decode().strip(),
            "conditions":{"target":"ja","source":"auto","temperature":0,"seed":42,
                          "context":8192,"max_output_tokens":2048,"history":False},"results":[]}
    baseline=gpu_used(); observed=[]; stop=threading.Event()
    def monitor():
        while not stop.is_set():
            value=gpu_used()
            if value is not None: observed.append(value)
            stop.wait(0.5)
    thread=threading.Thread(target=monitor,daemon=True);thread.start()
    output=directory/(args.profile+"_cli_results.json")
    try:
        for sample in samples:
            prompt=work/(sample["id"]+".prompt.txt")
            prompt.write_text(build_prompt(sample["source"],"ja"),encoding="utf-8")
            command=[str(binary/"llama-completion.exe"),"-m",str(model),"-f",str(prompt),
                     "-c","8192","-ngl","all","--device","Vulkan0","-n","2048",
                     "--temp","0","--seed","42","--no-conversation","--no-display-prompt",
                     "--simple-io","--perf","-r","<|plamo:tag|>","-r","<|plamo:bos|>"]
            started=time.perf_counter(); result=run(command); elapsed=time.perf_counter()-started
            raw=result.stdout.decode("utf-8",errors="strict").strip()
            text=raw.removesuffix(" [end of text]").strip().replace("\r\n","\n").replace("\r", "")
            for token in ("<|plamo:tag|>","<|plamo:bos|>"):
                if text.endswith(token): text=text[:-len(token)].rstrip()
            if not text: raise RuntimeError("Empty translation")
            log=result.stderr.decode("utf-8",errors="replace")
            match=re.search(r"(?<!prompt )eval time\s*=\s*([\d.]+) ms /\s*(\d+) runs\s*\([^\n]*?([\d.]+) tokens per second",log)
            if match and int(match[2])>=2047: raise RuntimeError("Output limit reached")
            row={"id":sample["id"],"output":text,"raw_stdout":raw,"process_seconds_including_load":round(elapsed,3)}
            if match: row.update(decode_ms=float(match[1]),decode_steps=int(match[2]),decode_tokens_per_second=float(match[3]))
            report["results"].append(row)
            (work/(sample["id"]+".stderr.txt")).write_text(log,encoding="utf-8")
            output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            print(f"{args.profile} {sample['id']} complete ({elapsed:.2f}s including load)",flush=True)
        print(f"{args.profile}: starting separate warmed-up speed benchmark",flush=True)
        result=run([str(binary/"llama-bench.exe"),"-m",str(model),"-ngl","99",
                    "-p","128","-n","128","-r","3","-o","json"],timeout=240)
        report["speed_benchmark"]=json.loads(result.stdout.decode("utf-8"))
        (work/"bench.stderr.txt").write_bytes(result.stderr)
    finally:
        stop.set();thread.join(timeout=12)
        report["vram_baseline_mib"]=baseline
        report["vram_peak_observed_mib"]=max(observed) if observed else None
        report["vram_peak_delta_mib"]=max(observed)-baseline if observed and baseline is not None else None
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Saved {output}",flush=True)


if __name__=="__main__": main()
