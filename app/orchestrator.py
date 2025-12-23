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
        """
        Sync a single playlist with metadata-driven approach.
        
        Workflow:
        1. Query YouTube for ALL tracks (ignore archive)
        2. Match tracks to local files and update their metadata
        3. Download new tracks (yt-dlp respects archive)
        4. Tag newly downloaded files
        5. Generate m3u8 from metadata (not YouTube data)
        """
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
        
        # PHASE 1: Query YouTube for complete track list (before download)
        self.logging_service.progress(f"Fetching track list from platform...")
        tracks_info, tracks_error = self.download_service.get_playlist_tracks(playlist_url)
        
        if tracks_error:
            self.logging_service.warning(f"⚠️  Could not fetch track list: {tracks_error}")
            # Continue with download anyway
        
        # PHASE 2: Match existing files and update their metadata
        existing_files = []
        if tracks_info:
            self.logging_service.progress(f"Checking {len(tracks_info)} tracks against local library...")
            for track in tracks_info:
                local_file = self.download_service.find_local_file(track)
                if local_file:
                    # File exists - update metadata with this playlist
                    updated = self.metadata_service.add_playlist(local_file, playlist_name)
                    if updated:
                        self.logging_service.progress(f"  ✓ Updated: {local_file.name}")
                    existing_files.append(local_file)
        
        # Snapshot files before download
        files_before = set(self.config.music.glob("*.*"))
        
        # PHASE 3: Download new tracks (archive prevents re-downloads)
        self.logging_service.progress(f"Downloading new tracks...")
        download_result = self.download_service.fetch(playlist_url)
        
        if not download_result.success:
            self.logging_service.error(f"Download failed: {download_result.error}")
            return download_result
        
        # PHASE 4: Tag newly downloaded files
        files_after = set(self.config.music.glob("*.*"))
        new_files = files_after - files_before
        
        if new_files:
            self.logging_service.progress(f"Tagging {len(new_files)} new file(s)...")
            for file in new_files:
                if file.suffix.lower() in ['.opus', '.mp3', '.m4a', '.ogg', '.flac', '.webm']:
                    self.metadata_service.add_playlist(file, playlist_name)
                    self.logging_service.progress(f"  ✓ Tagged: {file.name}")
        
        # PHASE 5: Generate m3u8 from metadata (all files with this playlist tag)
        playlist_result = self.playlist_service.generate_from_metadata(playlist_name)
        self.logging_service.log_result(playlist_result)
        
        # Validate m3u8 was created
        self._validate_playlist(playlist_name)
        
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
    
    def _validate_playlist(self, playlist_name: str):
        """Validate that m3u8 file exists and has content."""
        m3u8_path = self.config.playlists / f"{playlist_name}.m3u8"
        
        if not m3u8_path.exists():
            self.logging_service.error(
                f"❌ Validation failed: m3u8 file not created for {playlist_name}"
            )
            return False
        
        # Check if m3u8 has actual track entries (not just empty/comments)
        try:
            content = m3u8_path.read_text(encoding='utf-8')
            track_lines = [
                line for line in content.splitlines() 
                if line.strip() and not line.startswith('#')
            ]
            
            if not track_lines:
                self.logging_service.warning(
                    f"⚠️  m3u8 file exists but has no tracks: {playlist_name}"
                )
                return False
            
            self.logging_service.progress(
                f"✓ Validated: {len(track_lines)} track(s) in {playlist_name}.m3u8"
            )
            return True
            
        except Exception as e:
            self.logging_service.error(
                f"❌ Error validating {playlist_name}.m3u8: {e}"
            )
            return False
    
    def regenerate_all_playlists(self):
        """
        Regenerate m3u8 files from metadata.
        
        This scans all local files and generates playlists based on
        their metadata tags. Does NOT query YouTube.
        
        Use this to rebuild m3u8 files from local library.
        """
        self.prepare_environment()
        
        self.logging_service.progress("Scanning all files for playlist metadata...")
        
        # Generate all m3u8 from metadata
        results = self.playlist_service.generate_all_from_metadata()
        
        if not results:
            self.logging_service.warning("No playlists found in file metadata")
            return
        
        self.logging_service.progress(f"Found {len(results)} unique playlist(s) in metadata")
        
        # Log results
        for playlist_name, result in results.items():
            self.logging_service.progress(f"  {playlist_name}")
            self.logging_service.log_result(result)
            self._validate_playlist(playlist_name)
        
        self.logging_service.success("✅ All playlists regenerated from metadata")
