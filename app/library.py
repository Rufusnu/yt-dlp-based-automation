import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from .db import conn
from .deps import need
from .paths import ARCH, DL, NAS, NAS_MOUNT

router = APIRouter(prefix="/api/library")
AUDIO = {".opus", ".m4a", ".mp3", ".flac", ".ogg", ".wav", ".webm", ".aac"}
CAP = 500


def nas_mounted():
    return os.path.ismount(NAS_MOUNT) and NAS.is_dir()


def audio_files(d):
    """Set of audio file names directly in d (one scandir)."""
    out = set()
    try:
        with os.scandir(d) as it:
            for e in it:
                if os.path.splitext(e.name)[1].lower() in AUDIO and not e.name.startswith(".tmp") and e.is_file():
                    out.add(e.name)
    except OSError:
        pass
    return out


def subdirs(d):
    out = set()
    try:
        with os.scandir(d) as it:
            for e in it:
                if e.name != ".tmp" and e.is_dir():
                    out.add(e.name)
    except OSError:
        pass
    return out


def fixed_name(name):
    """Repaired name if `name` is UTF-8 read as Latin-1, else None."""
    if name.isascii():
        return None
    try:
        f = name.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return None
    return f if f != name else None


def plain(s):
    """Name without emoji/punctuation, for matching folders to playlists that never ran in the app."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]|_", "", s or "")).strip().casefold()


def count_lines(p):
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except OSError:
        return None


def scan_folder(name, mounted):
    loc = audio_files(DL / name)
    nas = audio_files(NAS / name) if mounted else set()
    miss = loc - nas if mounted else set()
    fx = fixed_name(name)
    return {"local": len(loc), "nas": len(nas), "missing_on_nas": len(miss),
            "only_on_nas": len(nas - loc) if mounted else 0,
            "garbled": fx is not None, "fixed_name": fx}


def valid_folder(name):
    if not name or name in (".", "..") or any(c in name for c in "/\\\0"):
        return False
    return True


def folder_dir(base, name):
    p = base / name
    try:
        if p.is_dir() and p.resolve().parent == base.resolve():
            return p
    except OSError:
        pass
    return None


def fill_titles():
    """Give playlists that never ran in the app their real (emoji) title, taken from the local folders and archive
    files, only when exactly one folder matches the name once emoji/punctuation are ignored."""
    names = subdirs(DL)
    try:
        names |= {p.name[:-len(".archive")] for p in ARCH.glob("*.archive")}
    except OSError:
        pass
    by = {}
    for n in names:
        by.setdefault(plain(n), set()).add(n)
    got = 0
    with conn() as c:
        rows = list(c.execute("SELECT id,name,title FROM playlists"))
        taken = {r["title"] for r in rows if r["title"]}
        pending = {}
        for r in rows:
            if not r["title"]:
                pending.setdefault(plain(r["name"]), []).append(r)
        for k, prs in pending.items():
            cand = [n for n in (by.get(k) or by.get(re.sub(r"^soundcloud ", "", k), ())) if n not in taken]
            if k and len(prs) == 1 and len(cand) == 1:
                c.execute("UPDATE playlists SET title=? WHERE id=?", (cand[0], prs[0]["id"]))
                got += 1
    return got


@router.get("")
def overview(request: Request):
    need(request)
    mounted = nas_mounted()
    names = subdirs(DL) | (subdirs(NAS) if mounted else set())
    with conn() as c:
        allp = list(c.execute("SELECT id,name,title,enabled FROM playlists"))
    pls = {r["title"]: r for r in allp if r["title"]}
    byplain = {}
    for r in allp:
        byplain.setdefault(plain(r["name"]), []).append(r)
    rows = []
    for n in names:
        r = {"folder": n, **scan_folder(n, mounted)}
        pl = pls.get(n)
        if not pl:  # fall back to the name, only when it is unambiguous and the playlist has no title yet
            cand = [x for x in byplain.get(plain(n), []) if not x["title"]]
            pl = cand[0] if len(cand) == 1 else None
        r["playlist_id"] = pl["id"] if pl else None
        r["playlist_name"] = pl["name"] if pl else None
        r["enabled"] = bool(pl["enabled"]) if pl else None
        r["archive"] = count_lines(ARCH / f"{n}.archive")
        r["single"] = n == "NA"  # yt-dlp's folder for single videos (no playlist title)
        r["diff"] = r["nas"] - r["archive"] if (mounted and r["archive"] is not None) else None
        r["differs"] = r["diff"] is not None and abs(r["diff"]) > max(3, 0.1 * r["archive"])
        rows.append(r)
    rows.sort(key=lambda r: (not r["garbled"], not r["missing_on_nas"] > 0, r["folder"].lower()))
    t = {k: sum(r[k] for r in rows) for k in ("local", "nas", "missing_on_nas", "only_on_nas")}
    t["folders"] = len(rows)
    t["playlists"] = sum(1 for r in rows if r["playlist_id"])
    t["differs"] = sum(1 for r in rows if r["differs"])
    t["garbled_folders"] = sum(r["garbled"] for r in rows)
    return {"nas_mounted": mounted, "totals": t, "folders": rows}


@router.get("/missing")
def missing(request: Request, folder: str = ""):
    need(request)
    if not valid_folder(folder):
        raise HTTPException(400, "bad folder name")
    mounted = nas_mounted()
    ld, nd = folder_dir(DL, folder), (folder_dir(NAS, folder) if mounted else None)
    if not ld and not nd:
        raise HTTPException(400, "unknown folder")
    loc = audio_files(ld) if ld else set()
    nas = audio_files(nd) if nd else set()
    a, b = sorted(loc - nas) if mounted else [], sorted(nas - loc)
    return {"folder": folder, "files": a[:CAP], "only_on_nas": b[:CAP],
            "truncated": len(a) > CAP or len(b) > CAP}


@router.post("/sync")
def sync(request: Request):
    need(request)
    if not nas_mounted():
        raise HTTPException(409, "NAS is not mounted")
    from .runner import runner
    if not runner.start_sync():
        raise HTTPException(409, "a run is already in progress")
    return {"ok": True}
