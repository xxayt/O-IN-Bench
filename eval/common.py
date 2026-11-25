"""Small shared helpers for resumable evaluation."""
import json
import os


# 读取 JSONL；仅内部续跑日志允许同一 ID 的后续记录覆盖旧记录。
def load_jsonl(path, latest=False):
    rows = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            if row["id"] in rows and not latest:
                raise ValueError(f"Duplicate ID: {row['id']}")
            rows[row["id"]] = row
    return list(rows.values())


# 原子写入配置和汇总，避免留下半份 JSON。
def save_json(path, value):
    with open(path + ".partial", "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(path + ".partial", path)
