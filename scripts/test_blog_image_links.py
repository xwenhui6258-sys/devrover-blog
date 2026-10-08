import unittest

from publish_blog_post import markdown_to_html


class ImageLinkTests(unittest.TestCase):
    def test_original_link_preserves_query(self):
        page = markdown_to_html('![核对图](assets/map.svg?v=1&size=2)')
        self.assertIn('href="assets/map.svg?v=1&amp;size=2"', page)
        self.assertIn('target="_blank" rel="noopener noreferrer"', page)
        self.assertIn('aria-label="查看原图：核对图（新窗口打开）"', page)
        self.assertIn('<figcaption>核对图<br>', page)

    def test_no_script_link(self):
        page = markdown_to_html('![测试](javascript:alert)')
        self.assertNotIn('article-image-original', page)

    def test_no_image_no_link(self):
        self.assertNotIn('article-image-original', markdown_to_html('只有正文。'))


if __name__ == '__main__':
    unittest.main()
