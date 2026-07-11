"""Sort each course's downloaded files into typed subfolders.

Categories (first match wins):
  Videos, Solutions, Practice & Tutorials, Past Exam Papers,
  Images & Misc, and Lecture Slides & Notes (the default for documents).
"""
import re
from collections import Counter
from pathlib import Path

VIDEO = {".mp4", ".m4v", ".mov", ".webm", ".avi", ".wmv"}
IMAGE = {".png", ".jpg", ".jpeg", ".gif", ".tif", ".tiff", ".bmp", ".svg", ".webp", ".heic"}


def category(name: str) -> str:
    low = name.lower()
    ext = Path(name).suffix.lower()
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


def run(output_dir):
    """Categorise every 'Lecture Materials & Files' folder under <output>/Canvas."""
    root = Path(output_dir) / "Canvas"
    grand = Counter()
    for materials in root.glob("*/*/Lecture Materials & Files"):
        for f in [p for p in materials.iterdir() if p.is_file()]:
            cat = category(f.name)
            grand[cat] += 1
            dest = materials / cat
            dest.mkdir(exist_ok=True)
            target = dest / f.name
            if target.exists():
                target = dest / f"{f.stem}__{abs(hash(str(f))) % 9999}{f.suffix}"
            f.rename(target)
    if grand:
        print("Organised files: " + "  ".join(f"{k}={v}" for k, v in grand.most_common()))
    else:
        print("Nothing to organise yet (run the Canvas backup first).")
