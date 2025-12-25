# yt-dlp-based-automation

Service-oriented YouTube/SoundCloud → VirtualDJ library sync tool that downloads playlists, organizes music with metadata tagging, and generates portable `.m3u8` playlists.

## Features

- **Unified Music Library** - All tracks in a flat directory with playlist info in metadata
- **SQLite Database** - Fast track lookups and deduplication via source IDs
- **Source ID Deduplication** - Tracks identified by YouTube/SoundCloud video ID, not filenames
- **Automatic Playlist Generation** - Creates VirtualDJ-compatible `.m3u8` playlists with relative paths
- **Metadata Tagging** - Embeds playlist names in file metadata for multi-playlist membership
- **Download Archive** - yt-dlp archive prevents re-downloading
- **Playlist Verification** - Compare local library against YouTube playlists
- **Orphan Detection** - Find and manage tracks without playlist assignments
- **Safe Destructive Operations** - Confirmation prompts for all data deletion
- **Idempotent & Safe** - Re-run anytime without breaking existing library
- **Emoji Support** - Preserves exact playlist names including emojis from YouTube/SoundCloud
- **Configurable** - All yt-dlp settings controlled via `yt-dlp.conf`
- **Clean Architecture** - Dependency injection, service-oriented design with result objects

## Installation

### 1. Clone the repository
```bash
git clone https://github.com/Rufusnu/yt-dlp-based-automation.git
cd yt-dlp-based-automation
```

### 2. Set up Python virtual environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Install yt-dlp
Make sure `yt-dlp` is installed and available in your PATH:
```bash
pip install yt-dlp
# or
sudo apt install yt-dlp
```

### 5. Configure playlists
```bash
cp config.yaml.example config.yaml
# Edit config.yaml and add your playlist URLs
```

## Configuration

### `config.yaml`
Main application configuration:
```yaml
library_dir: "./library"           # Where music is stored
archive_file: "./archive.txt"      # Download history
yt_dlp_config: "./yt-dlp.conf"    # yt-dlp settings file

playlists:
  - https://music.youtube.com/playlist?list=YOUR_PLAYLIST_ID
  - https://music.youtube.com/playlist?list=ANOTHER_PLAYLIST_ID
```

### `yt-dlp.conf`
Controls all yt-dlp download behavior:
- Audio format and quality
- Output path templates (artist - title naming)
- Metadata embedding
- Download throttling
- Network retry settings

See the included `yt-dlp.conf` for a complete example.

## Usage

### Sync Playlists (Default)
Download new tracks and update playlists:
```bash
python main.py
# or explicitly
python main.py sync

# Sync a specific playlist
python main.py sync --url "https://youtube.com/playlist?list=..."

# Show stats after sync
python main.py sync --stats
```

### Library Statistics
View library information:
```bash
python main.py stats
python main.py stats --detailed
```

### Orphan Management
Find tracks without playlist assignments:
```bash
# List orphaned tracks
python main.py orphans

# Assign orphans to a playlist
python main.py fix-orphans --playlist "Uncategorized"

# Delete orphaned files (with confirmation)
python main.py fix-orphans --delete
```

### Playlist Verification
Compare local library with YouTube playlist:
```bash
# Check for differences
python main.py verify --url "https://youtube.com/playlist?list=..."

# Remove stale playlist tags (requires confirmation)
python main.py verify --url "https://youtube.com/playlist?list=..." --fix
```

### Ambiguous Match Resolution
Handle tracks that couldn't be automatically matched:
```bash
# Show unresolved matches
python main.py ambiguous

# Interactively resolve matches
python main.py resolve-ambiguous
```

### Regeneration & Rebuild
```bash
# Regenerate all m3u8 files from database
python main.py regenerate-playlists

# Rebuild database from file metadata
python main.py rebuild-db
```

### Cleanup Commands

**Clear download archive** (force re-download everything on next sync):
```bash
python main.py clear-archive
```

**Delete all downloaded music**:
```bash
python main.py clear-downloads
```

**Delete generated playlists**:
```bash
python main.py clear-playlists
```

**Delete everything** (archive + music + playlists, requires confirmation):
```bash
python main.py clear-all
```

**Clear database only** (keeps files, requires confirmation):
```bash
python main.py clear-db
```

### Help
```bash
python main.py --help
```

## Project Structure

```
yt-dlp-based-automation/
├── app/
│   ├── config.py                  # Configuration loader
│   ├── models.py                  # Data models (Track, PlaylistInfo)
│   ├── results.py                 # Result objects for operations
│   ├── container.py               # Dependency injection container
│   ├── orchestrator.py            # Workflow orchestration
│   ├── services/
│   │   ├── database_service.py    # SQLite database for fast lookups
│   │   ├── download_service.py    # yt-dlp integration
│   │   ├── library_service.py     # Track discovery
│   │   ├── playlist_service.py    # .m3u8 generation
│   │   ├── metadata_service.py    # Tag embedding & source ID
│   │   ├── cleanup_service.py     # Cleanup operations
│   │   ├── filesystem_service.py  # File/directory operations
│   │   ├── logging_service.py     # Console output formatting
│   │   └── platforms/             # Platform-specific handlers
│   └── utils/
│
├── library/                       # ✅ PORTABLE - copy to other machines
│   ├── music/                     # Downloaded audio files (flat structure)
│   ├── playlists/                 # Generated .m3u8 files
│   └── library.db                 # SQLite database (can be rebuilt)
│
├── config.yaml                    # Your playlist URLs (gitignored)
├── config.yaml.example            # Template for config
├── yt-dlp.conf                   # yt-dlp settings
├── archive.txt                   # Download history (gitignored)
├── main.py                       # CLI entry point
├── requirements.txt              # Python dependencies
├── README.md                     # This file
└── ARCHITECTURE.md               # Architecture documentation
```

## Architecture

This project follows a **clean, service-oriented architecture** with:

- **Dependency Injection** - All services receive dependencies via constructor
- **Result Objects** - Services return structured results instead of logging directly
- **Separation of Concerns** - Business logic separate from presentation
- **Single Responsibility** - Each service has one clear purpose
- **Orchestration Pattern** - Workflow coordination separated from business logic

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed documentation.

## How It Works

1. **Fetch Playlist Info** - Queries yt-dlp for playlist title and track list with video IDs
2. **Database Deduplication** - Checks database for existing tracks by source ID (e.g., `youtube:dQw4w9WgXcQ`)
3. **Download New Tracks** - Uses yt-dlp to download only missing audio files
4. **Tag Metadata** - Embeds playlist name in file's comment tag and source ID in purl tag
5. **Update Database** - Adds new tracks to SQLite database with source IDs
6. **Generate Playlists** - Creates `.m3u8` files from database queries
7. **Archive** - yt-dlp records downloaded video IDs to prevent re-downloading

### Deduplication Strategy

The system uses **source IDs** (YouTube/SoundCloud video IDs) as the primary deduplication key:
- More reliable than filename matching (avoids false positives)
- Survives file renames
- Works even if video title changes on platform
- Database can always be rebuilt from file metadata

## Portability

Only the `library/` directory needs to be copied between machines:

```bash
# On machine A (after sync)
rsync -av library/ user@machineB:/path/to/yt2vdj/library/

# Or use USB drive
cp -r library/ /mnt/usb/yt2vdj-library/
```

The `.m3u8` playlists use relative paths (`../music/...`) so they work anywhere.

## VirtualDJ Integration

1. Open VirtualDJ
2. Go to Settings → Folders
3. Add `library/music/` as a music folder
4. Playlists in `library/playlists/` will be automatically detected

Tracks will appear with playlist membership based on the embedded metadata.

## Dependencies

- **Python 3.10+**
- **PyYAML** - Config file parsing
- **mutagen** - Audio metadata tagging
- **yt-dlp** - YouTube/SoundCloud downloader (also Python library for filename sanitization)

## Troubleshooting

**"No module named 'yaml'"**
```bash
pip install -r requirements.txt
```

**"yt-dlp: command not found"**
```bash
pip install yt-dlp
```

**Downloads are slow**
Adjust throttling in `yt-dlp.conf`:
```conf
--sleep-interval 5
--max-sleep-interval 10
```

**Playlist names don't match YouTube**
The script fetches names directly from yt-dlp's metadata. Check if your playlist URL is correct.

## Contributing

Issues and pull requests welcome at [github.com/Rufusnu/yt-dlp-based-automation](https://github.com/Rufusnu/yt-dlp-based-automation)

## License

See [LICENSE](LICENSE) file.
