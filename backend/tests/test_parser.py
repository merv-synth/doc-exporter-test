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

    def test_normalize_handles_unicode(self) -> None:
        self.assertEqual(normalize("Ｈéllo—１２3"), "héllo123")


if __name__ == "__main__":
    unittest.main()
