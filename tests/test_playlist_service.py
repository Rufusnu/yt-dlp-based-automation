"""Unit tests for PlaylistService."""
import pytest
from pathlib import Path
from app.services.playlist_service import PlaylistService
from app.services.metadata_service import MetadataService
from tests.conftest import create_opus_file


class TestPlaylistService:
    """Test suite for PlaylistService."""
    
    def test_sanitize_valid_playlist_name(self):
        """Test sanitization of valid playlist names."""
        assert PlaylistService._sanitize_playlist_name("Hip Hop Battle") == "Hip Hop Battle"
        assert PlaylistService._sanitize_playlist_name("⚪ Piano interesting") == "⚪ Piano interesting"
        assert PlaylistService._sanitize_playlist_name("Trap") == "Trap"
    
    def test_sanitize_reject_urls(self):
        """Test that URLs are rejected."""
        assert PlaylistService._sanitize_playlist_name("https://youtube.com/playlist") is None
        assert PlaylistService._sanitize_playlist_name("http://soundcloud.com/set") is None
        assert PlaylistService._sanitize_playlist_name("www.example.com") is None
    
    def test_sanitize_reject_paths(self):
        """Test that filesystem paths are rejected."""
        assert PlaylistService._sanitize_playlist_name("/home/user/playlist") is None
        assert PlaylistService._sanitize_playlist_name("../music/file") is None
    
    def test_sanitize_remove_invalid_chars(self):
        """Test removal of invalid filename characters."""
        result = PlaylistService._sanitize_playlist_name('Playlist<>:"|?*Name')
        assert '<' not in result
        assert '>' not in result
        assert ':' not in result
        assert '"' not in result
        assert '|' not in result
        assert '?' not in result
        assert '*' not in result
    
    def test_generate_from_metadata(self, mock_music_dir, mock_playlist_dir):
        """Test generating m3u8 from file metadata."""
        # Setup
        metadata_service = MetadataService()
        playlist_service = PlaylistService(mock_playlist_dir, mock_music_dir, metadata_service)
        
        # Create test files with metadata
        file1 = mock_music_dir / "Song1.opus"
        file2 = mock_music_dir / "Song2.opus"
        file3 = mock_music_dir / "Song3.opus"
        
        for file in [file1, file2, file3]:
            if not create_opus_file(file):
                pytest.skip("ffmpeg not available")
        
        # Add playlist tags
        metadata_service.add_playlist(file1, "Test Playlist")
        metadata_service.add_playlist(file2, "Test Playlist")
        # file3 not in playlist
        
        # Generate m3u8
        result = playlist_service.generate_from_metadata("Test Playlist")
        
        assert result.success is True
        
        # Check m3u8 file
        m3u8_path = mock_playlist_dir / "Test Playlist.m3u8"
        assert m3u8_path.exists()
        
        content = m3u8_path.read_text()
        assert "Song1.opus" in content
        assert "Song2.opus" in content
        assert "Song3.opus" not in content
    
    def test_generate_all_from_metadata(self, mock_music_dir, mock_playlist_dir):
        """Test generating all playlists from metadata."""
        # Setup
        metadata_service = MetadataService()
        playlist_service = PlaylistService(mock_playlist_dir, mock_music_dir, metadata_service)
        
        # Create test files
        file1 = mock_music_dir / "Song1.opus"
        file2 = mock_music_dir / "Song2.opus"
        file3 = mock_music_dir / "Song3.opus"
        
        for file in [file1, file2, file3]:
            if not create_opus_file(file):
                pytest.skip("ffmpeg not available")
        
        # Add to multiple playlists
        metadata_service.add_playlist(file1, "Playlist A")
        metadata_service.add_playlist(file2, "Playlist A")
        metadata_service.add_playlist(file2, "Playlist B")
        metadata_service.add_playlist(file3, "Playlist B")
        
        # Generate all
        results = playlist_service.generate_all_from_metadata()
        
        assert len(results) == 2
        assert "Playlist A" in results
        assert "Playlist B" in results
        assert all(r.success for r in results.values())
        
        # Check files created
        assert (mock_playlist_dir / "Playlist A.m3u8").exists()
        assert (mock_playlist_dir / "Playlist B.m3u8").exists()
    
    def test_generate_all_skips_invalid_names(self, mock_music_dir, mock_playlist_dir):
        """Test that invalid playlist names are skipped during generation."""
        from mutagen.oggopus import OggOpus
        
        # Setup
        metadata_service = MetadataService()
        playlist_service = PlaylistService(mock_playlist_dir, mock_music_dir, metadata_service)
        
        # Create file with URL in metadata (old/corrupted data)
        file1 = mock_music_dir / "Song1.opus"
        if not create_opus_file(file1):
            pytest.skip("ffmpeg not available")
        
        # Manually inject bad metadata
        audio = OggOpus(file1)
        audio["comment"] = ["https://soundcloud.com/bad/url", "Valid Playlist"]
        audio.save()
        
        # Generate all
        results = playlist_service.generate_all_from_metadata()
        
        # Should only have valid playlist, URL skipped
        assert "Valid Playlist" in results
        assert "https://soundcloud.com/bad/url" not in results
        assert (mock_playlist_dir / "Valid Playlist.m3u8").exists()
        assert not (mock_playlist_dir / "https:soundcloud.combadurl.m3u8").exists()
    
    def test_empty_playlist_generation(self, mock_music_dir, mock_playlist_dir):
        """Test generating m3u8 for playlist with no matching files."""
        metadata_service = MetadataService()
        playlist_service = PlaylistService(mock_playlist_dir, mock_music_dir, metadata_service)
        
        # Create file with different playlist
        file1 = mock_music_dir / "Song1.opus"
        if not create_opus_file(file1):
            pytest.skip("ffmpeg not available")
        metadata_service.add_playlist(file1, "Other Playlist")
        
        # Generate for non-existent playlist
        result = playlist_service.generate_from_metadata("Empty Playlist")
        
        assert result.success is True
        m3u8_path = mock_playlist_dir / "Empty Playlist.m3u8"
        assert m3u8_path.exists()
        
        # Should be empty (no track lines)
        content = m3u8_path.read_text()
        lines = [l for l in content.splitlines() if l.strip() and not l.startswith('#')]
        assert len(lines) == 0
