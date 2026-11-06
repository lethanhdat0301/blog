#!/usr/bin/env python3
"""Thử tóm tắt một URL bằng nhiều model Claude để so sánh chất lượng và chi phí.

Cách dùng:
  pip install anthropic
  set ANTHROPIC_API_KEY=sk-ant-...        (PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-...")
  python scripts/try_summarize.py <url> [model1 model2 ...]
Mặc định so sánh claude-haiku-5-5 và claude-sonnet-5-5.
"""
import sys
import urllib.request

import anthropic

# USD / 1M token (input, output) - giá cho prompt <= 100K token với Haiku
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}

SYSTEM = (
    "Bạn là biên tập viên cho một blog tài liệu tiếng Việt. Hãy tóm tắt và viết lại "
    "nội dung được cung cấp thành bài Markdown. Quy tắc: chỉ dùng thông tin có trong "
    "nguồn, không suy diễn hay thêm chi tiết; giữ nguyên tên riêng, số liệu, tên hàm "
    "và code; bỏ phần menu, quảng cáo, điều hướng. Cấu trúc: một đoạn mở đầu 2-3 câu, "
    "các ý chính dạng gạch đầu dòng, rồi mục 'Điểm cần nhớ'."
)


def fetch(url):
    req = urllib.request.Request(
        "https://r.jina.ai/" + url, headers={"User-Agent": "site-ingest"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def run(client, model, source):
    resp = client.messages.create(
        model=model,
        max_tokens=4000,
        system=SYSTEM,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": source}],
    )
    if resp.stop_reason == "refusal":
        return f"[model từ chối: {resp.stop_details}]", resp.usage
    text = "".join(b.text for b in resp.content if b.type == "text")
    return text, resp.usage


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # console Windows mặc định không in được tiếng Việt
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    url = sys.argv[1]
    models = sys.argv[2:] or ["claude-haiku-5-5", "claude-sonnet-5-5"]
    source = fetch(url)
    print(f"Nguồn: {url} ({len(source):,} ký tự)\n")
    client = anthropic.Anthropic()
    for m in models:
        try:
            text, u = run(client, m, source)
        except anthropic.APIStatusError as e:
            print(f"=== {m}: lỗi {e.status_code}: {e.message}\n")
            continue
        pin, pout = PRICES.get(m, (0, 0))
        cost = (u.input_tokens * pin + u.output_tokens * pout) / 1e6
        print(f"=== {m} | in {u.input_tokens:,} / out {u.output_tokens:,} tok | ~${cost:.4f}\n")
        print(text.strip() + "\n")


if __name__ == "__main__":
    main()
