import unittest

from publish_blog_post import PostMeta, apply_content_disclosure, render_page, article_image_url


class ShareImageTests(unittest.TestCase):
    def meta(self, cover=""):
        meta = PostMeta(title="Test", date="2026-09-22", summary="Summary", slug="sample")
        return apply_content_disclosure(meta, {"cover": cover})

    def test_cover_without_body_image(self):
        page = render_page(self.meta("assets/cover.png"), "<p>Article text.</p>")
        url = "https://7hui.top/blog/sample/assets/cover.png"
        self.assertIn(f'property="og:image" content="{url}"', page)
        self.assertIn(f'name="twitter:image" content="{url}"', page)
        self.assertIn('"image":["' + url + '"]', page)

    def test_cover_wins(self):
        page = render_page(self.meta("assets/cover.png"), '<p>Text.</p><img src="assets/body.png">')
        self.assertIn('og:image" content="https://7hui.top/blog/sample/assets/cover.png"', page)

    def test_fallback_and_no_image(self):
        page = render_page(self.meta(), '<p>Text.</p><img src="/assets/body.png">')
        self.assertIn('og:image" content="https://7hui.top/assets/body.png"', page)
        self.assertNotIn('og:image', render_page(self.meta(), '<p>Text.</p>'))

    def test_url_forms(self):
        for src, expected in [
            ("assets/a.png", "https://7hui.top/blog/sample/assets/a.png"),
            ("/assets/a.png", "https://7hui.top/assets/a.png"),
            ("https://example.com/a.png", "https://example.com/a.png"),
            ("data:image/png;base64,aaa", ""),
            ("javascript:alert(1)", ""),
        ]:
            with self.subTest(src=src):
                self.assertEqual(article_image_url(src, self.meta()), expected)


if __name__ == "__main__":
    unittest.main()
