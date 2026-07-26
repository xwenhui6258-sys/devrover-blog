#!/usr/bin/env python3
"""Validate the exact-one AdSense loader requirement inside HTML head tags."""

from __future__ import annotations

import argparse
import sys
from html.parser import HTMLParser
from pathlib import Path


ADSENSE_SRC = (
    "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js"
    "?client=ca-pub-3874391842550034"
)


class AdSenseParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_head = False
        self.loaders: list[tuple[bool, dict[str, str | None]]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag == "head":
            self.in_head = True
        if tag != "script":
            return
        values = dict(attrs)
        if values.get("src") == ADSENSE_SRC:
            self.loaders.append((self.in_head, values))

    def handle_endtag(self, tag: str) -> None:
        if tag == "head":
            self.in_head = False


def html_pages(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(target.glob("*/index.html"))


def validate(path: Path) -> list[str]:
    parser = AdSenseParser()
    parser.feed(path.read_text(encoding="utf-8"))
    if len(parser.loaders) != 1:
        return [f"expected one loader, found {len(parser.loaders)}"]
    in_head, attrs = parser.loaders[0]
    errors: list[str] = []
    if not in_head:
        errors.append("loader is outside head")
    if "async" not in attrs:
        errors.append("loader is missing async")
    if attrs.get("crossorigin") != "anonymous":
        errors.append("loader crossorigin must be anonymous")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    pages = [page for target in args.paths for page in html_pages(target)]
    if not pages:
        print("No HTML files found.", file=sys.stderr)
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
