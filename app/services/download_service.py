"""
Download service - orchestrates downloading and file matching.
Delegates platform-specific logic to platform services.
"""
import subprocess
import json
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime

from app.results import DownloadResult, OperationStatus
from app.services.platforms import PlatformFactory, TrackInfo


class DownloadService:
    """
    Handles downloading tracks and matching them to local files.
    
    Responsibilities:
    - Execute yt-dlp downloads
    - Delegate metadata fetching to platform services
    - Match tracks to local files using strict matching
    - Track ambiguous matches for manual review
    
    Does NOT handle:
    - Platform-specific metadata parsing (delegated to platform services)
    """
    
    # File extensions we support
    AUDIO_EXTENSIONS = ['.opus', '.mp3', '.m4a', '.webm', '.ogg', '.flac']
    
    def __init__(self, archive: Path, yt_dlp_config: Path, music_dir: Path):
        self.archive = archive
        self.yt_dlp_config = yt_dlp_config
        self.music_dir = music_dir
        
        # Ambiguous matches queue - stored in library directory
        self.ambiguous_queue_file = music_dir.parent / "ambiguous_matches.json"
    
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
        Find the local file matching a track using STRICT matching only.
        
        Matching strategy:
        1. Exact filename match using yt-dlp's sanitized expected_filename
        2. That's it. No fuzzy matching - it causes false positives.
        
        If no exact match is found, returns None. The caller should:
        - Let yt-dlp's archive handle deduplication
        - Or queue for manual review if needed
        
        Returns:
            Path to exact matching file, or None if not found
        """
        # Only match by exact filename (yt-dlp sanitized)
        for ext in self.AUDIO_EXTENSIONS:
            exact_path = self.music_dir / f"{track.expected_filename}{ext}"
            if exact_path.exists():
                return exact_path
        
        return None
    
    def find_local_file_strict(self, track: TrackInfo, 
                                require_source_id_match: bool = False) -> Tuple[Optional[Path], str]:
        """
        Find local file with detailed match information.
        
        This is a more verbose version that returns the match type,
        useful for debugging and reporting.
        
        Args:
            track: Track info from playlist
            require_source_id_match: If True, only return matches verified by source_id
            
        Returns:
            Tuple of (path or None, match_type)
            match_type is one of: 'exact_filename', 'not_found'
        """
        # Try exact filename match
        for ext in self.AUDIO_EXTENSIONS:
            exact_path = self.music_dir / f"{track.expected_filename}{ext}"
            if exact_path.exists():
                return exact_path, 'exact_filename'
        
        return None, 'not_found'
    
    # ==================== Ambiguous Match Queue ====================
    
    def queue_ambiguous_match(self, track: TrackInfo, playlist_name: str, 
                               reason: str, candidates: List[Path] = None):
        """
        Queue a track for manual review when matching is uncertain.
        
        Args:
            track: The track info from the playlist
            playlist_name: Which playlist this track is from
            reason: Why this match is ambiguous
            candidates: Optional list of potential file matches
        """
        queue = self._load_ambiguous_queue()
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'playlist': playlist_name,
            'track': {
                'title': track.title,
                'artist': track.artist,
                'video_id': track.video_id,
                'expected_filename': track.expected_filename,
            },
            'reason': reason,
            'candidates': [str(c) for c in (candidates or [])],
            'resolved': False,
            'resolution': None,
        }
        
        # Avoid duplicates (same video_id in same playlist)
        existing_ids = {(e['track']['video_id'], e['playlist']) for e in queue}
        if (track.video_id, playlist_name) not in existing_ids:
            queue.append(entry)
            self._save_ambiguous_queue(queue)
    
    def get_ambiguous_queue(self) -> List[Dict[str, Any]]:
        """Get all unresolved ambiguous matches."""
        queue = self._load_ambiguous_queue()
        return [e for e in queue if not e.get('resolved', False)]
    
    def resolve_ambiguous_match(self, video_id: str, playlist_name: str, 
                                  file_path: Optional[str], action: str):
        """
        Resolve an ambiguous match.
        
        Args:
            video_id: The track's video ID
            playlist_name: The playlist name
            file_path: The file to assign (or None if skipping)
            action: 'assign', 'skip', or 'download'
        """
        queue = self._load_ambiguous_queue()
        
        for entry in queue:
            if (entry['track']['video_id'] == video_id and 
                entry['playlist'] == playlist_name):
                entry['resolved'] = True
                entry['resolution'] = {
                    'action': action,
                    'file_path': file_path,
                    'resolved_at': datetime.now().isoformat(),
                }
                break
        
        self._save_ambiguous_queue(queue)
    
    def _load_ambiguous_queue(self) -> List[Dict[str, Any]]:
        """Load the ambiguous matches queue from disk."""
        if not self.ambiguous_queue_file.exists():
            return []
        
        try:
            with open(self.ambiguous_queue_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    
    def _save_ambiguous_queue(self, queue: List[Dict[str, Any]]):
        """Save the ambiguous matches queue to disk."""
        with open(self.ambiguous_queue_file, 'w') as f:
            json.dump(queue, f, indent=2)
