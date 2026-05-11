"""
EPUB to PDF conversion engine.
Renders via a Chromium-based browser (system Edge/Chrome or bundled Chromium).
This gives perfect CJK text rendering using Windows system fonts, working
internal PDF links from <a href="#..."> anchors, and post-processed PDF
bookmarks added via pypdf.
"""

import io
import os
import re
import base64
import tempfile
import zipfile
import shutil
from pathlib import Path
from typing import Optional, Callable
from urllib.parse import urlparse, unquote

from bs4 import BeautifulSoup
import ebooklib
from ebooklib import epub


def convert_epub_to_pdf(
    epub_path: str,
    output_path: str,
    font_family: str = "",
    cjk_font_family: str = "",
    code_font_family: str = "",
    font_size: int = 12,
    line_height: float = 1.6,
    margin: str = "2cm",
    progress_callback: Optional[Callable] = None,
) -> str:
    """
    Convert an EPUB file to PDF.

    Pipeline:
      1. Merge all spine HTML into one document (cross-doc links become #anchors).
      2. Inline images as base64.
      3. Render to PDF with a Chromium browser — CJK text uses Windows system fonts.
      4. Post-process with pypdf to add a PDF outline (TOC bookmarks).
    """

    def progress(msg: str, pct: Optional[int] = None) -> None:
        if progress_callback:
            progress_callback(msg, pct)

    progress("读取 EPUB 文件...", 5)
    book = epub.read_epub(epub_path)

    tmpdir = tempfile.mkdtemp(prefix="epub2pdf_")
    try:
        progress("解压资源文件...", 10)
        with zipfile.ZipFile(epub_path, "r") as zf:
            zf.extractall(tmpdir)

        progress("分析文档结构...", 18)

        items_by_name: dict = {}
        items_by_id: dict = {}
        for item in book.get_items():
            name = item.get_name()
            items_by_name[name] = item
            items_by_id[item.id] = item
            bn = os.path.basename(name)
            if bn not in items_by_name:
                items_by_name[bn] = item

        spine_items = []
        for item_id, _linear in book.spine:
            item = items_by_id.get(item_id)
            if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
                spine_items.append(item)

        if not spine_items:
            spine_items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))

        name_to_slug: dict = {}
        for item in spine_items:
            name = item.get_name()
            slug = _name_to_slug(name)
            name_to_slug[name] = slug
            name_to_slug[os.path.basename(name)] = slug

        progress("处理章节内容...", 28)
        sections = []
        all_headings: list = []   # [(level_int, text_str, id_str), ...]
        n = max(len(spine_items), 1)

        for i, item in enumerate(spine_items):
            slug = _name_to_slug(item.get_name())
            frag = _process_chapter(
                item, slug, name_to_slug, items_by_name, tmpdir, all_headings
            )
            sections.append(frag)
            progress(f"章节 {i + 1}/{len(spine_items)} 处理完成", 28 + int(35 * (i + 1) / n))

        progress("收集样式表...", 65)
        epub_css = _collect_epub_css(book, tmpdir)
        custom_css = _build_custom_css(font_family, cjk_font_family, code_font_family, font_size, line_height, margin)

        titles = book.get_metadata("DC", "title")
        title = titles[0][0] if titles else Path(epub_path).stem

        progress("组装 HTML 文档...", 70)
        html = _build_html(title, epub_css, custom_css, sections)

        progress("启动浏览器渲染 PDF...", 75)
        _render_pdf(html, output_path, margin)

        progress("添加目录书签...", 95)
        _add_bookmarks(output_path, all_headings)

        progress("转换完成！", 100)
        return output_path

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Chapter processing
# ---------------------------------------------------------------------------

def _name_to_slug(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug


def _process_chapter(
    item,
    slug: str,
    name_to_slug: dict,
    items_by_name: dict,
    tmpdir: str,
    headings: list,
) -> str:
    """Parse one EPUB document into an HTML fragment and collect headings."""
    try:
        raw = item.get_content().decode("utf-8", errors="replace")
    except Exception:
        return ""

    soup = BeautifulSoup(raw, "lxml")
    body = soup.find("body") or soup

    # Prefix all id attributes so they are unique in the merged document
    for tag in body.find_all(id=True):
        tag["id"] = f"{slug}-{tag['id']}"

    # Fix anchor links to point to the merged-document ids
    for a_tag in body.find_all("a", href=True):
        a_tag["href"] = _fix_link(a_tag["href"], slug, item.get_name(), name_to_slug)

    # Inline images as base64 data URIs
    for img in body.find_all("img", src=True):
        src = img["src"]
        if not src.startswith("data:") and not src.startswith("http"):
            img["src"] = _inline_image(src, item.get_name(), items_by_name, tmpdir)

    for svg_img in body.find_all("image"):
        for attr in ("xlink:href", "href"):
            val = svg_img.get(attr, "")
            if val and not val.startswith(("data:", "http", "#")):
                svg_img[attr] = _inline_image(val, item.get_name(), items_by_name, tmpdir)

    # Collect heading info for later PDF bookmark generation
    for htag in body.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        level = int(htag.name[1]) - 1   # h1 → 0, h2 → 1, …
        text = htag.get_text(" ", strip=True)[:120]
        hid = htag.get("id", "")
        if text:
            headings.append((level, text, hid))

    inner = body.decode_contents()
    return f'<div id="{slug}" class="epub-chapter">\n{inner}\n</div>\n'


def _fix_link(href: str, current_slug: str, current_name: str, name_to_slug: dict) -> str:
    if href.startswith(("http://", "https://", "mailto:", "javascript:")):
        return href
    if href.startswith("#"):
        return f"#{current_slug}-{href[1:]}"

    parsed = urlparse(href)
    path = unquote(parsed.path)
    fragment = parsed.fragment

    current_dir = os.path.dirname(current_name)
    resolved = (
        os.path.normpath(os.path.join(current_dir, path)).replace("\\", "/")
        if current_dir
        else path
    )

    target_slug = name_to_slug.get(resolved) or name_to_slug.get(os.path.basename(path))
    if target_slug:
        return f"#{target_slug}-{fragment}" if fragment else f"#{target_slug}"
    return href


def _inline_image(src: str, current_item_name: str, items_by_name: dict, tmpdir: str) -> str:
    src = unquote(src)
    item = items_by_name.get(src)

    if not item:
        current_dir = os.path.dirname(current_item_name)
        resolved = os.path.normpath(os.path.join(current_dir, src)).replace("\\", "/")
        item = items_by_name.get(resolved)

    if not item:
        item = items_by_name.get(os.path.basename(src))

    if not item:
        current_dir = os.path.dirname(current_item_name)
        abs_path = os.path.normpath(os.path.join(tmpdir, current_dir, src))
        if os.path.isfile(abs_path):
            mime = _guess_mime(abs_path)
            with open(abs_path, "rb") as fh:
                return f"data:{mime};base64,{base64.b64encode(fh.read()).decode()}"
        return src

    try:
        data = item.get_content()
        mime = item.media_type or "image/jpeg"
        return f"data:{mime};base64,{base64.b64encode(data).decode()}"
    except Exception:
        return src


def _guess_mime(path: str) -> str:
    return {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png",  ".gif": "image/gif",
        ".svg": "image/svg+xml", ".webp": "image/webp",
    }.get(Path(path).suffix.lower(), "image/jpeg")


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

def _collect_epub_css(book, tmpdir: str) -> str:
    parts = []
    for item in book.get_items_of_type(ebooklib.ITEM_STYLE):
        try:
            css = item.get_content().decode("utf-8", errors="replace")
        except Exception:
            continue
        item_dir = os.path.join(tmpdir, os.path.dirname(item.get_name()))

        def replace_url(m: re.Match) -> str:
            raw_url = m.group(1).strip("\"'")
            if raw_url.startswith(("data:", "http://", "https://")):
                return m.group(0)
            abs_path = os.path.normpath(os.path.join(item_dir, raw_url))
            if os.path.isfile(abs_path):
                return f'url("{abs_path.replace(chr(92), "/")}")'
            return "none"

        css = re.sub(r'url\(\s*(["\']?[^"\')\s]+["\']?)\s*\)', replace_url, css)
        parts.append(css)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Font name normalisation
# ---------------------------------------------------------------------------

# Maps user-friendly/Chinese names → CSS font-family string Chromium resolves.
FONT_ALIASES: dict = {
    "微软雅黑":           "Microsoft YaHei",
    "微软雅黑 light":     "Microsoft YaHei Light",
    "宋体":               "SimSun",
    "新宋体":             "NSimSun",
    "黑体":               "SimHei",
    "楷体":               "KaiTi",
    "仿宋":               "FangSong",
    "幼圆":               "YouYuan",
    "隶书":               "LiSu",
    "华文楷体":           "STKaiti",
    "华文宋体":           "STSong",
    "华文黑体":           "STHeiti",
    "华文仿宋":           "STFangsong",
    "华文细黑":           "STXihei",
    "华文中宋":           "STZhongsong",
    "方正舒体":           "FZShuTi",
    "方正姚体":           "FZYaoTi",
    "苹方":               "PingFang SC",
    "思源宋体":           "Source Han Serif SC",
    "思源黑体":           "Source Han Sans SC",
    "霞鹜文楷":           "LXGW WenKai",
    # Japanese fonts (Windows optional feature: 日语补充字体 / Japanese Supplemental Fonts)
    "ms明朝":             "MS Mincho",
    "ms mincho":          "MS Mincho",
    "ms p明朝":           "MS PMincho",
    "ms pmincho":         "MS PMincho",
    "明朝":               "MS Mincho",
    # Traditional Chinese fonts (Windows optional feature: 繁体中文补充字体)
    "细明体":             "MingLiU",
    "新细明体":           "PMingLiU",
    "新細明體":           "PMingLiU",
    "細明體":             "MingLiU",
    "细明体_hkscs":       "MingLiU_HKSCS",
    "标楷体":             "DFKai-SB",
    # lowercase / common typos
    "mingliu":            "MingLiU",
    "pmingliu":           "PMingLiU",
    "microsoft yahei":    "Microsoft YaHei",
    "simsun":             "SimSun",
    "simhei":             "SimHei",
    "kaiti":              "KaiTi",
    "fangsong":           "FangSong",
    "times new roman":    "Times New Roman",
    "arial":              "Arial",
    "calibri":            "Calibri",
    "georgia":            "Georgia",
    "courier new":        "Courier New",
    "helvetica":          "Helvetica",
    "verdana":            "Verdana",
    "trebuchet ms":       "Trebuchet MS",
}


def normalize_font_name(name: str) -> str:
    """Return the canonical CSS font-family name for user input."""
    stripped = name.strip()
    return FONT_ALIASES.get(stripped.lower()) or FONT_ALIASES.get(stripped) or stripped


def _build_custom_css(
    font_family: str,
    cjk_font_family: str,
    code_font_family: str,
    font_size: int,
    line_height: float,
    margin: str,
) -> str:
    """
    Build override CSS.

    Font strategy:
    ┌──────────────┬──────────────────────────────────────────────────────┐
    │ latin only   │ latin font for everything; CJK chars fall back to    │
    │              │ Microsoft YaHei via the browser's system fallback    │
    ├──────────────┼──────────────────────────────────────────────────────┤
    │ cjk only     │ CJK font applied to all text with !important         │
    ├──────────────┼──────────────────────────────────────────────────────┤
    │ both         │ @font-face + unicode-range splits by script:         │
    │              │ Latin chars  → latin font                            │
    │              │ CJK chars    → cjk font (precise unicode ranges)     │
    ├──────────────┼──────────────────────────────────────────────────────┤
    │ neither      │ Microsoft YaHei default, preserve EPUB per-element   │
    └──────────────┴──────────────────────────────────────────────────────┘
    All user-specified fonts are applied with !important so EPUB inline
    styles (higher specificity) cannot win.
    """
    latin = normalize_font_name(font_family) if font_family else ""
    cjk   = normalize_font_name(cjk_font_family) if cjk_font_family else ""
    code  = normalize_font_name(code_font_family) if code_font_family else "Consolas"
    code_stack = f'"{code}", "Courier New", monospace'

    # CJK unicode-range — covers Chinese (Simplified + Traditional),
    # Japanese kana, Korean hangul, and related punctuation/symbols.
    CJK_RANGE = (
        "U+2E80-2EFF,"   # CJK Radicals Supplement
        "U+3000-303F,"   # CJK Symbols and Punctuation
        "U+3040-30FF,"   # Hiragana + Katakana
        "U+3400-4DBF,"   # CJK Extension A
        "U+4E00-9FFF,"   # CJK Unified Ideographs (core)
        "U+AC00-D7AF,"   # Hangul Syllables
        "U+F900-FAFF,"   # CJK Compatibility Ideographs
        "U+FE10-FE1F,"   # Vertical Forms
        "U+FE30-FE4F,"   # CJK Compatibility Forms
        "U+FF00-FFEF,"   # Halfwidth/Fullwidth Forms
        "U+20000-2A6DF," # CJK Extension B
        "U+2A700-2CEAF"  # CJK Extensions C/D/E
    )

    if latin and cjk:
        # ── Two-font composite via @font-face + unicode-range ──────────────
        # Chromium picks the face whose unicode-range covers each character.
        # CJK face declared first = higher priority for CJK code points.
        font_face = f"""
@font-face {{
    font-family: "epub2pdf-text";
    src: local("{cjk}");
    unicode-range: {CJK_RANGE};
}}
@font-face {{
    font-family: "epub2pdf-text";
    src: local("{latin}");
}}
"""
        font_stack = f'"epub2pdf-text", "{latin}", "{cjk}", sans-serif'

    elif cjk:
        # ── CJK font only ──────────────────────────────────────────────────
        font_face  = ""
        font_stack = f'"{cjk}", "Microsoft YaHei", "SimHei", sans-serif'

    elif latin:
        # ── Latin font only; CJK falls back through browser system fonts ──
        font_face  = ""
        font_stack = f'"{latin}", "Microsoft YaHei", "SimHei", "SimSun", sans-serif'

    else:
        # ── No override ────────────────────────────────────────────────────
        font_face  = ""
        font_stack = '"Microsoft YaHei", "SimHei", "SimSun", sans-serif'

    # Apply with !important whenever ANY font is chosen by the user
    apply_important = "!important" if (latin or cjk) else ""
    font_override = f"""
body, p, div, span, section, article, aside, nav, header, footer, main,
h1, h2, h3, h4, h5, h6,
li, ol, ul, dl, dt, dd,
td, th, caption, label,
blockquote, address, figure, figcaption, cite, q, ruby, rt, rp {{
    font-family: {font_stack} {apply_important};
}}
""" if (latin or cjk) else ""

    h1 = max(font_size + 8, int(font_size * 1.8))
    h2 = max(font_size + 5, int(font_size * 1.5))
    h3 = max(font_size + 2, int(font_size * 1.25))

    return f"""
/* ===== epub2pdf overrides ===== */
{font_face}
@page {{
    margin: {margin};
    @bottom-center {{
        content: counter(page);
        font-size: {max(8, font_size - 3)}pt;
        color: #888;
    }}
}}

* {{ box-sizing: border-box; }}

body {{
    font-family: {font_stack};
    font-size: {font_size}pt;
    line-height: {line_height};
    color: #1a1a1a;
    background: white;
    word-wrap: break-word;
    overflow-wrap: break-word;
}}

{font_override}

/* Monospace blocks are never overridden */
pre, code, tt, kbd, samp {{
    font-family: {code_stack} !important;
    font-size: {max(8, font_size - 2)}pt;
}}

h1 {{
    font-family: {font_stack};
    font-size: {h1}pt;
    font-weight: bold;
    line-height: 1.3;
    margin-top: 1.4em;
    margin-bottom: 0.5em;
    page-break-before: always;
    break-before: page;
}}

.epub-chapter:first-child > h1:first-child,
.epub-chapter:first-child > *:first-child h1:first-child {{
    page-break-before: avoid;
    break-before: avoid;
}}

h2 {{
    font-family: {font_stack};
    font-size: {h2}pt;
    font-weight: bold;
    line-height: 1.3;
    margin-top: 1em;
    margin-bottom: 0.4em;
}}

h3 {{
    font-family: {font_stack};
    font-size: {h3}pt;
    font-weight: bold;
    margin-top: 0.8em;
    margin-bottom: 0.3em;
}}

h4, h5, h6 {{
    font-family: {font_stack};
    font-size: {font_size}pt;
    font-weight: bold;
    margin-top: 0.6em;
    margin-bottom: 0.2em;
}}

p {{
    margin: 0 0 0.6em 0;
    orphans: 2;
    widows: 2;
}}

a {{ color: #1a56db; text-decoration: underline; }}

img, svg {{
    max-width: 100%;
    height: auto;
    display: block;
}}

pre {{
    font-family: {code_stack};
    font-size: {max(8, font_size - 2)}pt;
    background: #f8f8f8;
    border: 1px solid #ddd;
    padding: 0.8em;
    white-space: pre-wrap;
    word-break: break-all;
    page-break-inside: avoid;
    break-inside: avoid;
}}

code {{
    font-family: {code_stack};
    font-size: {max(8, font_size - 2)}pt;
    background: #f0f0f0;
    padding: 0.1em 0.3em;
    border-radius: 2px;
}}

blockquote {{
    border-left: 3px solid #ccc;
    margin: 0.5em 0 0.5em 1.5em;
    padding: 0.3em 0.8em;
    color: #555;
}}

table {{
    border-collapse: collapse;
    width: 100%;
    margin: 0.6em 0;
    page-break-inside: avoid;
    break-inside: avoid;
}}

th, td {{
    border: 1px solid #ccc;
    padding: 0.3em 0.5em;
    text-align: left;
    vertical-align: top;
}}

th {{ background: #f0f0f0; font-weight: bold; }}

.epub-chapter {{ margin-bottom: 0.5em; }}
"""


def _build_html(title: str, epub_css: str, custom_css: str, sections: list) -> str:
    body = "\n".join(sections)
    safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>{safe_title}</title>
<style>
{epub_css}
{custom_css}
</style>
</head>
<body>
{body}
</body>
</html>"""


# ---------------------------------------------------------------------------
# PDF rendering (playwright)
# ---------------------------------------------------------------------------

def _render_pdf(html: str, output_path: str, margin: str) -> None:
    """Render HTML to PDF using a Chromium-based browser."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "playwright 未安装。请重新运行 install.bat。"
        ) from exc

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", encoding="utf-8", delete=False
    ) as fh:
        fh.write(html)
        html_file = fh.name

    try:
        with sync_playwright() as pw:
            browser = _launch_browser(pw)
            try:
                page = browser.new_page()
                file_url = "file:///" + html_file.replace("\\", "/")
                page.goto(file_url, wait_until="networkidle", timeout=60_000)
                page.pdf(
                    path=output_path,
                    format="A4",
                    print_background=True,
                    # Margins handled by CSS @page; pass zeros here to avoid doubling
                    margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                    tagged=True,
                )
            finally:
                browser.close()
    finally:
        try:
            os.unlink(html_file)
        except OSError:
            pass


def _launch_browser(pw):
    """
    Try browsers in order:
      1. Microsoft Edge (pre-installed on Windows 10/11)
      2. Google Chrome
      3. Bundled Chromium (requires: playwright install chromium)
    """
    for channel in ("msedge", "chrome", None):
        try:
            return (
                pw.chromium.launch(channel=channel)
                if channel
                else pw.chromium.launch()
            )
        except Exception:
            continue

    raise RuntimeError(
        "未找到可用浏览器。\n"
        "解决方法（任选一）：\n"
        "  1. 安装 Microsoft Edge 或 Google Chrome\n"
        "  2. 在命令行运行: playwright install chromium"
    )


# ---------------------------------------------------------------------------
# PDF bookmark post-processing (pypdf)
# ---------------------------------------------------------------------------

def _add_bookmarks(pdf_path: str, headings: list) -> None:
    """
    Add a PDF outline (bookmark tree) to the generated PDF.

    Searches each page's extracted text for heading strings to determine
    page numbers, then writes bookmarks via pypdf.  Wrapped in try/except
    so a failure here never aborts the conversion — the PDF is already
    saved and usable without bookmarks.
    """
    if not headings:
        return
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        return

    try:
        reader = PdfReader(pdf_path)
        writer = PdfWriter(clone_reader=reader)

        # Extract text from every page once
        page_texts = []
        for page in reader.pages:
            try:
                page_texts.append(page.extract_text() or "")
            except Exception:
                page_texts.append("")

        parent_stack: list = []   # [(level, outline_item), ...]

        for level, text, _hid in headings:
            # Match using first 40 characters (handles truncation / formatting)
            search = text[:40].strip()
            found_page = None
            for page_num, page_text in enumerate(page_texts):
                if search in page_text:
                    found_page = page_num
                    break

            if found_page is None:
                continue

            # Maintain parent stack for nested bookmarks
            while parent_stack and parent_stack[-1][0] >= level:
                parent_stack.pop()

            parent = parent_stack[-1][1] if parent_stack else None
            item = writer.add_outline_item(text[:100], found_page, parent=parent)
            parent_stack.append((level, item))

        with open(pdf_path, "wb") as fh:
            writer.write(fh)

    except Exception:
        pass  # bookmarks are optional — PDF is still valid without them
