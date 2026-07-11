"""Small shared helpers: filesystem-safe names, HTTP with rate-limit handling."""
import re
import time

import requests

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(name: str, maxlen: int = 150) -> str:
    """Turn any string into a safe file/folder name on Windows, macOS and Linux."""
    cleaned = _ILLEGAL.sub("_", name or "").strip(". ")
    return (cleaned[:maxlen].strip() or "unnamed")


def api_get(session: requests.Session, url: str, **kwargs) -> requests.Response:
    """GET with retry/back-off for Canvas' 403 'Rate Limit Exceeded' responses."""
    for attempt in range(6):
        resp = session.get(url, timeout=90, **kwargs)
        if resp.status_code == 403 and "Rate Limit" in resp.text:
            time.sleep(2 ** attempt)
            continue
        return resp
    return resp


def paginate(session: requests.Session, url: str, params: dict = None):
    """Yield items across Canvas pagination via the Link: rel="next" header."""
    params = dict(params or {})
    params.setdefault("per_page", 100)
    while url:
        resp = api_get(session, url, params=params)
        if not resp.ok:
            return
        data = resp.json()
        if isinstance(data, list):
            yield from data
        else:
            yield data
            return
        url = resp.links.get("next", {}).get("url")
        params = None  # already encoded into the next-page URL


def download(session: requests.Session, url: str, dest, expected_size: int = None) -> str:
    """Stream a file to dest. Returns 'new', 'have', or an error string."""
    from pathlib import Path
    dest = Path(dest)
    if dest.exists() and expected_size and dest.stat().st_size == expected_size:
        return "have"
    resp = api_get(session, url, stream=True)
    if not resp.ok:
        return f"http-{resp.status_code}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with open(tmp, "wb") as fh:
        for chunk in resp.iter_content(1024 * 512):
            fh.write(chunk)
    tmp.replace(dest)
    return "new"
