"""Shared site chrome for the static DevRover site.

The public site is deployed as plain HTML, so header and footer are rendered
at build/sync time instead of being injected by client-side JavaScript.
"""

from __future__ import annotations


SITE_NAME = "DevRover的个人站"
STYLE_VERSION = "20260824-layout-v1"


def render_site_header(active: str = "") -> str:
    nav_items = (
        ("blog", "/blog/", "博客"),
        ("tools", "/tools/", "工具"),
        ("about", "/about/", "关于"),
    )
    rendered_links = []
    for key, href, label in nav_items:
        current = ' aria-current="page"' if key == active else ""
        rendered_links.append(f'      <a href="{href}"{current}>{label}</a>')
    links = "\n".join(rendered_links)
    return f"""<header>
  <div class="container nav">
    <a class="brand" href="/"><img class="brand-icon" src="/assets/devrover-icon.png" width="36" height="36" alt="" aria-hidden="true">{SITE_NAME}</a>
    <nav>
{links}
    </nav>
  </div>
</header>"""


def render_site_footer() -> str:
    return f"""<footer class="site-footer">
  <div class="container footer-grid">
    <div class="footer-brand">
      <a href="/">{SITE_NAME}</a>
      <p>记录跨境金融中的具体问题、资料核验和实用工具。</p>
    </div>
    <nav class="footer-links" aria-label="站点信息">
      <a href="/about/">关于作者</a>
      <a href="/contact/">联系与纠错</a>
      <a href="/editorial-policy/">编辑与内容政策</a>
      <a href="/privacy/">隐私与 Cookie</a>
      <a href="/disclaimer/">免责声明</a>
      <a href="/terms/">使用条款</a>
    </nav>
  </div>
  <div class="container footer-bottom">
    <span>© 2026 {SITE_NAME}</span>
    <span>内容仅供一般信息与资料研究使用，不构成投资、税务或法律建议。</span>
  </div>
</footer>"""


def infer_active_nav(url_path: str) -> str:
    if url_path.startswith("/blog/"):
        return "blog"
    if url_path.startswith("/tools/"):
        return "tools"
    if url_path.startswith("/about/"):
        return "about"
    return ""
