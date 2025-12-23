"""
Platform-specific services for handling different music sources.
Each platform (YouTube, SoundCloud, etc.) has its own service that knows
how to fetch metadata and build expected filenames for that platform.
"""
from app.services.platforms.base import BasePlatformService, TrackInfo
from app.services.platforms.youtube import YouTubeService
from app.services.platforms.soundcloud import SoundCloudService
from app.services.platforms.factory import PlatformFactory

__all__ = [
    'BasePlatformService',
    'TrackInfo',
    'YouTubeService',
    'SoundCloudService',
    'PlatformFactory',
]
