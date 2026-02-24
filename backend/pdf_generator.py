from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

JAPANESE_FONT_NAME = "HeiseiKakuGo-W5"


def _ensure_japanese_font_registered() -> str:
    """Register a CJK-capable font and return its name."""
    try:
        pdfmetrics.getFont(JAPANESE_FONT_NAME)
    except KeyError:
        pdfmetrics.registerFont(UnicodeCIDFont(JAPANESE_FONT_NAME))
    return JAPANESE_FONT_NAME


def generate_pdf(scenes: list[dict[str, list[str] | str]], output_path: Path) -> None:
    """Generate a PDF from parsed scenes and script lines."""
    styles = getSampleStyleSheet()
    heading_style = styles["Heading2"].clone("SceneHeadingCJK")
    body_style = styles["BodyText"].clone("SceneBodyCJK")

    cjk_font = _ensure_japanese_font_registered()
    heading_style.fontName = cjk_font
    body_style.fontName = cjk_font

    story = []
    for scene in scenes:
        scene_id = str(scene["scene_id"])
        script_lines = scene["script"]

        story.append(Paragraph(f"Scene: {scene_id}", heading_style))
        story.append(Spacer(1, 4 * mm))

        for line in script_lines:
            story.append(Paragraph(str(line), body_style))
            story.append(Spacer(1, 2.5 * mm))

        story.append(Spacer(1, 5 * mm))

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )
    doc.build(story)
