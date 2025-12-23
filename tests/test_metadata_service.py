"""Unit tests for MetadataService."""
import pytest
from pathlib import Path
from mutagen.oggopus import OggOpus
from app.services.metadata_service import MetadataService


class TestMetadataService:
    """Test suite for MetadataService."""
    
    def test_add_playlist_to_new_file(self, sample_opus_file):
        """Test adding a playlist to a file with no existing metadata."""
        service = MetadataService()
        
        # Add first playlist
        result = service.add_playlist(sample_opus_file, "Test Playlist")
        
        assert result is True
        playlists = service.get_playlists(sample_opus_file)
        assert "Test Playlist" in playlists
        assert len(playlists) == 1
    
    def test_add_multiple_playlists(self, sample_opus_file):
        """Test adding multiple playlists to the same file."""
        service = MetadataService()
        
        # Add multiple playlists
        service.add_playlist(sample_opus_file, "Playlist 1")
        service.add_playlist(sample_opus_file, "Playlist 2")
        service.add_playlist(sample_opus_file, "Playlist 3")
        
        playlists = service.get_playlists(sample_opus_file)
        assert len(playlists) == 3
        assert "Playlist 1" in playlists
        assert "Playlist 2" in playlists
        assert "Playlist 3" in playlists
    
    def test_prevent_duplicate_playlists(self, sample_opus_file):
        """Test that duplicate playlist names are not added."""
        service = MetadataService()
        
        # Add same playlist twice
        result1 = service.add_playlist(sample_opus_file, "Test Playlist")
        result2 = service.add_playlist(sample_opus_file, "Test Playlist")
        
        assert result1 is True  # First add succeeds
        assert result2 is False  # Second add returns False (no change)
        
        playlists = service.get_playlists(sample_opus_file)
        assert len(playlists) == 1
        assert "Test Playlist" in playlists
    
    def test_get_playlists_from_empty_file(self, sample_opus_file):
        """Test getting playlists from file with no metadata."""
        service = MetadataService()
        
        playlists = service.get_playlists(sample_opus_file)
        
        assert isinstance(playlists, set)
        assert len(playlists) == 0
    
    def test_handle_nonexistent_file(self, temp_dir):
        """Test handling of non-existent files."""
        service = MetadataService()
        
        fake_file = temp_dir / "nonexistent.opus"
        
        result = service.add_playlist(fake_file, "Test")
        assert result is False
        
        playlists = service.get_playlists(fake_file)
        assert len(playlists) == 0
    
    def test_unicode_playlist_names(self, sample_opus_file):
        """Test handling of Unicode characters in playlist names."""
        service = MetadataService()
        
        # Add playlist with emoji and special characters
        service.add_playlist(sample_opus_file, "⚪ Piano interesting")
        service.add_playlist(sample_opus_file, "Hip Hop & R&B")
        
        playlists = service.get_playlists(sample_opus_file)
        assert "⚪ Piano interesting" in playlists
        assert "Hip Hop & R&B" in playlists
    
    def test_metadata_persistence(self, sample_opus_file):
        """Test that metadata persists after reload."""
        service = MetadataService()
        
        # Add playlist
        service.add_playlist(sample_opus_file, "Persistent Playlist")
        
        # Create new service instance (simulates app restart)
        new_service = MetadataService()
        playlists = new_service.get_playlists(sample_opus_file)
        
        assert "Persistent Playlist" in playlists
