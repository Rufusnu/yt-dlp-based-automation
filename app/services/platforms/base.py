"""
Base platform service interface.
All platform-specific services must implement this contract.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
import subprocess
import json


@dataclass
class TrackInfo:
    """Track information from a music platform."""
    title: str
    artist: str
    expected_filename: str  # The filename yt-dlp will generate
    video_id: str


class BasePlatformService(ABC):
    """
    Abstract base class for platform-specific services.
    
    Each platform (YouTube, SoundCloud, etc.) must implement:
    - get_playlist_name(): Fetch the playlist title
    - get_playlist_tracks(): Fetch all tracks with metadata
    - can_handle(): Check if this service handles a given URL
    """
    
    @staticmethod
    @abstractmethod
    def can_handle(url: str) -> bool:
        """Check if this service can handle the given URL."""
        pass
    
    @abstractmethod
    def get_playlist_name(self, playlist_url: str) -> Tuple[str, Optional[str]]:
        """
        Fetch playlist name from the platform.
        
        Returns:
            Tuple of (playlist_name, error_message or None)
        """
        pass
    
    @abstractmethod
    def get_playlist_tracks(self, playlist_url: str) -> Tuple[List[TrackInfo], Optional[str]]:
        """
        Fetch all track info from a playlist.
        
        Returns:
            Tuple of (list of TrackInfo, error_message or None)
        """
        pass
    
    def _run_ytdlp(self, args: List[str]) -> subprocess.CompletedProcess:
        """Run yt-dlp with given arguments."""
        cmd = ["yt-dlp"] + args
        return subprocess.run(cmd, capture_output=True, text=True, check=False)
    
    def _parse_json_lines(self, output: str) -> List[dict]:
        """Parse newline-delimited JSON output from yt-dlp."""
        results = []
        for line in output.strip().split('\n'):
            if not line.strip():
                continue
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return results
    
    def _build_filename(self, artist: str, title: str) -> str:
        """
        Build expected filename matching yt-dlp.conf template.
        Template: %(artist,uploader|Unknown Artist)s - %(title)s.%(ext)s
        """
        return f"{artist} - {title}"
