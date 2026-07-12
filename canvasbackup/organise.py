"""Sort each course's downloaded files, by COURSE SECTION then by type.

Many courses bundle several topics (e.g. "Structures, Structural Dynamics and
FEA") delivered as separate Canvas pages. This maps each downloaded file back to
the page (section) that linked it, giving:

    Lecture Materials & Files/<Section>/<Type>/file

Courses with fewer than two content sections are organised by <Type> only.

Types (first match wins): Videos, Solutions, Practice & Tutorials,
Past Exam Papers, Images & Misc, Lecture Slides & Notes (default).
"""
import html as htmllib
import re
from collections import Counter
from pathlib import Path

from .util import safe_name

VIDEO = {".mp4", ".m4v", ".mov", ".webm", ".avi", ".wmv"}
IMAGE = {".png", ".jpg", ".jpeg", ".gif", ".tif", ".tiff", ".bmp", ".svg", ".webp", ".heic"}
DOC = r"(?:pdf|pptx|ppt|docx|doc|mp4|m4v|mov|xls|xlsx|zip|txt|csv)"
ADMIN = re.compile(r"home ?page|schedule|assessment|feedback|succeeding|welcome|"
                   r"reading list|contents?$|announcement", re.I)


def category(name: str) -> str:
    low, ext = name.lower(), Path(name).suffix.lower()
    if ext in VIDEO:
        return "Videos"
    if re.search(r"solution|answers?\b|worked example|mark scheme", low):
        return "Solutions"
    if re.search(r"practice|tutorial|\btut\b|exercise|problem|worksheet|questions|activity", low):
        return "Practice & Tutorials"
    if re.search(r"\bexam\b|past paper|first sit|resit|\b20\d\d[-_ ]?20\d\d\b", low):
        return "Past Exam Papers"
    if ext in IMAGE:
        return "Images & Misc"
    return "Lecture Slides & Notes"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", htmllib.unescape(s).lower())


def _sections(course_dir: Path) -> dict:
    """{section_title: set(normalised filenames)} from saved Pages HTML."""
    out = {}
    pages_dir = course_dir / "Pages"
    if not pages_dir.is_dir():
        return out
    for p in pages_dir.glob("*.html"):
        txt = p.read_text(encoding="utf-8", errors="ignore")
        h1 = re.search(r"<h1>(.*?)</h1>", txt, re.S)
        title = htmllib.unescape(h1.group(1)).strip() if h1 else p.stem
        if not title or ADMIN.search(title):
            continue
        names = re.findall(rf'title="([^"]+\.{DOC})"', txt, re.I)
        names += re.findall(rf">([^<>]+\.{DOC})</a>", txt, re.I)
        refs = {_norm(n) for n in names}
        if refs:
            out[title] = refs
    return out


def run(output_dir):
    root = Path(output_dir) / "Canvas"
    grand = Counter()
    for materials in root.glob("*/*/Lecture Materials & Files"):
        course_dir = materials.parent
        sections = _sections(course_dir)
        files = [p for p in materials.rglob("*") if p.is_file()]
        use_sections = len(sections) >= 2
        for f in files:
            typ = category(f.name)
            if use_sections:
                nf = _norm(f.name)
                sec = next((t for t, refs in sections.items() if nf in refs), "Other Materials")
                dest = materials / safe_name(sec, 80) / typ
            else:
                dest = materials / typ
            grand[typ] += 1
            dest.mkdir(parents=True, exist_ok=True)
            target = dest / f.name
            if target.resolve() == f.resolve():
                continue
            if target.exists():
                target = dest / f"{f.stem}__{abs(hash(str(f))) % 9999}{f.suffix}"
            f.rename(target)
        # tidy empty leftover folders
        for d in sorted([p for p in materials.rglob("*") if p.is_dir()], reverse=True):
            if not any(d.iterdir()):
                d.rmdir()
    if grand:
        print("Organised files: " + "  ".join(f"{k}={v}" for k, v in grand.most_common()))
    else:
        print("Nothing to organise yet (run the Canvas backup first).")
