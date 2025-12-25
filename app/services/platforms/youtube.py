"""
YouTube/YouTube Music platform service.
Handles all YouTube-specific metadata fetching logic.
"""
from typing import List, Optional, Tuple
from app.services.platforms.base import BasePlatformService, TrackInfo


class YouTubeService(BasePlatformService):
    """
    Service for handling YouTube and YouTube Music playlists.
    
    YouTube characteristics:
    - Uses --flat-playlist for fast metadata fetching
    - Has 'title' in flat playlist output
    - Artist often in 'uploader' field, not 'artist'
    - Video IDs are typically 11 characters
    """
    
    SUPPORTED_DOMAINS = [
        'youtube.com',
        'youtu.be',
        'music.youtube.com',
    ]
    
    @staticmethod
    def can_handle(url: str) -> bool:
        """Check if URL is a YouTube/YouTube Music URL."""
        url_lower = url.lower()
        return any(domain in url_lower for domain in YouTubeService.SUPPORTED_DOMAINS)
    
    def get_playlist_name(self, playlist_url: str) -> Tuple[str, Optional[str]]:
        """
        Fetch playlist name from YouTube.
        Uses --flat-playlist with single item for speed.
        """
        result = self._run_ytdlp([
            "--dump-json",
            "--flat-playlist",
            "--playlist-items", "1",
            playlist_url,
        ])
        
        if result.returncode != 0:
            return "Unknown", result.stderr or "Failed to fetch playlist"
        
        entries = self._parse_json_lines(result.stdout)
        if not entries:
            return "Unknown", "No playlist data found"
        
        data = entries[0]
        
        # YouTube provides playlist_title in the response
        if "playlist_title" in data:
            return data["playlist_title"], None
        if "playlist" in data:
            return data["playlist"], None
        
        return "Unknown", "No playlist title in response"
    
    def get_playlist_tracks(self, playlist_url: str) -> Tuple[List[TrackInfo], Optional[str]]:
        """
        Fetch all tracks from a YouTube playlist.
        
        Uses --flat-playlist which is fast and provides:
        - title: Track title
        - uploader: Channel name (used as artist fallback)
        - id: Video ID
        """
        result = self._run_ytdlp([
            "--dump-json",
            "--flat-playlist",
            playlist_url,
        ])
        
        if result.returncode != 0:
            return [], result.stderr or "Failed to fetch playlist tracks"
        
        tracks = []
        for data in self._parse_json_lines(result.stdout):
            title = data.get("title")
            
            # Skip private/unavailable videos
            if not title or title == "[Private video]" or title == "[Deleted video]":
                continue
            
            # Only use actual artist metadata, not uploader/channel name
            # The channel name (uploader) is often wrong (e.g., "theladi6" instead of "Ladi6")
            artist = data.get("artist") or ""
            video_id = data.get("id", "")
            
            tracks.append(TrackInfo(
                title=title,
                artist=artist,
                expected_filename=self._build_filename(artist, title),
                video_id=video_id,
            ))
        
        return tracks, None
