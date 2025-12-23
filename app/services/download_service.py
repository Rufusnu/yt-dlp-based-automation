"""
Download service - orchestrates downloading and file matching.
Delegates platform-specific logic to platform services.
"""
import subprocess
import re
from pathlib import Path
from typing import List, Optional, Tuple

from app.results import DownloadResult, OperationStatus
from app.services.platforms import PlatformFactory, TrackInfo


class DownloadService:
    """
    Handles downloading tracks and matching them to local files.
    
    Responsibilities:
    - Execute yt-dlp downloads
    - Delegate metadata fetching to platform services
    - Match tracks to local files
    
    Does NOT handle:
    - Platform-specific metadata parsing (delegated to platform services)
    """
    
    def __init__(self, archive: Path, yt_dlp_config: Path, music_dir: Path):
        self.archive = archive
        self.yt_dlp_config = yt_dlp_config
        self.music_dir = music_dir
    
    def get_playlist_name(self, playlist_url: str) -> Tuple[str, Optional[str]]:
        """
        Fetch playlist name using the appropriate platform service.
        
        Returns:
            Tuple of (playlist_name, error_message or None)
        """
        service = PlatformFactory.get_service(playlist_url)
        if not service:
            return "Unknown", f"Unsupported platform for URL: {playlist_url}"
        
        return service.get_playlist_name(playlist_url)
    
    def get_playlist_tracks(self, playlist_url: str) -> Tuple[List[TrackInfo], Optional[str]]:
        """
        Fetch all tracks from a playlist using the appropriate platform service.
        
        Returns:
            Tuple of (list of TrackInfo, error_message or None)
        """
        service = PlatformFactory.get_service(playlist_url)
        if not service:
            return [], f"Unsupported platform for URL: {playlist_url}"
        
        return service.get_playlist_tracks(playlist_url)
    
    def fetch(self, playlist_url: str) -> DownloadResult:
        """
        Download playlist tracks using yt-dlp.
        
        This is platform-agnostic - yt-dlp handles all platforms.
        """
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
    
    def find_local_file(self, track: TrackInfo) -> Optional[Path]:
        """
        Find the local file matching a track.
        
        Matching strategy:
        1. Exact match: "Artist - Title.ext"
        2. Fuzzy match: search for files containing sanitized artist + title
        """
        extensions = ['.opus', '.mp3', '.m4a', '.webm', '.ogg', '.flac']
        
        # Strategy 1: Exact match
        for ext in extensions:
            exact_path = self.music_dir / f"{track.expected_filename}{ext}"
            if exact_path.exists():
                return exact_path
        
        # Strategy 2: Fuzzy match (handles yt-dlp filename sanitization)
        sanitized_title = self._sanitize_for_search(track.title)
        sanitized_artist = self._sanitize_for_search(track.artist)
        
        for f in self.music_dir.glob("*.*"):
            if f.suffix.lower() not in extensions:
                continue
            
            filename_lower = f.stem.lower()
            
            # Match if both artist and title are in filename
            if sanitized_title in filename_lower and sanitized_artist in filename_lower:
                return f
            
            # Or just title if artist is generic/unknown
            if track.artist == "Unknown Artist" and sanitized_title in filename_lower:
                return f
        
        return None
    
    def _sanitize_for_search(self, text: str) -> str:
        """Sanitize text for fuzzy filename matching."""
        # Keep only alphanumeric and spaces, lowercase
        cleaned = re.sub(r'[^\w\s]', '', text.lower())
        return cleaned.strip()
