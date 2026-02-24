from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pdf_generator import generate_pdf


class PdfGeneratorTests(unittest.TestCase):
    def test_generate_pdf_registers_japanese_capable_font(self) -> None:
        scenes = [{"scene_id": "scene__ja", "script": ["やあ、ようこそ。", "次へ進むにはボタンをクリック。"]}]

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "out.pdf"
            generate_pdf(scenes, output_path)
            pdf_bytes = output_path.read_bytes()

        self.assertIn(b"/HeiseiKakuGo-W5", pdf_bytes)


if __name__ == "__main__":
    unittest.main()
