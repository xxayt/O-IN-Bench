"""Chat Completions adapter for endpoints supporting native video_url input."""
import base64
import os

import requests

TIMEOUT = int(os.environ.get("API_TIMEOUT", "300"))


# 调用兼容接口并保留返回的模型名、终止原因与 token 用量。
def chat(base_url, api_key, model, messages, max_tokens, temperature):
    response = requests.post(
        base_url.rstrip("/") + "/chat/completions",
        headers={"Authorization": "Bearer " + api_key},
        json={"model": model, "messages": messages, "max_tokens": max_tokens,
              "temperature": temperature, "stream": False}, timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    choice = payload["choices"][0]
    text = choice["message"].get("content")
    if not isinstance(text, str):
        raise ValueError("API returned no text content")
    return text, {"model": payload.get("model"), "finish_reason": choice.get("finish_reason"),
                  "usage": payload.get("usage")}


# 原样编码包含音轨的完整 MP4，与现有 Qwen API 客户端的视频引用格式一致。
def video_content(path):
    with open(path, "rb") as f:
        video = base64.b64encode(f.read()).decode("utf-8")
    return [{"type": "video_url", "video_url": {"url": "data:video/mp4;base64," + video}}]
