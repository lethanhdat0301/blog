# Kho tài liệu

## Chạy thử local
    pip install -r requirements.txt "markitdown[pdf,docx,pptx]"
    python scripts/ingest.py https://github.com/squidfunk/mkdocs-material
    mkdocs serve

## Deploy (Cloudflare Pages)
- Build command: `pip install -r requirements.txt && mkdocs build`
- Output directory: `site`
- Biến môi trường: `PYTHON_VERSION=3.12`
- Rồi gắn tên miền ở tab Custom domains.

## Cách gửi nội dung
- Mở Issue trong repo, dán link hoặc link repo GitHub vào nội dung.
- Hoặc commit file PDF/DOCX/PPTX/MD vào `inbox/`.
Actions sẽ chuyển thành bài trong `docs/blog/posts/` và Cloudflare tự build lại.
