#!/usr/bin/env python3
"""Check that internal publishing material cannot leak through public pages."""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urljoin


FORBIDDEN_PUBLIC_MARKERS = (
    "innomad-archive",
    "写作取材",
    "/Users/",
    "/private/tmp",
    "file://",
)
EXPECTED_ROBOTS_RULES = (
    "Disallow: /incoming/",
    "Disallow: /blog/*/source.md",
    "Disallow: /blog/content-status.json",
)


def fetch_status(url: str, timeout: float) -> int:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "devrover-public-boundary-check/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)


def check_static(root: Path, errors: list[str]) -> None:
    robots = root / "robots.txt"
    if not robots.is_file():
        errors.append("robots.txt is missing")
    else:
        robots_text = robots.read_text(encoding="utf-8")
        for rule in EXPECTED_ROBOTS_RULES:
            if rule not in robots_text:
                errors.append(f"robots.txt is missing {rule}")

    blog_root = root / "blog"
    for index_path in sorted(blog_root.glob("*/index.html")):
        index_text = index_path.read_text(encoding="utf-8")
        for marker in FORBIDDEN_PUBLIC_MARKERS:
            if marker in index_text:
                errors.append(f"{index_path.relative_to(root)} contains {marker!r}")
        if re.search(r"href=[\"'][^\"']*/source\.md(?:[?#\"'])", index_text):
            errors.append(f"{index_path.relative_to(root)} links to source.md")

    for source_path in sorted(blog_root.glob("*/source.md")):
        source_text = source_path.read_text(encoding="utf-8")
        for marker in FORBIDDEN_PUBLIC_MARKERS:
            if marker in source_text:
                errors.append(f"{source_path.relative_to(root)} contains {marker!r}")


def check_http(root: Path, base_url: str, timeout: float, errors: list[str]) -> None:
    base = base_url.rstrip("/") + "/"
    source_paths = sorted(root.glob("blog/*/source.md"))
    incoming_paths = sorted(root.glob("incoming/**/*.md"))
    targets = [
        ("source", "/" + path.relative_to(root).as_posix())
        for path in source_paths
    ]
    targets.extend(
        ("incoming", "/" + path.relative_to(root).as_posix())
        for path in incoming_paths
    )
    targets.append(("incoming-root", "/incoming/"))
    targets.append(("content-status", "/blog/content-status.json"))

    for kind, path in targets:
        url = urljoin(base, path.lstrip("/"))
        try:
            status = fetch_status(url, timeout)
        except (OSError, urllib.error.URLError) as exc:
            errors.append(f"{kind} {url}: request failed: {exc}")
            continue
        if status not in (403, 404):
            errors.append(f"{kind} {url}: expected 403/404, got {status}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--site-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--base-url",
        help="Also request every source.md and incoming Markdown URL from this site.",
    )
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    root = args.site_root.resolve()
    errors: list[str] = []
    check_static(root, errors)
    if args.base_url:
        check_http(root, args.base_url, args.timeout, errors)

    if errors:
        for error in errors:
            print(f"FAIL {error}")
        return 1
    print(
        "PASS public-boundaries "
        f"sources={len(list((root / 'blog').glob('*/source.md')))} "
        f"incoming={len(list((root / 'incoming').glob('**/*.md')))} "
        f"http={'checked' if args.base_url else 'skipped'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
