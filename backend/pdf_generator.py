from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

LANGUAGE_FONT_CANDIDATES: dict[str, tuple[str, ...]] = {
    "japanese": ("HeiseiKakuGo-W5",),
    "chinese_traditional": ("MSung-Light", "HeiseiKakuGo-W5"),
    "chinese_simplified": ("STSong-Light", "HeiseiKakuGo-W5"),
    "korean": ("HYSMyeongJo-Medium", "HeiseiKakuGo-W5"),
}
THAI_FONT_CANDIDATES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "NotoSansThai",
        (
            "/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansThai-Regular.ttf",
        ),
    ),
    (
        "NotoSansThaiUI",
        (
            "/usr/share/fonts/truetype/noto/NotoSansThaiUI-Regular.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansThaiUI-Regular.ttf",
        ),
    ),
    (
        "TLWGGaruda",
        (
            "/usr/share/fonts/truetype/tlwg/Garuda.ttf",
            "/usr/share/fonts/truetype/tlwg/Garuda-Regular.ttf",
        ),
    ),
)
UNICODE_TTF_FALLBACK_NAME = "DejaVuSans"
UNICODE_TTF_FALLBACK_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
)
DEFAULT_UNICODE_FONT = "HeiseiKakuGo-W5"


def _register_cid_font(font_name: str) -> str | None:
    try:
        pdfmetrics.getFont(font_name)
        return font_name
    except KeyError:
        pass

    try:
        pdfmetrics.registerFont(UnicodeCIDFont(font_name))
        return font_name
    except Exception:
        return None


def _register_ttf_font(font_name: str, font_paths: tuple[str, ...]) -> str | None:
    try:
        pdfmetrics.getFont(font_name)
        return font_name
    except KeyError:
        pass

    for font_path in font_paths:
        if not Path(font_path).exists():
            continue

        try:
            pdfmetrics.registerFont(TTFont(font_name, font_path))
            return font_name
        except Exception:
            continue

    return None


def _register_thai_font() -> str | None:
    for font_name, font_paths in THAI_FONT_CANDIDATES:
        registered_font = _register_ttf_font(font_name, font_paths)
        if registered_font:
            return registered_font

    return None


def _register_unicode_ttf_fallback() -> str | None:
    try:
        pdfmetrics.getFont(UNICODE_TTF_FALLBACK_NAME)
        return UNICODE_TTF_FALLBACK_NAME
    except KeyError:
        pass

    return _register_ttf_font(UNICODE_TTF_FALLBACK_NAME, UNICODE_TTF_FALLBACK_PATHS)


def _is_thai(text: str) -> bool:
    return any("\u0E00" <= ch <= "\u0E7F" for ch in text)


def _is_hangul(text: str) -> bool:
    return any("\uAC00" <= ch <= "\uD7A3" for ch in text)


def _is_hiragana_or_katakana(text: str) -> bool:
    return any("\u3040" <= ch <= "\u30FF" for ch in text)


def _contains_cjk_unified(text: str) -> bool:
    return any("\u4E00" <= ch <= "\u9FFF" for ch in text)


def _prefer_traditional_chinese(text: str) -> bool:
    traditional_markers = "這個為與學體臺灣繁體龍門廣國"
    simplified_markers = "这个为与学体台湾繁体龙门广国"
    traditional_hits = sum(marker in text for marker in traditional_markers)
    simplified_hits = sum(marker in text for marker in simplified_markers)
    return traditional_hits >= simplified_hits


def _register_font_candidates(font_names: tuple[str, ...]) -> str | None:
    for font_name in font_names:
        registered = _register_cid_font(font_name)
        if registered:
            return registered
    return None


def get_font_for_text(text: str) -> str:
    """Return the best available font for the given text."""
    if _is_thai(text):
        thai_font = _register_thai_font()
        if thai_font:
            return thai_font

        unicode_ttf_fallback = _register_unicode_ttf_fallback()
        if unicode_ttf_fallback:
            return unicode_ttf_fallback

    if _is_hangul(text):
        korean_font = _register_font_candidates(LANGUAGE_FONT_CANDIDATES["korean"])
        if korean_font:
            return korean_font

    if _is_hiragana_or_katakana(text):
        japanese_font = _register_font_candidates(LANGUAGE_FONT_CANDIDATES["japanese"])
        if japanese_font:
            return japanese_font

    if _contains_cjk_unified(text):
        zh_key = "chinese_traditional" if _prefer_traditional_chinese(text) else "chinese_simplified"
        chinese_font = _register_font_candidates(LANGUAGE_FONT_CANDIDATES[zh_key])
        if chinese_font:
            return chinese_font

    fallback = _register_cid_font(DEFAULT_UNICODE_FONT)
    if fallback:
        return fallback

    return "Helvetica"


def _escape_paragraph_text(text: str) -> str:
    """Escape user-provided text so ReportLab does not apply inline XML styling."""
    return escape(text)


def _clone_with_font(style: ParagraphStyle, text: str, style_name: str) -> ParagraphStyle:
    style_with_font = style.clone(style_name)
    style_with_font.fontName = get_font_for_text(text)
    style_with_font.textColor = colors.black
    return style_with_font


def generate_pdf(scenes: list[dict[str, list[str] | str]], output_path: Path) -> None:
    """Generate a PDF from parsed scenes and script lines."""
    styles = getSampleStyleSheet()
    heading_base = styles["Heading2"]
    body_base = styles["BodyText"]

    story = []
    for scene in scenes:
        scene_id = str(scene["scene_id"])
        script_lines = scene["script"]

        heading_text = f"Scene: {scene_id}"
        heading_style = _clone_with_font(heading_base, heading_text, f"SceneHeading_{scene_id}")
        story.append(Paragraph(_escape_paragraph_text(heading_text), heading_style))
        story.append(Spacer(1, 4 * mm))

        for line_index, line in enumerate(script_lines):
            line_text = str(line)
            body_style = _clone_with_font(body_base, line_text, f"SceneBody_{scene_id}_{line_index}")
            story.append(Paragraph(_escape_paragraph_text(line_text), body_style))
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
