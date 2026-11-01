import json, os, re, shutil, signal, subprocess, threading, time
from datetime import datetime
from pathlib import Path

from .db import conn
from .paths import ARCH, BASE, CONF, COOKIES, DL, NAS, NAS_MOUNT, ytdlp_bin
IDLE_KILL = 600  # seconds without any yt-dlp output before the process is killed
SKIP = (".part", ".ytdl", ".temp", ".tmp")

ERRORS = [
    (r"confirm your age|age-restricted|inappropriate for some users", "Age-restricted video, needs YouTube cookies"),
    (r"Private video|members-only|Join this channel", "Private or members-only video"),
    (r"Video unavailable|has been removed|not available|no longer available|copyright", "Video unavailable or removed"),
    (r"HTTP Error 429|Too Many Requests|not a bot|rate-limit", "Rate-limited or bot check by the site, try again later"),
    (r"Unable to download|timed out|Temporary failure|Connection|Network is unreachable", "Network problem while downloading"),
    (r"ffmpeg|ffprobe|Postprocessing", "Conversion (ffmpeg) problem"),
]


def explain(line):
    for pat, text in ERRORS:
        if re.search(pat, line, re.I):
            return text
    return "Other error"


def safe_name(t):
    """Playlist title as a file name: no path separators, no leading dots (titles come from the internet)."""
    t = t.replace("\x00", "").replace("/", "_").replace("\\", "_").strip().lstrip(".")
    return t if t and t != ".." else ""


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def count_lines(p):
    try:
        return sum(1 for _ in open(p, encoding="utf-8", errors="replace"))
    except FileNotFoundError:
        return 0


def killgroup(p, sig=signal.SIGTERM):
    try:
        os.killpg(p.pid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def lookup_title(url):
    """Playlist title from YouTube/SoundCloud (one flat request); '' when it cannot be read."""
    try:
        r = subprocess.run([ytdlp_bin(), "--ignore-config", "--skip-download", "--flat-playlist", "--playlist-items", "1",
                            "--quiet", "--print", "%(playlist_title)s", "--", url], cwd=BASE, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=90, start_new_session=True)
    except (subprocess.TimeoutExpired, OSError):
        return ""
    lines = [l.strip() for l in r.stdout.splitlines() if l.strip()]
    return safe_name(lines[0]) if lines else ""


class Runner:
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.stop_flag = False
        self.proc = None
        self.last_out = time.time()
        self.epoch = 0
        self.log, self.base = [], 0
        self.status = {"state": "idle"}

    def addlog(self, line):
        with self.lock:
            self.log.append(f"{datetime.now():%H:%M:%S} {line}")
            if len(self.log) > 4000:
                del self.log[:1000]
                self.base += 1000

    def snapshot(self, since, epoch):
        with self.lock:
            reset = epoch != self.epoch
            if reset:
                since = 0
            return {"log": self.log[max(0, since - self.base):], "next": self.base + len(self.log), "epoch": self.epoch,
                    "reset": reset, "status": dict(self.status), "running": self.running}

    def start(self, ids):
        with self.lock:
            if self.running:
                return False
            self.running, self.stop_flag = True, False
            self.epoch += 1
            self.log, self.base = [], 0
            self.status = {"state": "starting"}
        threading.Thread(target=self._run, args=(ids,), daemon=True).start()
        threading.Thread(target=self._watchdog, daemon=True).start()
        return True

    def start_sync(self):
        """Copy-only job (no download): push everything not yet on the NAS."""
        with self.lock:
            if self.running:
                return False
            self.running, self.stop_flag = True, False
            self.epoch += 1
            self.log, self.base = [], 0
            self.status = {"state": "running", "idx": 1, "total": 1, "playlist": "Sync to NAS",
                           "step": "copying to NAS", "track": "", "pct": 0, "new": 0}
        threading.Thread(target=self._sync, daemon=True).start()
        return True

    def _sync(self):
        run_id, ok = None, False
        try:
            with conn() as c:
                run_id = c.execute("INSERT INTO runs(started,status) VALUES(?,?)", (now(), "running")).lastrowid
            self.addlog(f"Sync #{run_id}: copying files that are not on the NAS yet")
            ok = self._copy_to_nas()
        except Exception as e:
            self.addlog(f"Sync crashed: {e!r}")
        finally:
            try:
                if run_id:
                    with conn() as c:
                        c.execute("UPDATE runs SET ended=?,status=?,summary=? WHERE id=?",
                                  (now(), "ok" if ok else "errors", "sync to NAS only", run_id))
            finally:
                with self.lock:
                    self.running = False
                    self.status = {"state": "idle"}

    def stop(self):
        with self.lock:
            self.stop_flag = True
            p = self.proc
        if p and p.poll() is None:
            killgroup(p)
            threading.Timer(10, lambda: killgroup(p, signal.SIGKILL)).start()

    def _watchdog(self):
        while self.running:
            time.sleep(30)
            p = self.proc
            if p and p.poll() is None and time.time() - self.last_out > IDLE_KILL:
                self.addlog(f"  ✗ no output from yt-dlp for {IDLE_KILL // 60} min, killing it")
                killgroup(p, signal.SIGKILL)

    def _spawn(self, cmd, merge):
        with self.lock:
            if self.stop_flag:
                return None
            p = subprocess.Popen(cmd, cwd=BASE, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT if merge else subprocess.DEVNULL, text=True,
                                 encoding="utf-8", errors="replace", bufsize=1, start_new_session=True)
            self.proc, self.last_out = p, time.time()
            return p

    def _set(self, **kw):
        with self.lock:
            self.status.update(kw)

    # ---- run
    def _run(self, ids):
        run_id = None
        status, summary = "failed", ""
        try:
            with conn() as c:
                q = "SELECT * FROM playlists WHERE enabled=1 ORDER BY id" if ids is None else \
                    "SELECT * FROM playlists WHERE id IN (%s) ORDER BY id" % ",".join("?" * len(ids))
                pls = c.execute(q, [] if ids is None else ids).fetchall()
                run_id = c.execute("INSERT INTO runs(started,status) VALUES(?,?)", (now(), "running")).lastrowid
            self.addlog(f"Run #{run_id}: {len(pls)} playlist(s)")
            tot_new, tot_err = 0, 0
            for i, pl in enumerate(pls, 1):
                if self.stop_flag:
                    break
                new, errs = self._playlist(run_id, i, len(pls), pl)
                tot_new += new
                tot_err += errs
            status = "stopped" if self.stop_flag else ("errors" if tot_err else "ok")
            summary = f"{tot_new} new track(s), {tot_err} error(s)"
            self.addlog(f"Run finished: {status}, {summary}")
        except Exception as e:  # keep the UI usable whatever happens
            self.addlog(f"Run crashed: {e!r}")
            summary = f"crashed: {e!r}"[:200]
        finally:
            try:
                if run_id:
                    with conn() as c:
                        c.execute("UPDATE runs SET ended=?,status=?,summary=? WHERE id=?", (now(), status, summary, run_id))
            finally:
                with self.lock:
                    self.running = False
                    self.proc = None
                    self.status = {"state": "idle"}

    def _resolve_title(self, url):
        p = self._spawn([ytdlp_bin(), "--ignore-config", "--skip-download", "--flat-playlist", "--playlist-items", "1",
                         "--quiet", "--print", "%(playlist_title)s", "--", url], merge=False)
        if p is None:
            return ""
        try:
            out, _ = p.communicate(timeout=180)
        except subprocess.TimeoutExpired:
            killgroup(p, signal.SIGKILL)
            p.communicate()
            return ""
        lines = [l.strip() for l in (out or "").splitlines() if l.strip()]
        return safe_name(lines[0]) if lines else ""

    def _playlist(self, run_id, idx, total, pl):
        errors, skipped = [], 0
        with conn() as c:
            item = c.execute("INSERT INTO run_items(run_id,playlist_id,name,started,status) VALUES(?,?,?,?,?)",
                             (run_id, pl["id"], pl["name"], now(), "running")).lastrowid
        self._set(state="running", run_id=run_id, idx=idx, total=total, playlist=pl["name"], step="resolving name",
                  track="", pct=0, new=0)
        self.addlog(f"[{idx}/{total}] {pl['name']}")
        status, new, copied = "ok", 0, 0
        try:
            title = self._resolve_title(pl["url"])
            if self.stop_flag:
                raise RuntimeError("stopped")
            if not title:
                raise RuntimeError("could not determine the playlist name (network, private or removed playlist?)")
            with conn() as c:
                c.execute("UPDATE playlists SET title=? WHERE id=?", (title, pl["id"]))
            archive = ARCH / f"{title}.archive"
            before = count_lines(archive)
            self._set(step="downloading")
            errors, skipped, rc = self._pass(pl["url"], archive, cookies=False)
            if pl["source"] == "youtube" and not self.stop_flag and any(e["why"].startswith("Age-restricted") for e in errors):
                if COOKIES.exists():  # second pass only for playlists that hit age-restricted tracks
                    self.addlog("  age-restricted track(s) found, retrying them once with your cookies")
                    self._set(step="retrying with cookies", pct=0)
                    errors, _, rc = self._pass(pl["url"], archive, cookies=True)
                else:
                    self.addlog("  hint: upload YouTube cookies in Settings to download age-restricted tracks")
            new = max(0, count_lines(archive) - before)
            self._set(new=new)
            if rc and not errors and not self.stop_flag:
                errors.append({"text": f"yt-dlp exited with code {rc}", "why": "yt-dlp stopped unexpectedly"})
            if self.stop_flag:
                status = "stopped"
            elif errors:
                status = "errors"
            self.addlog(f"  {new} new, {skipped} already had, {len(errors)} error(s) (yt-dlp exit {rc})")
            if not self.stop_flag:
                self._set(step="copying to NAS")
                copied = 1 if self._copy_to_nas() else 0
                if not copied:
                    status = "errors" if status == "ok" else status
                    errors.append({"text": "copy to NAS failed", "why": "NAS copy failed, files are only on the VM"})
        except Exception as e:
            status = "stopped" if self.stop_flag else "failed"
            if str(e) != "stopped":
                errors.append({"text": str(e)[:400], "why": explain(str(e))})
                self.addlog(f"  ✗ {e}")
        with conn() as c:
            c.execute("UPDATE run_items SET ended=?,status=?,new_tracks=?,skipped=?,errors=?,copied=? WHERE id=?",
                      (now(), status, new, skipped, json.dumps(errors, ensure_ascii=False), copied, item))
            c.execute("UPDATE playlists SET last_run=? WHERE id=?", (now(), pl["id"]))
        return new, len(errors)

    def _pass(self, url, archive, cookies):
        """One yt-dlp run on a playlist; cookies (and a pause between requests) only when asked."""
        errors, skipped = [], 0
        extra = ["--cookies", str(COOKIES), "--sleep-requests", "1"] if cookies else []
        p = self._spawn([ytdlp_bin(), "--config-location", str(CONF), "--no-quiet", "--newline", *extra,
                         "--download-archive", str(archive), "--", url], merge=True)
        if p is None:
            raise RuntimeError("stopped")
        for raw in p.stdout:
            self.last_out = time.time()
            line = raw.rstrip("\n")
            m = re.match(r"\[download\]\s+([\d.]+)%", line)
            if m:
                self._set(pct=float(m.group(1)))
            elif "has already been recorded in the archive" in line:
                skipped += 1
            elif line.startswith(("[ExtractAudio] Destination:", "[download] Destination:")):
                name = os.path.splitext(os.path.basename(line.split("Destination:", 1)[1].strip()))[0]
                self._set(track=name, pct=0)
                self.addlog(f"  ↓ {name}")
            elif line.startswith("ERROR"):
                errors.append({"text": line[:400], "why": explain(line)})
                self.addlog(f"  ✗ {explain(line)}: {line[:200]}")
            elif line.startswith("WARNING"):
                self.addlog(f"  ! {line[:200]}")
        return errors, skipped, p.wait()

    def _copy_to_nas(self):
        """Copy files that are not on the NAS yet. Never overwrites or deletes; skips partial downloads."""
        if not os.path.ismount(NAS_MOUNT) or not NAS.is_dir():
            self.addlog(f"  ✗ NAS not mounted ({NAS_MOUNT}); nothing copied")
            return False
        n, bad = 0, 0
        for root, dirs, files in os.walk(DL):
            dirs[:] = [d for d in dirs if d != ".tmp"]
            rel = os.path.relpath(root, DL)
            dst = NAS if rel == "." else NAS / rel
            for f in files:
                if f.endswith(SKIP) or ".part-" in f:
                    continue
                t = dst / f
                if t.exists():
                    continue
                try:
                    dst.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(Path(root) / f, t)
                    n += 1
                except OSError as e:
                    bad += 1
                    try:
                        t.unlink()
                    except OSError:
                        pass
                    if bad <= 3:
                        self.addlog(f"  ✗ copy failed: {f}: {e}")
        self.addlog(f"  {'✓' if not bad else '✗'} copied {n} file(s) to NAS" + (f", {bad} failed" if bad else ""))
        return bad == 0


runner = Runner()
