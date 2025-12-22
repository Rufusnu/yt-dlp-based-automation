"""
Orchestrates the playlist synchronization workflow.
"""
from pathlib import Path
from app.container import ServiceContainer
from app.results import DownloadResult


class SyncOrchestrator:
    """Handles the complete sync workflow for playlists."""
    
    def __init__(self, container: ServiceContainer):
        self.container = container
        self.download_service = container.get('download')
        self.library_service = container.get('library')
        self.playlist_service = container.get('playlist')
        self.metadata_service = container.get('metadata')
        self.filesystem_service = container.get('filesystem')
        self.logging_service = container.get('logging')
        self.config = container.config
    
    def prepare_environment(self):
        """Ensure required directories exist."""
        self.filesystem_service.ensure_directory(self.config.music)
        self.filesystem_service.ensure_directory(self.config.playlists)
    
    def sync_all_playlists(self):
        """Sync all configured playlists."""
        self.prepare_environment()
        
        all_successful = True
        for playlist_url in self.config.playlist_urls:
            result = self.sync_single_playlist(playlist_url)
            if not result.success:
                all_successful = False
        
        if all_successful:
            self.logging_service.success(
                self.logging_service._format_message('sync_complete')
            )
        else:
            self.logging_service.warning(
                "Sync completed with some errors"
            )
    
    def sync_single_playlist(self, playlist_url: str) -> DownloadResult:
        """Sync a single playlist."""
        # Get playlist metadata
        playlist_name, error = self.download_service.get_playlist_name(playlist_url)
        
        if error:
            self.logging_service.warning(
                self.logging_service._format_message(
                    'playlist_name_fetch_failed',
                    error=error
                )
            )
        
        self.logging_service.progress(
            self.logging_service._format_message(
                'sync_start',
                playlist_name=playlist_name
            )
        )
        
        # Download tracks
        download_result = self.download_service.fetch(playlist_url)
        
        if not download_result.success:
            self.logging_service.error(f"Download failed: {download_result.error}")
            return download_result
        
        # Get all tracks from library
        tracks = list(self.library_service.all_tracks())
        
        # Update metadata for each track
        for track in tracks:
            self.metadata_service.add_playlist(track.file, playlist_name)
        
        # Generate/update playlist file
        playlist_result = self.playlist_service.update(playlist_name, tracks)
        self.logging_service.log_result(playlist_result)
        
        # Cleanup temporary files
        self._cleanup_temp_directory()
        
        return download_result
    
    def _cleanup_temp_directory(self):
        """Remove temporary download directory."""
        tmp_dir = self.config.music / ".tmp"
        if self.filesystem_service.remove_directory(tmp_dir):
            self.logging_service.cleanup(
                self.logging_service._format_message('cleanup_temp')
            )
