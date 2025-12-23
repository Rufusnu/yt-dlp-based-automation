# Test Suite

Comprehensive test suite for the yt-dlp-based-automation project.

## Running Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/test_metadata_service.py

# Run specific test
pytest tests/test_metadata_service.py::TestMetadataService::test_add_playlist_to_new_file

# Run with coverage report
pytest tests/ --cov=app --cov-report=html
```

## Test Structure

### Unit Tests
- **test_metadata_service.py** - Tests for reading/writing playlist metadata in audio files
- **test_playlist_service.py** - Tests for m3u8 generation and playlist name sanitization
- **test_platform_services.py** - Tests for platform detection (YouTube, SoundCloud)

### Integration Tests
- **test_integration.py** - End-to-end workflow tests covering:
  - Multiple playlist membership without file duplication
  - Metadata-driven regeneration
  - Corrupted metadata handling

## Test Coverage

The test suite validates:

✅ **Metadata Service**
- Adding playlists to audio files
- Reading playlists from metadata
- Preventing duplicate playlist tags
- Unicode playlist name support
- Metadata persistence across reloads

✅ **Playlist Service**
- M3u8 generation from file metadata
- Sanitization of playlist names (reject URLs/paths)
- Generating all playlists from metadata
- Handling invalid/corrupted metadata gracefully

✅ **Platform Services**
- URL detection for YouTube and SoundCloud
- Platform-specific service instantiation
- Unsupported URL handling

✅ **Integration Workflows**
- Files can belong to multiple playlists (no duplication)
- Playlists can be regenerated from metadata alone
- System handles corrupted metadata without crashing

## Requirements

Tests require:
- `pytest>=7.0.0`
- `pytest-cov>=4.0.0` (for coverage reports)
- `ffmpeg` (for creating test opus files)

Install dev dependencies:
```bash
pip install -r requirements-dev.txt
```

## Key Design Principles Tested

1. **Metadata as Source of Truth** - M3u8 files generated from file metadata, not YouTube queries
2. **Single Responsibility** - Each service has one clear purpose
3. **Platform Abstraction** - Different platforms handled by dedicated services
4. **Defensive Programming** - Invalid data (URLs, paths) handled gracefully
5. **Portability** - Metadata stored in files, survives app restarts

## CI/CD Integration

Add to your CI pipeline:
```yaml
- name: Run tests
  run: |
    source venv/bin/activate
    pytest tests/ -v --cov=app
```
