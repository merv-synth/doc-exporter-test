from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

_CONTENT_TYPES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""

_RELS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""

_DOCUMENT_RELS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>
"""


def _paragraph(text: str) -> str:
    return f"<w:p><w:r><w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>"


def generate_word_document(scenes: list[dict[str, list[str] | str]], output_path: Path) -> None:
    body: list[str] = [_paragraph("Synthesia Video Script Export")]

    for index, scene in enumerate(scenes, start=1):
        scene_id = str(scene.get("scene_id") or f"scene_{index}")
        scene_title = str(scene.get("scene_title") or "").strip()
        script_lines = scene.get("script") if isinstance(scene.get("script"), list) else []

        body.append(_paragraph(f"Scene {index}"))
        body.append(_paragraph(f"ID: {scene_id}"))
        if scene_title:
            body.append(_paragraph(f"Title: {scene_title}"))
        body.append(_paragraph("Script:"))

        if script_lines:
            for line in script_lines:
                body.append(_paragraph(f"• {line}"))
        else:
            body.append(_paragraph("• [No script lines]"))

    document_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
        f"<w:body>{''.join(body)}<w:sectPr/></w:body>"
        "</w:document>"
    )

    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as docx_zip:
        docx_zip.writestr("[Content_Types].xml", _CONTENT_TYPES_XML)
        docx_zip.writestr("_rels/.rels", _RELS_XML)
        docx_zip.writestr("word/_rels/document.xml.rels", _DOCUMENT_RELS_XML)
        docx_zip.writestr("word/document.xml", document_xml)
