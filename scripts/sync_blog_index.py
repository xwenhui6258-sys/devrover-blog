#!/usr/bin/env python3
"""Synchronize the static blog index with posts.json and the tag taxonomy."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import quote_plus


CATEGORY_ORDER = ["跨境投资", "券商入金", "海外银行卡", "美股账户"]
CATEGORY_TONES = {
    "美股账户": "blue",
    "海外银行卡": "green",
    "券商入金": "gold",
    "跨境投资": "purple",
}
SERIES_INTRO = {
    "大陆用户海外券商开户": "嘉信、IBKR、W-8BEN、地址证明",
    "海外银行卡与资金流转": "Wise、实体卡、入金出金路径",
    "美股新手基础设施": "账户安全、数据源、税务基础",
    "海外资产入门": "模拟交易、账户类型、基础流程",
}


def link(path: str, label: str, filter_type: str, value: str, classes: str) -> str:
    class_attr = f' class="{classes}"' if classes else ""
    return (
        f'<a{class_attr} href="{path}" data-filter-type="{filter_type}" '
        f'data-filter-value="{html.escape(value, quote=True)}">{html.escape(label)}</a>'
    )


def category_url(category: str) -> str:
    return "/blog/" if category == "全部" else f"/blog/?category={quote_plus(category)}"


def tag_url(tag: str) -> str:
    return "/blog/" if tag == "全部" else f"/blog/?tag={quote_plus(tag)}"


def sorted_posts(posts: list[dict]) -> list[dict]:
    return sorted(posts, key=lambda post: str(post.get("updated") or post.get("date") or ""), reverse=True)


def render_post(post: dict) -> str:
    tone = CATEGORY_TONES.get(post.get("category"), "neutral")
    category = str(post.get("category", ""))
    tags = "".join(
        link(tag_url(tag), tag, "tag", tag, "") for tag in post.get("tags", [])
    )
    updated = str(post.get("updated") or post.get("date") or "").replace("-", ".")
    reading = html.escape(str(post.get("readingTime") or "5 分钟"))
    series = str(post.get("series") or "")
    series_suffix = f" · {html.escape(series)}" if series else ""
    url = str(post.get("url") or f'/blog/{post["slug"]}/')
    return f'''<article class="post-card">
      {link(category_url(category), category, "category", category, f"category-pill {tone}")}
      <h3><a href="{html.escape(url, quote=True)}">{html.escape(str(post["title"]))}</a></h3>
      <p>{html.escape(str(post.get("summary") or ""))}</p>
      <div class="post-meta">{updated} · {reading}读完{series_suffix}</div>
      <div class="post-tags">{tags}</div>
    </article>'''


def render_category_filters(posts: list[dict]) -> str:
    counts = Counter(post.get("category") for post in posts)
    categories = ["全部", *CATEGORY_ORDER]
    extras = sorted(set(counts) - set(CATEGORY_ORDER))
    categories.extend(extras)
    parts = []
    for category in categories:
        count = len(posts) if category == "全部" else counts[category]
        tone = "neutral" if category == "全部" else CATEGORY_TONES.get(category, "neutral")
        active = " active" if category == "全部" else ""
        label = (
            f'<span>{html.escape(category)}</span>'
            f'<span class="filter-count" aria-hidden="true">{count}</span>'
        )
        parts.append(
            f'<a class="filter-chip{active} {tone}" href="{category_url(category)}" '
            f'data-filter-type="category" data-filter-value="{html.escape(category, quote=True)}" '
            f'aria-label="{html.escape(category, quote=True)}，{count} 篇文章">{label}</a>'
        )
    return "".join(parts)


def render_hero_categories() -> str:
    return "".join(
        link(category_url(category), category, "category", category, f"mini-chip {CATEGORY_TONES[category]}")
        for category in CATEGORY_ORDER
    )


def render_tag_filters(tags: list[str]) -> str:
    values = ["全部", *tags]
    return "".join(
        link(tag_url(tag), tag, "tag", "" if tag == "全部" else tag, "filter-chip" + (" active" if tag == "全部" else ""))
        for tag in values
    )


def render_series(posts: list[dict]) -> str:
    counts = Counter(post.get("series") for post in posts if post.get("series"))
    order = list(dict.fromkeys(post.get("series") for post in posts if post.get("series")))
    cards = []
    for series in order:
        href = f"/blog/?series={quote_plus(series)}"
        cards.append(f'''<a class="series-card" href="{href}" data-filter-type="series" data-filter-value="{html.escape(series, quote=True)}" aria-current="false">
      <h3>{html.escape(series)}</h3>
      <p>{html.escape(SERIES_INTRO.get(series, "相关文章会自动归档到这个系列。"))}</p>
      <span>已发布 {counts[series]} 篇</span>
    </a>''')
    return "".join(cards)


def replace_one(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise SystemExit(f"could not replace {label}: matches={count}")
    return updated


def synchronize(index_text: str, posts: list[dict], taxonomy: dict) -> str:
    ordered = sorted_posts(posts)
    static_posts = "\n".join(render_post(post) for post in ordered)
    index_text = replace_one(
        index_text,
        r'(<div class="post-list" id="postList">).*?(</div>\n    </div>\n\n    <aside class="series-panel")',
        lambda match: match.group(1) + static_posts + match.group(2),
        "static post list",
    )
    index_text = replace_one(
        index_text,
        r'(<div class="filter-chips" id="categoryFilters">).*?(</div>)',
        lambda match: match.group(1) + render_category_filters(posts) + match.group(2),
        "category filters",
    )
    index_text = replace_one(
        index_text,
        r'(<div class="blog-guide-tags" id="heroCategories">).*?(</div>)',
        lambda match: match.group(1) + render_hero_categories() + match.group(2),
        "hero categories",
    )
    index_text = replace_one(
        index_text,
        r'(<div class="filter-chips tag-filter-chips" id="tagFilters">).*?(</div>)',
        lambda match: match.group(1) + render_tag_filters(taxonomy["tags"]) + match.group(2),
        "tag filters",
    )
    index_text = replace_one(
        index_text,
        r'(<div class="series-list" id="seriesList">).*?(</div>\n      <div class="meta-note">)',
        lambda match: match.group(1) + render_series(ordered) + match.group(2),
        "series list",
    )
    fallback = json.dumps(posts, ensure_ascii=False, indent=2)
    index_text = replace_one(
        index_text,
        r'const fallbackPosts = \[.*?\];\n\nconst canonicalTags',
        f"const fallbackPosts = {fallback};\n\nconst canonicalTags",
        "fallback posts",
    )
    canonical = json.dumps(taxonomy["tags"], ensure_ascii=False, indent=2)
    aliases = json.dumps(taxonomy.get("aliases", {}), ensure_ascii=False, indent=2, sort_keys=True)
    index_text = replace_one(
        index_text,
        r'const canonicalTags = \[.*?\];\nconst tagAliases = \{.*?\};',
        f"const canonicalTags = {canonical};\nconst tagAliases = {aliases};",
        "taxonomy constants",
    )
    return index_text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", action="store_true", help="Fail when blog/index.html is stale.")
    args = parser.parse_args()
    root = args.site_root.resolve()
    posts = json.loads((root / "blog" / "posts.json").read_text(encoding="utf-8"))
    taxonomy = json.loads((root / "blog" / "tag-taxonomy.json").read_text(encoding="utf-8"))
    index_path = root / "blog" / "index.html"
    current = index_path.read_text(encoding="utf-8")
    expected = synchronize(current, posts, taxonomy)
    if args.check:
        if current != expected:
            print("FAIL blog/index.html is not synchronized", file=sys.stderr)
            return 1
        print(f"PASS blog/index.html synchronized with {len(posts)} posts")
        return 0
    if current != expected:
        index_path.write_text(expected, encoding="utf-8")
        print(f"updated {index_path}")
    else:
        print(f"unchanged {index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
