from __future__ import annotations

from lxml import etree


def parse_scenes_from_xliff(xliff_content: bytes) -> list[dict[str, list[str] | str]]:
    """Parse Synthesia scene scripts from an XLIFF 1.2 document with namespace safety."""
    try:
        root = etree.fromstring(xliff_content)
    except etree.XMLSyntaxError as exc:
        raise ValueError("Invalid XLIFF content") from exc

    namespaces = {
        "x": "urn:oasis:names:tc:xliff:document:1.2",
        "syn": "urn:synthesia:video",
    }

    scenes: list[dict[str, list[str] | str]] = []

    for group in root.xpath(".//x:group", namespaces=namespaces):
        scene_id = group.get("id") or group.get("resname") or "unknown_scene"
        lines: list[str] = []

        trans_units = group.xpath(
            ".//x:trans-unit[starts-with(@id, 'script__scene__')]",
            namespaces=namespaces,
        )

        for trans_unit in trans_units:
            source = trans_unit.find("x:source", namespaces=namespaces)
            if source is None:
                continue

            text = "".join(source.itertext()).strip()
            if text:
                lines.append(text)

        if lines:
            scenes.append({"scene_id": scene_id, "script": lines})

    return scenes
