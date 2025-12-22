# yt-dlp-based-automation

Service-oriented YouTube/SoundCloud → VirtualDJ library sync tool that downloads playlists, organizes music by playlist name, and generates portable `.m3u8` playlists with metadata tagging.

## Features

- **Unified Music Library** - All tracks in one central location organized by playlist
- **Automatic Playlist Generation** - Creates VirtualDJ-compatible `.m3u8` playlists with relative paths
- **Metadata Tagging** - Embeds playlist names in file metadata for multi-playlist membership
- **Download Archive** - Tracks downloaded songs to avoid duplicates on re-runs
- **Idempotent & Safe** - Re-run anytime without breaking existing library
- **Emoji Support** - Preserves exact playlist names including emojis from YouTube/SoundCloud
- **Configurable** - All yt-dlp settings controlled via `yt-dlp.conf`
- **Cleanup Tools** - Built-in commands to manage archive and downloads
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

**Delete everything** (archive + music + playlists):
```bash
python main.py clear-all
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
│   ├── models.py                  # Data models (Track)
│   ├── results.py                 # Result objects for operations
│   ├── container.py               # Dependency injection container
│   ├── orchestrator.py            # Workflow orchestration
│   ├── services/
│   │   ├── download_service.py    # yt-dlp integration
│   │   ├── library_service.py     # Track discovery
│   │   ├── playlist_service.py    # .m3u8 generation
│   │   ├── metadata_service.py    # Tag embedding
│   │   ├── cleanup_service.py     # Cleanup operations
│   │   ├── filesystem_service.py  # File/directory operations
│   │   └── logging_service.py     # Console output formatting
│   └── utils/
│
├── library/                       # ✅ PORTABLE - copy to other machines
│   ├── music/                     # Downloaded audio files (organized by playlist)
│   └── playlists/                 # Generated .m3u8 files
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

1. **Fetch Playlist Names** - Queries yt-dlp for the actual playlist title from YouTube/SoundCloud
2. **Download Tracks** - Uses yt-dlp with your configured settings to download audio
3. **Organize Files** - Saves tracks in `library/music/[Playlist Name]/[Artist] - [Title].opus`
4. **Tag Metadata** - Embeds playlist name in file's comment tag (allows multiple playlists per track)
5. **Generate Playlists** - Creates `.m3u8` files with relative paths pointing to tracks
6. **Archive** - Records downloaded video IDs to prevent re-downloading

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

- **Python 3.8+**
- **PyYAML** - Config file parsing
- **mutagen** - Audio metadata tagging
- **yt-dlp** - YouTube/SoundCloud downloader (system dependency)

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
