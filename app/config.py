import yaml
from pathlib import Path

class Config:
    def __init__(self, path="config.yaml"):
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        self.library = Path(raw["library_dir"]).resolve()
        self.music = self.library / "music"
        self.playlists = self.library / "playlists"
        self.archive = Path(raw["archive_file"]).resolve()
        self.yt_dlp_config = Path(raw["yt_dlp_config"]).resolve()
        
        # Database file - default to library/library.db
        self.database = self.library / "library.db"

        self.playlist_urls = raw["playlists"]
