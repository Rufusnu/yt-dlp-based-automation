"""Unit tests for platform services."""
import pytest
from app.services.platforms.factory import PlatformFactory
from app.services.platforms.youtube import YouTubeService
from app.services.platforms.soundcloud import SoundCloudService


class TestPlatformFactory:
    """Test suite for PlatformFactory."""
    
    def test_youtube_url_detection(self):
        """Test detection of YouTube URLs."""
        urls = [
            "https://www.youtube.com/playlist?list=PLxxx",
            "https://youtube.com/watch?v=xxx&list=PLyyy",
            "https://music.youtube.com/playlist?list=PLzzz",
            "https://m.youtube.com/playlist?list=PLaaa",
        ]
        
        for url in urls:
            assert PlatformFactory.is_supported(url)
            service = PlatformFactory.get_service(url)
            assert isinstance(service, YouTubeService)
    
    def test_soundcloud_url_detection(self):
        """Test detection of SoundCloud URLs."""
        urls = [
            "https://soundcloud.com/artist/sets/playlist",
            "https://www.soundcloud.com/user/track",
            "https://soundcloud.com/user/likes",
        ]
        
        for url in urls:
            assert PlatformFactory.is_supported(url)
            service = PlatformFactory.get_service(url)
            assert isinstance(service, SoundCloudService)
    
    def test_unsupported_url(self):
        """Test handling of unsupported URLs."""
        urls = [
            "https://spotify.com/playlist/xxx",
            "https://example.com/music",
            "not-a-url",
            "",
        ]
        
        for url in urls:
            assert not PlatformFactory.is_supported(url)
            service = PlatformFactory.get_service(url)
            assert service is None


class TestYouTubeService:
    """Test suite for YouTubeService."""
    
    def test_can_handle_youtube_urls(self):
        """Test YouTube URL validation."""
        service = YouTubeService()
        
        assert service.can_handle("https://www.youtube.com/playlist?list=PLxxx")
        assert service.can_handle("https://music.youtube.com/playlist?list=PLyyy")
        assert not service.can_handle("https://soundcloud.com/playlist")
        assert not service.can_handle("invalid-url")


class TestSoundCloudService:
    """Test suite for SoundCloudService."""
    
    def test_can_handle_soundcloud_urls(self):
        """Test SoundCloud URL validation."""
        service = SoundCloudService()
        
        assert service.can_handle("https://soundcloud.com/artist/sets/playlist")
        assert service.can_handle("https://www.soundcloud.com/user/track")
        assert not service.can_handle("https://youtube.com/playlist")
        assert not service.can_handle("invalid-url")
