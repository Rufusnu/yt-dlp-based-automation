"""Pytest configuration and shared fixtures."""
import pytest
from pathlib import Path
import tempfile
import shutil
import subprocess


def create_opus_file(file_path: Path) -> bool:
    """Create a minimal valid opus file for testing."""
    result = subprocess.run(
        [
            'ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono',
            '-t', '0.1', '-c:a', 'libopus', '-b:a', '32k',
            '-y', '-loglevel', 'quiet', str(file_path)
        ],
        capture_output=True
    )
    return result.returncode == 0 and file_path.exists()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    tmp = Path(tempfile.mkdtemp())
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def mock_music_dir(temp_dir):
    """Create a mock music directory with test files."""
    music_dir = temp_dir / "music"
    music_dir.mkdir()
    return music_dir


@pytest.fixture
def mock_playlist_dir(temp_dir):
    """Create a mock playlist directory."""
    playlist_dir = temp_dir / "playlists"
    playlist_dir.mkdir()
    return playlist_dir


@pytest.fixture
def sample_opus_file(mock_music_dir):
    """Create a sample opus file for testing."""
    file_path = mock_music_dir / "Test Song - Artist.opus"
    
    if not create_opus_file(file_path):
        pytest.skip("ffmpeg not available - skipping tests that require real opus files")
    
    return file_path
