from __future__ import annotations

import logging
import json
import html
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
VTT_BLOCK_RE = re.compile(
    r"(?:\n|\A)(?:\d+\s*\n)?"
    r"(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})\s*\n"
    r"(.*?)(?=\n\s*\n|\Z)",
    re.DOTALL,
)


def _find_xliff_value(payload: Any) -> str | None:
    """Recursively find an XLIFF/XML string in JSON-like payloads."""
    if isinstance(payload, str):
        if "<xliff" in payload or payload.lstrip().startswith("<?xml"):
            return payload
        if "&lt;xliff" in payload:
            unescaped = html.unescape(payload)
            if "<xliff" in unescaped:
                return unescaped
        return None

    if isinstance(payload, dict):
        for key in ("xliff", "content", "data"):
            if key in payload:
                found = _find_xliff_value(payload[key])
                if found:
                    return found

        for value in payload.values():
            found = _find_xliff_value(value)
            if found:
                return found

    if isinstance(payload, list):
        for value in payload:
            found = _find_xliff_value(value)
            if found:
                return found

    return None


def sanitize_xliff_content(xliff_content: str) -> str:
    """Normalize XLIFF payload before XML parsing."""
    if not xliff_content:
        return ""

    text = xliff_content.strip()

    if text.startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None

        extracted = _find_xliff_value(payload)
        if extracted:
            text = extracted

    stripped = text.lstrip("\ufeff\n\r\t ")
    xliff_start = stripped.find("<")
    return stripped[xliff_start:] if xliff_start >= 0 else stripped


def _decode_xliff_bytes(xliff_content: bytes) -> str:
    """Decode XLIFF bytes while preserving non-ASCII text where possible."""
    if not xliff_content:
        return ""

    for encoding in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            decoded = xliff_content.decode(encoding)
        except UnicodeDecodeError:
            continue

        if "<xliff" in decoded or decoded.lstrip().startswith("{"):
            return decoded

    return xliff_content.decode("utf-8", errors="replace")


def normalize(text: str) -> str:
    """Unicode-aware normalization for matching across all scripts."""
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text)
    return "".join(
        ch
        for ch in text.casefold()
        if unicodedata.category(ch)[0] in ("L", "N", "M")
    )


def _srt_time_to_seconds(timecode: str) -> float:
    hours, minutes, seconds_ms = timecode.split(":")
    seconds, millis = seconds_ms.split(",")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000


def _vtt_time_to_seconds(timecode: str) -> float:
    hours, minutes, seconds_ms = timecode.split(":")
    seconds, millis = seconds_ms.split(".")
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


def parse_vtt(vtt_content: str) -> list[dict[str, Any]]:
    """Parse a VTT payload into timing/content dictionaries."""
    cues: list[dict[str, Any]] = []

    for match in VTT_BLOCK_RE.finditer(vtt_content):
        start = _vtt_time_to_seconds(match.group(1))
        end = _vtt_time_to_seconds(match.group(2))
        content = match.group(3).strip()
        if not content:
            continue
        cues.append({"start": start, "end": end, "content": content})

    if not cues:
        logger.error("VTT parse error: no valid cue blocks found")

    return cues


def _get_xliff_paths(root: ET.Element) -> tuple[dict[str, str], str, str, str]:
    ns = {"ns": "urn:oasis:names:tc:xliff:document:1.2"}
    if not root.findall(".//ns:group", ns):
        ns = {}

    if ns:
        return ns, ".//ns:group", "ns:trans-unit", "ns:source"
    return ns, ".//group", "trans-unit", "source"


def _extract_voice_texts(source: ET.Element) -> list[str]:
    texts: list[str] = []
    for element in source.iter():
        if not element.tag.endswith('g'):
            continue

        tag = element.attrib.get("tag")
        ctype = element.attrib.get("ctype")
        if tag != "voice" and ctype != "x-syn-voice":
            continue

        voice_text = "".join(element.itertext()).strip()
        if voice_text:
            texts.append(voice_text)

    return texts


def parse_scenes_from_xliff(xliff_content: bytes) -> list[dict[str, list[str] | str]]:
    """Parse Synthesia scene scripts from an XLIFF 1.2 document with namespace safety."""
    cleaned = sanitize_xliff_content(_decode_xliff_bytes(xliff_content))

    try:
        root = ET.fromstring(cleaned)
    except ET.ParseError as exc:
        logger.error("XLIFF parse error after sanitization: %s", exc)
        raise ValueError("Invalid XLIFF content") from exc

    ns, group_path, trans_unit_path, source_path = _get_xliff_paths(root)

    scenes: list[dict[str, list[str] | str]] = []
    for group in root.findall(group_path, ns):
        scene_id = group.attrib.get("id") or group.attrib.get("resname") or "unknown_scene"
        scene_title: str | None = None

        lines: list[str] = []
        for trans_unit in group.findall(trans_unit_path, ns):
            trans_unit_id = trans_unit.attrib.get("id", "")
            source = trans_unit.find(source_path, ns)
            if source is None:
                continue

            if trans_unit_id.startswith("element__title__scene__") and scene_title is None:
                title_text = "".join(source.itertext()).strip()
                if title_text:
                    scene_title = title_text
                continue

            if not trans_unit_id.startswith("script__scene__"):
                continue

            voice_texts = _extract_voice_texts(source)
            if voice_texts:
                lines.extend(voice_texts)

            if not voice_texts:
                source_text = "".join(source.itertext()).strip()
                if source_text:
                    lines.append(source_text)

        if lines:
            scene_payload: dict[str, list[str] | str] = {"scene_id": scene_id, "script": lines}
            if scene_title:
                scene_payload["scene_title"] = scene_title
            scenes.append(scene_payload)

    return scenes


def parse_scenes_from_srt_and_xliff(srt_path: str, xliff_path: str) -> list[dict[str, Any]]:
    """Extract scenes from XLIFF and align script scenes against SRT cue timings."""
    xliff_raw = Path(xliff_path).read_bytes()
    cleaned = sanitize_xliff_content(_decode_xliff_bytes(xliff_raw))

    root = ET.fromstring(cleaned)
    ns, group_path, trans_unit_path, source_path = _get_xliff_paths(root)

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

            voice_texts = _extract_voice_texts(source)
            if voice_texts:
                parts.extend(voice_texts)

            if not voice_texts:
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

    subtitle_content = Path(srt_path).read_text(encoding="utf-8")
    subtitle_cues = parse_srt(subtitle_content)
    if not subtitle_cues and "-->" in subtitle_content:
        subtitle_cues = parse_vtt(subtitle_content)

    for cue in subtitle_cues:
        cue["norm"] = normalize(cue["content"])

    script_scenes_with_timing: list[dict[str, Any]] = []
    script_scenes_to_match = [scene for scene in all_scenes_from_xliff if scene["is_script_scene"]]

    scene_idx = 0
    accumulated_norm_text = ""
    scene_start_time: float | None = None

    for subtitle_block in subtitle_cues:
        if scene_idx >= len(script_scenes_to_match):
            break

        if scene_start_time is None:
            scene_start_time = subtitle_block["start"]

        accumulated_norm_text += subtitle_block["norm"]

        current_scene = script_scenes_to_match[scene_idx]
        target_norm_text = normalize(current_scene["script"])

        if not target_norm_text:
            continue

        is_direct_match = target_norm_text in accumulated_norm_text
        is_substring_progress_match = (
            accumulated_norm_text in target_norm_text
            and len(accumulated_norm_text) >= int(len(target_norm_text) * 0.85)
        )
        is_overflow_match = len(accumulated_norm_text) >= max(40, int(len(target_norm_text) * 1.35))

        if is_direct_match or is_substring_progress_match or is_overflow_match:
            end_time = subtitle_block["end"]

            current_scene["start_time"] = scene_start_time
            current_scene["end_time"] = end_time
            current_scene["screenshot_time"] = end_time - 0.2
            script_scenes_with_timing.append(current_scene)

            scene_idx += 1
            accumulated_norm_text = ""
            scene_start_time = None

    last_seen_subtitle_time = subtitle_cues[-1]["end"] if subtitle_cues else 0.0

    while scene_idx < len(script_scenes_to_match):
        scene = script_scenes_to_match[scene_idx]
        fallback_start = scene_start_time if scene_start_time is not None else last_seen_subtitle_time
        fallback_end = fallback_start + 2.0
        scene["start_time"] = fallback_start
        scene["end_time"] = fallback_end
        scene["screenshot_time"] = fallback_end - 0.2
        script_scenes_with_timing.append(scene)
        last_seen_subtitle_time = fallback_end
        scene_idx += 1

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
