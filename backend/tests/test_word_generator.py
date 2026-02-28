from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from word_generator import generate_word_document


class WordGeneratorTests(unittest.TestCase):
    def test_generate_word_document_includes_scene_details(self) -> None:
        scenes = [
            {
                "scene_id": "scene__1",
                "scene_title": "Intro",
                "script": ["Hello", "World"],
            }
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "export.docx"
            generate_word_document(scenes, output_path)
            self.assertTrue(output_path.exists())

            with ZipFile(output_path) as document_zip:
                doc_xml = document_zip.read("word/document.xml").decode("utf-8")

        self.assertIn("Synthesia Video Script Export", doc_xml)
        self.assertIn("Scene 1", doc_xml)
        self.assertIn("ID: scene__1", doc_xml)
        self.assertIn("Title: Intro", doc_xml)
        self.assertIn("Script:", doc_xml)
        self.assertIn("• Hello", doc_xml)
        self.assertIn("• World", doc_xml)


if __name__ == "__main__":
    unittest.main()
