from app.results import CleanupResult, OperationStatus

class CleanupService:
    def __init__(self, library_dir, archive_file, filesystem):
        self.library_dir = library_dir
        self.archive_file = archive_file
        self.music_dir = library_dir / "music"
        self.playlists_dir = library_dir / "playlists"
        self.filesystem = filesystem

    def clear_archive(self) -> CleanupResult:
        """Delete the download archive file"""
        if self.filesystem.remove_file(self.archive_file):
            return CleanupResult(
                success=True,
                operation="clear_archive",
                status=OperationStatus.SUCCESS,
                cleanup_type="archive",
                path=str(self.archive_file),
                data={"path": str(self.archive_file)}
            )
        return CleanupResult(
            success=False,
            operation="clear_archive",
            status=OperationStatus.NOT_FOUND,
            cleanup_type="archive",
            path=str(self.archive_file),
            data={"path": str(self.archive_file)}
        )

    def clear_downloads(self) -> CleanupResult:
        """Delete all downloaded music files"""
        if self.filesystem.remove_directory(self.music_dir):
            self.filesystem.ensure_directory(self.music_dir)
            return CleanupResult(
                success=True,
                operation="clear_downloads",
                status=OperationStatus.SUCCESS,
                cleanup_type="downloads",
                path=str(self.music_dir),
                data={"path": str(self.music_dir)}
            )
        return CleanupResult(
            success=False,
            operation="clear_downloads",
            status=OperationStatus.NOT_FOUND,
            cleanup_type="downloads",
            path=str(self.music_dir),
            data={"path": str(self.music_dir)}
        )

    def clear_playlists(self) -> CleanupResult:
        """Delete all generated playlist files"""
        if self.playlists_dir.exists():
            for playlist_file in self.playlists_dir.glob("*.m3u8"):
                self.filesystem.remove_file(playlist_file)
            return CleanupResult(
                success=True,
                operation="clear_playlists",
                status=OperationStatus.SUCCESS,
                cleanup_type="playlists",
                path=str(self.playlists_dir),
                data={"path": str(self.playlists_dir)}
            )
        return CleanupResult(
            success=False,
            operation="clear_playlists",
            status=OperationStatus.NOT_FOUND,
            cleanup_type="playlists",
            path=str(self.playlists_dir),
            data={"path": str(self.playlists_dir)}
        )

    def clear_all(self) -> list[CleanupResult]:
        """Delete everything: archive, downloads, and playlists"""
        results = []
        results.append(self.clear_archive())
        results.append(self.clear_downloads())
        results.append(self.clear_playlists())
        return results
