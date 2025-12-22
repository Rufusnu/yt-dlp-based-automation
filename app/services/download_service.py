import subprocess
import json
from app.services.logging_service import LoggingService

class DownloadService:
    def __init__(self, archive, yt_dlp_config):
        self.archive = archive
        self.yt_dlp_config = yt_dlp_config

    def get_playlist_name(self, playlist_url):
        """Fetch playlist name from yt-dlp"""
        cmd = [
            "yt-dlp",
            "--dump-json",
            "--flat-playlist",
            "--playlist-items", "1",
            playlist_url,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line.strip():
                        data = json.loads(line)
                        # Get playlist_title if available
                        if "playlist_title" in data:
                            return data["playlist_title"]
                        # Fallback to playlist field
                        if "playlist" in data:
                            return data["playlist"]
        except Exception as e:
            LoggingService.warning(f"Could not fetch playlist name: {e}")
        return "Unknown"

    def fetch(self, playlist_url):
        cmd = [
            "yt-dlp",
            "--config-location", str(self.yt_dlp_config),
            "--download-archive", str(self.archive),
            playlist_url,
        ]
        subprocess.run(cmd, check=False)
