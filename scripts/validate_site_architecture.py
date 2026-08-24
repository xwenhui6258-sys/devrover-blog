#!/usr/bin/env python3
"""Validate DevRover canonical metadata, discovery links, and sitemap coverage."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from publish_blog_post import parse_front_matter


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
DISALLOWED_PUBLIC_HOSTS = ("innomad.io",)
REQUIRED_PUBLIC_DISCLOSURE_FIELDS = (
    "content_type",
    "article_format",
    "evidence",
    "scope",
    "boundary",
    "content_reviewed",
    "source_reviewed",
)
SOURCE_REVIEW_MAX_AGE_DAYS = 180
PUBLIC_ARTICLE_FORMATS = {
    "机制拆解",
    "决策比较",
    "流程核对",
    "异常排查",
    "资料核验",
}
UNSUPPORTED_RESEARCH_CLAIM_PATTERNS = (
    re.compile(
        r"(?:我|本人|作者)(?:已经|已|曾|亲自|实际)[^。\n]{0,48}"
        r"(?:开户|入金|出金|下单|交易|持仓|收益|到账|结单)"
    ),
    re.compile(
        r"(?:我的|作者的)(?:真实)?(?:账户|订单|入金|出金|持仓|交易|收益|结单)"
        r"(?:已|成功|记录|结果|显示|证明)"
    ),
)
STRUCTURAL_UTILITY_HEADINGS = {
    "参考资料",
    "官方资料",
    "官方资料与核对入口",
}
GENERIC_TEMPLATE_HEADINGS = {
    "结论先行",
    "先给结论",
    "本次复核说明",
}
SOURCE_SECTION_PATTERN = re.compile(
    r"(?m)^##\s+(?:参考资料|官方资料|官方资料与核对入口)\s*$"
)
PRIMARY_SOURCE_HOST_SUFFIXES = (
    "gov",
    "gov.hk",
    "interactivebrokers.com",
    "interactivebrokers.ie",
    "interactivebrokers.com.sg",
    "interactivebrokers.com.hk",
    "interactivebrokers.co.uk",
    "ibkrguides.com",
    "schwab.com",
    "finra.org",
    "sipc.org",
    "hkma.gov.hk",
    "ofca.gov.hk",
    "sfc.hk",
    "ird.gov.hk",
    "chinatax.gov.cn",
    "mas.gov.sg",
    "sse.com.cn",
    "nacha.org",
    "frbservices.org",
    "centralbank.ie",
    "fca.org.uk",
    "hsbc.com.hk",
    "bochk.com",
)


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


def markdown_external_urls(text: str) -> list[str]:
    return re.findall(r"\]\((https?://[^)\s]+)\)", text)


def markdown_internal_blog_slugs(text: str) -> list[str]:
    return re.findall(
        r"\]\((?:https://7hui\.top)?/blog/([^/)]+)/?(?:[?#][^)]*)?\)",
        text,
    )


def is_primary_source_host(host: str) -> bool:
    normalized = host.lower().strip(".")
    return any(
        normalized == suffix or normalized.endswith("." + suffix)
        for suffix in PRIMARY_SOURCE_HOST_SUFFIXES
    )


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
    article_format_counts: dict[str, int] = {}
    heading_signatures: dict[tuple[str, ...], list[str]] = {}
    generic_heading_slugs: dict[str, list[str]] = {}
    contextual_incoming_links: dict[str, int] = {}

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
        for host in DISALLOWED_PUBLIC_HOSTS:
            if host in text.lower():
                errors.append(f"{relative_file}: contains disallowed legacy host {host}")
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

    home = (root / "index.html").read_text(encoding="utf-8")
    posts_by_url = {str(post.get("url") or ""): post for post in posts}
    home_guide_cards = re.findall(
        r'<article class="home-guide-card">(.*?)</article>',
        home,
        flags=re.DOTALL,
    )
    if len(home_guide_cards) != 3:
        errors.append(f"index.html: expected 3 home guide cards, found {len(home_guide_cards)}")
    for card in home_guide_cards:
        title_match = re.search(
            r'<h3><a href="([^"]+)">(.*?)</a></h3>',
            card,
            flags=re.DOTALL,
        )
        date_match = re.search(r'<time datetime="([^"]+)">', card)
        if not title_match or not date_match:
            errors.append("index.html: incomplete home guide card metadata")
            continue
        card_url = title_match.group(1)
        post = posts_by_url.get(card_url)
        if not post:
            errors.append(f"index.html: home guide card is not public {card_url}")
            continue
        card_title = html.unescape(re.sub(r"<[^>]+>", "", title_match.group(2))).strip()
        post_title = str(post.get("title") or "")
        if card_title != post_title and not post_title.startswith(card_title):
            errors.append(f"index.html: stale home guide title for {card_url}")
        expected_updated = str(post.get("updated") or post.get("date") or "")
        if date_match.group(1) != expected_updated:
            errors.append(f"index.html: stale home guide date for {card_url}")

    for post in posts:
        slug = str(post["slug"])
        url = str(post["url"])
        source = root / "blog" / slug / "source.md"
        if not source.is_file():
            errors.append(f"{slug}: missing source.md")
            continue
        source_text = source.read_text(encoding="utf-8")
        for host in DISALLOWED_PUBLIC_HOSTS:
            if host in source_text.lower():
                errors.append(f"{slug}: source contains disallowed legacy host {host}")
        front_matter, _, source_body = parse_front_matter(source_text)
        if front_matter.get("status") != "published":
            errors.append(f"{slug}: public post source status is not published")
        missing_disclosure = [
            field for field in REQUIRED_PUBLIC_DISCLOSURE_FIELDS if not front_matter.get(field)
        ]
        if missing_disclosure:
            errors.append(
                f"{slug}: missing content disclosure fields {missing_disclosure}"
            )
        parsed_review_dates: dict[str, date] = {}
        for field in ("content_reviewed", "source_reviewed"):
            raw_review_date = str(front_matter.get(field) or "")
            if not raw_review_date:
                continue
            try:
                parsed_review_dates[field] = date.fromisoformat(raw_review_date)
            except ValueError:
                errors.append(f"{slug}: invalid ISO date for {field}={raw_review_date}")
        for field, reviewed_date in parsed_review_dates.items():
            if reviewed_date > date.today():
                errors.append(f"{slug}: future review date for {field}={reviewed_date}")
        raw_updated = str(front_matter.get("updated") or front_matter.get("date") or "")
        try:
            modified_date = date.fromisoformat(raw_updated)
        except ValueError:
            errors.append(f"{slug}: invalid ISO date for updated/date={raw_updated}")
            modified_date = None
        content_reviewed = parsed_review_dates.get("content_reviewed")
        if modified_date and content_reviewed and modified_date < content_reviewed:
            errors.append(
                f"{slug}: dateModified {modified_date} predates content review "
                f"{content_reviewed}"
            )
        source_reviewed = parsed_review_dates.get("source_reviewed")
        if source_reviewed and (date.today() - source_reviewed).days > SOURCE_REVIEW_MAX_AGE_DAYS:
            errors.append(
                f"{slug}: source review is older than {SOURCE_REVIEW_MAX_AGE_DAYS} days "
                f"({source_reviewed})"
            )
        article_format = str(front_matter.get("article_format") or "")
        if article_format and article_format not in PUBLIC_ARTICLE_FORMATS:
            errors.append(f"{slug}: unsupported article_format={article_format}")
        if article_format:
            article_format_counts[article_format] = article_format_counts.get(article_format, 0) + 1
        content_type = str(front_matter.get("content_type") or "")
        if "个人经验" in content_type and not front_matter.get("experience_evidence"):
            errors.append(
                f"{slug}: personal-experience content is missing experience_evidence"
            )
        if "个人经验" not in content_type:
            for pattern in UNSUPPORTED_RESEARCH_CLAIM_PATTERNS:
                match = pattern.search(source_body)
                if match:
                    errors.append(
                        f"{slug}: research article contains unsupported firsthand claim "
                        f"{match.group(0)!r}"
                    )
        source_urls = sorted(set(markdown_external_urls(source_body)))
        source_hosts = {
            (urlparse(source_url).hostname or "").lower()
            for source_url in source_urls
        }
        if len(source_urls) < 3:
            errors.append(f"{slug}: fewer than 3 external source links")
        if len(source_hosts) < 2:
            errors.append(f"{slug}: source links do not span 2 domains")
        if not any(is_primary_source_host(host) for host in source_hosts):
            errors.append(f"{slug}: no primary or official source domain found")
        internal_slugs = markdown_internal_blog_slugs(source_body)
        if not internal_slugs:
            errors.append(f"{slug}: no contextual internal blog link in source body")
        for target_slug in internal_slugs:
            if target_slug == slug:
                errors.append(f"{slug}: contextual link points to itself")
            elif target_slug not in slugs:
                errors.append(
                    f"{slug}: contextual link targets non-public article {target_slug}"
                )
            else:
                contextual_incoming_links[target_slug] = (
                    contextual_incoming_links.get(target_slug, 0) + 1
                )
        source_section = SOURCE_SECTION_PATTERN.search(source_body)
        if not source_section:
            errors.append(f"{slug}: missing a labeled source section")
        else:
            reference_urls = set(markdown_external_urls(source_body[source_section.end() :]))
            if len(reference_urls) < 2:
                errors.append(f"{slug}: source section has fewer than 2 external links")
        headings = [
            heading.strip()
            for heading in re.findall(r"(?m)^##\s+(.+?)\s*$", source_body)
        ]
        substantive_headings = [
            heading for heading in headings if heading not in STRUCTURAL_UTILITY_HEADINGS
        ]
        if len(substantive_headings) < 3:
            errors.append(f"{slug}: too few substantive H2 headings")
        signature = tuple(substantive_headings[:3])
        if signature:
            heading_signatures.setdefault(signature, []).append(slug)
        for heading in headings:
            if heading in GENERIC_TEMPLATE_HEADINGS:
                generic_heading_slugs.setdefault(heading, []).append(slug)
        page = root / "blog" / slug / "index.html"
        if not page.is_file():
            errors.append(f"{slug}: missing index.html")
            continue
        text = page.read_text(encoding="utf-8")
        for host in DISALLOWED_PUBLIC_HOSTS:
            if host in text.lower():
                errors.append(f"{slug}: page contains disallowed legacy host {host}")
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
        if 'class="article-disclaimer"' not in text:
            errors.append(f"{slug}: missing article disclaimer")
        if 'class="article-evidence"' not in text:
            errors.append(f"{slug}: missing content evidence disclosure")
        if article_format and article_format not in text:
            errors.append(f"{slug}: article format is not visible to readers")
        source_reviewed_raw = str(front_matter.get("source_reviewed") or "")
        if source_reviewed_raw and f"官方资料复核：{source_reviewed_raw}" not in text:
            errors.append(f"{slug}: source review date is not visible to readers")
        if "本文仅供一般信息与资料研究使用，不构成投资、税务或法律建议。" not in text:
            errors.append(f"{slug}: missing concise advice disclaimer")
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

    if len(article_format_counts) < 4:
        errors.append(
            "public articles do not use enough reader-facing formats: "
            f"found={sorted(article_format_counts)}"
        )
    for heading, slugs_using_heading in generic_heading_slugs.items():
        if len(slugs_using_heading) > 1:
            errors.append(
                f"generic H2 heading is repeated across public articles: "
                f"{heading}={sorted(slugs_using_heading)}"
            )
    for signature, slugs_using_signature in heading_signatures.items():
        if len(slugs_using_signature) > 1:
            errors.append(
                "public articles share the same opening structure: "
                f"{signature}={sorted(slugs_using_signature)}"
            )
    for slug in slugs:
        if contextual_incoming_links.get(slug, 0) < 1:
            errors.append(f"{slug}: no contextual incoming link from another public article")

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
