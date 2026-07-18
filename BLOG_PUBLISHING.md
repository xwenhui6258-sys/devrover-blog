# 7hui.top 博客发布规范

这个网站的博客根目录是：

```text
/opt/1panel/www/sites/7hui.top/index
```

后续发布文章时，每篇文章都用一个独立输入目录，目录里放 Markdown 和图片资源。

## 输入目录

推荐结构：

```text
incoming/article-id/
  article-id.md
  images/
    cover.jpg
    image_01.png
    image_02.jpg
```

也兼容这种导出结构：

```text
incoming/article-id/
  article-id.md
  images/article-id/
    cover.jpg
    image_01.png
```

注意：Codex 必须能读取输入目录。Mac 本机路径例如 `/Users/xwenhui/...` 如果没有上传到服务器或工作区，发布脚本无法直接读取。

## 输出目录

发布后生成：

```text
blog/<slug>/
  index.html
  source.md
  assets/
    cover.jpg
    image_01.png
```

其中：

- `index.html` 是最终网页。
- `source.md` 是重写图片路径后的 Markdown 源文。
- `assets/` 存放该文章自己的图片，避免不同文章资源混在一起。

## 发布命令

在站点根目录执行：

```bash
cd /opt/1panel/www/sites/7hui.top/index
scripts/publish_blog_post.py incoming/article-id --slug article-url-slug
```

也可以显式指定站点根目录：

```bash
/opt/1panel/www/sites/7hui.top/index/scripts/publish_blog_post.py \
  /opt/1panel/www/sites/7hui.top/index/incoming/article-id \
  --site-root /opt/1panel/www/sites/7hui.top/index \
  --slug article-url-slug
```

## Markdown Front Matter

脚本会优先读取 Markdown front matter：

```yaml
---
title: "文章标题"
date: "2026-07-12"
summary: "文章摘要"
slug: "optional-slug"
---
```

如果缺少字段：

- `title`：从第一个 `# 标题` 或文件名推断。
- `date`：使用当天日期。
- `summary`：从正文自动截取。
- `slug`：从标题生成，或用命令里的 `--slug`。

## 当前文章详情页样式

当前已确定的博客详情页规范：

- 页面沿用全站导航和 `assets/style.css`。
- 正文和导航栏使用同一套页面边界。
- 文章外层使用 `.article-layout`。
- 正文列宽：约 `920px`。
- 右侧目录列：约 `170px`，字号较小。
- 小屏幕下目录自动移动到正文下方。
- 文章图片全宽展示，圆角、细边框、轻阴影。
- Markdown 表格会渲染为横向可滚动表格。
- H2 与 H3 会自动生成锚点；右侧目录只展示 H2，绝不展示 H3 或更深层级。

标题规则：

- 如果标题包含 `全流程：`，会自动拆成两行。
- 主标题示例：`大陆身份开嘉信理财（Charles Schwab）`
- 副标题示例：`全流程：手把手图文教程`
- 顶部不再显示 `返回博客 / BLOG`。

## 博客分类与标签

- `category` 表示文章唯一的主归属；当前分类为 `跨境投资`、`券商入金`、`海外银行卡`、`美股账户`。
- `tags` 表示可以跨分类浏览的长期主题。唯一白名单见 `blog/tag-taxonomy.json`。
- 每篇文章必须有 1–3 个标签，标签必须来自白名单；不要把产品功能、英文同义词、表单名或单篇文章关键词新增为标签。
- 新文章不会自动扩充标签池。确需新增长期主题时，必须先更新标签白名单、迁移别名并说明原因。
- 同一篇文章的 `blog/<slug>/source.md` 和 `blog/posts.json` 标签必须一致。
- 首页分类数量由 `posts.json` 自动统计；运行同步脚本后，不得手工维护数字或重复维护文章卡片。

更新文章元数据或 `posts.json` 后执行：

```bash
python3 scripts/sync_blog_index.py
python3 scripts/validate_blog_taxonomy.py
```

## 后续给 Codex 的用法

你把文章目录上传后，可以直接这样说：

```text
请按 7hui.top 博客发布规范发布这篇文章：
/opt/1panel/www/sites/7hui.top/index/incoming/article-id

slug 用：
my-article-slug
```

如果需要合并两篇文章，可以这样说：

```text
请把这两篇文章合并成一篇发布：
/opt/1panel/www/sites/7hui.top/index/incoming/article-a
/opt/1panel/www/sites/7hui.top/index/incoming/article-b

主文章 slug 用：
my-merged-article
```

如果需要删除导入噪音内容，直接说明要删的原文片段。发布前应先改 `incoming/` 里的原始 Markdown，再重新生成，避免下次重建时内容又回来。

## 发布后检查

每次发布后至少检查：

```bash
find blog/<slug>/assets -type f | wc -l
rg -n "目标标题|目标 slug" blog/index.html blog/<slug>/index.html
rg -n "不应出现的文本" blog/<slug>/source.md blog/<slug>/index.html
python3 scripts/validate_blog_toc.py blog/<slug>/index.html
python3 scripts/sync_blog_index.py --check
python3 scripts/validate_blog_taxonomy.py
```

确认：

- 博客列表已更新。
- 文章 URL 可访问。
- 图片数量正确。
- 图片路径已变成 `assets/...`。
- 右侧目录正常生成。
- 右侧目录仅展示一级标题（H2）；运行 python3 scripts/validate_blog_toc.py blog/文章-slug/index.html 必须通过。
- 标签只使用 `blog/tag-taxonomy.json` 白名单，每篇 1–3 个，首页内嵌数据和静态卡片与 `posts.json` 一致。
- 不需要的导入文本已删除。
