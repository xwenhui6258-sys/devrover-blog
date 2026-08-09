#!/usr/bin/env python3
"""Validate DevRover canonical metadata, discovery links, and sitemap coverage."""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


SITE_URL = "https://7hui.top"
STATIC_PAGES = {
    "/": "index.html",
    "/blog/": "blog/index.html",
    "/tools/": "tools/index.html",
    "/tools/json/": "tools/json/index.html",
    "/tools/timestamp/": "tools/timestamp/index.html",
    "/about/": "about/index.html",
    "/contact/": "contact/index.html",
    "/editorial-policy/": "editorial-policy/index.html",
    "/privacy/": "privacy/index.html",
    "/disclaimer/": "disclaimer/index.html",
    "/terms/": "terms/index.html",
}
REQUIRED_FOOTER_LINKS = (
    "/about/",
    "/contact/",
    "/editorial-policy/",
    "/privacy/",
    "/disclaimer/",
    "/terms/",
)
ADSENSE_LOADER = "pagead2.googlesyndication.com/pagead/js/adsbygoogle.js"
ADSENSE_STATIC_PAGES = {"/", "/blog/"}


def canonical_from_html(text: str) -> str:
    match = re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"', text)
    return match.group(1) if match else ""


def json_ld_payloads(text: str) -> list[dict]:
    payloads: list[dict] = []
    for raw in re.findall(
        r'<script\b[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        text,
        flags=re.DOTALL | re.IGNORECASE,
    ):
        payloads.append(json.loads(raw))
    return payloads


def graph_types(payloads: list[dict]) -> set[str]:
    types: set[str] = set()
    for payload in payloads:
        nodes = payload.get("@graph") if isinstance(payload, dict) else None
        if not isinstance(nodes, list):
            nodes = [payload]
        for node in nodes:
            if isinstance(node, dict):
                node_type = node.get("@type")
                if isinstance(node_type, str):
                    types.add(node_type)
    return types


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--site-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    args = parser.parse_args()
    root = args.site_root.resolve()
    posts = json.loads((root / "blog" / "posts.json").read_text(encoding="utf-8"))
    errors: list[str] = []

    slugs = [str(post.get("slug") or "") for post in posts]
    urls = [str(post.get("url") or "") for post in posts]
    if len(slugs) != len(set(slugs)):
        errors.append("posts.json contains duplicate slugs")
    if len(urls) != len(set(urls)):
        errors.append("posts.json contains duplicate URLs")

    expected_urls = {SITE_URL + path for path in STATIC_PAGES}
    expected_urls.update(SITE_URL + url for url in urls)
    try:
        sitemap_root = ET.parse(root / "sitemap.xml").getroot()
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        sitemap_urls = {
            str(node.text or "")
            for node in sitemap_root.findall("sm:url/sm:loc", namespace)
        }
        if sitemap_urls != expected_urls:
            errors.append(
                "sitemap URL mismatch: "
                f"missing={sorted(expected_urls - sitemap_urls)} "
                f"extra={sorted(sitemap_urls - expected_urls)}"
            )
    except (OSError, ET.ParseError) as exc:
        errors.append(f"invalid sitemap.xml: {exc}")

    robots = (root / "robots.txt").read_text(encoding="utf-8")
    if "Sitemap: https://7hui.top/sitemap.xml" not in robots:
        errors.append("robots.txt does not advertise the sitemap")

    for path, relative_file in STATIC_PAGES.items():
        page = root / relative_file
        text = page.read_text(encoding="utf-8")
        expected_canonical = SITE_URL + path
        if canonical_from_html(text) != expected_canonical:
            errors.append(f"{relative_file}: canonical mismatch")
        if '<meta property="og:title"' not in text:
            errors.append(f"{relative_file}: missing Open Graph title")
        if '<meta name="twitter:card"' not in text:
            errors.append(f"{relative_file}: missing Twitter card")
        for footer_path in REQUIRED_FOOTER_LINKS:
            if f'href="{footer_path}"' not in text:
                errors.append(f"{relative_file}: missing footer link {footer_path}")
        loader_count = text.count(ADSENSE_LOADER)
        expected_loaders = 1 if path in ADSENSE_STATIC_PAGES else 0
        if loader_count != expected_loaders:
            errors.append(
                f"{relative_file}: expected {expected_loaders} AdSense loaders, "
                f"found {loader_count}"
            )

    blog_index = (root / "blog" / "index.html").read_text(encoding="utf-8")
    for marker in (
        'id="blogSearch"',
        'id="secondaryFiltersToggle"',
        'id="loadMorePosts"',
        'id="blog-jsonld"',
    ):
        if marker not in blog_index:
            errors.append(f"blog/index.html: missing {marker}")

    for post in posts:
        slug = str(post["slug"])
        url = str(post["url"])
        page = root / "blog" / slug / "index.html"
        if not page.is_file():
            errors.append(f"{slug}: missing index.html")
            continue
        text = page.read_text(encoding="utf-8")
        if canonical_from_html(text) != SITE_URL + url:
            errors.append(f"{slug}: canonical mismatch")
        try:
            types = graph_types(json_ld_payloads(text))
        except json.JSONDecodeError as exc:
            errors.append(f"{slug}: invalid JSON-LD: {exc}")
            types = set()
        if not {"BlogPosting", "BreadcrumbList"}.issubset(types):
            errors.append(f"{slug}: incomplete article JSON-LD types={sorted(types)}")
        if 'class="breadcrumbs"' not in text:
            errors.append(f"{slug}: missing breadcrumbs")
        if 'class="article-taxonomy"' not in text:
            errors.append(f"{slug}: missing article taxonomy")
        if "<time " not in text:
            errors.append(f"{slug}: missing semantic time")
        if 'class="article-byline"' not in text:
            errors.append(f"{slug}: missing visible author byline")
        if 'class="article-author-note"' not in text:
            errors.append(f"{slug}: missing author and verification note")
        for footer_path in REQUIRED_FOOTER_LINKS:
            if f'href="{footer_path}"' not in text:
                errors.append(f"{slug}: missing footer link {footer_path}")
        discovery_match = re.search(
            r'<section class="article-discovery".*?</section>',
            text,
            flags=re.DOTALL,
        )
        if not discovery_match:
            errors.append(f"{slug}: missing article discovery section")
            continue
        discovery = discovery_match.group(0)
        if discovery.count('class="related-card"') != 3:
            errors.append(f"{slug}: related article count is not 3")
        if f'href="{url}"' in discovery:
            errors.append(f"{slug}: discovery section links to itself")
        if "/Users/" in text or "file://" in text:
            errors.append(f"{slug}: contains a local absolute path")

    if errors:
        for error in errors:
            print(f"FAIL {error}")
        return 1
    print(
        f"PASS static_pages={len(STATIC_PAGES)} articles={len(posts)} "
        f"sitemap_urls={len(expected_urls)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
