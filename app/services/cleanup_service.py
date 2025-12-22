import shutil

class CleanupService:
    def __init__(self, library_dir, archive_file):
        self.library_dir = library_dir
        self.archive_file = archive_file
        self.music_dir = library_dir / "music"
        self.playlists_dir = library_dir / "playlists"

    def clear_archive(self):
        """Delete the download archive file"""
        if self.archive_file.exists():
            self.archive_file.unlink()
            print(f"✅ Cleared archive: {self.archive_file}")
        else:
            print(f"ℹ️  Archive not found: {self.archive_file}")

    def clear_downloads(self):
        """Delete all downloaded music files"""
        if self.music_dir.exists():
            shutil.rmtree(self.music_dir)
            self.music_dir.mkdir(parents=True, exist_ok=True)
            print(f"✅ Cleared downloads: {self.music_dir}")
        else:
            print(f"ℹ️  Music directory not found: {self.music_dir}")

    def clear_playlists(self):
        """Delete all generated playlist files"""
        if self.playlists_dir.exists():
            for playlist_file in self.playlists_dir.glob("*.m3u8"):
                playlist_file.unlink()
            print(f"✅ Cleared playlists: {self.playlists_dir}")
        else:
            print(f"ℹ️  Playlists directory not found: {self.playlists_dir}")

    def clear_all(self):
        """Delete everything: archive, downloads, and playlists"""
        print("🗑️  Clearing all data...")
        self.clear_archive()
        self.clear_downloads()
        self.clear_playlists()
        print("✅ All data cleared")
