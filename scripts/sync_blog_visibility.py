#!/usr/bin/env python3
"""Synchronize public blog/posts.json with the content visibility manifest.

The site keeps source folders for hidden, redirected, and retired articles so they
can be repaired and restored later. Only public posts belong in posts.json,
the blog list, and the sitemap.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from publish_blog_post import parse_front_matter, parse_front_matter_tags, plain_summary


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def status_sets(status: dict) -> tuple[set[str], dict[str, str], set[str]]:
    hidden = {str(slug) for slug in status.get("hiddenSlugs", [])}
    redirects = {
        str(slug): str(target)
        for slug, target in dict(status.get("redirects", {})).items()
    }
    retired = {str(slug) for slug in status.get("retiredSlugs", [])}
    overlap = (hidden & set(redirects)) | (hidden & retired) | (set(redirects) & retired)
    if overlap:
        raise ValueError(f"content status has overlapping slugs: {sorted(overlap)}")
    return hidden, redirects, retired


def record_from_source(root: Path, slug: str, override: dict) -> dict:
    source = root / "blog" / slug / "source.md"
    if not source.is_file():
        raise FileNotFoundError(f"public addition is missing source.md: {source}")
    text = source.read_text(encoding="utf-8")
    front, raw_front, body = parse_front_matter(text)
    title = str(front.get("title") or "").strip()
    post_date = str(front.get("date") or "").strip()
    category = str(front.get("category") or "").strip()
    series = str(front.get("series") or "").strip()
    tags = parse_front_matter_tags(raw_front)
    if not title or not post_date or not category or not series or not tags:
        raise ValueError(f"public addition has incomplete front matter: {source}")
    summary = str(front.get("summary") or front.get("description") or plain_summary(body)).strip()
    reading_time = str(override.get("readingTime") or "").strip()
    if not summary or not reading_time:
        raise ValueError(f"public addition is missing summary or readingTime: {slug}")
    return {
        "title": title,
        "slug": slug,
        "url": f"/blog/{slug}/",
        "date": post_date,
        "updated": str(front.get("updated") or post_date).strip(),
        "category": category,
        "series": series,
        "tags": tags,
        "summary": summary,
        "readingTime": reading_time,
    }


def expected_posts(root: Path) -> list[dict]:
    posts_path = root / "blog" / "posts.json"
    status_path = root / "blog" / "content-status.json"
    posts = read_json(posts_path)
    status = read_json(status_path)
    if not isinstance(posts, list) or not isinstance(status, dict):
        raise ValueError("posts.json must be a list and content-status.json must be an object")
    hidden, redirects, retired = status_sets(status)
    excluded = hidden | set(redirects) | retired
    result: dict[str, dict] = {}
    for post in posts:
        if not isinstance(post, dict):
            raise ValueError("posts.json contains a non-object record")
        slug = str(post.get("slug") or "")
        if not slug:
            raise ValueError("posts.json contains a record without slug")
        if slug in excluded:
            continue
        if slug in result:
            raise ValueError(f"posts.json contains duplicate slug: {slug}")
        result[slug] = post

    additions = status.get("publicAdditions", {})
    if not isinstance(additions, dict):
        raise ValueError("publicAdditions must be an object")
    for slug, override in additions.items():
        slug = str(slug)
        if slug in excluded:
            raise ValueError(f"public addition is also non-public: {slug}")
        if not isinstance(override, dict):
            raise ValueError(f"public addition override must be an object: {slug}")
        result[slug] = record_from_source(root, slug, override)

    source_slugs = {
        source.parent.name
        for source in (root / "blog").glob("*/source.md")
    }
    unclassified = source_slugs - set(result) - excluded
    if unclassified:
        raise ValueError(
            "source articles are neither public nor assigned a non-public status: "
            f"{sorted(unclassified)}"
        )

    overrides = status.get("publicOverrides", {})
    if not isinstance(overrides, dict):
        raise ValueError("publicOverrides must be an object")
    allowed_override_fields = {
        "title", "date", "updated", "category", "series", "tags", "summary", "readingTime", "url",
    }
    for slug, override in overrides.items():
        slug = str(slug)
        if slug not in result:
            raise ValueError(f"public override does not target a public post: {slug}")
        if not isinstance(override, dict):
            raise ValueError(f"public override must be an object: {slug}")
        unknown = sorted(set(override) - allowed_override_fields)
        if unknown:
            raise ValueError(f"public override has unsupported fields for {slug}: {unknown}")
        result[slug] = {**result[slug], **override}

    return sorted(
        result.values(),
        key=lambda post: str(post.get("updated") or post.get("date") or ""),
        reverse=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--site-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.site_root.resolve()
    posts_path = root / "blog" / "posts.json"
    try:
        expected = expected_posts(root)
        current = read_json(posts_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    if current == expected:
        print(f"PASS public posts synchronized count={len(expected)}")
        return 0
    if args.check:
        print("FAIL blog/posts.json is not synchronized with content-status.json", file=sys.stderr)
        return 1
    posts_path.write_text(
        json.dumps(expected, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"PASS synchronized public posts count={len(expected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
