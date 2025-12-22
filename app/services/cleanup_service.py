from app.services.filesystem_service import FileSystemService
from app.services.logging_service import LoggingService

class CleanupService:
    def __init__(self, library_dir, archive_file):
        self.library_dir = library_dir
        self.archive_file = archive_file
        self.music_dir = library_dir / "music"
        self.playlists_dir = library_dir / "playlists"

    def clear_archive(self):
        """Delete the download archive file"""
        if FileSystemService.remove_file(self.archive_file):
            LoggingService.success(f"Cleared archive: {self.archive_file}")
        else:
            LoggingService.info(f"Archive not found: {self.archive_file}")

    def clear_downloads(self):
        """Delete all downloaded music files"""
        if FileSystemService.remove_directory(self.music_dir):
            FileSystemService.ensure_directory(self.music_dir)
            LoggingService.success(f"Cleared downloads: {self.music_dir}")
        else:
            LoggingService.info(f"Music directory not found: {self.music_dir}")

    def clear_playlists(self):
        """Delete all generated playlist files"""
        if self.playlists_dir.exists():
            for playlist_file in self.playlists_dir.glob("*.m3u8"):
                FileSystemService.remove_file(playlist_file)
            LoggingService.success(f"Cleared playlists: {self.playlists_dir}")
        else:
            LoggingService.info(f"Playlists directory not found: {self.playlists_dir}")

    def clear_all(self):
        """Delete everything: archive, downloads, and playlists"""
        LoggingService.cleanup("Clearing all data...")
        self.clear_archive()
        self.clear_downloads()
        self.clear_playlists()
        LoggingService.success("All data cleared")
