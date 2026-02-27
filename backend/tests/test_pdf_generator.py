from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pdf_generator import generate_pdf, get_font_for_text


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


if __name__ == "__main__":
    unittest.main()
