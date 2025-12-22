"""
Dependency injection container for managing service instances.
"""
from pathlib import Path
from app.config import Config
from app.services.download_service import DownloadService
from app.services.library_service import LibraryService
from app.services.playlist_service import PlaylistService
from app.services.metadata_service import MetadataService
from app.services.cleanup_service import CleanupService
from app.services.filesystem_service import FileSystemService
from app.services.logging_service import LoggingService


class ServiceContainer:
    """Central container for all application services."""
    
    def __init__(self, config: Config):
        self.config = config
        self._services = {}
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize all services with their dependencies."""
        # Core services (no dependencies)
        self._services['filesystem'] = FileSystemService()
        self._services['logging'] = LoggingService()
        
        # Business logic services (with dependencies)
        self._services['download'] = DownloadService(
            archive=self.config.archive,
            yt_dlp_config=self.config.yt_dlp_config
        )
        
        self._services['library'] = LibraryService(
            music_dir=self.config.music
        )
        
        self._services['playlist'] = PlaylistService(
            playlist_dir=self.config.playlists
        )
        
        self._services['metadata'] = MetadataService()
        
        self._services['cleanup'] = CleanupService(
            library_dir=self.config.library,
            archive_file=self.config.archive,
            filesystem=self.get('filesystem')
        )
    
    def get(self, service_name: str):
        """Get a service instance by name."""
        if service_name not in self._services:
            raise ValueError(f"Service '{service_name}' not found")
        return self._services[service_name]
