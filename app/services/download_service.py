import subprocess
import json

class DownloadService:
    def __init__(self, archive, yt_dlp_config):
        self.archive = archive
        self.yt_dlp_config = yt_dlp_config

    def get_playlist_name(self, playlist_url):
        """Fetch playlist name from yt-dlp"""
        cmd = [
            "yt-dlp",
            "--dump-json",
            "--playlist-items", "0",
            "--flat-playlist",
            playlist_url,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout.strip().split('\n')[0])
                return data.get("playlist_title") or data.get("title") or "Unknown"
        except Exception:
            pass
        return "Unknown"

    def fetch(self, playlist_url):
        cmd = [
            "yt-dlp",
            "--config-location", str(self.yt_dlp_config),
            "--download-archive", str(self.archive),
            playlist_url,
        ]
        subprocess.run(cmd, check=False)
