个人静态网站部署说明

目录：
- /index.html               首页
- /blog/index.html          博客列表
- /tools/index.html         工具箱
- /tools/json/index.html    JSON 工具
- /about/index.html         关于页
- /assets/style.css         全站样式
- /404.html                 404 页面

部署：
1. 在 1Panel 中打开现有网站的“网站目录”。
2. 先备份或删除默认首页文件。
3. 上传本压缩包并解压。
4. 确保 index.html 位于网站根目录，而不是多套一层文件夹。
5. 访问主域名、/tools/、/tools/json/ 检查效果。

注意：
纯静态网站不能在服务器端直接执行 Python。
简单工具优先使用 JavaScript；需要在浏览器中运行 Python 时，可接入 Pyodide。
