#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""블로그 draft 병합 · HTML 생성 · sitemap 갱신

사용법:
  python publish_blog.py --add          # Downloads/blog-draft.json 자동 탐색 후 병합
  python publish_blog.py --add --draft path/to/blog-draft.json
  python publish_blog.py --rebuild      # blog-posts.json만으로 전체 재생성
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data" / "blog-posts.json"
BLOG_DIR = ROOT / "blog"
DRAFT_NAME = "blog-draft.json"


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def find_draft_in_downloads() -> Path | None:
    downloads = Path.home() / "Downloads"
    if not downloads.is_dir():
        return None
    candidates = sorted(
        downloads.glob(DRAFT_NAME),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-") or "post"


def inline_format(text: str) -> str:
    links: list[str] = []

    def stash_link(label: str, href: str) -> str:
        href = href.strip()
        label = label.strip()
        rel = ' rel="noopener noreferrer"' if href.startswith(("http://", "https://")) else ""
        links.append(f'<a href="{escape(href, quote=True)}"{rel}>{escape(label)}</a>')
        return f"\x00LINK{len(links) - 1}\x00"

    text = re.sub(
        r"\[\[([^\]|]+)\|([^\]]+)\]\]",
        lambda m: stash_link(m.group(1), m.group(2)),
        text,
    )
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: stash_link(m.group(1), m.group(2)),
        text,
    )
    text = re.sub(
        r'<a\s+href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',
        lambda m: stash_link(re.sub(r"<[^>]+>", "", m.group(2)), m.group(1)),
        text,
        flags=re.IGNORECASE,
    )

    text = escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)

    def autolink(m: re.Match[str]) -> str:
        url = m.group(1)
        return stash_link(url, url)

    text = re.sub(r"(?<!\")https?://[^\s<]+", autolink, text)

    for i, html in enumerate(links):
        text = text.replace(f"\x00LINK{i}\x00", html)
    return text


def markdown_to_html(body: str) -> str:
    if not body or not body.strip():
        return ""

    raw = body.strip()
    if raw.startswith("<") or "<div class=" in raw[:300]:
        return raw

    lines = raw.split("\n")
    html_parts: list[str] = []
    i = 0

    def flush_paragraph(buf: list[str]) -> None:
        if not buf:
            return
        text = " ".join(s.strip() for s in buf if s.strip())
        if text:
            if re.match(r"^\d+\.\s", text):
                html_parts.append(f"<p>{inline_format(text)}</p>")
            else:
                html_parts.append(f"<p>{inline_format(text)}</p>")
        buf.clear()

    list_buf: list[str] = []
    para_buf: list[str] = []

    def flush_list() -> None:
        nonlocal list_buf
        if not list_buf:
            return
        items = "".join(f"<li>{inline_format(item)}</li>" for item in list_buf)
        html_parts.append(f"<ul>{items}</ul>")
        list_buf = []

    while i < len(lines):
        line = lines[i].rstrip()

        if line.strip() == "":
            flush_paragraph(para_buf)
            flush_list()
            i += 1
            continue

        if line.startswith(":::warn"):
            flush_paragraph(para_buf)
            flush_list()
            block: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(":::"):
                block.append(lines[i])
                i += 1
            inner = "<br>".join(inline_format(l) for l in block if l.strip())
            html_parts.append(f'<div class="callout warn">{inner}</div>')
            if i < len(lines) and lines[i].strip().startswith(":::"):
                i += 1
            continue

        if line.startswith(":::callout"):
            flush_paragraph(para_buf)
            flush_list()
            block = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(":::"):
                block.append(lines[i])
                i += 1
            inner = "<br>".join(inline_format(l) for l in block if l.strip())
            html_parts.append(f'<div class="callout">{inner}</div>')
            if i < len(lines) and lines[i].strip().startswith(":::"):
                i += 1
            continue

        if line.startswith("## "):
            flush_paragraph(para_buf)
            flush_list()
            html_parts.append(f"<h2>{inline_format(line[3:].strip())}</h2>")
            i += 1
            continue

        if line.startswith("### "):
            flush_paragraph(para_buf)
            flush_list()
            html_parts.append(f"<h3>{inline_format(line[4:].strip())}</h3>")
            i += 1
            continue

        if line.lstrip().startswith("- "):
            flush_paragraph(para_buf)
            list_buf.append(line.lstrip()[2:].strip())
            i += 1
            continue

        if re.match(r"^\d+\.\s", line.lstrip()):
            flush_paragraph(para_buf)
            flush_list()
            html_parts.append(f"<p>{inline_format(line.strip())}</p>")
            i += 1
            continue

        para_buf.append(line)
        i += 1

    flush_paragraph(para_buf)
    flush_list()
    return "\n".join(html_parts)


def post_body_html(post: dict) -> str:
    if post.get("body_html"):
        return post["body_html"]
    return markdown_to_html(post.get("body", ""))


def format_date_kr(date_str: str) -> str:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        weekdays = "월화수목금토일"
        return f"{d.year}년 {d.month}월 {d.day}일 ({weekdays[d.weekday()]})"
    except ValueError:
        return date_str


def nav_links(root: bool = False) -> str:
    p = "" if root else "../"
    return f"""<a href="{p}index.html">홈</a>
        <a href="{p}blog.html">블로그</a>
        <a href="{p}guide.html">가이드</a>
        <a href="{p}tips.html">팁</a>
        <a href="{p}faq.html">FAQ</a>"""


def render_post_page(post: dict, meta: dict) -> str:
    site = meta.get("site_name", "직장인 재충전소")
    slug = meta.get("site_slug", "site-004")
    keywords = meta.get("keywords", "")
    title = post["title"]
    desc = post.get("description", post.get("lead", ""))
    date = post.get("date", "")
    lead = post.get("lead", "")
    crumb = post.get("breadcrumb", title)
    body = post_body_html(post)
    pid = post["id"]

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)} — {escape(site)}</title>
  <meta name="description" content="{escape(desc)}" />
  <meta name="keywords" content="{escape(keywords)}" />
  <meta property="og:type" content="article" />
  <meta property="article:published_time" content="{escape(date)}" />
  <link rel="stylesheet" href="../styles.css" />
</head>
<body>
  <a class="skip-link" href="#main">본문으로 건너뛰기</a>
  <div class="page">
    <header class="topbar topbar--inner">
      <a class="logo" href="../index.html"><span class="logo-b">재</span><span class="logo-g">충</span><span class="logo-e">전</span><span class="logo-rest">소</span></a>
      <button type="button" class="menu-btn" aria-expanded="false" aria-controls="topnav">메뉴</button>
      <nav class="topbar-nav" id="topnav" aria-label="주요 메뉴">
        {nav_links(root=False)}
      </nav>
    </header>
    <main id="main" class="content-area">
      <nav class="breadcrumb"><a href="../index.html">홈</a> › <a href="../blog.html">블로그</a> › {escape(crumb)}</nav>
      <p class="results-meta" style="margin-bottom:0.5rem;">{escape(format_date_kr(date))}</p>
      <h1 class="page-title">{escape(title)}</h1>
      <p class="page-lead">{escape(lead)}</p>
      <article class="article">
        {body}
      </article>
    </main>
    <footer class="site-footer"><div class="footer-inner"><p class="footer-copy">© {escape(site)} · {escape(slug)} · Render</p></div></footer>
  </div>
  <script src="../js/main.js"></script>
</body>
</html>
"""


def render_blog_list(posts: list[dict], meta: dict) -> str:
    site = meta.get("site_name", "직장인 재충전소")
    slug = meta.get("site_slug", "site-004")
    keywords = meta.get("keywords", "")
    base = meta.get("base_url", "")

    cards = []
    for post in posts:
        pid = post["id"]
        title = escape(post["title"])
        lead = escape(post.get("lead", ""))
        date = escape(post.get("date", ""))
        cards.append(f"""
        <article class="result-card" data-searchable="{escape(post.get('title','') + ' ' + post.get('lead',''))}">
          <div class="result-url"><span class="result-favicon">재</span> {escape(base.replace('https://',''))} › blog › {escape(pid)}</div>
          <h2><a href="blog/{escape(pid)}.html">{title}</a></h2>
          <p>{lead}</p>
          <span class="result-tag">{date}</span>
        </article>""")

    cards_html = "\n".join(cards)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>블로그 — {escape(site)}</title>
  <meta name="description" content="직장인 피로·야근·스트레스·번아웃 웰니스 블로그 글 모음." />
  <meta name="keywords" content="{escape(keywords)}" />
  <link rel="stylesheet" href="styles.css" />
</head>
<body>
  <a class="skip-link" href="#main">본문으로 건너뛰기</a>
  <div class="page">
    <header class="topbar topbar--inner">
      <a class="logo" href="index.html"><span class="logo-b">재</span><span class="logo-g">충</span><span class="logo-e">전</span><span class="logo-rest">소</span></a>
      <button type="button" class="menu-btn" aria-expanded="false" aria-controls="topnav">메뉴</button>
      <nav class="topbar-nav" id="topnav" aria-label="주요 메뉴">
        <a href="index.html">홈</a>
        <a href="blog.html" aria-current="page">블로그</a>
        <a href="guide.html">가이드</a>
        <a href="tips.html">팁</a>
        <a href="faq.html">FAQ</a>
        <a href="blog-write.html">글쓰기</a>
      </nav>
    </header>
    <main id="main" class="content-area">
      <nav class="breadcrumb"><a href="index.html">홈</a> › 블로그</nav>
      <h1 class="page-title">블로그</h1>
      <p class="page-lead">야근·스트레스·번아웃·마사지·웰니스 이야기. 직장인 재충전을 위한 글 모음입니다.</p>
      <p class="results-meta" data-results-meta>총 {len(posts)}개 글</p>
      {cards_html}
    </main>
    <footer class="site-footer">
      <div class="footer-inner">
        <nav class="footer-links" aria-label="푸터 메뉴">
          <a href="blog-write.html">글쓰기</a>
          <a href="guide.html">가이드</a>
          <a href="tips.html">팁</a>
          <a href="faq.html">FAQ</a>
        </nav>
        <p class="footer-copy">© {escape(site)} · {escape(slug)} · Render</p>
      </div>
    </footer>
  </div>
  <script src="js/main.js"></script>
</body>
</html>
"""


def render_sitemap(posts: list[dict], meta: dict) -> str:
    base = meta.get("base_url", "").rstrip("/")
    static_pages = [
        ("/", "weekly", "1.0", None),
        ("/blog.html", "weekly", "0.9", None),
        ("/blog-write.html", "monthly", "0.3", None),
        ("/guide.html", "monthly", "0.9", None),
        ("/tips.html", "monthly", "0.8", None),
        ("/faq.html", "monthly", "0.8", None),
    ]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, freq, pri, lastmod in static_pages:
        loc = f"{base}{path}"
        lm = f"\n  <lastmod>{lastmod}</lastmod>" if lastmod else ""
        lines.append(f"  <url><loc>{loc}</loc><changefreq>{freq}</changefreq><priority>{pri}</priority>{lm}</url>")
    for post in posts:
        pid = post["id"]
        date = post.get("date", "")
        loc = f"{base}/blog/{pid}.html"
        lines.append(
            f'  <url><loc>{loc}</loc><lastmod>{date}</lastmod><changefreq>monthly</changefreq><priority>0.7</priority></url>'
        )
    lines.append("</urlset>\n")
    return "\n".join(lines)


def merge_draft(data: dict, draft: dict) -> dict:
    post = dict(draft)
    if not post.get("id"):
        post["id"] = slugify(post.get("title", "post"))
    if not post.get("description"):
        post["description"] = (post.get("lead") or "")[:160]
    if not post.get("breadcrumb"):
        post["breadcrumb"] = post.get("title", post["id"])

    posts = data.get("posts", [])
    idx = next((i for i, p in enumerate(posts) if p.get("id") == post["id"]), None)
    if idx is not None:
        posts[idx] = {**posts[idx], **post}
        print(f"  업데이트: {post['id']}")
    else:
        posts.insert(0, post)
        print(f"  추가: {post['id']}")

    data["posts"] = posts
    return data


def publish_all(data: dict) -> None:
    posts = sorted(data.get("posts", []), key=lambda p: p.get("date", ""), reverse=True)
    meta = data

    BLOG_DIR.mkdir(parents=True, exist_ok=True)
    valid_ids = {p["id"] for p in posts}

    for path in BLOG_DIR.glob("*.html"):
        if path.stem not in valid_ids:
            path.unlink()
            print(f"  삭제: {path.name}")

    for post in posts:
        out = BLOG_DIR / f"{post['id']}.html"
        out.write_text(render_post_page(post, meta), encoding="utf-8")
        print(f"  생성: blog/{out.name}")

    (ROOT / "blog.html").write_text(render_blog_list(posts, meta), encoding="utf-8")
    print("  생성: blog.html")

    (ROOT / "sitemap.xml").write_text(render_sitemap(posts, meta), encoding="utf-8")
    print("  생성: sitemap.xml")


def main() -> int:
    parser = argparse.ArgumentParser(description="블로그 draft 병합 및 HTML 생성")
    parser.add_argument("--add", action="store_true", help="blog-draft.json 병합 후 게시")
    parser.add_argument("--rebuild", action="store_true", help="blog-posts.json만으로 재생성")
    parser.add_argument("--draft", type=str, help="draft JSON 경로 (기본: Downloads/blog-draft.json)")
    args = parser.parse_args()

    if not DATA_FILE.exists():
        print(f"오류: {DATA_FILE} 없음", file=sys.stderr)
        return 1

    data = load_json(DATA_FILE)

    if args.add:
        draft_path = Path(args.draft) if args.draft else find_draft_in_downloads()
        if not draft_path or not draft_path.exists():
            print("오류: blog-draft.json을 찾을 수 없습니다.", file=sys.stderr)
            print(f"  예상 위치: {Path.home() / 'Downloads' / DRAFT_NAME}", file=sys.stderr)
            return 1
        print(f"draft 로드: {draft_path}")
        draft = load_json(draft_path)
        if "post" in draft and isinstance(draft["post"], dict):
            draft = draft["post"]
        data = merge_draft(data, draft)
        save_json(DATA_FILE, data)

    if not args.add and not args.rebuild:
        parser.print_help()
        return 0

    print("게시 파일 생성 중...")
    publish_all(data)
    print("완료.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
