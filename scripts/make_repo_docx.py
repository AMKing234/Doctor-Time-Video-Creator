#!/usr/bin/env python3
"""Create a Word .docx listing every repository link supplied by the user.

No third-party dependency: writes a minimal, valid OOXML package with stdlib.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

REPOS = [
    ("Jakeschincariol / youtube-agent-skill",
     "https://github.com/Jakeschincariol/youtube-agent-skill.git",
     "11 YouTube skills (script, SEO, edit, chapters, retention, shorts, audit) — pipeline me wired"),
    ("lemomo-ai / lemo-opuscar",
     "https://github.com/lemomo-ai/lemo-opuscar.git",
     "99 cinematic film styles — style reference"),
    ("mrdoob / three.js",
     "https://github.com/mrdoob/three.js.git",
     "3D WebGL rendering — 3D thumbnail studio"),
    ("patch-gg / pixelfx",
     "https://github.com/patch-gg/pixelfx.git",
     "244 pixel-art effects — optional thumbnails/sprites"),
    ("ahujasid / mcp-for-blender",
     "https://github.com/ahujasid/mcp-for-blender.git",
     "Blender 3D control via MCP (Blender optional)"),
    ("pmndrs / react-three-rapier",
     "https://github.com/pmndrs/react-three-rapier.git",
     "Physics for React Three Fiber — optional 3D motion"),
    ("pmndrs / react-postprocessing",
     "https://github.com/pmndrs/react-postprocessing.git",
     "Postprocessing effects — optional cinematic bloom"),
    ("librosa / librosa",
     "https://github.com/librosa/librosa.git",
     "Audio and beat analysis — optional beat-synced cuts"),
    ("Vincentwei1021 / video-shotcraft",
     "https://github.com/Vincentwei1021/video-shotcraft.git",
     "Shot planning — optional shot-list enhancement"),
    ("JohnHeibel / ClaudeAnimationBase",
     "https://github.com/JohnHeibel/ClaudeAnimationBase.git",
     "Code-driven motion templates"),
    ("joeseesun / opus-video-prompts",
     "https://github.com/joeseesun/opus-video-prompts.git",
     "Video prompt library"),
    ("yihui-dev / awesome-opus5-5-videos",
     "https://github.com/yihui-dev/awesome-opus5-5-videos.git",
     "Curated videos — style and trend reference"),
]

OUR_REPO = "https://github.com/AMKing234/Doctor-Time-Video-Creator"


def run(text: str, *, bold: bool = False, size: int | None = None,
        color: str | None = None, italic: bool = False) -> str:
    props = []
    if bold:
        props.append("<w:b/>")
    if italic:
        props.append("<w:i/>")
    if color:
        props.append(f'<w:color w:val="{color}"/>')
    if size:
        props.append(f'<w:sz w:val="{size * 2}"/>')
    rpr = f"<w:rPr>{''.join(props)}</w:rPr>" if props else ""
    return f'<w:r>{rpr}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def para(text: str = "", *, bold: bool = False, size: int | None = None,
         color: str | None = None, italic: bool = False, style: str | None = None) -> str:
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{ppr}{run(text, bold=bold, size=size, color=color, italic=italic)}</w:p>"


def cell(text: str, width: int, *, bold: bool = False,
         hyperlink_id: str | None = None) -> str:
    if hyperlink_id:
        content = (
            f'<w:hyperlink r:id="{hyperlink_id}">'
            + run(text, color="0563C1")
            + "</w:hyperlink>"
        )
    else:
        content = run(text, bold=bold, size=9)
    return (
        '<w:tc>'
        f'<w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>'
        '<w:shd w:val="clear" w:color="auto" w:fill="F2F2F2"/></w:tcPr>'
        f"<w:p>{content}</w:p>"
        "</w:tc>"
    )


def build_document() -> tuple[str, str]:
    rels: list[str] = [
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
        'officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    ]
    hyper_links: list[str] = []

    for i, (_name, url, _use) in enumerate(REPOS, start=2):
        rid = f"rId{i}"
        hyper_links.append(
            f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/'
            f'officeDocument/2006/relationships/hyperlink" Target="{escape(url)}" '
            'TargetMode="External"/>'
        )

    ours_id = f"rId{len(REPOS) + 2}"
    hyper_links.append(
        f'<Relationship Id="{ours_id}" Type="http://schemas.openxmlformats.org/'
        f'officeDocument/2006/relationships/hyperlink" Target="{OUR_REPO}" '
        'TargetMode="External"/>'
    )

    rows = [
        "<w:tr>"
        + cell("#", 600, bold=True)
        + cell("Repository", 3600, bold=True)
        + cell("Link", 6000, bold=True)
        + cell("Kaam", 5200, bold=True)
        + "</w:tr>"
    ]
    for i, (name, url, use) in enumerate(REPOS, start=1):
        rows.append(
            "<w:tr>"
            + cell(str(i), 600)
            + cell(name, 3600)
            + cell(url, 6000, hyperlink_id=f"rId{i + 1}")
            + cell(use, 5200)
            + "</w:tr>"
        )

    table = (
        "<w:tbl><w:tblPr>"
        '<w:tblBorders>'
        '<w:top w:val="single" w:sz="4" w:color="BFBFBF"/>'
        '<w:left w:val="single" w:sz="4" w:color="BFBFBF"/>'
        '<w:bottom w:val="single" w:sz="4" w:color="BFBFBF"/>'
        '<w:right w:val="single" w:sz="4" w:color="BFBFBF"/>'
        '<w:insideH w:val="single" w:sz="4" w:color="BFBFBF"/>'
        '<w:insideV w:val="single" w:sz="4" w:color="BFBFBF"/>'
        '</w:tblBorders>'
        "</w:tblPr>"
        '<w:tblGrid><w:gridCol w:w="600"/><w:gridCol w:w="3600"/>'
        '<w:gridCol w:w="6000"/><w:gridCol w:w="5200"/></w:tblGrid>'
        + "".join(rows)
        + "</w:tbl>"
    )

    body = "".join([
        para("Repository Links", bold=True, size=22, color="D4AF37"),
        para("Doctor Time Video Creator — aapke dwara diye gaye saare repository links",
             italic=True, size=11, color="666666"),
        para(""),
        para("Kul 12 repositories. Sab is device par vendor/ folder me locally clone hain aur "
             "scripts/fetch_vendors.sh se dobara fetch ho sakte hain. Link par click karne par "
             "browser me repository khulegi.", size=11),
        para(""),
        table,
        para(""),
        para("Project repository (banaya gaya): ", bold=True, size=11)
        .replace("</w:p>", "")
        + f'<w:hyperlink r:id="{ours_id}">' + run(OUR_REPO, color="0563C1")
        + "</w:hyperlink></w:p>",
        para(""),
        para("Tip: Word me link par right-click karke 'Open Hyperlink' chuno.",
             italic=True, size=10, color="666666"),
    ])

    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<w:body>{body}"
        '<w:sectPr><w:pgSz w:w="15840" w:h="12240"/>'
        '<w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720" '
        'w:header="360" w:footer="360" w:gutter="0"/></w:sectPr>'
        "</w:body></w:document>"
    )
    rel_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(rels + hyper_links)
        + "</Relationships>"
    )
    return document, rel_xml


STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr>
<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/>
</w:rPr></w:rPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="character" w:styleId="Hyperlink"><w:name w:val="Hyperlink"/>
<w:rPr><w:color w:val="0563C1"/><w:u w:val="single"/></w:rPr></w:style>
</w:styles>"""

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

CORE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:title>Repository Links — Doctor Time Video Creator</dc:title>
<dc:creator>Doctor Time Video Creator</dc:creator>
<cp:keywords>repositories, github, video creator</cp:keywords>
</cp:coreProperties>"""

APP = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
<Application>Doctor Time Video Creator</Application>
</Properties>"""


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("Repository-Links.docx")
    document, rels = build_document()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", ROOT_RELS)
        z.writestr("word/document.xml", document)
        z.writestr("word/_rels/document.xml.rels", rels)
        z.writestr("word/styles.xml", STYLES)
        z.writestr("docProps/core.xml", CORE)
        z.writestr("docProps/app.xml", APP)
    print(f"Created {target} ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
