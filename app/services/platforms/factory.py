"""
Platform factory for selecting the appropriate platform service.
"""
from typing import Optional
from app.services.platforms.base import BasePlatformService
from app.services.platforms.youtube import YouTubeService
from app.services.platforms.soundcloud import SoundCloudService


class PlatformFactory:
    """
    Factory for creating platform-specific services based on URL.
    
    Usage:
        service = PlatformFactory.get_service(url)
        if service:
            name, _ = service.get_playlist_name(url)
            tracks, _ = service.get_playlist_tracks(url)
    """
    
    # Register all platform services here
    # Order matters: first match wins
    _platforms = [
        YouTubeService,
        SoundCloudService,
    ]
    
    @classmethod
    def get_service(cls, url: str) -> Optional[BasePlatformService]:
        """
        Get the appropriate platform service for a URL.
        
        Args:
            url: The playlist URL
            
        Returns:
            Platform service instance, or None if URL not supported
        """
        for platform_class in cls._platforms:
            if platform_class.can_handle(url):
                return platform_class()
        return None
    
    @classmethod
    def is_supported(cls, url: str) -> bool:
        """Check if URL is supported by any registered platform."""
        return any(p.can_handle(url) for p in cls._platforms)
    
    @classmethod
    def get_supported_platforms(cls) -> list[str]:
        """Get list of supported platform names."""
        return [p.__name__.replace('Service', '') for p in cls._platforms]
