import subprocess
import json
from app.results import DownloadResult, OperationStatus

class DownloadService:
    def __init__(self, archive, yt_dlp_config):
        self.archive = archive
        self.yt_dlp_config = yt_dlp_config

    def get_playlist_name(self, playlist_url) -> tuple[str, str | None]:
        """Fetch playlist name from yt-dlp. Returns (name, error)"""
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
                            return data["playlist_title"], None
                        # Fallback to playlist field
                        if "playlist" in data:
                            return data["playlist"], None
        except Exception as e:
            return "Unknown", str(e)
        return "Unknown", "No playlist data found"

    def fetch(self, playlist_url) -> DownloadResult:
        """Download playlist tracks."""
        cmd = [
            "yt-dlp",
            "--config-location", str(self.yt_dlp_config),
            "--download-archive", str(self.archive),
            playlist_url,
        ]
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        
        if result.returncode == 0:
            return DownloadResult(
                success=True,
                operation="download",
                status=OperationStatus.SUCCESS,
                data={"url": playlist_url}
            )
        else:
            return DownloadResult(
                success=False,
                operation="download",
                status=OperationStatus.FAILED,
                error=result.stderr or "Download failed",
                data={"url": playlist_url}
            )
