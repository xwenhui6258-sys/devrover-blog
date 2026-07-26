#!/usr/bin/env python3
"""Rebuild every blog article page from source.md and posts.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from publish_blog_post import (
    PostMeta,
    make_public,
    markdown_to_html,
    optimize_article_images,
    parse_front_matter,
    remove_duplicate_title,
    render_page,
)


def meta_from_post(post: dict) -> PostMeta:
    return PostMeta(
        title=str(post["title"]),
        date=str(post["date"]),
        summary=str(post.get("summary") or ""),
        slug=str(post["slug"]),
        updated=str(post.get("updated") or post["date"]),
        category=str(post.get("category") or ""),
        series=str(post.get("series") or ""),
        tags=tuple(str(tag) for tag in post.get("tags") or []),
        reading_time=str(post.get("readingTime") or ""),
        url=str(post.get("url") or f'/blog/{post["slug"]}/'),
    )


def expected_page(root: Path, post: dict, posts: list[dict]) -> tuple[Path, str]:
    meta = meta_from_post(post)
    post_dir = root / "blog" / meta.slug
    source_path = post_dir / "source.md"
    if not source_path.is_file():
        raise FileNotFoundError(f"missing source.md: {source_path}")
    source_text = source_path.read_text(encoding="utf-8")
    front_matter, _, body = parse_front_matter(source_text)
    source_title = front_matter.get("title")
    if source_title:
        meta.title = source_title
    body = remove_duplicate_title(body, meta.title)
    article_html = optimize_article_images(markdown_to_html(body), post_dir)
    return post_dir / "index.html", render_page(meta, article_html, posts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--site-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--slug",
        action="append",
        default=[],
        help="Rebuild only this slug. Repeat for more than one article.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when a generated article page is stale.",
    )
    args = parser.parse_args()

    root = args.site_root.resolve()
    posts = json.loads((root / "blog" / "posts.json").read_text(encoding="utf-8"))
    requested = set(args.slug)
    selected = [post for post in posts if not requested or post.get("slug") in requested]
    missing = requested - {str(post.get("slug")) for post in selected}
    if missing:
        print(f"FAIL unknown slugs: {sorted(missing)}", file=sys.stderr)
        return 2

    changed = 0
    errors: list[str] = []
    for post in selected:
        try:
            page_path, expected = expected_page(root, post, posts)
        except (FileNotFoundError, ValueError) as exc:
            errors.append(str(exc))
            continue
        current = page_path.read_text(encoding="utf-8") if page_path.is_file() else ""
        if current == expected:
            continue
        changed += 1
        if args.check:
            errors.append(f"stale article page: {page_path}")
            continue
        page_path.write_text(expected, encoding="utf-8")
        make_public(page_path)

    if errors:
        for error in errors:
            print(f"FAIL {error}", file=sys.stderr)
        return 1
    action = "checked" if args.check else "rebuilt"
    print(f"PASS {action} articles={len(selected)} changed={changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
