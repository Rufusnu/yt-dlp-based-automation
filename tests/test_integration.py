"""Integration tests for complete workflows."""
import pytest
from pathlib import Path
from mutagen.oggopus import OggOpus
from app.services.metadata_service import MetadataService
from app.services.playlist_service import PlaylistService
from tests.conftest import create_opus_file


class TestIntegration:
    """Integration tests for complete workflows."""
    
    def test_multiple_playlist_membership(self, mock_music_dir, mock_playlist_dir):
        """
        Test that a file can belong to multiple playlists without duplication.
        
        This is TEST 1 from the test plan.
        """
        metadata_service = MetadataService()
        playlist_service = PlaylistService(mock_playlist_dir, mock_music_dir, metadata_service)
        
        # Create a single file
        song_file = mock_music_dir / "Polyphia - Playing God.opus"
        if not create_opus_file(song_file):
            pytest.skip("ffmpeg not available")
        
        # Add to multiple playlists
        metadata_service.add_playlist(song_file, "Piano interesting")
        metadata_service.add_playlist(song_file, "Experimental")
        metadata_service.add_playlist(song_file, "Instrumental")
        
        # Verify file has all playlists in metadata
        playlists = metadata_service.get_playlists(song_file)
        assert len(playlists) == 3
        assert "Piano interesting" in playlists
        assert "Experimental" in playlists
        assert "Instrumental" in playlists
        
        # Generate all m3u8 files
        results = playlist_service.generate_all_from_metadata()
        
        # Verify file appears in all three m3u8 files
        for playlist_name in ["Piano interesting", "Experimental", "Instrumental"]:
            m3u8_path = mock_playlist_dir / f"{playlist_name}.m3u8"
            assert m3u8_path.exists()
            content = m3u8_path.read_text()
            assert "Polyphia - Playing God.opus" in content
        
        # Verify only ONE physical file exists
        all_files = list(mock_music_dir.glob("*Playing God*"))
        assert len(all_files) == 1
    
    def test_metadata_driven_regeneration(self, mock_music_dir, mock_playlist_dir):
        """
        Test that playlists can be regenerated from metadata without external sources.
        
        This is TEST 4 from the test plan.
        """
        metadata_service = MetadataService()
        playlist_service = PlaylistService(mock_playlist_dir, mock_music_dir, metadata_service)
        
        # Create files with metadata
        for i in range(5):
            file = mock_music_dir / f"Song{i}.opus"
            if not create_opus_file(file):
                pytest.skip("ffmpeg not available")
            
            # Add to different playlists
            if i < 3:
                metadata_service.add_playlist(file, "Playlist A")
            if i >= 2:
                metadata_service.add_playlist(file, "Playlist B")
        
        # Generate all playlists from metadata
        results = playlist_service.generate_all_from_metadata()
        
        # Verify both playlists created
        assert len(results) == 2
        assert "Playlist A" in results
        assert "Playlist B" in results
        
        # Verify Playlist A has songs 0, 1, 2
        playlist_a = (mock_playlist_dir / "Playlist A.m3u8").read_text()
        assert "Song0.opus" in playlist_a
        assert "Song1.opus" in playlist_a
        assert "Song2.opus" in playlist_a
        assert "Song3.opus" not in playlist_a
        assert "Song4.opus" not in playlist_a
        
        # Verify Playlist B has songs 2, 3, 4
        playlist_b = (mock_playlist_dir / "Playlist B.m3u8").read_text()
        assert "Song2.opus" in playlist_b
        assert "Song3.opus" in playlist_b
        assert "Song4.opus" in playlist_b
        assert "Song0.opus" not in playlist_b
        assert "Song1.opus" not in playlist_b
    
    def test_corrupted_metadata_handling(self, mock_music_dir, mock_playlist_dir):
        """
        Test that corrupted/invalid metadata (URLs, paths) doesn't crash the system.
        """
        metadata_service = MetadataService()
        playlist_service = PlaylistService(mock_playlist_dir, mock_music_dir, metadata_service)
        
        # Create file with valid and invalid metadata
        file = mock_music_dir / "Song.opus"
        if not create_opus_file(file):
            pytest.skip("ffmpeg not available")
        
        # Manually inject both valid and invalid metadata
        audio = OggOpus(file)
        audio["comment"] = [
            "Valid Playlist",
            "https://soundcloud.com/corrupted/url",
            "/invalid/path/name",
            "Another Valid Playlist"
        ]
        audio.save()
        
        # Generate all - should not crash
        results = playlist_service.generate_all_from_metadata()
        
        # Should only have valid playlists
        assert "Valid Playlist" in results
        assert "Another Valid Playlist" in results
        assert len(results) == 2
        
        # Verify m3u8 files created only for valid names
        assert (mock_playlist_dir / "Valid Playlist.m3u8").exists()
        assert (mock_playlist_dir / "Another Valid Playlist.m3u8").exists()
