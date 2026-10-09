#!/usr/bin/env python3
"""Build the technical-report PDF from the authoritative Markdown source."""

from __future__ import annotations

import html
import os
import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.build_paper import inline  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output/pdf/agent-retry-safety-report.pdf"
BLUE = colors.HexColor("#123b5d")
GRAY = colors.HexColor("#526578")


def typography(text: str) -> str:
    return text.translate(str.maketrans({"–": "-", "—": "-", "‑": "-"}))


def markup(text: str) -> str:
    return (
        inline(typography(text))
        .replace("<strong>", "<b>")
        .replace("</strong>", "</b>")
        .replace("<em>", "<i>")
        .replace("</em>", "</i>")
        .replace("<code>", '<font name="ReportMono" size="8.4">')
        .replace("</code>", "</font>")
    )


def build() -> None:
    font_dir = Path(
        os.environ.get("RETRY_SAFETY_FONT_DIR", "/usr/share/fonts/truetype/dejavu")
    )
    fonts = {
        "ReportSerif": "DejaVuSerif.ttf",
        "ReportSerifBold": "DejaVuSerif-Bold.ttf",
        "ReportSans": "DejaVuSans.ttf",
        "ReportSansBold": "DejaVuSans-Bold.ttf",
        "ReportMono": "DejaVuSansMono.ttf",
    }
    for name, filename in fonts.items():
        path = font_dir / filename
        if not path.is_file():
            raise SystemExit(
                f"Missing {path}; set RETRY_SAFETY_FONT_DIR to DejaVu fonts"
            )
        pdfmetrics.registerFont(TTFont(name, str(path)))
    pdfmetrics.registerFontFamily(
        "ReportSerif",
        normal="ReportSerif",
        bold="ReportSerifBold",
        italic="ReportSerif",
        boldItalic="ReportSerifBold",
    )
    pdfmetrics.registerFontFamily(
        "ReportSans",
        normal="ReportSans",
        bold="ReportSansBold",
        italic="ReportSans",
        boldItalic="ReportSansBold",
    )
    body = ParagraphStyle(
        "body",
        fontName="ReportSerif",
        fontSize=10,
        leading=14.5,
        spaceAfter=8,
        textColor=colors.HexColor("#1d2733"),
        splitLongWords=True,
        allowWidows=0,
        allowOrphans=0,
    )
    heading = ParagraphStyle(
        "heading",
        parent=body,
        fontName="ReportSansBold",
        fontSize=13,
        leading=17,
        textColor=BLUE,
        spaceBefore=15,
        spaceAfter=8,
        keepWithNext=True,
    )
    subheading = ParagraphStyle(
        "subheading",
        parent=heading,
        fontSize=10.5,
        leading=14,
        spaceBefore=10,
    )
    title_style = ParagraphStyle(
        "title",
        parent=heading,
        fontSize=22,
        leading=28,
        alignment=TA_CENTER,
        spaceBefore=0,
        spaceAfter=14,
    )
    author_style = ParagraphStyle(
        "author",
        parent=body,
        fontName="ReportSans",
        fontSize=11,
        alignment=TA_CENTER,
        spaceAfter=16,
    )
    table_style = ParagraphStyle(
        "table",
        parent=body,
        fontName="ReportSans",
        fontSize=8,
        leading=11,
        spaceAfter=0,
        splitLongWords=False,
    )
    metadata_style = ParagraphStyle(
        "metadata",
        parent=body,
        fontName="ReportSans",
        fontSize=8,
        leading=11,
        spaceAfter=2,
        textColor=GRAY,
    )
    code_style = ParagraphStyle(
        "code",
        parent=body,
        fontName="ReportMono",
        fontSize=7.4,
        leading=10,
        leftIndent=8,
        rightIndent=8,
        borderPadding=8,
        backColor=colors.HexColor("#f2f5f7"),
    )
    bullet_style = ParagraphStyle(
        "bullet",
        parent=body,
        leftIndent=15,
        firstLineIndent=0,
        bulletFontName="ReportSans",
        bulletFontSize=9,
    )
    source = (ROOT / "paper/paper.md").read_text(encoding="utf-8")
    story: list = []
    paragraph: list[str] = []
    table_lines: list[str] = []
    code_lines: list[str] = []
    in_code = False

    def flush_paragraph() -> None:
        if paragraph:
            story.append(Paragraph(markup(" ".join(paragraph)), body))
            paragraph.clear()

    def flush_table() -> None:
        if not table_lines:
            return
        rows = []
        for line in table_lines:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                continue
            rows.append([Paragraph(markup(c), table_style) for c in cells])
        width = A4[0] - 100
        if len(rows[0]) == 4:
            fractions = [0.15, 0.28, 0.40, 0.17]
        else:
            fractions = [0.23, 0.19, 0.15, 0.16, 0.12, 0.15]
        table = Table(rows, colWidths=[width * f for f in fractions], repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf2f9")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#dce3e9")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.append(KeepTogether([Spacer(1, 5), table, Spacer(1, 10)]))
        table_lines.clear()

    for line in source.splitlines():
        if line.startswith("```"):
            flush_paragraph()
            flush_table()
            if in_code:
                story.append(
                    KeepTogether(
                        [
                            Preformatted(typography("\n".join(code_lines)), code_style),
                            Spacer(1, 8),
                        ]
                    )
                )
                code_lines.clear()
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(line)
            continue
        if line.startswith("|"):
            flush_paragraph()
            table_lines.append(line)
            continue
        flush_table()
        if not line.strip():
            flush_paragraph()
            continue
        match = re.match(r"^(#{1,3}) (.*)$", line)
        if match:
            flush_paragraph()
            level, text = len(match[1]), match[2]
            style = title_style if level == 1 else heading if level == 2 else subheading
            story.append(Paragraph(markup(text), style))
            continue
        if line.startswith("**Author:** "):
            flush_paragraph()
            story.append(
                Paragraph(html.escape(line.removeprefix("**Author:** ")), author_style)
            )
            continue
        if line.startswith(
            (
                "**Technical report",
                "**Evidence snapshot",
                "**Manuscript revision",
                "**Repository",
                "**License",
                "**Release",
            )
        ):
            flush_paragraph()
            story.append(Paragraph(markup(line), metadata_style))
            continue
        match = re.match(r"^(?:- |(\d+)\. )(.*)$", line)
        if match:
            flush_paragraph()
            story.append(
                Paragraph(
                    markup(match[2]),
                    bullet_style,
                    bulletText=f"{match[1]}." if match[1] else "•",
                )
            )
            continue
        paragraph.append(line)
    flush_paragraph()
    flush_table()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    title = source.splitlines()[0].removeprefix("# ")
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=50,
        rightMargin=50,
        topMargin=46,
        bottomMargin=48,
        title=title,
        author="Karl von Poncet",
        subject="Technical report; conformance harness and exploratory model pilot",
    )

    def page_chrome(canvas, document) -> None:
        canvas.saveState()
        canvas.setFont("ReportSans", 8)
        canvas.setFillColor(GRAY)
        canvas.drawString(
            50, 26, "Karl von Poncet | Retry Safety Lab | Technical report v1.0"
        )
        canvas.drawRightString(A4[0] - 50, 26, str(document.page))
        canvas.restoreState()

    doc.build(story, onFirstPage=page_chrome, onLaterPages=page_chrome)
    print(f"built {OUTPUT}")


if __name__ == "__main__":
    build()
