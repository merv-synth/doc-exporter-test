from __future__ import annotations

import logging
import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


logger = logging.getLogger("doc_exporter.parser")
SRT_BLOCK_RE = re.compile(
    r"\s*(\d+)\s*\n"
    r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n"
    r"(.*?)(?=\n\s*\n|\Z)",
    re.DOTALL,
)


def sanitize_xliff_content(xliff_content: str) -> str:
    """Normalize XLIFF payload before XML parsing."""
    if not xliff_content:
        return ""

    stripped = xliff_content.lstrip("\ufeff\n\r\t ")
    xliff_start = stripped.find("<")
    return stripped[xliff_start:] if xliff_start >= 0 else stripped


def normalize(text: str) -> str:
    """Unicode-aware normalization for matching across all scripts."""
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text)
    return "".join(
        ch
        for ch in text.casefold()
        if unicodedata.category(ch)[0] in ("L", "N")
    )


def _srt_time_to_seconds(timecode: str) -> float:
    hours, minutes, seconds_ms = timecode.split(":")
    seconds, millis = seconds_ms.split(",")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000


def parse_srt(srt_content: str) -> list[dict[str, Any]]:
    """Parse an SRT payload into timing/content dictionaries."""
    cues: list[dict[str, Any]] = []

    for match in SRT_BLOCK_RE.finditer(srt_content):
        start = _srt_time_to_seconds(match.group(2))
        end = _srt_time_to_seconds(match.group(3))
        content = match.group(4).strip()
        cues.append({"start": start, "end": end, "content": content})

    if not cues:
        logger.error("SRT parse error: no valid cue blocks found")

    return cues


def _get_xliff_paths(root: ET.Element) -> tuple[dict[str, str], str, str, str, str]:
    ns = {"ns": "urn:oasis:names:tc:xliff:document:1.2"}
    if not root.findall(".//ns:group", ns):
        ns = {}

    if ns:
        return ns, ".//ns:group", "ns:trans-unit", "ns:source", ".//ns:g[@tag='voice']"
    return ns, ".//group", "trans-unit", "source", ".//g[@tag='voice']"


def parse_scenes_from_xliff(xliff_content: bytes) -> list[dict[str, list[str] | str]]:
    """Parse Synthesia scene scripts from an XLIFF 1.2 document with namespace safety."""
    cleaned = sanitize_xliff_content(xliff_content.decode("utf-8", errors="ignore"))

    try:
        root = ET.fromstring(cleaned)
    except ET.ParseError as exc:
        logger.error("XLIFF parse error after sanitization: %s", exc)
        raise ValueError("Invalid XLIFF content") from exc

    ns, group_path, trans_unit_path, source_path, voice_path = _get_xliff_paths(root)

    scenes: list[dict[str, list[str] | str]] = []
    for group in root.findall(group_path, ns):
        scene_id = group.attrib.get("id") or group.attrib.get("resname") or "unknown_scene"

        lines: list[str] = []
        for trans_unit in group.findall(trans_unit_path, ns):
            trans_unit_id = trans_unit.attrib.get("id", "")
            if not trans_unit_id.startswith("script__scene__"):
                continue

            source = trans_unit.find(source_path, ns)
            if source is None:
                continue

            had_voice_text = False
            for voice in source.findall(voice_path, ns):
                text = "".join(voice.itertext()).strip()
                if text:
                    lines.append(text)
                    had_voice_text = True

            if not had_voice_text:
                source_text = "".join(source.itertext()).strip()
                if source_text:
                    lines.append(source_text)

        if lines:
            scenes.append({"scene_id": scene_id, "script": lines})

    return scenes


def parse_scenes_from_srt_and_xliff(srt_path: str, xliff_path: str) -> list[dict[str, Any]]:
    """Extract scenes from XLIFF and align script scenes against SRT cue timings."""
    xliff_raw = Path(xliff_path).read_text(encoding="utf-8", errors="ignore")
    cleaned = sanitize_xliff_content(xliff_raw)

    root = ET.fromstring(cleaned)
    ns, group_path, trans_unit_path, source_path, voice_path = _get_xliff_paths(root)

    all_scenes_from_xliff: list[dict[str, Any]] = []
    for i, group in enumerate(root.findall(group_path, ns)):
        gid = group.attrib.get("id", "")

        parts: list[str] = []
        for trans_unit in group.findall(trans_unit_path, ns):
            trans_unit_id = trans_unit.attrib.get("id", "")
            if not trans_unit_id.startswith("script__scene__"):
                continue

            source = trans_unit.find(source_path, ns)
            if source is None:
                continue

            had_voice_text = False
            for voice in source.findall(voice_path, ns):
                text = "".join(voice.itertext()).strip()
                if text:
                    parts.append(text)
                    had_voice_text = True

            if not had_voice_text:
                source_text = "".join(source.itertext()).strip()
                if source_text:
                    parts.append(source_text)

        full_text = " ".join(parts).strip()
        all_scenes_from_xliff.append(
            {
                "id": gid,
                "script": full_text,
                "is_script_scene": bool(full_text),
                "original_order": i,
            }
        )

    srt_content = Path(srt_path).read_text(encoding="utf-8")
    srt_cues = parse_srt(srt_content)
    for cue in srt_cues:
        cue["norm"] = normalize(cue["content"])

    script_scenes_with_timing: list[dict[str, Any]] = []
    script_scenes_to_match = [scene for scene in all_scenes_from_xliff if scene["is_script_scene"]]

    scene_idx = 0
    accumulated_norm_text = ""
    scene_start_time: float | None = None

    for srt_block in srt_cues:
        if scene_idx >= len(script_scenes_to_match):
            break

        if scene_start_time is None:
            scene_start_time = srt_block["start"]

        accumulated_norm_text += srt_block["norm"]

        current_scene = script_scenes_to_match[scene_idx]
        target_norm_text = normalize(current_scene["script"])

        if target_norm_text and target_norm_text in accumulated_norm_text:
            end_time = srt_block["end"]

            current_scene["start_time"] = scene_start_time
            current_scene["end_time"] = end_time
            current_scene["screenshot_time"] = end_time - 0.2
            script_scenes_with_timing.append(current_scene)

            scene_idx += 1
            accumulated_norm_text = ""
            scene_start_time = None

    final_ordered_scenes: list[dict[str, Any]] = []
    script_scene_timeline = {scene["original_order"]: scene for scene in script_scenes_with_timing}

    last_end_time = 0.0

    for i, scene_data in enumerate(all_scenes_from_xliff):
        if scene_data["is_script_scene"]:
            if i in script_scene_timeline:
                timed_scene = script_scene_timeline[i]
                final_ordered_scenes.append(
                    {
                        "id": timed_scene["id"],
                        "title": f"Scene {len(final_ordered_scenes) + 1}",
                        "script": timed_scene["script"],
                        "start_time": timed_scene["start_time"],
                        "end_time": timed_scene["end_time"],
                        "screenshot_time": timed_scene["screenshot_time"],
                    }
                )
                last_end_time = timed_scene["end_time"]
        else:
            next_script_scene_start = None
            for j in range(i + 1, len(all_scenes_from_xliff)):
                if j in script_scene_timeline:
                    next_script_scene_start = script_scene_timeline[j]["start_time"]
                    break

            start_time = last_end_time
            end_time = next_script_scene_start if next_script_scene_start is not None else start_time + 2.0
            final_ordered_scenes.append(
                {
                    "id": scene_data["id"],
                    "title": f"Scene {len(final_ordered_scenes) + 1}",
                    "script": "[Visual Scene]",
                    "start_time": start_time,
                    "end_time": end_time,
                    "screenshot_time": (start_time + end_time) / 2,
                }
            )
            last_end_time = end_time

    return final_ordered_scenes
