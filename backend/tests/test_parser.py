from __future__ import annotations

import json
import tempfile
import textwrap
import unittest
from pathlib import Path

from parser import normalize, parse_scenes_from_srt_and_xliff, parse_scenes_from_xliff, parse_srt


class ParserTests(unittest.TestCase):
    def test_parse_scenes_from_xliff_uses_voice_and_fallback_text(self) -> None:
        xliff = textwrap.dedent(
            """\
            <xliff xmlns=\"urn:oasis:names:tc:xliff:document:1.2\" version=\"1.2\">
              <file>
                <body>
                  <group id=\"scene_1\">
                    <trans-unit id=\"script__scene__1\">
                      <source><g tag=\"voice\">Hello there</g></source>
                    </trans-unit>
                    <trans-unit id=\"script__scene__2\">
                      <source>General Kenobi</source>
                    </trans-unit>
                  </group>
                  <group id=\"scene_2\">
                    <trans-unit id=\"layout__scene__2\"><source>Not script</source></trans-unit>
                  </group>
                </body>
              </file>
            </xliff>
            """
        ).encode("utf-8")

        scenes = parse_scenes_from_xliff(xliff)

        self.assertEqual(
            scenes,
            [{"scene_id": "scene_1", "script": ["Hello there", "General Kenobi"]}],
        )


    def test_parse_scenes_from_xliff_supports_json_wrapped_japanese_xliff(self) -> None:
        xliff = """<?xml version='1.0' encoding='utf-8'?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2"><file><body><group id="scene__ja"><trans-unit id="script__scene__ja"><source><g ctype="x-syn-voice">やあ、ようこそ。
次へ進むにはボタンをクリック。</g></source></trans-unit></group></body></file></xliff>"""
        payload = json.dumps({"xliff": xliff}).encode("utf-8")

        scenes = parse_scenes_from_xliff(payload)

        self.assertEqual(
            scenes,
            [{"scene_id": "scene__ja", "script": ["やあ、ようこそ。\n次へ進むにはボタンをクリック。"]}],
        )


    def test_parse_scenes_from_xliff_supports_json_wrapped_thai_xliff(self) -> None:
        xliff = """<?xml version='1.0' encoding='utf-8'?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2"><file><body><group id="scene__th"><trans-unit id="script__scene__th"><source><g ctype="x-syn-voice">สวัสดีค่ะ
คลิกที่นี่เพื่อดำเนินการต่อ</g></source></trans-unit></group></body></file></xliff>"""
        payload = json.dumps({"xliff": xliff}).encode("utf-8")

        scenes = parse_scenes_from_xliff(payload)

        self.assertEqual(
            scenes,
            [{"scene_id": "scene__th", "script": ["สวัสดีค่ะ\nคลิกที่นี่เพื่อดำเนินการต่อ"]}],
        )

    def test_parse_scenes_from_xliff_supports_api_style_thai_response(self) -> None:
        xliff = textwrap.dedent(
            """\
            <?xml version='1.0' encoding='utf-8'?>
            <xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2" xmlns:syn="urn:synthesia:video">
              <file original="TH demo" datatype="html" source-language="th" syn:video-id="v1" syn:snapshot-id="s1">
                <body>
                  <group id="scene__d056a155">
                    <trans-unit id="script__scene__d056a155">
                      <source><g id="1" ctype="x-syn-voice" syn:voice-id="voice-1">สวัสดีค่ะ และยินดีต้อนรับ\nคลิกที่นี่เพื่อดําเนินการต่อ</g></source>
                    </trans-unit>
                    <trans-unit id="element__title__scene__d056a155">
                      <source><g id="1" ctype="x-html-p">ภาพรวมชีวิต</g></source>
                    </trans-unit>
                  </group>
                  <group id="scene__0534f09e">
                    <trans-unit id="script__scene__0534f09e">
                      <source><g id="1" ctype="x-syn-voice" syn:voice-id="voice-1">แนวทางการนําทาง\nหากต้องการไปยังสไลด์ถัดไป</g></source>
                    </trans-unit>
                  </group>
                </body>
              </file>
            </xliff>
            """
        )
        payload = json.dumps({"xliff": xliff}).encode("utf-8")

        scenes = parse_scenes_from_xliff(payload)

        self.assertEqual(len(scenes), 2)
        self.assertEqual(scenes[0]["scene_id"], "scene__d056a155")
        self.assertIn("สวัสดีค่ะ", scenes[0]["script"][0])
        self.assertIn("คลิกที่นี่เพื่อดําเนินการต่อ", scenes[0]["script"][0])
        self.assertEqual(scenes[1]["scene_id"], "scene__0534f09e")

    def test_parse_scenes_from_xliff_supports_utf16_japanese_xliff(self) -> None:
        xliff = """<?xml version='1.0' encoding='utf-16'?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2"><file><body><group id="scene_utf16"><trans-unit id="script__scene__ja"><source><g tag="voice">日本語のテキストです。</g></source></trans-unit></group></body></file></xliff>""".encode("utf-16")

        scenes = parse_scenes_from_xliff(xliff)

        self.assertEqual(
            scenes,
            [{"scene_id": "scene_utf16", "script": ["日本語のテキストです。"]}],
        )

    def test_parse_srt_invalid_returns_empty(self) -> None:
        self.assertEqual(parse_srt("not an srt"), [])

    def test_parse_scenes_from_srt_and_xliff_builds_timeline_with_visual_scene(self) -> None:
        xliff = textwrap.dedent(
            """\
            <xliff xmlns=\"urn:oasis:names:tc:xliff:document:1.2\" version=\"1.2\">
              <file>
                <body>
                  <group id=\"s1\">
                    <trans-unit id=\"script__scene__1\"><source><g tag=\"voice\">Hello world</g></source></trans-unit>
                  </group>
                  <group id=\"v1\">
                    <trans-unit id=\"layout__scene__2\"><source>Visual only</source></trans-unit>
                  </group>
                  <group id=\"s2\">
                    <trans-unit id=\"script__scene__3\"><source>Bye now</source></trans-unit>
                  </group>
                </body>
              </file>
            </xliff>
            """
        )

        srt_text = textwrap.dedent(
            """\
            1
            00:00:00,000 --> 00:00:01,000
            Hello world

            2
            00:00:01,200 --> 00:00:02,000
            Bye now
            """
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            xliff_path = tmp_path / "captions.xliff"
            srt_path = tmp_path / "captions.srt"
            xliff_path.write_text(xliff, encoding="utf-8")
            srt_path.write_text(srt_text, encoding="utf-8")

            scenes = parse_scenes_from_srt_and_xliff(str(srt_path), str(xliff_path))

        self.assertEqual(len(scenes), 3)
        self.assertEqual(scenes[0]["id"], "s1")
        self.assertEqual(scenes[1]["id"], "v1")
        self.assertEqual(scenes[2]["id"], "s2")
        self.assertEqual(scenes[1]["script"], "[Visual Scene]")
        self.assertAlmostEqual(scenes[0]["start_time"], 0.0)
        self.assertAlmostEqual(scenes[0]["end_time"], 1.0)
        self.assertAlmostEqual(scenes[2]["start_time"], 1.2)
        self.assertAlmostEqual(scenes[2]["end_time"], 2.0)

    def test_parse_scenes_from_srt_and_xliff_supports_utf16_thai_xliff(self) -> None:
        xliff = """<?xml version='1.0' encoding='utf-16'?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2"><file><body><group id="scene_th"><trans-unit id="script__scene__th"><source><g ctype="x-syn-voice">สวัสดีค่ะ</g></source></trans-unit></group></body></file></xliff>""".encode("utf-16")

        srt_text = textwrap.dedent(
            """\
            1
            00:00:00,000 --> 00:00:01,000
            สวัสดีค่ะ
            """
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            xliff_path = tmp_path / "captions_utf16.xliff"
            srt_path = tmp_path / "captions.srt"
            xliff_path.write_bytes(xliff)
            srt_path.write_text(srt_text, encoding="utf-8")

            scenes = parse_scenes_from_srt_and_xliff(str(srt_path), str(xliff_path))

        self.assertEqual(len(scenes), 1)
        self.assertEqual(scenes[0]["id"], "scene_th")
        self.assertEqual(scenes[0]["script"], "สวัสดีค่ะ")
        self.assertAlmostEqual(scenes[0]["start_time"], 0.0)
        self.assertAlmostEqual(scenes[0]["end_time"], 1.0)

    def test_normalize_handles_unicode(self) -> None:
        self.assertEqual(normalize("Ｈéllo—１２3"), "héllo123")

    def test_normalize_preserves_thai_diacritics(self) -> None:
        self.assertEqual(normalize("ดําเนินการต่อ"), "ดําเนินการต่อ")


if __name__ == "__main__":
    unittest.main()
