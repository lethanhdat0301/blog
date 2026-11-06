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


def write_post(title, body, kind, source=None):
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


def ingest_github(owner, repo, url):
    readme = http_get(
        f"https://api.github.com/repos/{owner}/{repo}/readme",
        {"Accept": "application/vnd.github.raw+json"},
    )
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
