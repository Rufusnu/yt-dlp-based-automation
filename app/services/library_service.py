from app.models import Track
from pathlib import Path

class LibraryService:
    def __init__(self, music_dir):
        self.music_dir = music_dir

    def all_tracks(self):
        """
        Find all audio files in the flat music directory.
        Excludes .tmp directory.
        """
        for f in self.music_dir.glob("*.*"):
            # Skip if it's a directory or in .tmp
            if f.is_dir() or ".tmp" in f.parts:
                continue
            # Only include audio files
            if f.suffix.lower() in ['.opus', '.mp3', '.m4a', '.flac', '.ogg', '.webm']:
                yield Track(f.stem, f)
    
    def tracks_in_playlist(self, playlist_name: str):
        """
        Legacy method for backwards compatibility.
        With flat structure, this falls back to checking for subfolder.
        """
        playlist_folder = self.music_dir / playlist_name
        if not playlist_folder.exists() or not playlist_folder.is_dir():
            return []
        
        tracks = []
        for f in playlist_folder.glob("*.*"):
            if f.suffix.lower() in ['.opus', '.mp3', '.m4a', '.flac', '.ogg', '.webm']:
                tracks.append(Track(f.stem, f))
        return tracks
