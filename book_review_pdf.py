#!/usr/bin/env python3
"""通用书评 Markdown → PDF 生成器 (reportlab + Songti)"""

import re
import sys
import os

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── 字体 ──────────────────────────────────────────────
TTC_PATH = "/System/Library/Fonts/Supplemental/Songti.ttc"
FONT_NAME = "Songti"
FONT_BOLD = "Songti-Bold"
FONT_ITALIC = "Songti-Italic"

# Songti.ttc subfontIndex:
#   0 = Songti SC / Black  (特粗)
#   1 = Songti SC / Bold   (粗体)
#   2 = Songti TC / Bold
#   3 = Songti SC / Light
#   4 = STSong / Regular
#   5 = Songti TC / Light
#   6 = Songti SC / Regular
#   7 = Songti TC / Regular

# 正文体用 Regular (index=6)，粗体用 Bold (index=1)
pdfmetrics.registerFont(TTFont(FONT_NAME, TTC_PATH, subfontIndex=6))
pdfmetrics.registerFont(TTFont(FONT_BOLD, TTC_PATH, subfontIndex=1))
pdfmetrics.registerFont(TTFont(FONT_ITALIC, TTC_PATH, subfontIndex=3))  # Light 充当斜体

# 注册字体映射，让 <b> 标签自动用 Bold
from reportlab.pdfbase.pdfmetrics import registerFontFamily
registerFontFamily(FONT_NAME, normal=FONT_NAME, bold=FONT_BOLD, italic=FONT_ITALIC, boldItalic=FONT_BOLD)

# 尝试注册粗体（用 subfontIndex=1 或 fallback）
try:
    pdfmetrics.registerFont(TTFont(FONT_NAME + "-Bold", TTC_PATH, subfontIndex=1))
except Exception:
    try:
        pdfmetrics.registerFont(TTFont(FONT_NAME + "-Bold", TTC_PATH, subfontIndex=0))
    except Exception:
        pass

try:
    pdfmetrics.registerFont(TTFont(FONT_NAME + "-Italic", TTC_PATH, subfontIndex=2))
except Exception:
    try:
        pdfmetrics.registerFont(TTFont(FONT_NAME + "-Italic", TTC_PATH, subfontIndex=0))
    except Exception:
        pass

# ── 颜色 ──────────────────────────────────────────────
COLOR_BODY = HexColor("#1e1e1e")
COLOR_H1 = HexColor("#333333")
COLOR_H2 = HexColor("#444444")
COLOR_META = HexColor("#555555")
COLOR_QUOTE = HexColor("#503c28")
COLOR_LINE = HexColor("#b4966a")
COLOR_FOOTER = HexColor("#999999")

# ── 样式 ──────────────────────────────────────────────
def make_styles():
    styles = {}
    styles["title"] = ParagraphStyle(
        "title", fontName=FONT_NAME, fontSize=20, leading=28,
        alignment=TA_CENTER, textColor=COLOR_H1, spaceAfter=4,
    )
    styles["title_sub"] = ParagraphStyle(
        "title_sub", fontName=FONT_NAME, fontSize=14, leading=20,
        alignment=TA_CENTER, textColor=COLOR_H1, spaceAfter=4,
    )
    styles["h2"] = ParagraphStyle(
        "h2", fontName=FONT_NAME, fontSize=14, leading=22,
        textColor=COLOR_H2, spaceBefore=12, spaceAfter=6,
    )
    styles["subtitle"] = ParagraphStyle(
        "subtitle", fontName=FONT_NAME, fontSize=14, leading=22,
        alignment=TA_CENTER, textColor=COLOR_META, spaceAfter=4,
    )
    styles["meta"] = ParagraphStyle(
        "meta", fontName=FONT_NAME, fontSize=10, leading=16,
        textColor=COLOR_META, spaceAfter=2,
    )
    styles["body"] = ParagraphStyle(
        "body", fontName=FONT_NAME, fontSize=11, leading=20,
        alignment=TA_JUSTIFY, textColor=COLOR_BODY,
        firstLineIndent=24, spaceAfter=6,
    )
    styles["body_noindent"] = ParagraphStyle(
        "body_ni", fontName=FONT_NAME, fontSize=11, leading=20,
        alignment=TA_JUSTIFY, textColor=COLOR_BODY, spaceAfter=6,
    )
    styles["quote"] = ParagraphStyle(
        "quote", fontName=FONT_NAME, fontSize=10.5, leading=18,
        leftIndent=30, rightIndent=10, textColor=COLOR_QUOTE,
        spaceBefore=6, spaceAfter=6, borderPadding=4,
    )
    styles["sign"] = ParagraphStyle(
        "sign", fontName=FONT_NAME, fontSize=11, leading=18,
        alignment=TA_CENTER, textColor=COLOR_BODY, spaceBefore=12,
    )
    styles["footer"] = ParagraphStyle(
        "footer", fontName=FONT_NAME, fontSize=8, leading=10,
        alignment=TA_CENTER, textColor=COLOR_FOOTER,
    )
    return styles


# ── Markdown 解析 ─────────────────────────────────────
def md_escape(text):
    """转义 reportlab 不支持的字符"""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    # reportlab Paragraph 支持 <b><i> 标签，需保留
    return text


def inline_format(text):
    """处理 **bold** 和 *italic* 行内格式"""
    text = md_escape(text)
    # **bold** → <b>bold</b>
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    # *italic* → <i>italic</i>  (注意不匹配 **)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
    return text


def parse_md(md_text):
    """解析 markdown，返回 flowables 列表"""
    styles = make_styles()
    flowables = []
    lines = md_text.strip().split("\n")
    i = 0

    # 图片路径基于 md 文件所在目录
    base_dir = os.path.dirname(os.path.abspath(md_file_path)) if md_file_path else "."

    while i < len(lines):
        line = lines[i].rstrip()

        # 跳过空行
        if not line.strip():
            i += 1
            continue

        # H1 标题
        if line.startswith("# ") and not line.startswith("## "):
            title_text = line[2:].strip()
            # 检查标题中是否包含 ——（破折号），如果有则分成主标题+副标题
            if "——" in title_text:
                dash_idx = title_text.index("——")
                main_title = title_text[:dash_idx].rstrip()
                sub_title = "——" + title_text[dash_idx + 2:]
                flowables.append(Paragraph(inline_format(main_title), styles["title"]))
                flowables.append(Paragraph(inline_format(sub_title), styles["title_sub"]))
            else:
                flowables.append(Paragraph(inline_format(title_text), styles["title"]))
            # 向下查找副标题（跳过空行，找以 —— 开头的行）
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and lines[j].strip().startswith("——"):
                flowables.append(Paragraph(inline_format(lines[j].strip()), styles["subtitle"]))
                flowables.append(Spacer(1, 6))
                i = j + 1
            else:
                flowables.append(Spacer(1, 6))
                i += 1
            continue

        # H2/H3
        if line.startswith("## "):
            flowables.append(Paragraph(inline_format(line[3:].strip()), styles["h2"]))
            i += 1
            continue

        if line.startswith("### "):
            flowables.append(Paragraph(inline_format(line[4:].strip()), styles["h2"]))
            i += 1
            continue

        # 水平线 ---
        if re.match(r"^-{3,}$", line.strip()):
            flowables.append(Spacer(1, 4))
            flowables.append(HRFlowable(
                width="50%", thickness=0.5, color=COLOR_LINE,
                hAlign="CENTER", spaceBefore=2, spaceAfter=8,
            ))
            i += 1
            continue

        # 图片 ![alt](path)
        img_match = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", line)
        if img_match:
            img_path = img_match.group(2)
            # 如果是相对路径，基于 md 文件目录
            if not os.path.isabs(img_path):
                img_path = os.path.join(base_dir, img_path)
            if os.path.exists(img_path):
                # 图片宽度自适应，最大 120mm
                from reportlab.lib.utils import ImageReader
                img_reader = ImageReader(img_path)
                iw, ih = img_reader.getSize()
                # daliao.jpg 签名图缩小一半
                if os.path.basename(img_path) == "daliao.jpg":
                    max_w = 20 * mm
                    max_h = 25 * mm
                elif os.path.basename(img_path) == "OnTheRoad.png":
                    max_w = 144 * mm  # 120mm * 1.2，放大20%
                    max_h = 144 * mm
                else:
                    max_w = 120 * mm
                    max_h = 144 * mm  # 160mm * 0.9 = 144mm，高度减少10%
                ratio = min(max_w / iw, max_h / ih, 1.0)
                w = iw * ratio
                h = ih * ratio
                img = Image(img_path, width=w, height=h)
                img.hAlign = "CENTER"
                flowables.append(Spacer(1, 4))
                flowables.append(img)
                # 不在末尾加 Spacer，避免空白页
            i += 1
            continue

        # 署名行 *大米斗...*
        if line.strip().startswith("*") and line.strip().endswith("*") and "大米斗" in line:
            # 去掉首尾 *
            sign_text = line.strip()[1:-1]
            sign_para = Paragraph(inline_format(sign_text), styles["sign"])
            # 检查下一行是否是 daliao.jpg 图片，如果是则绑定在一起不分页
            if i + 1 < len(lines) and "daliao.jpg" in lines[i + 1]:
                from reportlab.platypus import KeepTogether
                # 先移除最后一个 Spacer（如果有）
                while flowables and isinstance(flowables[-1], Spacer):
                    flowables.pop()
                # 构建图片
                img_path = "daliao.jpg"
                if not os.path.isabs(img_path):
                    img_path = os.path.join(base_dir, img_path)
                if os.path.exists(img_path):
                    from reportlab.lib.utils import ImageReader
                    img_reader = ImageReader(img_path)
                    iw, ih = img_reader.getSize()
                    max_w = 20 * mm
                    max_h = 25 * mm
                    ratio = min(max_w / iw, max_h / ih, 1.0)
                    w = iw * ratio
                    h = ih * ratio
                    img = Image(img_path, width=w, height=h)
                    img.hAlign = "CENTER"
                    flowables.append(KeepTogether([sign_para, Spacer(1, 2), img]))
                    i += 2  # 跳过署名和图片两行
                    continue
            flowables.append(sign_para)
            i += 1
            continue

        # 引用块 > 
        if line.strip().startswith(">"):
            quote_text = line.strip().lstrip(">").strip()
            # 收集多行引用
            while i + 1 < len(lines) and lines[i + 1].strip().startswith(">"):
                i += 1
                quote_text += " " + lines[i].strip().lstrip(">").strip()
            flowables.append(Paragraph(inline_format(quote_text), styles["quote"]))
            i += 1
            continue

        # 出版信息行（**书名：** 开头）
        if line.strip().startswith("**书名") or line.strip().startswith("**书名："):
            flowables.append(Paragraph(inline_format(line.strip()), styles["meta"]))
            i += 1
            continue

        # 普通段落（收集连续非空非特殊行）
        para_lines = [line]
        while i + 1 < len(lines):
            next_line = lines[i + 1].rstrip()
            if (not next_line.strip() or
                next_line.startswith("#") or
                next_line.startswith("![") or
                next_line.startswith("---") or
                next_line.strip().startswith(">") or
                next_line.strip().startswith("*大米斗") or
                (next_line.strip().startswith("**书名"))):
                break
            i += 1
            para_lines.append(next_line)

        para_text = " ".join(para_lines)
        # 判断是否需要首行缩进：交叉引用、一句话等无标题段落也缩进
        flowables.append(Paragraph(inline_format(para_text), styles["body"]))
        i += 1

    return flowables


# ── 页眉页脚 ─────────────────────────────────────────
def on_page(canvas, doc):
    canvas.saveState()
    # 页脚页码
    canvas.setFont(FONT_NAME, 8)
    canvas.setFillColor(COLOR_FOOTER)
    canvas.drawCentredString(A4[0] / 2, 15, f"— {doc.page} —")
    canvas.restoreState()


# ── 主流程 ───────────────────────────────────────────
def generate_pdf(md_path, output_path=None):
    global md_file_path
    md_file_path = md_path

    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    if output_path is None:
        # 输出到 md 文件同目录
        base = os.path.splitext(md_path)[0]
        output_path = base + ".pdf"

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=25 * mm, rightMargin=25 * mm,
        topMargin=25 * mm, bottomMargin=25 * mm,
    )

    flowables = parse_md(md_text)
    # 去掉末尾多余的 Spacer
    while flowables and isinstance(flowables[-1], Spacer):
        flowables.pop()
    doc.build(flowables, onFirstPage=on_page, onLaterPages=on_page)

    print(f"PDF saved to: {output_path}")
    print(f"Pages: {doc.page}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 book_review_pdf.py <markdown_file> [output_pdf]")
        sys.exit(1)
    md_path = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    generate_pdf(md_path, out)