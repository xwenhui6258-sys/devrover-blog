#!/usr/bin/env python3
"""Generate the canonical XML sitemap for 7hui.top."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path


SITE_URL = "https://7hui.top"
STATIC_PATHS = (
    "/",
    "/blog/",
    "/tools/",
    "/tools/json/",
    "/tools/timestamp/",
    "/about/",
    "/contact/",
    "/editorial-policy/",
    "/privacy/",
    "/disclaimer/",
    "/terms/",
)


def render_url(path: str, lastmod: str = "") -> str:
    lastmod_xml = f"\n    <lastmod>{html.escape(lastmod)}</lastmod>" if lastmod else ""
    return (
        "  <url>\n"
        f"    <loc>{html.escape(SITE_URL + path)}</loc>{lastmod_xml}\n"
        "  </url>"
    )


def render_sitemap(posts: list[dict]) -> str:
    latest = max(
        (str(post.get("updated") or post.get("date") or "") for post in posts),
        default="",
    )
    entries = [
        render_url(path, latest if path == "/blog/" else "")
        for path in STATIC_PATHS
    ]
    entries.extend(
        render_url(
            str(post.get("url") or f'/blog/{post["slug"]}/'),
            str(post.get("updated") or post.get("date") or ""),
        )
        for post in posts
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + "\n</urlset>\n"
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
    posts = json.loads((root / "blog" / "posts.json").read_text(encoding="utf-8"))
    expected = render_sitemap(posts)
    sitemap_path = root / "sitemap.xml"
    current = sitemap_path.read_text(encoding="utf-8") if sitemap_path.is_file() else ""
    if current == expected:
        print(f"PASS sitemap urls={len(STATIC_PATHS) + len(posts)}")
        return 0
    if args.check:
        print("FAIL sitemap.xml is stale", file=sys.stderr)
        return 1
    sitemap_path.write_text(expected, encoding="utf-8")
    sitemap_path.chmod(0o644)
    print(f"PASS generated sitemap urls={len(STATIC_PATHS) + len(posts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
