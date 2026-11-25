"""Score public O-IN-Bench predictions independently of inference."""
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm

from eval.common import load_jsonl, save_json
from eval.metrics import DIMENSIONS, build_summary
from eval.prompts import JUDGE_PROMPT
from models.openai_api import chat

DATA_ROOT = os.environ.get("DATA_ROOT", "./O-IN-Bench")
PREDICTIONS = os.environ.get("PREDICTIONS", "./outputs/model/predictions.jsonl")
OUTPUT_DIR = os.environ.get("SCORE_DIR", "./outputs/model/scores")
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "gpt-6-luna")
JUDGE_API_BASE = os.environ.get("JUDGE_API_BASE", "")
JUDGE_API_KEY = os.environ.get("JUDGE_API_KEY", "")
WORKERS = int(os.environ.get("WORKERS", "4"))
OVERRIDE = os.environ.get("OVERRIDE", "0") == "1"


# 只将问题、场景、语言、完整 rubric 和最终回答交给裁判。
def build_prompt(doc, response):
    payload = {key: doc[key] for key in ("language", "question", "context", "rubric")}
    payload["final_response"] = response
    return JUDGE_PROMPT + json.dumps(payload, ensure_ascii=False)


# 沿用 WeMM 独立推理的最终回答提取，未闭合思考按无最终回答处理。
def extract_final(response):
    if "</think>" in response:
        return response.rsplit("</think>", 1)[1].strip(), None
    if "<think>" in response:
        return "", "unclosed_think"
    return response.strip(), None


# 严格解析各维度的独立评分和理由，不将非法返回默认为零分。
def parse_judgment(raw):
    text = raw.strip()
    if text.startswith("```"):
        text = "\n".join(text.splitlines()[1:-1])
    value = json.loads(text)
    if value.get("status") == "unjudgeable":
        if not isinstance(value.get("reason"), str) or not value["reason"].strip():
            raise ValueError("Missing unjudgeable reason")
        return value
    if value.get("status") != "ok":
        raise ValueError("Invalid judge status")
    for key in DIMENSIONS:
        part = value[key]
        if type(part.get("score")) is not int or part["score"] not in (0, 1):
            raise ValueError(f"Invalid {key} score")
        if not isinstance(part.get("reason"), str) or not part["reason"].strip():
            raise ValueError(f"Missing {key} reason")
    return value


# 三项独立判定只在计算总分时门控，不改写原始维度。
def gated_score(scores):
    return scores["language"] * scores["intent"] * (1 + scores["content"]) / 2


# 沿用原脚本去除空模板占位符，识别没有实际回复的输出。
def strip_placeholders(text):
    for marker in ("[RESPONSE]", "<response>", "</response>", "<|response|>"):
        text = text.replace(marker, "")
    return text.strip()


# 严格判定沉默标记和空回答，其余需要回应的样本才调用 GPT。
def rule_scores(response_required, response):
    text = response.strip()
    if not response_required:
        intent = int(text == "[SILENCE]")
        return {"language": None, "intent": intent, "content": None}, float(intent)
    if text in ("", "[SILENCE]") or not strip_placeholders(text):
        return dict.fromkeys(DIMENSIONS, 0), 0.0
    return None


# 独立执行原有评分规则，调用或解析失败保留空分数，允许下次重试。
def evaluate_one_case(doc, response):
    case = {key: doc[key] for key in ("id", "task_l1", "task_l2", "language", "response_required")}
    case.update(judge_model=JUDGE_MODEL, source_response=response, status="response_missing",
                scores=dict.fromkeys(DIMENSIONS), score=None, judge_trace=[])
    if response is None:
        return case
    text, warning = extract_final(response)
    case.update(response=text, extraction_warning=warning)
    ruled = rule_scores(doc["response_required"], text)
    if ruled is not None:
        scores, score = ruled
        case.update(status="ok", scores=scores, score=score, method="rule")
        return case
    messages = [{"role": "user", "content": build_prompt(doc, text)}]
    case.update(status="judge_error", method="llm", judge_input=messages)
    for attempt in range(3):
        trace = {"attempt": attempt + 1}
        case["judge_trace"].append(trace)
        try:
            raw, _ = chat(JUDGE_API_BASE, JUDGE_API_KEY, JUDGE_MODEL, messages, 1536, 0)
            trace["raw_response"] = raw
            parsed = parse_judgment(raw)
            if parsed["status"] == "unjudgeable":
                scores = dict.fromkeys(DIMENSIONS, 0)
                reasons = dict.fromkeys(DIMENSIONS, parsed["reason"])
            else:
                scores = {k: parsed[k]["score"] for k in DIMENSIONS}
                reasons = {k: parsed[k]["reason"] for k in DIMENSIONS}
            case.update(status="ok", scores=scores, score=gated_score(scores), reasons=reasons)
            return case
        except Exception as exc:
            trace["error"] = str(exc)
    return case


# 按标注全量汇总，缺失预测和裁判失败不会被静默排除。
def main():
    data_file = os.path.join(DATA_ROOT, "data", "test.jsonl")
    docs = load_jsonl(data_file)
    predictions = {row["id"]: row for row in load_jsonl(PREDICTIONS)}
    unknown = set(predictions) - {doc["id"] for doc in docs}
    if unknown:
        raise ValueError(f"Predictions contain unknown IDs: {sorted(unknown)[:5]}")
    if not JUDGE_API_BASE or not JUDGE_API_KEY:
        raise ValueError("Set JUDGE_API_BASE and JUDGE_API_KEY")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    result_file = os.path.join(OUTPUT_DIR, "judgments.jsonl")
    previous = {} if OVERRIDE or not os.path.exists(result_file) else {
        row["id"]: row for row in load_jsonl(result_file, latest=True)}
    results = {}
    pending = []
    for doc in docs:
        response = predictions.get(doc["id"], {}).get("response")
        old = previous.get(doc["id"])
        if old and old["status"] == "ok" and old.get("source_response") == response:
            results[doc["id"]] = old
        else:
            pending.append((doc, response))
    with open(result_file, "w" if OVERRIDE else "a", encoding="utf-8") as f:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = [pool.submit(evaluate_one_case, doc, response) for doc, response in pending]
            for future in tqdm(as_completed(futures), total=len(futures), desc="Scoring"):
                row = future.result()
                results[row["id"]] = row
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
    rows = [results[doc["id"]] for doc in docs]
    with open(result_file + ".partial", "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(result_file + ".partial", result_file)
    summary = build_summary(rows)
    save_json(os.path.join(OUTPUT_DIR, "summary.json"), summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["score"] is None:
        raise SystemExit("Incomplete evaluation; inspect judgments.jsonl and retry")


if __name__ == "__main__":
    main()
