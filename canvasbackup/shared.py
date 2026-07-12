"""Collect files & folders that OTHER people shared with you (OneDrive/SharePoint).

This is opt-in. It reuses the rclone OneDrive login (no separate sign-in): it
reads the access token rclone already stored, asks Microsoft Graph for your
"Shared with you" list (the reliable insights/shared feed — the classic
sharedWithMe API misses almost everything), then downloads each shared item.

Files that your institution blocks from download (e.g. view-only videos) are
reported and skipped. Output: <output>/OneDrive Shared/.
"""
import json
import re
import subprocess
import time
from pathlib import Path

import requests

from .onedrive import REMOTE

GRAPH = "https://graph.microsoft.com/v1.0"
ILLEGAL = str.maketrans('<>:"/\\|?*', "_________")


def _rclone_config_path(exe):
    out = subprocess.run([exe, "config", "file"], capture_output=True, text=True)
    for line in out.stdout.splitlines():
        line = line.strip()
        if line.lower().endswith(".conf"):
            return line
    return None


def _read_token(exe):
    """Pull the OAuth access token rclone stored for the OneDrive remote."""
    from configparser import ConfigParser
    path = _rclone_config_path(exe)
    if not path or not Path(path).exists():
        return None
    cp = ConfigParser()
    cp.read(path)
    if REMOTE not in cp or "token" not in cp[REMOTE]:
        return None
    try:
        return json.loads(cp[REMOTE]["token"]).get("access_token")
    except (json.JSONDecodeError, KeyError):
        return None


def _refresh_token(exe):
    subprocess.run([exe, "about", f"{REMOTE}:"], capture_output=True)
    return _read_token(exe)


class _Graph:
    def __init__(self, exe):
        self.exe = exe
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"Bearer {_read_token(exe)}"

    def get(self, url, **kw):
        for attempt in range(8):
            r = self.s.get(url, timeout=90, **kw)
            if r.status_code == 401:
                self.s.headers["Authorization"] = f"Bearer {_refresh_token(self.exe)}"
                continue
            if r.status_code == 429:
                time.sleep(int(r.headers.get("Retry-After", 0)) or min(2 ** attempt, 60))
                continue
            return r
        return r


def _safe(name):
    return (name or "unnamed").translate(ILLEGAL).strip()[:150] or "unnamed"


def _my_drive_id(g):
    r = g.get(f"{GRAPH}/me/drive?$select=id")
    return r.json().get("id") if r.ok else None


def _shared_items(g):
    """Return unique (driveId, itemId) shared with the user, via insights/shared."""
    seen, out = set(), []
    url = f"{GRAPH}/me/insights/shared?$top=100"
    while url:
        r = g.get(url)
        if not r.ok:
            break
        j = r.json()
        for it in j.get("value", []):
            rid = it.get("resourceReference", {}).get("id", "")
            m = re.match(r"drives/([^/]+)/items/(.+)", rid)
            if m and (m.group(1), m.group(2)) not in seen:
                seen.add((m.group(1), m.group(2)))
                out.append((m.group(1), m.group(2)))
        url = j.get("@odata.nextLink")
    return out


def _download_file(g, drive, item, dest: Path):
    r = g.get(f"{GRAPH}/drives/{drive}/items/{item}")  # no $select (keeps downloadUrl)
    if not r.ok:
        return "meta-fail"
    j = r.json()
    url = j.get("@microsoft.graph.downloadUrl")
    if dest.exists() and dest.stat().st_size == j.get("size", 0):
        return "have"
    if not url:
        return "no-url"
    dl = g.get(url, stream=True)
    if not dl.ok:
        return f"blocked-{dl.status_code}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with open(tmp, "wb") as f:
        for chunk in dl.iter_content(1024 * 512):
            f.write(chunk)
    tmp.replace(dest)
    return "new"


def _walk(g, drive, item, dest: Path, stats):
    url = f"{GRAPH}/drives/{drive}/items/{item}/children?$top=200"
    while url:
        r = g.get(url)
        if not r.ok:
            return
        j = r.json()
        for it in j.get("value", []):
            name = _safe(it.get("name"))
            if "folder" in it:
                _walk(g, drive, it["id"], dest / name, stats)
            else:
                res = _download_file(g, drive, it["id"], dest / name)
                stats[res] = stats.get(res, 0) + 1
        url = j.get("@odata.nextLink")


def run(cfg, exe):
    """Ask, then collect shared items. exe is the rclone path from onedrive.run."""
    ans = input("\nAlso collect all documents & folders shared with you by "
                "others? [y/N]: ").strip().lower()
    if ans not in ("y", "yes"):
        print("Skipping shared documents.")
        return
    if not _read_token(exe):
        print("Could not read your OneDrive login from rclone — skip.")
        return

    g = _Graph(exe)
    mydrive = _my_drive_id(g)
    dest_root = Path(cfg["output_dir"]) / "OneDrive Shared"
    print("Finding everything shared with you (this can take a moment)...")
    refs = _shared_items(g)
    print(f"Found {len(refs)} shared items. Downloading (skips your own files)...")

    stats = {}
    for drive, item in refs:
        if drive == mydrive:
            stats["own"] = stats.get("own", 0) + 1
            continue
        r = g.get(f"{GRAPH}/drives/{drive}/items/{item}")
        if not r.ok:
            stats["meta-fail"] = stats.get("meta-fail", 0) + 1
            continue
        j = r.json()
        name = _safe(j.get("name"))
        if "folder" in j:
            _walk(g, drive, item, dest_root / name, stats)
        else:
            dest = dest_root / name
            if dest.exists():
                dest = dest_root / f"{Path(name).stem}__{item[:6]}{Path(name).suffix}"
            res = _download_file(g, drive, item, dest)
            stats[res] = stats.get(res, 0) + 1

    got = stats.get("new", 0) + stats.get("have", 0)
    blocked = sum(v for k, v in stats.items() if str(k).startswith("blocked"))
    print(f"\nShared documents done: {got} downloaded, {blocked} blocked by your "
          f"institution (usually view-only videos), saved to {dest_root}")
