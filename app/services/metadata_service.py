from mutagen.oggopus import OggOpus
from mutagen.mp3 import MP3
from mutagen.id3 import COMM, TXXX
from mutagen.mp4 import MP4
from pathlib import Path
from typing import List, Set, Optional, Tuple


class MetadataService:
    """
    Handles reading and writing metadata in audio files.
    
    Stores:
    - Playlist names in the 'comment' tag field
    - Source ID in 'description' or custom field (for deduplication)
    
    Supports multiple playlists per file (append-only).
    """
    
    # Custom tag names for source ID storage
    SOURCE_ID_TAG_OPUS = "SOURCE_ID"
    SOURCE_ID_TAG_MP3_DESC = "SOURCE_ID"
    SOURCE_ID_TAG_MP4 = "----:com.apple.iTunes:SOURCE_ID"
    
    def __init__(self):
        pass
    
    def add_playlist(self, file: Path, playlist_name: str) -> bool:
        """
        Add a playlist name to file metadata.
        If playlist already exists in metadata, does nothing.
        
        Returns:
            True if metadata was updated, False otherwise
        """
        try:
            # Get existing playlists
            current_playlists = self.get_playlists(file)
            
            # Check if already tagged
            if playlist_name in current_playlists:
                return False  # Already has this playlist
            
            # Add new playlist
            audio = self._load_audio(file)
            if not audio:
                return False
            
            if isinstance(audio, OggOpus):
                tags = audio.tags or {}
                comments = list(tags.get("comment", []))
                comments.append(playlist_name)
                tags["comment"] = comments
                audio.save()
                return True
            
            elif isinstance(audio, MP3):
                if audio.tags is None:
                    audio.add_tags()
                # ID3 uses COMM frame for comments
                audio.tags.add(COMM(encoding=3, lang='eng', desc='', text=playlist_name))
                audio.save()
                return True
            
            elif isinstance(audio, MP4):
                if audio.tags is None:
                    audio.tags = {}
                # MP4 uses \xa9cmt for comments
                comments = audio.tags.get('\xa9cmt', [])
                if not isinstance(comments, list):
                    comments = [comments]
                comments.append(playlist_name)
                audio.tags['\xa9cmt'] = comments
                audio.save()
                return True
            
            return False
            
        except Exception as e:
            return False
    
    def remove_playlist(self, file: Path, playlist_name: str) -> bool:
        """
        Remove a playlist name from file metadata.
        
        Returns:
            True if metadata was updated, False otherwise
        """
        try:
            # Get existing playlists
            current_playlists = self.get_playlists(file)
            
            # Check if playlist exists
            if playlist_name not in current_playlists:
                return False  # Doesn't have this playlist
            
            audio = self._load_audio(file)
            if not audio:
                return False
            
            if isinstance(audio, OggOpus):
                tags = audio.tags or {}
                comments = list(tags.get("comment", []))
                comments = [c for c in comments if c != playlist_name]
                tags["comment"] = comments
                audio.save()
                return True
            
            elif isinstance(audio, MP3):
                if audio.tags is None:
                    return False
                # Remove matching COMM frames
                frames_to_keep = []
                for frame in audio.tags.getall('COMM'):
                    if frame.text and playlist_name not in frame.text:
                        frames_to_keep.append(frame)
                audio.tags.delall('COMM')
                for frame in frames_to_keep:
                    audio.tags.add(frame)
                audio.save()
                return True
            
            elif isinstance(audio, MP4):
                if audio.tags is None:
                    return False
                comments = audio.tags.get('\xa9cmt', [])
                if not isinstance(comments, list):
                    comments = [comments]
                comments = [c for c in comments if c != playlist_name]
                audio.tags['\xa9cmt'] = comments
                audio.save()
                return True
            
            return False
            
        except Exception as e:
            return False
    
    def get_playlists(self, file: Path) -> Set[str]:
        """
        Get all playlist names from file metadata.
        
        Filters out URLs (which yt-dlp stores in the comment field as source URLs)
        to only return actual playlist names.
        
        Returns:
            Set of playlist names (empty if none found)
        """
        try:
            audio = self._load_audio(file)
            if not audio:
                return set()
            
            raw_comments = []
            
            if isinstance(audio, OggOpus):
                tags = audio.tags or {}
                raw_comments = list(tags.get("comment", []))
            
            elif isinstance(audio, MP3):
                # ID3 COMM frames
                for frame in audio.tags.getall('COMM'):
                    if frame.text:
                        raw_comments.extend(frame.text)
            
            elif isinstance(audio, MP4):
                comments = audio.tags.get('\xa9cmt', [])
                if not isinstance(comments, list):
                    comments = [comments]
                raw_comments = comments
            
            # Filter out URLs (yt-dlp stores source URLs in comment field)
            # and return only actual playlist names
            playlists = set()
            for comment in raw_comments:
                comment_str = str(comment).strip()
                if not comment_str:
                    continue
                # Skip URLs - they're source URLs, not playlist names
                if comment_str.startswith(('http://', 'https://', 'www.')):
                    continue
                playlists.add(comment_str)
            
            return playlists
            
        except Exception:
            return set()
    
    # ==================== Source ID Methods ====================
    
    def set_source_id(self, file: Path, source_id: str) -> bool:
        """
        Store the source ID (e.g., 'youtube:dQw4w9WgXcQ') in file metadata.
        Used for deduplication - even if video is deleted, we know where it came from.
        
        Returns:
            True if metadata was updated, False on error
        """
        try:
            audio = self._load_audio(file)
            if not audio:
                return False
            
            if isinstance(audio, OggOpus):
                if audio.tags is None:
                    audio.tags = {}
                audio.tags[self.SOURCE_ID_TAG_OPUS] = [source_id]
                audio.save()
                return True
            
            elif isinstance(audio, MP3):
                if audio.tags is None:
                    audio.add_tags()
                # Use TXXX frame for custom tags
                audio.tags.add(TXXX(encoding=3, desc=self.SOURCE_ID_TAG_MP3_DESC, text=source_id))
                audio.save()
                return True
            
            elif isinstance(audio, MP4):
                if audio.tags is None:
                    audio.tags = {}
                # MP4 custom tag
                from mutagen.mp4 import MP4FreeForm
                audio.tags[self.SOURCE_ID_TAG_MP4] = [MP4FreeForm(source_id.encode('utf-8'))]
                audio.save()
                return True
            
            return False
            
        except Exception:
            return False
    
    def get_source_id(self, file: Path) -> Optional[str]:
        """
        Get the source ID from file metadata.
        
        First checks for our custom SOURCE_ID tag, then falls back to extracting
        from yt-dlp's embedded 'purl' (webpage URL) tag.
        
        Returns:
            Source ID string (e.g., 'youtube:xxx') or None if not found
        """
        try:
            audio = self._load_audio(file)
            if not audio:
                return None
            
            source_id = None
            purl = None
            
            if isinstance(audio, OggOpus):
                tags = audio.tags or {}
                # First try our custom tag
                values = tags.get(self.SOURCE_ID_TAG_OPUS, [])
                source_id = values[0] if values else None
                # Fallback to purl (webpage URL embedded by yt-dlp)
                if not source_id:
                    purl_values = tags.get("purl", [])
                    purl = purl_values[0] if purl_values else None
            
            elif isinstance(audio, MP3):
                if audio.tags:
                    # First try our custom TXXX tag
                    for frame in audio.tags.getall('TXXX'):
                        if frame.desc == self.SOURCE_ID_TAG_MP3_DESC:
                            source_id = str(frame.text[0]) if frame.text else None
                            break
                    # Fallback to purl TXXX tag
                    if not source_id:
                        for frame in audio.tags.getall('TXXX'):
                            if frame.desc == 'PURL':
                                purl = str(frame.text[0]) if frame.text else None
                                break
            
            elif isinstance(audio, MP4):
                if audio.tags:
                    # First try our custom tag
                    values = audio.tags.get(self.SOURCE_ID_TAG_MP4, [])
                    if values:
                        source_id = bytes(values[0]).decode('utf-8')
                    # Fallback to purl tag (MP4 uses different key)
                    if not source_id:
                        purl_values = audio.tags.get("----:com.apple.iTunes:PURL", [])
                        if purl_values:
                            purl = bytes(purl_values[0]).decode('utf-8')
            
            # If we have source_id from custom tag, return it
            if source_id:
                return source_id
            
            # Extract source_id from purl (webpage URL)
            if purl:
                return self._extract_source_id_from_url(purl)
            
            return None
            
        except Exception:
            return None
    
    def _extract_source_id_from_url(self, url: str) -> Optional[str]:
        """
        Extract platform and video ID from a URL.
        
        Examples:
            https://www.youtube.com/watch?v=dQw4w9WgXcQ -> youtube:dQw4w9WgXcQ
            https://soundcloud.com/artist/track -> soundcloud:<hash>
        
        Returns:
            Source ID string or None
        """
        import re
        
        # YouTube
        yt_patterns = [
            r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
            r'youtu\.be/([a-zA-Z0-9_-]{11})',
            r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
            r'music\.youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        ]
        for pattern in yt_patterns:
            match = re.search(pattern, url)
            if match:
                return f"youtube:{match.group(1)}"
        
        # SoundCloud - URLs don't have simple IDs, use a hash of the URL
        if 'soundcloud.com' in url:
            import hashlib
            # Normalize URL and hash it
            normalized = url.lower().strip().rstrip('/')
            url_hash = hashlib.md5(normalized.encode()).hexdigest()[:12]
            return f"soundcloud:{url_hash}"
        
        return None
    
    def get_all_metadata(self, file: Path) -> Tuple[Set[str], Optional[str]]:
        """
        Get both playlists and source_id from a file in one call.
        More efficient for bulk operations.
        
        Returns:
            Tuple of (playlists set, source_id or None)
        """
        return self.get_playlists(file), self.get_source_id(file)
    
    def get_title_artist(self, file: Path) -> Tuple[str, str]:
        """
        Extract title and artist from file metadata.
        
        Returns:
            Tuple of (title, artist) - uses filename as fallback for title
        """
        try:
            audio = self._load_audio(file)
            if not audio:
                return file.stem, ""
            
            title = ""
            artist = ""
            
            if isinstance(audio, OggOpus):
                tags = audio.tags or {}
                title = tags.get("title", [""])[0] if tags.get("title") else ""
                artist = tags.get("artist", [""])[0] if tags.get("artist") else ""
            
            elif isinstance(audio, MP3):
                if audio.tags:
                    title = str(audio.tags.get("TIT2", ""))
                    artist = str(audio.tags.get("TPE1", ""))
            
            elif isinstance(audio, MP4):
                if audio.tags:
                    title = audio.tags.get("\xa9nam", [""])[0] if audio.tags.get("\xa9nam") else ""
                    artist = audio.tags.get("\xa9ART", [""])[0] if audio.tags.get("\xa9ART") else ""
            
            # Fallback to filename parsing if no title
            if not title:
                title = file.stem
            
            return title, artist
            
        except Exception:
            return file.stem, ""
    
    def _load_audio(self, file: Path):
        """Load audio file with appropriate handler based on extension."""
        ext = file.suffix.lower()
        
        try:
            if ext in ['.opus', '.ogg']:
                return OggOpus(file)
            elif ext == '.mp3':
                return MP3(file)
            elif ext in ['.m4a', '.mp4']:
                return MP4(file)
        except Exception:
            pass
        
        return None
