"""
SoundCloud platform service.
Handles all SoundCloud-specific metadata fetching logic.
"""
import time
from typing import List, Optional, Tuple
from app.services.platforms.base import BasePlatformService, TrackInfo


class SoundCloudService(BasePlatformService):
    """
    Service for handling SoundCloud playlists.
    
    SoundCloud characteristics:
    - --flat-playlist does NOT return track metadata (only URLs)
    - Must use --no-download to get full metadata (slower)
    - Has proper 'artist' field for most tracks
    - Also has 'uploader' as fallback
    - Track IDs are numeric
    """
    
    SUPPORTED_DOMAINS = [
        'soundcloud.com',
    ]
    
    @staticmethod
    def can_handle(url: str) -> bool:
        """Check if URL is a SoundCloud URL."""
        url_lower = url.lower()
        return any(domain in url_lower for domain in SoundCloudService.SUPPORTED_DOMAINS)
    
    def get_playlist_name(self, playlist_url: str) -> Tuple[str, Optional[str]]:
        """
        Fetch playlist name from SoundCloud.
        Uses --flat-playlist with single item (faster, and playlist_title is available).
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
        
        # SoundCloud provides playlist_title even in flat mode
        if "playlist_title" in data:
            return data["playlist_title"], None
        if "playlist" in data:
            return data["playlist"], None
        
        return "Unknown", "No playlist title in response"
    
    def get_playlist_tracks(self, playlist_url: str) -> Tuple[List[TrackInfo], Optional[str]]:
        """
        Fetch all tracks from a SoundCloud playlist.
        
        Note: SoundCloud requires full metadata fetch (--no-download)
        because --flat-playlist doesn't return track title/artist.
        This is slower but necessary for accurate matching.
        
        Rate limiting: Added delays to avoid SoundCloud ban/timeouts.
        """
        # Add delay before request to be gentle with SoundCloud servers
        time.sleep(2)
        
        result = self._run_ytdlp([
            "--dump-json",
            "--no-download",
            "--sleep-requests", "2",  # 2 second delay between requests
            "--socket-timeout", "30",  # Increase timeout to 30 seconds
            playlist_url,
        ])
        
        if result.returncode != 0:
            return [], result.stderr or "Failed to fetch playlist tracks"
        
        tracks = []
        for data in self._parse_json_lines(result.stdout):
            # SoundCloud has good metadata support
            title = data.get("title") or data.get("track") or "Unknown Title"
            # Only use actual artist metadata, not uploader/channel name
            artist = data.get("artist") or ""
            track_id = data.get("id", "")
            
            tracks.append(TrackInfo(
                title=title,
                artist=artist,
                expected_filename=self._build_filename(artist, title),
                video_id=str(track_id),
            ))
        
        return tracks, None
