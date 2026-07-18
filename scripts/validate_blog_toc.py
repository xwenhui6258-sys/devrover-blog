#!/usr/bin/env python3
"""Validate that DevRover article tables of contents link to H2 only."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


TOC_BLOCK = re.compile(
    r'<aside\b[^>]*class="[^"]*\barticle-toc\b[^"]*"[^>]*>.*?</aside>',
    re.IGNORECASE | re.DOTALL,
)
TOC_LEVEL = re.compile(r'class="[^"]*\btoc-level-(\d+)\b[^"]*"', re.IGNORECASE)
H2 = re.compile(r"<h2\b", re.IGNORECASE)


def article_pages(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(target.glob("*/index.html"))


def validate(path: Path) -> list[str]:
    html = path.read_text(encoding="utf-8")
    toc_blocks = TOC_BLOCK.findall(html)
    h2_count = len(H2.findall(html))
    if not toc_blocks:
        return ["missing article-toc"] if h2_count else []

    levels = [int(level) for block in toc_blocks for level in TOC_LEVEL.findall(block)]
    errors: list[str] = []
    if any(level != 2 for level in levels):
        errors.append(f"directory contains non-H2 levels: {levels}")
    if len(levels) != h2_count:
        errors.append(f"directory links={len(levels)}, h2 headings={h2_count}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="article index.html or a blog directory")
    args = parser.parse_args()

    pages = [page for target in args.paths for page in article_pages(target)]
    if not pages:
        print("No article index.html files found.", file=sys.stderr)
        return 2

    failures = 0
    for page in pages:
        errors = validate(page)
        if errors:
            failures += 1
            print(f"FAIL {page}: {'; '.join(errors)}")
        else:
            print(f"PASS {page}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
