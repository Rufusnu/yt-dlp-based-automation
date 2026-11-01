import os, re, shutil, subprocess
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from .deps import need
from .paths import BASE, BIN_DIR, CONF, COOKIES, DATA, ytdlp_bin
from .runner import runner

router = APIRouter(prefix="/api/settings")

# ---- cookies -------------------------------------------------------------
MAX_COOKIES = 512 * 1024
LOGIN = {"SID", "HSID", "SSID", "APISID", "SAPISID", "LOGIN_INFO", "__Secure-1PSID", "__Secure-3PSID",
         "__Secure-1PAPISID", "__Secure-3PAPISID"}


def _iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")


def _is_g(domain):
    d = domain.lstrip(".").lower()
    return any(d == s or d.endswith("." + s) for s in ("youtube.com", "google.com"))


def parse_cookies(text):
    """-> list of (domain, expiry, name). Raises ValueError (never echoes content)."""
    out = []
    for n, line in enumerate(text.split("\n"), 1):
        line = line.rstrip("\r")
        if line.startswith("#HttpOnly_"):
            line = line[len("#HttpOnly_"):]
        elif not line.strip() or line.lstrip().startswith("#"):
            continue
        f = line.split("\t")
        if len(f) != 7:
            raise ValueError(f"Line {n} is not a cookie line (expected 7 tab-separated fields). Export again as Netscape cookies.txt.")
        try:
            exp = int(float(f[4])) if f[4].strip() else 0
        except ValueError:
            raise ValueError(f"Line {n} has an invalid expiry field.")
        out.append((f[0], exp, f[5]))
    return out


def validate_cookies(text):
    if len(text.encode("utf-8", "replace")) > MAX_COOKIES:
        raise ValueError("Cookie text is too large (max 512 KB).")
    if "\x00" in text:
        raise ValueError("Cookie text contains invalid characters.")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    cs = parse_cookies(text)
    if not any(_is_g(d) for d, _, _ in cs):
        raise ValueError("No cookies for youtube.com or google.com found. Export the cookies while on youtube.com, logged in.")
    return text.strip("\n") + "\n"


def cookie_info(text, now=None):
    now = now or datetime.now(timezone.utc).timestamp()
    cs = parse_cookies(text)
    yt = [c for c in cs if _is_g(c[0])]
    login = [c for c in yt if c[2] in LOGIN]
    exps = [c[1] for c in login if c[1] > 0]
    early = min(exps) if exps else None
    expired = early is not None and early < now
    w = []
    if not login:
        w.append("No Google/YouTube login cookies (SID, LOGIN_INFO ...) found; you may not have been logged in when exporting.")
    if expired:
        w.append("Login cookies have expired; export and upload them again.")
    elif early is not None and early - now < 7 * 86400:
        w.append("Login cookies expire within 7 days.")
    return {"entries": len(cs), "youtube_entries": len(yt), "earliest_expiry": _iso(early) if early else None,
            "expired": expired, "warnings": w}


def cookie_status():
    try:
        st = COOKIES.stat()
    except FileNotFoundError:
        return {"present": False, "size": 0, "modified": None, "entries": 0, "youtube_entries": 0,
                "earliest_expiry": None, "expired": False, "warnings": []}
    r = {"present": True, "size": st.st_size, "modified": _iso(st.st_mtime)}
    try:
        r.update(cookie_info(COOKIES.read_text("utf-8", "replace")))
    except ValueError:
        r.update(entries=0, youtube_entries=0, earliest_expiry=None, expired=False,
                 warnings=["Stored cookie file could not be parsed (yt-dlp may have rewritten it); upload it again."])
    return r


def write_atomic(path, data, mode=None):
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode if mode is not None else 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(data)
        os.chmod(tmp, mode if mode is not None else 0o600)
        os.replace(tmp, path)
    except BaseException:
        try: os.unlink(tmp)
        except OSError: pass
        raise


def busy():
    if runner.running:
        raise HTTPException(409, "A run is active; wait for it to finish.")


@router.get("/cookies")
def cookies_get(request: Request):
    need(request)
    return cookie_status()


@router.post("/cookies")
def cookies_set(request: Request, body: dict):
    need(request)
    text = body.get("text")
    if not isinstance(text, str):
        raise HTTPException(400, "text required")
    busy()
    try:
        text = validate_cookies(text)
    except ValueError as e:
        raise HTTPException(400, str(e))
    DATA.mkdir(parents=True, exist_ok=True)
    write_atomic(COOKIES, text, 0o600)
    return cookie_status()


@router.delete("/cookies")
def cookies_del(request: Request):
    need(request)
    busy()
    COOKIES.unlink(missing_ok=True)
    return cookie_status()

# ---- yt-dlp version / update ---------------------------------------------


def version_of(binary):
    try:
        r = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=20, cwd=DATA if DATA.is_dir() else None)
        return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None
    except (OSError, subprocess.SubprocessError):
        return None


@router.get("/ytdlp")
def ytdlp_get(request: Request):
    need(request)
    return {"version": version_of(ytdlp_bin()), "using_updatable_copy": (BIN_DIR / "yt-dlp").exists()}


@router.post("/ytdlp/update")
def ytdlp_update(request: Request):
    need(request)
    busy()
    cp, prev = BIN_DIR / "yt-dlp", BIN_DIR / "yt-dlp.prev"
    before = version_of(ytdlp_bin())
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    if not cp.exists():
        src = shutil.which("yt-dlp") or "/usr/local/bin/yt-dlp"
        if not os.path.exists(src):
            raise HTTPException(500, "yt-dlp binary not found to copy")
        shutil.copy2(src, cp)
        os.chmod(cp, 0o755)
    shutil.copy2(cp, prev)
    try:
        r = subprocess.run([str(cp), "-U"], capture_output=True, text=True, timeout=180, cwd=DATA if DATA.is_dir() else None)
        out = (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        out = "Update timed out after 180 s."
    except OSError as e:
        out = f"Could not run updater: {e.__class__.__name__}"
    after = version_of(str(cp))
    if after is None:
        shutil.copy2(prev, cp)
        os.chmod(cp, 0o755)
        out += "\nNew binary failed --version; previous binary restored."
        after = version_of(str(cp))
    return {"before": before, "after": after, "changed": before != after, "output": out[-2000:]}

# ---- config --------------------------------------------------------------
BOOLS = {"embed_thumbnail": "--embed-thumbnail", "embed_metadata": "--embed-metadata"}
INTS = {"audio_quality": ("--audio-quality", 0, 10), "sleep_interval": ("--sleep-interval", 0, 300),
        "max_sleep_interval": ("--max-sleep-interval", 0, 600), "concurrent_fragments": ("--concurrent-fragments", 1, 8),
        "retries": ("--retries", 0, 50), "fragment_retries": ("--fragment-retries", 0, 50),
        "socket_timeout": ("--socket-timeout", 5, 300)}
FLAGS = {k: v[0] for k, v in INTS.items()} | {"throttled_rate": "--throttled-rate"} | BOOLS
RATE = re.compile(r"^\d+[KkMm]?$")


def _active(line, flag):
    m = re.match(r"^\s*" + re.escape(flag) + r"(?:\s+(.*?))?\s*$", line)
    return (True, m.group(1)) if m else (False, None)


def read_values(text):
    lines = text.split("\n")
    vals = {}
    for k, flag in FLAGS.items():
        found, v = None, None
        for ln in lines:
            ok, val = _active(ln, flag)
            if ok:
                found, v = True, val
                break
        if k in BOOLS:
            vals[k] = bool(found)
        elif not found or v is None:
            vals[k] = None
        elif k in INTS:
            vals[k] = int(v) if re.fullmatch(r"\d+", v) else v
        else:
            vals[k] = v
    return vals


def validate_values(new, cur):
    out = {}
    for k, v in new.items():
        if k not in FLAGS:
            raise ValueError(f"Unknown setting: {k}")
        if k in BOOLS:
            if not isinstance(v, bool):
                raise ValueError(f"{k}: must be true or false")
        elif k in INTS:
            lo, hi = INTS[k][1:]
            if isinstance(v, str) and re.fullmatch(r"\d{1,6}", v.strip()):
                v = int(v)
            if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
                raise ValueError(f"{k}: must be a whole number from {lo} to {hi}")
        else:
            if isinstance(v, int) and not isinstance(v, bool):
                v = str(v)
            if not isinstance(v, str) or not RATE.match(v.strip()):
                raise ValueError(f"{k}: must be a number with optional K or M, e.g. 100K")
            v = v.strip()
        out[k] = v
    m = {**cur, **out}
    s, mx = m.get("sleep_interval"), m.get("max_sleep_interval")
    if isinstance(s, int) and isinstance(mx, int) and mx < s and ("sleep_interval" in out or "max_sleep_interval" in out):
        raise ValueError("max_sleep_interval: must be at least sleep_interval")
    return out


def rewrite(text, new):
    lines = text.split("\n")
    tail = lines[-1] == ""
    if tail:
        lines.pop()
    for k, v in new.items():
        flag = FLAGS[k]
        if k in BOOLS:
            act = [i for i, ln in enumerate(lines) if _active(ln, flag)[0]]
            if v and not act:
                cm = [i for i, ln in enumerate(lines) if re.match(r"^\s*#\s*" + re.escape(flag) + r"\s*$", ln)]
                if cm:
                    lines[cm[0]] = flag
                else:
                    lines.append(flag)
            elif not v:
                for i in act:
                    lines[i] = "#" + lines[i]
        else:
            hit = False
            for i, ln in enumerate(lines):
                if _active(ln, flag)[0]:
                    lead = re.match(r"\s*", ln).group(0)
                    lines[i] = f"{lead}{flag} {v}"
                    hit = True
            if not hit:
                lines.append(f"{flag} {v}")
    return "\n".join(lines) + "\n" if (tail or not text) else "\n".join(lines)


def prune_backups(conf, keep=10):
    for p in sorted(conf.parent.glob(conf.name + ".bak-*"))[:-keep]:
        p.unlink(missing_ok=True)


def config_state():
    try:
        raw = CONF.read_text("utf-8", "replace")
    except FileNotFoundError:
        raw = ""
    return {"values": read_values(raw), "raw": raw}


@router.get("/config")
def config_get(request: Request):
    need(request)
    return config_state()


@router.put("/config")
def config_put(request: Request, body: dict):
    need(request)
    vals = body.get("values")
    if not isinstance(vals, dict):
        raise HTTPException(400, "values required")
    busy()
    st = config_state()
    try:
        new = validate_values({k: v for k, v in vals.items() if v is not None or k not in FLAGS}, st["values"])
    except ValueError as e:
        raise HTTPException(400, str(e))
    text = rewrite(st["raw"], new)
    if text != st["raw"]:
        if CONF.exists():
            bak = CONF.with_name(CONF.name + datetime.now().strftime(".bak-%Y%m%d-%H%M%S"))
            shutil.copy2(CONF, bak)
            prune_backups(CONF)
            mode = CONF.stat().st_mode & 0o777
        else:
            mode = 0o644
        write_atomic(CONF, text, mode)
    return config_state()
