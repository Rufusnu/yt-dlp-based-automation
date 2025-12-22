from app.models import Track

class LibraryService:
    def __init__(self, music_dir):
        self.music_dir = music_dir

    def all_tracks(self):
        """Recursively find all audio files, excluding .tmp directory"""
        for f in self.music_dir.rglob("*.*"):
            # Skip temporary directory
            if ".tmp" in f.parts:
                continue
            # Only include audio files
            if f.suffix.lower() in ['.opus', '.mp3', '.m4a', '.flac', '.ogg', '.webm']:
                yield Track(f.stem, f)
