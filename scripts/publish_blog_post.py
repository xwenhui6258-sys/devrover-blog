#!/usr/bin/env python3
"""Publish a Markdown article directory into the static blog."""

from __future__ import annotations

import argparse
import html
import re
import shutil
import sys
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import quote


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".svg"}


@dataclass
class PostMeta:
    title: str
    date: str
    summary: str
    slug: str


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return slug or f"post-{date.today().isoformat()}"


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    raw = text[4:end].strip()
    body = text[end + 4 :].lstrip("\n")
    meta: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip().lower()] = value.strip().strip("'\"")
    return meta, body


def first_heading(body: str) -> str | None:
    match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    return match.group(1).strip() if match else None


def remove_duplicate_title(body: str, title: str) -> str:
    pattern = re.compile(r"^#\s+" + re.escape(title) + r"\s*\n+", re.MULTILINE)
    return pattern.sub("", body, count=1)


def plain_summary(body: str) -> str:
    clean = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    clean = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", clean)
    clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean)
    clean = re.sub(r"^[#>\-\*\d.\s]+", "", clean, flags=re.MULTILINE)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:120] + ("..." if len(clean) > 120 else "")


def choose_markdown(input_dir: Path, explicit: str | None) -> Path:
    if explicit:
        md = Path(explicit).expanduser()
        if not md.is_absolute():
            md = input_dir / md
        return md
    candidates = sorted(input_dir.glob("*.md"))
    if len(candidates) != 1:
        raise SystemExit(f"Expected exactly one .md file in {input_dir}, found {len(candidates)}.")
    return candidates[0]


def find_asset(input_dir: Path, target: str) -> Path | None:
    source = (input_dir / target).resolve()
    if source.exists():
        return source
    by_name = input_dir / "images" / Path(target).name
    if by_name.exists():
        return by_name.resolve()
    matches = [path for path in input_dir.rglob(Path(target).name) if path.is_file()]
    return matches[0].resolve() if matches else None


def rewrite_asset_paths(markdown: str, input_dir: Path, post_dir: Path) -> str:
    assets_dir = post_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    def replace(match: re.Match[str]) -> str:
        alt = match.group(1)
        target = match.group(2).strip()
        if re.match(r"^(https?:)?//", target) or target.startswith("/"):
            return match.group(0)
        source = find_asset(input_dir, target)
        if source is None:
            return match.group(0)
        destination = assets_dir / source.name
        if source.is_file() and source.suffix.lower() in IMAGE_EXTS:
            shutil.copy2(source, destination)
            return f"![{alt}](assets/{quote(destination.name)})"
        return match.group(0)

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", replace, markdown)


def copy_remaining_images(input_dir: Path, post_dir: Path) -> None:
    assets_dir = post_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    for source in input_dir.rglob("*"):
        if source.is_file() and source.suffix.lower() in IMAGE_EXTS:
            shutil.copy2(source, assets_dir / source.name)


def inline_markdown(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1">', text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    paragraph: list[str] = []
    in_code = False
    code_lang = ""
    code_lines: list[str] = []
    in_list = False
    in_quote = False
    table_lines: list[str] = []

    def close_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            output.append(f"<p>{inline_markdown(' '.join(paragraph))}</p>")
            paragraph = []

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            output.append("</ul>")
            in_list = False

    def close_quote() -> None:
        nonlocal in_quote
        if in_quote:
            output.append("</blockquote>")
            in_quote = False

    def is_table_divider(value: str) -> bool:
        cells = [cell.strip() for cell in value.strip().strip("|").split("|")]
        return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)

    def close_table() -> None:
        nonlocal table_lines
        if not table_lines:
            return
        rows = [[cell.strip() for cell in row.strip().strip("|").split("|")] for row in table_lines]
        if len(rows) >= 2 and is_table_divider(table_lines[1]):
            header = rows[0]
            body_rows = rows[2:]
            output.append("<div class=\"table-wrap\"><table>")
            output.append("<thead><tr>" + "".join(f"<th>{inline_markdown(cell)}</th>" for cell in header) + "</tr></thead>")
            output.append("<tbody>")
            for row in body_rows:
                output.append("<tr>" + "".join(f"<td>{inline_markdown(cell)}</td>" for cell in row) + "</tr>")
            output.append("</tbody></table></div>")
        else:
            for row in table_lines:
                output.append(f"<p>{inline_markdown(row)}</p>")
        table_lines = []

    for raw in lines:
        line = raw.rstrip()
        fence = re.match(r"^```(\w+)?\s*$", line)
        if fence:
            if in_code:
                output.append(
                    f'<pre><code class="language-{html.escape(code_lang)}">'
                    + html.escape("\n".join(code_lines))
                    + "</code></pre>"
                )
                in_code = False
                code_lines = []
                code_lang = ""
            else:
                close_paragraph()
                close_list()
                close_quote()
                in_code = True
                code_lang = fence.group(1) or ""
            continue
        if in_code:
            code_lines.append(raw)
            continue

        if not line.strip():
            close_table()
            close_paragraph()
            close_list()
            close_quote()
            continue

        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", line.strip()):
            close_table()
            close_paragraph()
            close_list()
            close_quote()
            output.append("<hr>")
            continue

        heading = re.match(r"^(#{1,4})\s+(.+)$", line)
        if heading:
            close_table()
            close_paragraph()
            close_list()
            close_quote()
            level = len(heading.group(1))
            output.append(f"<h{level}>{inline_markdown(heading.group(2))}</h{level}>")
            continue

        image = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", line)
        if image:
            close_table()
            close_paragraph()
            close_list()
            close_quote()
            output.append(f'<figure><img src="{html.escape(image.group(2))}" alt="{html.escape(image.group(1))}"><figcaption>{html.escape(image.group(1))}</figcaption></figure>')
            continue

        bullet = re.match(r"^[-*]\s+(.+)$", line)
        if bullet:
            close_table()
            close_paragraph()
            close_quote()
            if not in_list:
                output.append("<ul>")
                in_list = True
            output.append(f"<li>{inline_markdown(bullet.group(1))}</li>")
            continue

        quote_match = re.match(r"^>\s?(.+)$", line)
        if quote_match:
            close_table()
            close_paragraph()
            close_list()
            if not in_quote:
                output.append("<blockquote>")
                in_quote = True
            output.append(f"<p>{inline_markdown(quote_match.group(1))}</p>")
            continue

        if "|" in line and line.strip().startswith("|"):
            close_paragraph()
            close_list()
            close_quote()
            table_lines.append(line)
            continue

        close_table()
        paragraph.append(line)

    close_table()
    close_paragraph()
    close_list()
    close_quote()
    return "\n".join(output)


def heading_text(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value)).strip()


def add_heading_ids_and_toc(article_html: str) -> tuple[str, str]:
    used: set[str] = set()
    items: list[tuple[int, str, str]] = []
    counter = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal counter
        level = int(match.group(1))
        content = match.group(2)
        if level not in {2, 3}:
            return match.group(0)
        counter += 1
        base = f"section-{counter}"
        anchor = base
        suffix = 2
        while anchor in used:
            anchor = f"{base}-{suffix}"
            suffix += 1
        used.add(anchor)
        items.append((level, anchor, heading_text(content)))
        return f'<h{level} id="{anchor}">{content}</h{level}>'

    article_html = re.sub(r"<h([1-4])>(.*?)</h\1>", replace, article_html, flags=re.DOTALL)
    if not items:
        return article_html, ""

    links = "\n".join(
        f'      <a class="toc-level-{level}" href="#{anchor}">{html.escape(text)}</a>'
        for level, anchor, text in items
    )
    toc_html = f"""<aside class="article-toc" aria-label="文章目录">
    <div class="toc-title">目录</div>
    <nav>
{links}
    </nav>
  </aside>"""
    return article_html, toc_html


def render_page(meta: PostMeta, article_html: str) -> str:
    article_html, toc_html = add_heading_ids_and_toc(article_html)
    title_main = meta.title
    title_subtitle = ""
    if "全流程：" in meta.title:
        title_main, tail = meta.title.split("全流程：", 1)
        title_main = title_main.strip()
        title_subtitle = "全流程：" + tail.strip()
    title_html = f"<h1>{html.escape(title_main)}</h1>"
    if title_subtitle:
        title_html += f'\n      <p class="article-subtitle">{html.escape(title_subtitle)}</p>'
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="description" content="{html.escape(meta.summary)}">
  <title>{html.escape(meta.title)}｜DevRover的个人站</title>
  <link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon-32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="/assets/favicon-16.png">
  <link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
  <link rel="stylesheet" href="/assets/style.css?v=20260713-article-toc-2">
</head>
<body>
<header>
  <div class="container nav">
    <a class="brand" href="/"><img class="brand-icon" src="/assets/devrover-icon.png" alt="" aria-hidden="true">DevRover的个人站</a>
    <nav>
      <a href="/blog/">博客</a>
      <a href="/tools/">工具</a>
      <a href="/about/">关于</a>
    </nav>
  </div>
</header>

<main class="article-page">
  <div class="article-layout">
    <article class="article">
      {title_html}
      <p class="article-meta">{html.escape(meta.date)}</p>
      {article_html}
    </article>
    {toc_html}
  </div>
</main>
<footer>
  <div class="container">© 2026 DevRover的个人站 · 纯静态部署</div>
</footer>
<button class="back-to-top" type="button" aria-label="回到顶部" title="回到顶部"><span>↑</span><strong>顶部</strong></button>
<script>
  const backToTop = document.querySelector('.back-to-top');
  const toggleBackToTop = () => {{
    backToTop.classList.toggle('visible', window.scrollY > 420);
  }};
  window.addEventListener('scroll', toggleBackToTop, {{ passive: true }});
  backToTop.addEventListener('click', () => window.scrollTo({{ top: 0, behavior: 'smooth' }}));
  toggleBackToTop();
</script>
</body>
</html>
"""


def update_blog_index(blog_root: Path, meta: PostMeta) -> None:
    index = blog_root / "index.html"
    text = index.read_text(encoding="utf-8")
    item = f'    <a class="item" href="/blog/{html.escape(meta.slug)}/"><strong>{html.escape(meta.title)}</strong><br><small>{html.escape(meta.date)} · {html.escape(meta.summary)}</small></a>'
    pattern = re.compile(r'    <a class="item" href="/blog/' + re.escape(meta.slug) + r'/".*?</a>\n?', re.DOTALL)
    text = pattern.sub("", text)
    text = text.replace('    <a class="item" href="#"><strong>第一篇文章：网站正式上线</strong><br><small>2026-07-05 · 示例文章</small></a>\n', "")
    text = text.replace('  <div class="list">\n', f'  <div class="list">\n{item}\n', 1)
    index.write_text(text, encoding="utf-8")


def make_public(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        path.chmod(0o755)
        for child in path.iterdir():
            make_public(child)
    else:
        path.chmod(0o644)


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish a Markdown article directory.")
    parser.add_argument("input_dir", help="Directory containing one Markdown file and related images.")
    parser.add_argument("--markdown", help="Markdown file name or path. Defaults to the only .md in input_dir.")
    parser.add_argument("--slug", help="URL slug. Defaults to front matter slug or title.")
    parser.add_argument("--site-root", default=str(Path(__file__).resolve().parents[1]), help="Static site root. Defaults to the repository root containing this script.")
    args = parser.parse_args()

    site_root = Path(args.site_root).expanduser().resolve()
    blog_root = site_root / "blog"
    input_dir = Path(args.input_dir).expanduser().resolve()
    if not input_dir.exists():
        raise SystemExit(f"Input directory does not exist: {input_dir}")
    markdown_path = choose_markdown(input_dir, args.markdown)
    if not markdown_path.exists():
        raise SystemExit(f"Markdown file does not exist: {markdown_path}")

    source_text = markdown_path.read_text(encoding="utf-8")
    front_matter, body = parse_front_matter(source_text)
    title = front_matter.get("title") or first_heading(body) or markdown_path.stem
    post_date = front_matter.get("date") or date.today().isoformat()
    summary = front_matter.get("summary") or front_matter.get("description") or plain_summary(body)
    slug = args.slug or front_matter.get("slug") or slugify(title)

    post_dir = blog_root / slug
    post_dir.mkdir(parents=True, exist_ok=True)
    body = remove_duplicate_title(body, title)
    rewritten_body = rewrite_asset_paths(body, input_dir, post_dir)
    copy_remaining_images(input_dir, post_dir)
    (post_dir / "source.md").write_text("---\n" + "\n".join(f"{k}: {v}" for k, v in front_matter.items()) + "\n---\n\n" + rewritten_body, encoding="utf-8")

    meta = PostMeta(title=title, date=post_date, summary=summary, slug=slug)
    (post_dir / "index.html").write_text(render_page(meta, markdown_to_html(rewritten_body)), encoding="utf-8")
    update_blog_index(blog_root, meta)
    make_public(post_dir)
    make_public(blog_root / "index.html")
    print(f"Published /blog/{slug}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
