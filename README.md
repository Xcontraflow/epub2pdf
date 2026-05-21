# EPUB2PDF

将 EPUB 电子书转换为 PDF 的 Windows 桌面工具。CJK 文本渲染清晰，保留内部链接和目录书签。

![Platform](https://img.shields.io/badge/platform-Windows-blue)
![Python](https://img.shields.io/badge/python-3.9+-blue)

## 功能

- EPUB → PDF 一键转换
- 完美中文/日文/韩文渲染（使用 Windows 系统字体）
- 自动生成 PDF 书签目录
- 保留原书内部链接
- 自定义字体、字号、行距、页边距
- Claude 风格简洁 UI

## 快速使用（推荐：下载 Release）

无需安装 Python，直接下载可执行文件。

1. 打开 [Releases 页面](https://github.com/Xcontraflow/epub2pdf/releases/latest)
2. 下载 `EPUB2PDF-vX.X.X-win64.zip`
3. 解压到任意目录（例如 `D:\Tools\EPUB2PDF\`）
4. 双击 `EPUB2PDF.exe` 启动
5. 可选：双击 `create_shortcut.bat` 创建桌面快捷方式

**首次运行需 Edge 或 Chrome 浏览器**（Windows 10/11 自带 Edge，无需额外安装）。

## 从源码运行（开发者）

需 Python 3.9+。

```bash
git clone https://github.com/Xcontraflow/epub2pdf.git
cd epub2pdf
install.bat
run.bat
```

或手动安装：

```bash
pip install -r requirements.txt
python main.py
```

## 自己打包 exe

```bash
build_exe.bat
```

产物在 `dist\EPUB2PDF\EPUB2PDF.exe`。

## 依赖

- `ebooklib` — 解析 EPUB
- `beautifulsoup4` + `lxml` — HTML 处理
- `playwright` — Chromium PDF 渲染
- `pypdf` — PDF 后处理（书签）
- `Pillow` — 图像处理
- `customtkinter` — UI

## 许可证

MIT
