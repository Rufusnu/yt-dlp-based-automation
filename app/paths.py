import os
from pathlib import Path

BASE = Path(os.environ.get("YT_BASE", "/data/yt-dlp"))
DATA = BASE / "webui"
CONF = BASE / "yt-dlp.conf"
ARCH = BASE / "archive"
DL = BASE / "downloads"
NAS = Path(os.environ.get("YT_NAS", "/data/nas/downloads"))
NAS_MOUNT = Path(os.environ.get("YT_NAS_MOUNT", "/data/nas"))
COOKIES = DATA / "cookies.txt"  # Netscape format, 0600, content is never shown or logged
BIN_DIR = DATA / "bin"          # writable copy of yt-dlp that the Settings page can update


def ytdlp_bin():
    p = BIN_DIR / "yt-dlp"
    return str(p) if p.exists() else os.environ.get("YT_BIN", "yt-dlp")
