from mutagen.oggopus import OggOpus
from mutagen.mp3 import MP3
from mutagen.id3 import COMM
from mutagen.mp4 import MP4
from pathlib import Path
from typing import List, Set


class MetadataService:
    """
    Handles reading and writing playlist metadata in audio files.
    
    Stores playlist names in the 'comment' tag field.
    Supports multiple playlists per file (append-only).
    """
    
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
    
    def get_playlists(self, file: Path) -> Set[str]:
        """
        Get all playlist names from file metadata.
        
        Returns:
            Set of playlist names (empty if none found)
        """
        try:
            audio = self._load_audio(file)
            if not audio:
                return set()
            
            playlists = []
            
            if isinstance(audio, OggOpus):
                tags = audio.tags or {}
                playlists = list(tags.get("comment", []))
            
            elif isinstance(audio, MP3):
                # ID3 COMM frames
                for frame in audio.tags.getall('COMM'):
                    if frame.text:
                        playlists.extend(frame.text)
            
            elif isinstance(audio, MP4):
                comments = audio.tags.get('\xa9cmt', [])
                if not isinstance(comments, list):
                    comments = [comments]
                playlists = comments
            
            # Return as set to remove duplicates
            return set(str(p).strip() for p in playlists if p)
            
        except Exception:
            return set()
    
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
