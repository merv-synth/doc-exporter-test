from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from parser import parse_scenes_from_xliff
from reportlab.lib import colors

from pdf_generator import _clone_with_font, _escape_paragraph_text, generate_pdf, get_font_for_text


class PdfGeneratorTests(unittest.TestCase):
    def test_generate_pdf_renders_cjk_and_thai_content(self) -> None:
        scenes = [
            {
                "scene_id": "scene__i18n",
                "script": [
                    "繁體中文：歡迎使用文件匯出工具。",
                    "简体中文：欢迎使用文档导出工具。",
                    "ไทย: ยินดีต้อนรับสู่เครื่องมือส่งออกเอกสาร",
                    "한국어: 문서 내보내기 도구에 오신 것을 환영합니다.",
                    "日本語（丁寧）: ご利用ありがとうございます。",
                ],
            }
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "out.pdf"
            generate_pdf(scenes, output_path)
            pdf_bytes = output_path.read_bytes()

        # The generated document must contain at least one embedded unicode-capable font.
        self.assertIn(b"/HeiseiKakuGo-W5", pdf_bytes)


    def test_generate_pdf_structures_scene_heading_title_and_script_sections(self) -> None:
        scenes = [
            {
                "scene_id": "scene__1",
                "scene_title": "Welcome",
                "script": ["Line one", "Line two"],
            }
        ]

        paragraph_calls: list[str] = []

        def _fake_paragraph(text: str, _style):
            paragraph_calls.append(text)
            return text

        class _FakeDoc:
            def build(self, _story):
                return None

        with patch("pdf_generator.Paragraph", side_effect=_fake_paragraph), patch(
            "pdf_generator.SimpleDocTemplate", return_value=_FakeDoc()
        ):
            generate_pdf(scenes, Path("unused.pdf"))

        self.assertIn("Scene 1", paragraph_calls)
        self.assertIn("Title: Welcome", paragraph_calls)
        self.assertIn("Script:", paragraph_calls)
        self.assertIn("• Line one", paragraph_calls)
        self.assertIn("• Line two", paragraph_calls)

    def test_font_selection_for_target_languages(self) -> None:
        with patch("pdf_generator._register_thai_font", return_value="NotoSansThai"):
            self.assertEqual(get_font_for_text("ภาษาไทย"), "NotoSansThai")

        with patch("pdf_generator._register_thai_font", return_value=None), patch(
            "pdf_generator._register_unicode_ttf_fallback", return_value="DejaVuSans"
        ):
            self.assertEqual(get_font_for_text("ภาษาไทย"), "DejaVuSans")

        with patch("pdf_generator._register_font_candidates", return_value="HYSMyeongJo-Medium"):
            self.assertEqual(get_font_for_text("한국어"), "HYSMyeongJo-Medium")

        with patch("pdf_generator._register_font_candidates", return_value="HeiseiKakuGo-W5"):
            self.assertEqual(get_font_for_text("日本語です"), "HeiseiKakuGo-W5")

        with patch("pdf_generator._register_font_candidates", return_value="MSung-Light"):
            self.assertEqual(get_font_for_text("繁體中文"), "MSung-Light")

        with patch("pdf_generator._register_font_candidates", return_value="STSong-Light"):
            self.assertEqual(get_font_for_text("简体中文"), "STSong-Light")


    def test_escape_paragraph_text_disables_inline_font_color_markup(self) -> None:
        input_text = '<font color="white">สวัสดีค่ะ</font>'
        escaped = _escape_paragraph_text(input_text)

        self.assertEqual(escaped, '&lt;font color="white"&gt;สวัสดีค่ะ&lt;/font&gt;')

    def test_generate_pdf_from_parsed_api_style_thai_scene(self) -> None:
        payload = {
            "xliff": """<?xml version='1.0' encoding='utf-8'?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2" xmlns:syn="urn:synthesia:video"><file source-language="th"><body><group id="scene__th"><trans-unit id="script__scene__th"><source><g ctype="x-syn-voice" syn:voice-id="v1">สวัสดีค่ะ และยินดีต้อนรับ
คลิกที่นี่เพื่อดำเนินการต่อ</g></source></trans-unit></group></body></file></xliff>"""
        }

        scenes = parse_scenes_from_xliff(json.dumps(payload).encode("utf-8"))

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "thai.pdf"
            generate_pdf(scenes, output_path)
            pdf_bytes = output_path.read_bytes()

        self.assertGreater(len(pdf_bytes), 1000)
        self.assertIn(get_font_for_text("สวัสดีค่ะ").encode("utf-8"), pdf_bytes)

    def test_clone_with_font_enforces_black_text_and_bullets(self) -> None:
        from reportlab.lib.styles import ParagraphStyle

        base_style = ParagraphStyle("Body", textColor=colors.white, bulletColor=colors.white)
        cloned = _clone_with_font(base_style, "Line one", "BodyClone")

        self.assertEqual(cloned.textColor, colors.black)
        self.assertEqual(cloned.bulletColor, colors.black)


if __name__ == "__main__":
    unittest.main()
