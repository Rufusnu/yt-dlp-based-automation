import contextlib, os, re, sqlite3
from pathlib import Path

BASE = Path(os.environ.get("YT_BASE", "/data/yt-dlp"))
DATA = BASE / "webui"
SCHEMA = """
CREATE TABLE IF NOT EXISTS playlists(
  id INTEGER PRIMARY KEY, key TEXT UNIQUE, url TEXT NOT NULL, name TEXT NOT NULL,
  source TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, title TEXT, last_run TEXT);
CREATE TABLE IF NOT EXISTS runs(
  id INTEGER PRIMARY KEY, started TEXT, ended TEXT, status TEXT, summary TEXT);
CREATE TABLE IF NOT EXISTS run_items(
  id INTEGER PRIMARY KEY, run_id INTEGER, playlist_id INTEGER, name TEXT,
  started TEXT, ended TEXT, status TEXT, new_tracks INTEGER DEFAULT 0,
  skipped INTEGER DEFAULT 0, errors TEXT DEFAULT '[]', copied INTEGER DEFAULT 0);
"""


_ready = False


@contextlib.contextmanager
def conn():
    global _ready
    DATA.mkdir(exist_ok=True)
    c = sqlite3.connect(DATA / "app.db", timeout=30)
    c.row_factory = sqlite3.Row
    if not _ready:
        c.executescript(SCHEMA)
        _ready = True
    try:
        with c:
            yield c
    finally:
        c.close()


def norm_key(url):
    m = re.search(r"[?&]list=([^&]+)", url)
    if m:
        return "yt:" + m.group(1)
    return url.split("?")[0].rstrip("/")


def source_of(url):
    return "soundcloud" if "soundcloud.com" in url else "youtube"


LINE = re.compile(r'^\s*(#\s*)?"(https?://[^"]+)"\s*(?:#\s*(.*))?$')


def parse_script(path):
    out = []
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:  # the import button is optional
        return out
    for line in text.splitlines():
        m = LINE.match(line)
        if m:
            out.append((m.group(2), (m.group(3) or "").strip(), m.group(1) is None))
    return out


def import_scripts():
    """Playlists from the all-playlists script; enabled = active in the selective script."""
    allp = parse_script(BASE / "download_playlists_hq.bash")
    sel = parse_script(BASE / "download_playlists_hq_selective.bash")
    active = {norm_key(u) for u, _, on in sel if on}
    items = {}
    for u, n, _ in allp + sel:
        items.setdefault(norm_key(u), (u, n))
    added = 0
    with conn() as c:
        for k, (u, n) in items.items():
            if c.execute("SELECT 1 FROM playlists WHERE key=?", (k,)).fetchone():
                continue
            c.execute("INSERT OR IGNORE INTO playlists(key,url,name,source,enabled) VALUES(?,?,?,?,?)",
                      (k, u, n or "(unnamed)", source_of(u), 1 if k in active else 0))
            added += 1
    return added
