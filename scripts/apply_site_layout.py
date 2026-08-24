#!/usr/bin/env python3
"""Apply shared header/footer markup to generated static HTML pages."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from site_layout import STYLE_VERSION, infer_active_nav, render_site_footer, render_site_header


HEADER_PATTERN = re.compile(r"<header>.*?</header>", re.DOTALL)
FOOTER_PATTERN = re.compile(r'<footer class="site-footer">.*?</footer>', re.DOTALL)
STYLE_PATTERN = re.compile(r'href="/assets/style\.css\?v=[^"]+"')


def page_url_path(site_root: Path, html_path: Path) -> str:
    relative = html_path.relative_to(site_root)
    if relative.name == "404.html":
        return ""
    if relative.name == "index.html":
        parent = relative.parent.as_posix()
        return "/" if parent == "." else f"/{parent}/"
    return "/" + relative.with_suffix("").as_posix()


def apply_layout(site_root: Path, html_path: Path) -> bool:
    source = html_path.read_text(encoding="utf-8")
    updated = STYLE_PATTERN.sub(f'href="/assets/style.css?v={STYLE_VERSION}"', source)
    active = infer_active_nav(page_url_path(site_root, html_path))
    if HEADER_PATTERN.search(updated):
        updated = HEADER_PATTERN.sub(render_site_header(active), updated, count=1)
    if FOOTER_PATTERN.search(updated):
        updated = FOOTER_PATTERN.sub(render_site_footer(), updated, count=1)
    if updated == source:
        return False
    html_path.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site_root", nargs="?", default=Path(__file__).resolve().parents[1], type=Path)
    args = parser.parse_args()
    site_root = args.site_root.resolve()
    changed = []
    for html_path in sorted(site_root.rglob("*.html")):
        if ".git" in html_path.parts:
            continue
        if apply_layout(site_root, html_path):
            changed.append(html_path.relative_to(site_root).as_posix())
    print(f"Updated {len(changed)} HTML files")
    for path in changed:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
