# yt-dlp playlist downloader with a web interface

A small self-hosted web app that makes a yt-dlp playlist workflow easier to manage and human readable.
It keeps your list of YouTube / YouTube Music / SoundCloud playlists, downloads only new tracks (yt-dlp download
archive per playlist), copies them to a NAS folder, and shows what happened in plain language.
It uses **your own `yt-dlp.conf`**, so downloads behave exactly like running yt-dlp by hand.

> The previous contents of this repository (a Python CLI, work in progress) are kept on the `old-main` branch.

## Features
- **Playlists:** sortable table with the real playlist names (emoji included), on/off selection with *Select all /
  Deselect all* and a filter, add by URL (the name is read from the playlist), rename, remove, run one.
- **Run:** *Run all selected* with live progress (playlist n of m, current track, percent), a readable log and a Stop
  button. One run at a time.
- **History:** every run with per-playlist result and errors explained in plain words (age-restricted, private or
  removed video, rate limit, network, ffmpeg).
- **Library:** tracks on the NAS per playlist next to the archive count, files waiting to be copied (with a *Sync*
  button), detection of folders with garbled (mojibake) names.
- **Settings:** YouTube cookies upload for age-restricted videos, yt-dlp version and update button, and a form for
  the common `yt-dlp.conf` options (backup is made before every edit).
- Password login (scrypt), CSRF header check, same-site cookie. No built-in HTTPS: run it on a trusted LAN/VPN or
  behind a reverse proxy.

## Install
Needs Docker with the compose plugin.

```bash
git clone https://github.com/Rufusnu/yt-dlp-based-automation.git
cd yt-dlp-based-automation
cp .env.example .env        # edit the paths, see below
docker compose up -d --build
echo 'choose-a-password' | docker compose run --rm -T --no-deps ytdlp-web python3 -m app.setpw --stdin
docker compose restart
```
Open `http://<host>:8099`. Change the password later with
`docker exec -it ytdlp-web python3 -m app.setpw` and then `docker restart ytdlp-web`.

### Folder layout (`YT_BASE`)
```
YT_BASE/
  yt-dlp.conf     your yt-dlp options (the app passes it with --config-location)
  archive/        one "<playlist title>.archive" file per playlist (yt-dlp --download-archive)
  downloads/      staging folder yt-dlp writes to (set -P in yt-dlp.conf to this path)
  webui/          created by the app: database, password hash, session key, cookies, updatable yt-dlp copy
```
`YT_BASE` and the NAS mount are mounted at the same path inside the container, so absolute paths in `yt-dlp.conf`
(for example `-P "/home/you/scripts/yt-dlp/downloads/"`) keep working. Finished files are copied from
`downloads/` to `YT_NAS` (never overwriting, partial downloads skipped); the copy is refused if `YT_NAS_MOUNT`
is not mounted.

A minimal `yt-dlp.conf` that matches the app:
```
-i
-x
-f "bestaudio"
--audio-quality 0
-P "/path/to/YT_BASE/downloads/"
-o "%(playlist_title)s/%(artist|)s%(artist& - |)s%(title)s.%(ext)s"
-P temp:.tmp/
--sleep-interval 5
--max-sleep-interval 15
--embed-metadata
--embed-thumbnail
```
The archive file is named after the playlist title, so keep `%(playlist_title)s` in the output template.

### Importing existing playlists (optional)
*Import from scripts* reads two bash scripts in `YT_BASE` named `download_playlists_hq.bash` (all playlists) and
`download_playlists_hq_selective.bash` (the active ones). It looks for lines like
`"https://music.youtube.com/playlist?list=..." # name`; a leading `#` marks a playlist as inactive. If the files are
not there, nothing happens: just add playlists by URL.

## Age-restricted videos and cookies
Every playlist is first downloaded **anonymously**. Only if a YouTube playlist reports age-restricted tracks, and a
cookie file has been uploaded in Settings, the app runs that playlist once more with the cookies and a pause between
requests. SoundCloud never gets cookies. To export cookies: use an age-verified, preferably secondary, Google
account; open a private window, log in at youtube.com, open `https://www.youtube.com/robots.txt` in the same tab,
export youtube.com cookies with a cookies.txt browser extension, close the window, then upload the file in
*Settings > YouTube cookies*. Cookies expire and rotate, so re-upload when the error comes back. Using an account
with yt-dlp can get the account flagged; this is your risk.

## Security notes
- The cookie file is stored with mode 0600 and its content is never shown or logged.
- Do not expose port 8099 to the internet without HTTPS in front of it.
- Do not run your old scripts and the web app at the same time (the app cannot see them).
- Do not edit a bash script while it is running (bash reads it incrementally).

## Layout
`app/main.py` routes and login, `app/runner.py` download and copy logic, `app/library.py` library view,
`app/settings.py` cookies / yt-dlp update / config editor, `app/db.py` SQLite and script import,
`static/` single-page UI (no build step).

## License
GPL-3.0, see `LICENSE`.
