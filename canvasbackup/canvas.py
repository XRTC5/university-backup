"""Full Canvas LMS backup for one student account.

Downloads, per course: files, lecture slides, assignments + your own
submissions, announcements, discussions, pages, modules, quizzes, grades, and
Canvas-hosted videos. Crucially it also handles schools that DISABLE the Pages
and Files tabs (common): when the bulk list APIs return 403/empty it recovers
the content by crawling linked pages and harvesting embedded file/media IDs.

Everything is grouped into  <output>/Canvas/<Term>/<CODE (Course Name)>/ .
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from .util import api_get, download, paginate, safe_name

PAGE_LINK = re.compile(r"/courses/(\d+)/pages/([\w~%.\-]+)")
FILE_LINK = re.compile(r"/(?:courses/\d+/)?files/(\d+)")
MEDIA_LINK = re.compile(r"media_attachments(?:_iframe)?/(\d+)")
YT_ID = re.compile(
    r"(?:youtube\.com/(?:watch\?[^\"'<>\s]*?v=|embed/|shorts/|live/)|youtu\.be/)"
    r"([A-Za-z0-9_-]{11})")


def connect(cfg):
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {cfg['canvas_token']}"
    base = cfg["canvas_url"].rstrip("/")
    me = api_get(s, f"{base}/api/v1/users/self")
    if not me.ok:
        raise SystemExit(f"Could not log in to Canvas ({me.status_code}). "
                         "Check your Canvas web address and token.")
    return s, base, me.json()


def list_courses(s, base):
    """Every course on the account, including ones the school hides.

    After a term ends many universities conclude enrollments and drop those
    courses from the /courses listing entirely, so students see only one or
    two active shells. The enrollments endpoint still knows every course the
    account was enrolled in, and fetching those courses directly by id
    usually still works, so merge both sources. Courses the school has
    actually revoked (403/404) are reported and skipped.
    """
    courses = {c["id"]: c for c in paginate(s, f"{base}/api/v1/courses",
                                            {"include[]": "term",
                                             "state[]": ["available", "completed"],
                                             "enrollment_state": ""})}
    enrolled = {e["course_id"] for e in paginate(
        s, f"{base}/api/v1/users/self/enrollments",
        {"state[]": ["active", "completed", "invited", "inactive"]})}
    hidden = sorted(enrolled - set(courses))
    if hidden:
        print(f"Course list shows {len(courses)} course(s); enrollments reveal "
              f"{len(hidden)} more the school hides - fetching those directly.")
    for cid in hidden:
        r = api_get(s, f"{base}/api/v1/courses/{cid}", params={"include[]": "term"})
        try:
            c = r.json() if r.ok else {}
        except ValueError:
            c = {}
        if c.get("name"):
            courses[cid] = c
        else:
            why = ("restricted by course dates" if c.get("access_restricted_by_date")
                   else f"HTTP {r.status_code}")
            print(f"  course {cid}: not accessible ({why}) - skipped.")
    return list(courses.values())


def _html_bodies(s, base, cid):
    """Yield every HTML body in a course: pages (crawled), announcements,
    assignments, discussions, and external module items."""
    # --- pages: try the list API, else BFS-crawl from front page + modules ---
    seeds, pages = set(), {}
    fp = api_get(s, f"{base}/api/v1/courses/{cid}/front_page")
    if fp.ok and fp.json().get("url"):
        seeds.add(fp.json()["url"])
    listed = api_get(s, f"{base}/api/v1/courses/{cid}/pages", params={"per_page": 100})
    if listed.ok and isinstance(listed.json(), list):
        for p in listed.json():
            if p.get("url"):
                seeds.add(p["url"])
    for m in paginate(s, f"{base}/api/v1/courses/{cid}/modules", {"include[]": "items"}):
        for it in m.get("items") or []:
            if it.get("type") == "Page" and it.get("page_url"):
                seeds.add(it["page_url"])
    queue, done = list(seeds), set()
    while queue:
        slug = queue.pop()
        if slug in done:
            continue
        done.add(slug)
        r = api_get(s, f"{base}/api/v1/courses/{cid}/pages/{slug}")
        if not r.ok:
            continue
        body = r.json().get("body") or ""
        pages[slug] = r.json()
        for mm in PAGE_LINK.finditer(body):
            if int(mm.group(1)) == cid and mm.group(2) not in done:
                queue.append(mm.group(2))
    for slug, p in pages.items():
        yield ("page", slug, p.get("title", slug), p.get("body") or "")

    for a in paginate(s, f"{base}/api/v1/courses/{cid}/discussion_topics",
                      {"only_announcements": True}):
        yield ("announcement", str(a["id"]), a.get("title", ""), a.get("message") or "")
    for d in paginate(s, f"{base}/api/v1/courses/{cid}/discussion_topics"):
        yield ("discussion", str(d["id"]), d.get("title", ""), d.get("message") or "")
    for asg in paginate(s, f"{base}/api/v1/courses/{cid}/assignments"):
        yield ("assignment", str(asg["id"]), asg.get("name", ""), asg.get("description") or "")


def _download_file_by_id(s, base, cid, fid, dest_dir):
    for url in (f"{base}/api/v1/courses/{cid}/files/{fid}", f"{base}/api/v1/files/{fid}"):
        r = api_get(s, url)
        if r.ok:
            break
    else:
        return None
    meta = r.json()
    name = safe_name(meta.get("display_name") or str(fid))
    if not meta.get("url"):
        return None
    status = download(s, meta["url"], dest_dir / name, meta.get("size"))
    return name if status in ("new", "have") else None


def backup_course(s, base, course, out_root, stats):
    cid = course["id"]
    term = safe_name((course.get("term") or {}).get("name") or "Other Term", 60)
    code = course.get("course_code") or str(cid)
    name = course.get("name") or code
    folder = out_root / term / safe_name(f"{code} ({name})" if name != code else code, 120)
    files_dir = folder / "Lecture Materials & Files"
    pages_dir = folder / "Pages"
    folder.mkdir(parents=True, exist_ok=True)
    print(f"  {code}: {name}")

    file_ids, media_ids, yt, saved_pages = set(), set(), {}, 0
    course_record = {"course_id": cid, "code": code, "name": name, "term": term, "pages": []}

    # bulk file list (works when the Files tab is enabled)
    for f in paginate(s, f"{base}/api/v1/courses/{cid}/files"):
        file_ids.add(str(f["id"]))

    for kind, ident, title, body in _html_bodies(s, base, cid):
        file_ids.update(FILE_LINK.findall(body))
        media_ids.update(MEDIA_LINK.findall(body))
        for vid in set(YT_ID.findall(body)):
            yt.setdefault(vid, []).append(title)
        if kind == "page" and body:
            pages_dir.mkdir(parents=True, exist_ok=True)
            (pages_dir / f"{safe_name(title)}.html").write_text(
                f"<h1>{title}</h1>\n{body}", encoding="utf-8")
            saved_pages += 1
            course_record["pages"].append(title)

    # download everything referenced
    def grab(fid):
        return _download_file_by_id(s, base, cid, fid, files_dir)
    with ThreadPoolExecutor(max_workers=4) as ex:
        got = [n for n in ex.map(grab, file_ids | media_ids) if n]
    stats["files"] += len(got)
    stats["pages"] += saved_pages

    # assignments + your own submissions
    for asg in paginate(s, f"{base}/api/v1/courses/{cid}/assignments"):
        sub = api_get(s, f"{base}/api/v1/courses/{cid}/assignments/{asg['id']}/submissions/self")
        if sub.ok:
            for att in sub.json().get("attachments") or []:
                if att.get("url"):
                    download(s, att["url"],
                             folder / "My Submissions" / safe_name(att.get("filename", "file")),
                             att.get("size"))

    # grades + quizzes (records, not re-gradeable content)
    enroll = [e for e in paginate(s, f"{base}/api/v1/courses/{cid}/enrollments",
                                  {"user_id": "self"})]
    quizzes = list(paginate(s, f"{base}/api/v1/courses/{cid}/quizzes"))
    (folder / "grades_and_quizzes.json").write_text(
        json.dumps({"enrollments": enroll, "quizzes": quizzes}, indent=2), encoding="utf-8")

    # YouTube links professors curated -> clickable shortcuts
    if yt:
        yt_dir = folder / "YouTube Links"
        yt_dir.mkdir(exist_ok=True)
        lines = [f"# YouTube links — {name}", ""]
        for vid, contexts in yt.items():
            url = f"https://www.youtube.com/watch?v={vid}"
            (yt_dir / f"{safe_name(contexts[0] or vid, 80)}.url").write_text(
                f"[InternetShortcut]\nURL={url}\n", encoding="utf-8")
            lines.append(f"- {url}  (from: {contexts[0]})")
        (yt_dir / "links.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    (folder / "course_info.json").write_text(json.dumps(course_record, indent=2), encoding="utf-8")
    stats["courses"] += 1


def run(cfg):
    s, base, me = connect(cfg)
    out_root = Path(cfg["output_dir"]) / "Canvas"
    out_root.mkdir(parents=True, exist_ok=True)
    print(f"\nLogged in as {me.get('name')}. Backing up to {out_root}\n")
    courses = list_courses(s, base)
    print(f"Found {len(courses)} courses.\n")
    stats = {"courses": 0, "files": 0, "pages": 0}
    for c in courses:
        try:
            backup_course(s, base, c, out_root, stats)
        except Exception as e:  # keep going even if one course misbehaves
            print(f"    ! problem with course {c.get('course_code')}: {e}")
    print(f"\nCanvas backup done: {stats['courses']} courses, "
          f"{stats['files']} files, {stats['pages']} pages.")
    return out_root
