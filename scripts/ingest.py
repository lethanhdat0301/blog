#!/usr/bin/env python3
"""Chuyển link / repo GitHub / file trong inbox/ thành bài Markdown cho MkDocs blog.

Cách dùng:
  python scripts/ingest.py https://example.com/bai-viet https://github.com/user/repo
  ISSUE_BODY="..." python scripts/ingest.py     # lấy mọi URL trong nội dung issue
  python scripts/ingest.py                      # xử lý các file trong inbox/
"""
import datetime
import os
import pathlib
import re
import sys
import unicodedata
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
POSTS = ROOT / "docs" / "blog" / "posts"
INBOX = ROOT / "inbox"

URL_RE = re.compile(r"https?://[^\s)>\]]+")
GH_REPO_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/#?]+?)(?:\.git)?/?$")


def http_get(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": "site-ingest", **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def slugify(text):
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")[:60] or "untitled"


def first_heading(md):
    m = re.search(r"^#\s+(.+)$", md, re.M)
    return m.group(1).strip() if m else None


# --- Soạn lại nội dung bằng Claude -------------------------------------------
# Task nhẹ (nội dung ngắn) -> Haiku rẻ; task lớn (nội dung dài) -> Sonnet.
# Đổi bằng biến môi trường, không cần sửa code.
MODEL_LIGHT = os.environ.get("LLM_MODEL_LIGHT", "claude-haiku-5-5")
MODEL_HEAVY = os.environ.get("LLM_MODEL_HEAVY", "claude-sonnet-5-5")
HEAVY_OVER_CHARS = int(os.environ.get("LLM_HEAVY_OVER_CHARS", "40000"))
MAX_CHARS = 1_500_000  # ~ giới hạn an toàn cho cửa sổ ngữ cảnh 1M token (không cắt bớt, quá thì bỏ qua)

SYSTEM = (
    "Bạn là biên tập viên cho một blog tài liệu tiếng Việt. Hãy tóm tắt và viết lại "
    "nội dung được cung cấp thành bài Markdown. Quy tắc: chỉ dùng thông tin có trong "
    "nguồn, không suy diễn hay thêm chi tiết; giữ nguyên tên riêng, số liệu, tên hàm "
    "và code; bỏ phần menu, quảng cáo, điều hướng. Dòng đầu tiên là tiêu đề dạng "
    "'# Tiêu đề'. Sau đó: một đoạn mở đầu 2-3 câu, các ý chính dạng gạch đầu dòng, "
    "rồi mục '## Điểm cần nhớ'. Chỉ trả về nội dung bài, không giải thích thêm."
)


def pick_model(text):
    return MODEL_HEAVY if len(text) > HEAVY_OVER_CHARS else MODEL_LIGHT


def rewrite(body):
    """Trả về bài đã soạn lại (Markdown) hoặc None nếu bỏ qua / lỗi -> dùng nguyên bản gốc."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    if len(body) > MAX_CHARS:
        print("! nội dung quá dài, bỏ qua bước soạn lại", file=sys.stderr)
        return None
    try:
        import anthropic

        model = pick_model(body)
        resp = anthropic.Anthropic().messages.create(
            model=model,
            max_tokens=16000,
            system=SYSTEM,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": body}],
        )
        if resp.stop_reason != "end_turn":
            print(f"! {model} dừng sớm ({resp.stop_reason}), dùng bản gốc", file=sys.stderr)
            return None
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        print(f"  ({model}: {resp.usage.input_tokens} in / {resp.usage.output_tokens} out)")
        return text or None
    except Exception as e:
        print(f"! lỗi khi soạn lại, dùng bản gốc: {e}", file=sys.stderr)
        return None


def write_post(title, body, kind, source=None):
    new = rewrite(body)
    if new:
        title = first_heading(new) or title
        body = new
    body = re.sub(r"^\s*#\s+.+\n*", "", body, count=1)  # tránh lặp tiêu đề cấp 1
    today = datetime.date.today().isoformat()
    path = POSTS / f"{today}-{slugify(title)}.md"
    n = 2
    while path.exists():
        path = POSTS / f"{today}-{slugify(title)}-{n}.md"
        n += 1
    front = ["---", f"date: {today}", "categories:", f"  - {kind}", "---", ""]
    head = [f"# {title}", ""]
    if source:
        head += [f"> Nguồn: <{source}>", ""]
    head += ["<!-- more -->", ""]
    path.write_text("\n".join(front + head) + body.strip() + "\n", encoding="utf-8")
    print(f"+ {path.relative_to(ROOT)}")


def ingest_url(url):
    m = GH_REPO_RE.match(url)
    if m:
        return ingest_github(m.group(1), m.group(2), url)
    # r.jina.ai trả về Markdown sạch của trang web
    raw = http_get("https://r.jina.ai/" + url)
    title = None
    tm = re.match(r"Title:\s*(.+)", raw)
    if tm:
        title = tm.group(1).strip()
    body = raw.split("Markdown Content:", 1)[-1]
    write_post(title or first_heading(body) or url, body, "link", url)


IMG_EXT = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".avif", ".bmp")
SKIP_PREFIX = ("http://", "https://", "#", "mailto:", "data:", "//", "tel:")
REL_RE = re.compile(r'''((?:src|href)=")([^"]*)(")|(\]\()([^)\s]+)''')
ALERTS = {"NOTE": "note", "TIP": "tip", "IMPORTANT": "info", "WARNING": "warning", "CAUTION": "danger"}


def absolutize(md, owner, repo):
    """README GitHub dùng đường dẫn tương đối (ảnh, link nội bộ) nên sẽ hỏng khi chép sang site.
    Đổi chúng thành URL tuyệt đối: ảnh -> raw.githubusercontent.com, còn lại -> trang blob/tree trên GitHub."""

    def fix(path):
        if not path or path.startswith(SKIP_PREFIX):
            return path
        m = re.match(r"([^#?]*)([#?].*)?$", path)
        base, tail = m.group(1), m.group(2) or ""
        rel = base.lstrip("/")
        while rel.startswith("./"):
            rel = rel[2:]
        if rel.lower().endswith(IMG_EXT):
            return f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{rel}{tail}"
        kind = "tree" if rel.endswith("/") or not rel else "blob"
        return f"https://github.com/{owner}/{repo}/{kind}/HEAD/{rel}{tail}"

    def sub(m):
        if m.group(1):
            return m.group(1) + fix(m.group(2)) + m.group(3)
        return m.group(4) + fix(m.group(5))

    return REL_RE.sub(sub, md)


def convert_alerts(md):
    """> [!TIP] ... (cú pháp riêng của GitHub) -> admonition của Material."""
    out, lines, i = [], md.split("\n"), 0
    while i < len(lines):
        m = re.match(r"^>\s*\[!(\w+)\]\s*(.*)$", lines[i])
        if m and m.group(1).upper() in ALERTS:
            body = [m.group(2)] if m.group(2) else []
            i += 1
            while i < len(lines) and lines[i].startswith(">"):
                body.append(lines[i][1:].lstrip())
                i += 1
            out.append(f"!!! {ALERTS[m.group(1).upper()]}")
            out += ["    " + b if b else "" for b in body]
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def ingest_github(owner, repo, url):
    readme = http_get(
        f"https://api.github.com/repos/{owner}/{repo}/readme",
        {"Accept": "application/vnd.github.raw+json"},
    )
    readme = convert_alerts(absolutize(readme, owner, repo))
    write_post(f"{owner}/{repo}", readme, "repo", url)


def ingest_file(path):
    if path.suffix.lower() in {".md", ".txt"}:
        body = path.read_text(encoding="utf-8", errors="replace")
    else:
        from markitdown import MarkItDown  # pip install "markitdown[pdf,docx,pptx]"

        body = MarkItDown().convert(str(path)).text_content
    write_post(first_heading(body) or path.stem, body, "tai-lieu")
    path.unlink()  # bản gốc vẫn còn trong lịch sử git


def main():
    urls = [a for a in sys.argv[1:] if a.startswith("http")]
    urls += URL_RE.findall(os.environ.get("ISSUE_BODY", ""))
    for u in dict.fromkeys(urls):
        try:
            ingest_url(u)
        except Exception as e:
            print(f"! lỗi với {u}: {e}", file=sys.stderr)
    for f in sorted(INBOX.iterdir()):
        if f.is_file() and f.name != ".gitkeep":
            try:
                ingest_file(f)
            except Exception as e:
                print(f"! lỗi với {f.name}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
