from app.models import Track

class LibraryService:
    def __init__(self, music_dir):
        self.music_dir = music_dir

    def all_tracks(self):
        for f in self.music_dir.glob("*.*"):
            yield Track(f.stem, f)
