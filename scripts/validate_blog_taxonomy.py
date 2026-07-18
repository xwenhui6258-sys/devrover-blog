#!/usr/bin/env python3
"""Validate DevRover blog tags, source metadata, and index synchronization."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


def source_tags(path: Path) -> list[str] | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    front = text[4:end]
    match = re.search(r"(?m)^tags:\s*$", front)
    if not match:
        return None
    tags: list[str] = []
    for line in front[match.end() :].lstrip("\n").splitlines():
        item = re.match(r"^[ \t]+-\s*(.+?)\s*$", line)
        if not item:
            break
        tags.append(item.group(1).strip("'\""))
    return tags


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.site_root.resolve()
    taxonomy_path = root / "blog" / "tag-taxonomy.json"
    posts_path = root / "blog" / "posts.json"
    errors: list[str] = []

    try:
        taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
        posts = json.loads(posts_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1

    allowed = taxonomy.get("tags")
    maximum = taxonomy.get("maxTagsPerPost")
    aliases = taxonomy.get("aliases", {})
    if not isinstance(allowed, list) or not allowed:
        errors.append("taxonomy tags must be a non-empty list")
        allowed = []
    if len(allowed) != len(set(allowed)):
        errors.append("taxonomy tags contain duplicates")
    if len(allowed) + 1 > 10:
        errors.append(f"homepage chips exceed 10 including 全部: {len(allowed) + 1}")
    if not isinstance(maximum, int) or maximum < 1 or maximum > 3:
        errors.append(f"maxTagsPerPost must be 1..3, got {maximum!r}")
        maximum = 3
    for alias, target in aliases.items():
        if target not in allowed:
            errors.append(f"alias target is not canonical: {alias} -> {target}")

    slugs: set[str] = set()
    urls: set[str] = set()
    assignments = 0
    for index, post in enumerate(posts):
        slug = post.get("slug")
        url = post.get("url")
        tags = post.get("tags")
        label = slug or f"post[{index}]"
        if not slug or slug in slugs:
            errors.append(f"missing or duplicate slug: {label}")
        else:
            slugs.add(slug)
        if not url or url in urls:
            errors.append(f"missing or duplicate url: {label}")
        else:
            urls.add(url)
        if not isinstance(tags, list) or not tags:
            errors.append(f"{label}: tags must be a non-empty list")
            continue
        assignments += len(tags)
        if len(tags) > maximum:
            errors.append(f"{label}: {len(tags)} tags exceeds {maximum}")
        if len(tags) != len(set(tags)):
            errors.append(f"{label}: duplicate tags")
        unknown = sorted(set(tags) - set(allowed))
        if unknown:
            errors.append(f"{label}: unknown tags {unknown}")
        source = root / "blog" / str(slug) / "source.md"
        if not source.is_file():
            errors.append(f"{label}: missing source.md")
        else:
            actual = source_tags(source)
            if actual != tags:
                errors.append(f"{label}: source tags {actual!r} != posts tags {tags!r}")

    source_slugs = {path.parent.name for path in (root / "blog").glob("*/source.md")}
    if source_slugs != slugs:
        errors.append(
            f"source/post slug mismatch: only_source={sorted(source_slugs - slugs)}, "
            f"only_posts={sorted(slugs - source_slugs)}"
        )

    index_html = (root / "blog" / "index.html").read_text(encoding="utf-8")
    if "tagFiltersToggle" in index_html or "展开全部标签" in index_html:
        errors.append("blog index still contains the obsolete tag expansion control")
    static_match = re.search(
        r'<div class="post-list" id="postList">(.*?)</div>\n    </div>\n\n    <aside class="series-panel"',
        index_html,
        re.DOTALL,
    )
    static_count = static_match.group(1).count('<article class="post-card">') if static_match else -1
    if static_count != len(posts):
        errors.append("static post-card count does not match posts.json")
    sync = subprocess.run(
        [sys.executable, str(root / "scripts" / "sync_blog_index.py"), "--site-root", str(root), "--check"],
        text=True,
        capture_output=True,
    )
    if sync.returncode:
        errors.append(sync.stderr.strip() or sync.stdout.strip() or "blog index sync check failed")

    if errors:
        for error in errors:
            print(f"FAIL {error}")
        return 1

    counts = Counter(post["category"] for post in posts)
    categories = ", ".join(f"{name}={count}" for name, count in counts.items())
    print(
        f"PASS posts={len(posts)} canonical_tags={len(allowed)} assignments={assignments} "
        f"source_files={len(source_slugs)} categories=({categories})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
