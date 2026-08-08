#!/usr/bin/env python3
"""技术报告 Markdown → PDF 转换脚本（weasyprint，A4/宋体小四/1.5 倍行距）。

用法: python3 report/build_pdf.py
输出: report/技术报告.pdf
依赖: pip install weasyprint markdown-it-py
"""
import re
import sys
from pathlib import Path

from markdown_it import MarkdownIt
from weasyprint import HTML

REPORT_DIR = Path(__file__).resolve().parent
MD_PATH = REPORT_DIR / "技术报告.md"
PDF_PATH = REPORT_DIR / "技术报告.pdf"

CSS = """
@page {
    size: A4;
    margin: 2.5cm 2.2cm 2.5cm 2.2cm;
    @bottom-center {
        content: counter(page);
        font-family: "Noto Serif CJK SC", serif;
        font-size: 10pt;
        color: #555;
    }
}
body {
    font-family: "Noto Serif CJK SC", "AR PL UMing CN", serif;
    font-size: 12pt;            /* 小四 */
    line-height: 1.5;           /* 1.5 倍行距 */
    text-align: justify;
    color: #000;
}
/* 封面 */
h1.cover-title {
    text-align: center;
    font-size: 20pt;
    margin-top: 3cm;
    margin-bottom: 0.6cm;
}
p.cover-sub {
    text-align: center;
    font-size: 14pt;
    margin-bottom: 1.2cm;
}
table.cover-table {
    width: 70%;
    margin: 0 auto 1cm auto;
    border: none;
    font-size: 12pt;
}
table.cover-table td {
    border: none;
    padding: 0.25em 0.4em;
}
table.cover-table td:first-child {
    width: 30%;
    font-weight: bold;
    text-align: right;
    color: #333;
}
blockquote.cover-note {
    width: 70%;
    margin: 0 auto;
    border: 1px solid #999;
    padding: 0.6em 1em;
    font-size: 10.5pt;
    color: #444;
    background: #fafafa;
}
/* 正文标题 */
h1, h2, h3, h4 {
    font-family: "Noto Serif CJK SC", serif;
    font-weight: bold;
    color: #000;
    page-break-after: avoid;
}
h1 { font-size: 16pt; margin: 1.2em 0 0.6em 0; border-bottom: 2px solid #333; padding-bottom: 0.2em; }
h2 { font-size: 14pt; margin: 1.0em 0 0.5em 0; }
h3 { font-size: 12.5pt; margin: 0.8em 0 0.4em 0; }
h4 { font-size: 12pt; margin: 0.6em 0 0.3em 0; }
p { margin: 0.35em 0 0.35em 0; }
ul, ol { margin: 0.35em 0; padding-left: 1.8em; }
li { margin: 0.12em 0; }
strong { font-weight: bold; }
a { color: #000; text-decoration: none; }
/* 表格 */
table {
    border-collapse: collapse;
    width: 100%;
    font-size: 10.5pt;
    margin: 0.5em 0 0.8em 0;
    page-break-inside: auto;
}
th, td {
    border: 1px solid #666;
    padding: 0.28em 0.45em;
    text-align: left;
    vertical-align: top;
}
th { background: #efefef; font-weight: bold; }
tr { page-break-inside: avoid; }
/* 代码 */
pre {
    font-family: "DejaVu Sans Mono", "Noto Sans Mono", monospace;
    font-size: 9pt;
    line-height: 1.3;
    background: #f6f6f6;
    border: 1px solid #ccc;
    padding: 0.5em 0.7em;
    white-space: pre;
    overflow: hidden;
    page-break-inside: avoid;
    margin: 0.5em 0;
}
code {
    font-family: "DejaVu Sans Mono", "Noto Sans Mono", monospace;
    font-size: 10pt;
    background: #f2f2f2;
    padding: 0 0.2em;
}
pre code { background: none; padding: 0; font-size: 9pt; }
/* 分隔线 */
hr { border: none; border-top: 1px solid #999; margin: 1em 0; }
/* 引用 */
blockquote {
    border-left: 3px solid #999;
    margin: 0.5em 0;
    padding: 0.1em 1em;
    color: #333;
}
"""


def cover_transform(html: str) -> str:
    """给封面（第一个 h1 + 第一个表格 + 引用块）加样式类。"""
    html = re.sub(
        r"<h1>(.*?)</h1>", r"<h1 class=\"cover-title\">\1</h1>", html, count=1
    )
    html = re.sub(
        r"<p><em>.*?</em></p>",
        lambda m: m.group(0),
        html,
        count=0,
    )
    # 封面副标题：紧跟标题的加粗行 "—— 最终技术报告 ——"
    html = re.sub(
        r"<p><strong>—— (.*?) ——</strong></p>",
        r"<p class=\"cover-sub\">—— \1 ——</p>",
        html,
        count=1,
    )
    # 第一个表格 → 封面信息表
    parts = html.split("<table>", 1)
    if len(parts) == 2:
        html = parts[0] + "<table class=\"cover-table\">" + parts[1]
    # 封面后的格式说明引用块
    html = re.sub(
        r"<blockquote>\s*<p>([^<]*格式说明[^<]*)</p>\s*</blockquote>",
        r"<blockquote class=\"cover-note\"><p>\1</p></blockquote>",
        html,
        count=1,
    )
    # 第一个 hr 后换页（封面页结束）
    html = re.sub(r"<hr />", "<div style=\"page-break-after: always;\"></div><hr />", html, count=1)
    return html


def main() -> int:
    md_text = MD_PATH.read_text(encoding="utf-8")
    md = MarkdownIt("js-default")
    body = md.render(md_text)
    body = cover_transform(body)
    html_doc = (
        "<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        f"<style>{CSS}</style></head><body>{body}</body></html>"
    )
    HTML(string=html_doc, base_url=str(REPORT_DIR)).write_pdf(str(PDF_PATH))
    print(f"OK -> {PDF_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
