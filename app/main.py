import json, sqlite3, time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from . import auth
from .deps import need
from .library import fill_titles, router as library_router
from .settings import router as settings_router
from .db import BASE, conn, import_scripts, norm_key, source_of
from .runner import ARCH, count_lines, lookup_title, now, runner, safe_name

STATIC = Path(__file__).resolve().parent.parent / "static"
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(SessionMiddleware, secret_key=auth.secret_key(), session_cookie="ytw",
                   same_site="strict", max_age=7 * 24 * 3600)
fails = {}  # ip -> (count, blocked_until)

with conn() as _c:  # runs/items left "running" by a restart
    _c.execute("UPDATE runs SET status='interrupted', ended=? WHERE status='running'", (now(),))
    _c.execute("UPDATE run_items SET status='interrupted', ended=? WHERE status='running'", (now(),))




app.include_router(library_router)
app.include_router(settings_router)


@app.get("/static/{name}")
def static_js(name: str, request: Request):
    if name not in ("library.js", "settings.js"):
        raise HTTPException(404, "not found")
    need(request)
    return FileResponse(STATIC / name, media_type="application/javascript")


@app.get("/login", response_class=HTMLResponse)
def login_page():
    return (STATIC / "login.html").read_text(encoding="utf-8")


@app.post("/login")
def login(request: Request, body: dict):  # plain def: runs in the threadpool, the sleep/scrypt do not block the loop
    ip = request.client.host if request.client else "?"
    for k in [k for k, (_, u) in fails.items() if u and u < time.time()]:
        fails.pop(k, None)
    cnt, until = fails.get(ip, (0, 0))
    if until > time.time():
        return JSONResponse({"error": "too many attempts, wait a minute"}, status_code=429)
    if auth.check_password(str(body.get("password", ""))):
        fails.pop(ip, None)
        request.session["ok"] = True
        return {"ok": True}
    cnt += 1
    fails[ip] = (cnt, time.time() + 60 if cnt >= 5 else 0)
    time.sleep(1)
    return JSONResponse({"error": "wrong password"}, status_code=401)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/")
def index(request: Request):
    if not request.session.get("ok"):
        return RedirectResponse("/login")
    return FileResponse(STATIC / "index.html")


def rows(c):
    out = []
    for r in c.execute("SELECT * FROM playlists ORDER BY source DESC, name COLLATE NOCASE"):
        d = dict(r)
        d["display"] = r["title"] or r["name"]
        d["tracks"] = count_lines(ARCH / f"{safe_name(r['title'])}.archive") if safe_name(r["title"] or "") else None
        out.append(d)
    return out


@app.get("/api/playlists")
def playlists(request: Request):
    need(request)
    with conn() as c:
        return rows(c)


@app.post("/api/import")
def do_import(request: Request):
    need(request)
    return {"added": import_scripts(), "named": fill_titles()}


@app.post("/api/playlists")
def add_playlist(request: Request, body: dict):  # plain def: the name lookup takes a few seconds
    need(request)
    url = str(body.get("url", "")).strip()
    if not url.startswith(("https://", "http://")):
        raise HTTPException(400, "URL must start with http(s)://")
    with conn() as c:
        if c.execute("SELECT 1 FROM playlists WHERE key=?", (norm_key(url),)).fetchone():
            raise HTTPException(409, "this playlist is already in the list")
    title = lookup_title(url)
    if not title:
        raise HTTPException(400, "could not read the playlist name from that URL (wrong link, private playlist, or no network)")
    with conn() as c:
        try:
            c.execute("INSERT INTO playlists(key,url,name,source,enabled,title) VALUES(?,?,?,?,1,?)",
                      (norm_key(url), url, title, source_of(url), title))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "this playlist is already in the list")
    return {"ok": True, "name": title}


@app.post("/api/playlists/bulk")
async def bulk_enable(request: Request):
    need(request)
    b = await request.json()
    try:
        ids = [int(i) for i in b.get("ids", [])]
    except (TypeError, ValueError):
        raise HTTPException(400, "bad ids")
    on = 1 if b.get("enabled") else 0
    with conn() as c:
        c.executemany("UPDATE playlists SET enabled=? WHERE id=?", [(on, i) for i in ids])
    return {"ok": True, "changed": len(ids)}


@app.patch("/api/playlists/{pid}")
async def edit_playlist(pid: int, request: Request):
    need(request)
    b = await request.json()
    with conn() as c:
        if "enabled" in b:
            c.execute("UPDATE playlists SET enabled=? WHERE id=?", (1 if b["enabled"] else 0, pid))
        if "name" in b and str(b["name"]).strip():
            c.execute("UPDATE playlists SET name=? WHERE id=?", (str(b["name"]).strip(), pid))
    return {"ok": True}


@app.delete("/api/playlists/{pid}")
def del_playlist(pid: int, request: Request):
    need(request)
    with conn() as c:
        c.execute("DELETE FROM playlists WHERE id=?", (pid,))
    return {"ok": True}


@app.post("/api/run")
async def run(request: Request):
    need(request)
    b = await request.json()
    ids = b.get("ids")
    if ids is not None:
        try:
            ids = [int(i) for i in ids]
        except (TypeError, ValueError):
            raise HTTPException(400, "bad ids")
        if not ids:
            raise HTTPException(400, "nothing selected")
    if not runner.start(ids):
        raise HTTPException(409, "a run is already in progress")
    return {"ok": True}


@app.post("/api/stop")
def stop(request: Request):
    need(request)
    runner.stop()
    return {"ok": True}


@app.get("/api/status")
def status(request: Request, since: int = 0, epoch: int = -1):
    need(request)
    return runner.snapshot(since, epoch)


@app.get("/api/runs")
def runs(request: Request):
    need(request)
    with conn() as c:
        out = []
        for r in c.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 30"):
            d = dict(r)
            d["items"] = [dict(i, errors=json.loads(i["errors"] or "[]")) for i in
                          c.execute("SELECT * FROM run_items WHERE run_id=? ORDER BY id", (r["id"],))]
            out.append(d)
        return out
