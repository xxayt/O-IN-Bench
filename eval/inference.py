"""Generate O-IN-Bench responses with an audio-visual Chat Completions endpoint."""
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm

from eval.common import load_jsonl
from eval.prompts import SYSTEM_PROMPT, USER_PROMPT
from models.openai_api import chat, video_content

DATA_ROOT = os.path.abspath(os.environ.get("DATA_ROOT", "./O-IN-Bench"))
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "./outputs/model")
API_BASE = os.environ.get("API_BASE", "")
API_KEY = os.environ.get("API_KEY", "")
MODEL_NAME = os.environ.get("MODEL_NAME", "")
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "1024"))
WORKERS = int(os.environ.get("WORKERS", "4"))
MAX_SAMPLES = int(os.environ.get("MAX_SAMPLES", "-1"))
SKIP_SAMPLES = int(os.environ.get("SKIP_SAMPLES", "0"))
OVERRIDE = os.environ.get("OVERRIDE", "0") == "1"


# 只发送音视频和共享指令，标注字段不进入模型输入。
def predict(doc):
    try:
        content = video_content(os.path.join(DATA_ROOT, doc["video_path"]))
        content.append({"type": "text", "text": USER_PROMPT})
        messages = [{"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": content}]
        response, metadata = chat(API_BASE, API_KEY, MODEL_NAME, messages, MAX_TOKENS, 0)
        return {"id": doc["id"], "response": response, "response_meta": metadata}
    except Exception as exc:
        return {"id": doc["id"], "response": None, "error": str(exc)}


# 并发推理并逐条落盘，续跑仅跳过已获得回答的样本。
def main():
    if not API_BASE or not API_KEY or not MODEL_NAME:
        raise ValueError("Set API_BASE, API_KEY and MODEL_NAME")
    data_file = os.path.join(DATA_ROOT, "data", "test.jsonl")
    docs = load_jsonl(data_file)[SKIP_SAMPLES:]
    if MAX_SAMPLES > 0:
        docs = docs[:MAX_SAMPLES]
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, "predictions.jsonl")
    previous = {} if OVERRIDE or not os.path.exists(path) else {
        row["id"]: row for row in load_jsonl(path, latest=True)}
    pending = [doc for doc in docs if previous.get(doc["id"], {}).get("response") is None]
    with open(path, "w" if OVERRIDE else "a", encoding="utf-8") as f:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = [pool.submit(predict, doc) for doc in pending]
            for future in tqdm(as_completed(futures), total=len(futures), desc="Inference"):
                row = future.result()
                previous[row["id"]] = row
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
    # 将续跑日志整理成每个 ID 一条记录，便于单独交给评分工具。
    with open(path + ".partial", "w", encoding="utf-8") as f:
        for row in previous.values():
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(path + ".partial", path)
    failed = sum(previous[doc["id"]].get("response") is None for doc in docs)
    print(f"Selected: {len(docs)}, failed: {failed}, predictions: {path}")
    if failed:
        raise SystemExit("Some requests failed; rerun with OVERRIDE=0 to retry")


if __name__ == "__main__":
    main()
