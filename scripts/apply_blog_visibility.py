#!/usr/bin/env python3
"""Apply noindex, redirect fallback, and retirement pages from content-status.json."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path


SITE_URL = "https://7hui.top"
SITE_NAME = "DevRover的个人站"
STYLE_VERSION = "20260809-trust-v1"
ADSENSE_LOADER = "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-3874391842550034"
ADSENSE_LOADER_PATTERN = re.compile(
    r'\s*<script\b[^>]*\bsrc=["\']'
    + re.escape(ADSENSE_LOADER)
    + r'["\'][^>]*>\s*</script>',
    flags=re.IGNORECASE,
)


def read_status(root: Path) -> tuple[set[str], dict[str, str], set[str]]:
    path = root / "blog" / "content-status.json"
    status = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(status, dict):
        raise ValueError("content-status.json must be an object")
    hidden = {str(slug) for slug in status.get("hiddenSlugs", [])}
    redirects = {
        str(slug): str(target)
        for slug, target in dict(status.get("redirects", {})).items()
    }
    retired = {str(slug) for slug in status.get("retiredSlugs", [])}
    overlap = (hidden & set(redirects)) | (hidden & retired) | (set(redirects) & retired)
    if overlap:
        raise ValueError(f"content status has overlapping slugs: {sorted(overlap)}")
    for slug, target in redirects.items():
        if not slug or not target.startswith("/blog/") or not target.endswith("/"):
            raise ValueError(f"invalid redirect: {slug!r} -> {target!r}")
    return hidden, redirects, retired


def header() -> str:
    return f'''<header>
  <div class="container nav">
    <a class="brand" href="/"><img class="brand-icon" src="/assets/devrover-icon.png" width="36" height="36" alt="" aria-hidden="true">{SITE_NAME}</a>
    <nav>
      <a href="/blog/">博客</a>
      <a href="/tools/">工具</a>
      <a href="/about/">关于</a>
    </nav>
  </div>
</header>'''


def footer() -> str:
    return '''<footer class="site-footer">
  <div class="container footer-grid"><div class="footer-brand"><a href="/">DevRover的个人站</a><p>记录跨境金融、海外投资与数字生活中的真实问题、核验过程和实用工具。</p></div><nav class="footer-links" aria-label="站点信息"><a href="/about/">关于作者</a><a href="/contact/">联系与纠错</a><a href="/editorial-policy/">编辑与内容政策</a><a href="/privacy/">隐私与 Cookie</a><a href="/disclaimer/">免责声明</a><a href="/terms/">使用条款</a></nav></div>
  <div class="container footer-bottom"><span>© 2026 DevRover的个人站</span><span>内容仅供信息与经验交流，不构成投资、税务或法律建议。</span></div>
</footer>'''


def simple_page(title: str, description: str, body: str, canonical: str = "", refresh_target: str = "") -> str:
    canonical_tag = f'\n  <link rel="canonical" href="{html.escape(SITE_URL + canonical, quote=True)}">' if canonical else ""
    refresh = f'\n  <meta http-equiv="refresh" content="0;url={html.escape(refresh_target, quote=True)}">' if refresh_target else ""
    script = (
        f'\n  <script>location.replace({json.dumps(refresh_target)});</script>'
        if refresh_target
        else ""
    )
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="robots" content="noindex,follow,noarchive">
  <meta name="description" content="{html.escape(description, quote=True)}">{canonical_tag}{refresh}
  <title>{html.escape(title)}｜{SITE_NAME}</title>
  <link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon-32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="/assets/favicon-16.png">
  <link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
  <link rel="stylesheet" href="/assets/style.css?v={STYLE_VERSION}">{script}
</head>
<body>
{header()}
<main class="page"><div class="container">{body}</div></main>
{footer()}
</body>
</html>
'''


def hidden_page(existing: str) -> str:
    if not existing:
        raise ValueError("cannot apply noindex to a missing article page")
    robots = '<meta name="robots" content="noindex,follow">'
    if re.search(r'<meta\s+name="robots"[^>]*>', existing, flags=re.IGNORECASE):
        updated = re.sub(r'<meta\s+name="robots"[^>]*>', robots, existing, count=1, flags=re.IGNORECASE)
    else:
        updated, count = re.subn(
            r'(<meta\s+name="viewport"[^>]*>\s*)',
            r'\1  ' + robots + '\n  ',
            existing,
            count=1,
            flags=re.IGNORECASE,
        )
        if count != 1:
            raise ValueError("article page is missing viewport metadata")
    updated, loader_count = ADSENSE_LOADER_PATTERN.subn("", updated)
    if loader_count > 1:
        raise ValueError("article page contains multiple AdSense loaders")
    return updated


def redirect_page(target: str) -> str:
    body = (
        f'<h1>内容已合并</h1><p class="lead">这篇内容已整理到更完整的文章中，正在跳转。</p>'
        f'<a class="button primary" href="{html.escape(target, quote=True)}">继续阅读</a>'
    )
    return simple_page("内容已合并", "这篇内容已合并到更完整的文章。", body, canonical=target, refresh_target=target)


def retired_page() -> str:
    body = (
        '<h1>内容已下线</h1><p class="lead">这篇旧文因内容标准复核而不再提供。</p>'
        '<p>请浏览经过当前核验的博客内容，或通过联系页面提交纠错和问题。</p>'
        '<p><a class="button primary" href="/blog/">返回博客</a></p>'
    )
    return simple_page("内容已下线", "该旧文已因内容标准复核而下线。", body)


def check_page(path: Path, fragments: tuple[str, ...]) -> list[str]:
    if not path.is_file():
        return [f"missing {path}"]
    text = path.read_text(encoding="utf-8")
    return [f"{path}: missing {fragment!r}" for fragment in fragments if fragment not in text]


def expected_nonpublic(root: Path) -> tuple[set[str], dict[str, str], set[str]]:
    hidden, redirects, retired = read_status(root)
    all_nonpublic = hidden | set(redirects) | retired
    posts = json.loads((root / "blog" / "posts.json").read_text(encoding="utf-8"))
    listed = {str(post.get("slug") or "") for post in posts}
    overlap = listed & all_nonpublic
    if overlap:
        raise ValueError(f"non-public slugs still appear in posts.json: {sorted(overlap)}")
    return hidden, redirects, retired


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    hidden, redirects, retired = expected_nonpublic(root)
    sitemap = (root / "sitemap.xml").read_text(encoding="utf-8") if (root / "sitemap.xml").is_file() else ""
    posts = json.loads((root / "blog" / "posts.json").read_text(encoding="utf-8"))
    surface_paths = [root / "index.html", root / "blog" / "index.html"]
    surface_paths.extend(root / "blog" / str(post.get("slug")) / "index.html" for post in posts)
    surfaces = {
        str(path.relative_to(root)): path.read_text(encoding="utf-8")
        for path in surface_paths
        if path.is_file()
    }
    for slug in hidden:
        path = root / "blog" / slug / "index.html"
        errors.extend(check_page(path, ('<meta name="robots" content="noindex,follow">',)))
        if path.is_file() and ADSENSE_LOADER in path.read_text(encoding="utf-8"):
            errors.append(f"{path}: hidden page still contains AdSense loader")
    for slug, target in redirects.items():
        path = root / "blog" / slug / "index.html"
        errors.extend(check_page(path, ('<meta name="robots" content="noindex,follow,noarchive">', f'content="0;url={target}"', f'location.replace({json.dumps(target)})')))
    for slug in retired:
        path = root / "blog" / slug / "index.html"
        errors.extend(check_page(path, ('<meta name="robots" content="noindex,follow,noarchive">', '<h1>内容已下线</h1>')))
        retired_text = path.read_text(encoding="utf-8") if path.is_file() else ""
        if "建议适当填大" in retired_text:
            errors.append(f"{path}: retired page still contains removed guidance")
    for slug in hidden | set(redirects) | retired:
        url = f"/blog/{slug}/"
        if url in sitemap:
            errors.append(f"sitemap still includes {url}")
        for label, surface in surfaces.items():
            if f'href="{url}"' in surface:
                errors.append(f"{label} still links to {url}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.site_root.resolve()
    try:
        hidden, redirects, retired = expected_nonpublic(root)
        if not args.check:
            for slug in hidden:
                path = root / "blog" / slug / "index.html"
                path.write_text(hidden_page(path.read_text(encoding="utf-8")), encoding="utf-8")
            for slug, target in redirects.items():
                (root / "blog" / slug / "index.html").write_text(redirect_page(target), encoding="utf-8")
            for slug in retired:
                (root / "blog" / slug / "index.html").write_text(retired_page(), encoding="utf-8")
        errors = validate(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"FAIL {error}")
        return 1
    action = "checked" if args.check else "applied"
    print(f"PASS visibility {action} hidden={len(hidden)} redirects={len(redirects)} retired={len(retired)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
