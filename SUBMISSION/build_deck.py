#!/usr/bin/env python3
"""Build the slide deck PDF from the deck markdown, without a markup dependency.

    python3 build_deck.py deck_and_form.md deck.pdf

Renders a clean, dark, presentation-style PDF: one page per slide, title large, body lines
as bullets. Uses only the standard library plus whatever PDF writer is available on the host
(reportlab if present, otherwise a minimal built-in PDF writer).
"""
import re
import sys
from pathlib import Path


def _slides(md: str):
    """Split the deck markdown into (title, [lines]) slides."""
    slides = []
    for block in re.split(r"\n\*\*\d+\s*·\s*", md):
        if "**" not in block:
            continue
        lines = [l.strip(" -*") for l in block.splitlines() if l.strip()]
        if not lines:
            continue
        title = re.sub(r"\*\*|\*", "", lines[0]).strip()
        body = [re.sub(r"\*\*|\*", "", l).strip() for l in lines[1:]]
        slides.append((title, body))
    return slides


_ESC = str.maketrans({"\\": r"\\", "(": r"\(", ")": r"\)"})


def _pdf_minimal(path: str, slides) -> None:
    """A tiny PDF writer: one page per slide, Helvetica, dark background."""
    W, H = 720, 405   # 16:9 points
    objs = []
    font = "F1"
    for title, body in slides:
        def esc(s):
            return s.translate(_ESC)[:110]
        content = ["q 0.043 0.055 0.075 rg 0 0 %d %d re f Q" % (W, H)]
        content.append("BT /F2 26 Tf 1 1 1 rg 48 %d Td (%s) Tj ET" % (H - 90, esc(title)))
        y = H - 140
        for line in body[:11]:
            content.append("BT /F1 12 Tf 0.75 0.78 0.82 rg 48 %d Td (%s) Tj ET" % (y, esc(line)))
            y -= 22
        stream = "\n".join(content)
        objs.append(stream)
    # assemble
    parts = []
    parts.append("%PDF-1.4\n")
    offsets = [0]
    body = []
    # objects: 1 catalog, 2 pages, 3..(3+n-1) pages, then fonts, then contents
    n = len(slides)
    kids = []
    # We'll number: 1=catalog, 2=pages, fonts at 3,4, then page objs and content objs
    font1, font2 = 3, 4
    first_page = 5
    page_ids = [first_page + i for i in range(n)]
    content_start = first_page + n
    content_ids = [content_start + i for i in range(n)]

    def obj(num, text):
        body.append((num, text))

    obj(1, "<< /Type /Catalog /Pages 2 0 R >>")
    kids_str = " ".join(f"{pid} 0 R" for pid in page_ids)
    obj(2, f"<< /Type /Pages /Count {n} /Kids [{kids_str}] >>")
    obj(font1, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    obj(font2, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    for i, (pid, cid) in enumerate(zip(page_ids, content_ids)):
        obj(pid, f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {W} {H}] "
                 f"/Resources << /Font << /F1 {font1} 0 R /F2 {font2} 0 R >> >> "
                 f"/Contents {cid} 0 R >>")
        s = objs[i]
        obj(cid, f"<< /Length {len(s)} >>\nstream\n{s}\nendstream")

    body.sort(key=lambda t: t[0])
    out = "%PDF-1.4\n"
    offs = {}
    for num, text in body:
        offs[num] = len(out)
        out += f"{num} 0 obj\n{text}\nendobj\n"
    xref_pos = len(out)
    maxnum = max(offs)
    out += f"xref\n0 {maxnum+1}\n"
    out += "0000000000 65535 f \n"
    for i in range(1, maxnum + 1):
        out += f"{offs.get(i, 0):010d} 00000 n \n"
    out += f"trailer\n<< /Size {maxnum+1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF"
    Path(path).write_bytes(out.encode("latin-1", "replace"))


def main():
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "deck_and_form.md")
    dst = sys.argv[2] if len(sys.argv) > 2 else "deck.pdf"
    md = src.read_text()
    # only the deck section (before the form copy)
    md = md.split("## Submission form copy")[0]
    slides = _slides(md)
    if not slides:
        print("no slides parsed", file=sys.stderr)
        return 1
    _pdf_minimal(dst, slides)
    print(f"wrote {dst}: {len(slides)} slides, {Path(dst).stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
