import sys
from app.config import Config
from app.services.download_service import DownloadService
from app.services.library_service import LibraryService
from app.services.playlist_service import PlaylistService
from app.services.metadata_service import MetadataService
from app.services.cleanup_service import CleanupService
from app.services.filesystem_service import FileSystemService
from app.services.logging_service import LoggingService

def show_usage():
    print("""
Usage: python main.py [command]

Commands:
  sync              Sync playlists (default)
  clear-archive     Delete download archive only
  clear-downloads   Delete all music files only
  clear-playlists   Delete all playlist files only
  clear-all         Delete everything (archive + downloads + playlists)
    """)

cfg = Config()

# Handle cleanup commands
if len(sys.argv) > 1:
    command = sys.argv[1]
    
    if command in ["-h", "--help", "help"]:
        show_usage()
        sys.exit(0)
    
    cleanup = CleanupService(cfg.library, cfg.archive)
    
    if command == "clear-archive":
        cleanup.clear_archive()
        sys.exit(0)
    elif command == "clear-downloads":
        cleanup.clear_downloads()
        sys.exit(0)
    elif command == "clear-playlists":
        cleanup.clear_playlists()
        sys.exit(0)
    elif command == "clear-all":
        cleanup.clear_all()
        sys.exit(0)
    elif command == "sync":
        pass  # Continue to sync
    else:
        show_usage()
        sys.exit(1)

# Normal sync operation
FileSystemService.ensure_directory(cfg.music)
FileSystemService.ensure_directory(cfg.playlists)

downloader = DownloadService(
    cfg.archive,
    cfg.yt_dlp_config,
)

library = LibraryService(cfg.music)
playlist_service = PlaylistService(cfg.playlists)
metadata = MetadataService()

for playlist_url in cfg.playlist_urls:
    playlist_name = downloader.get_playlist_name(playlist_url)
    LoggingService.progress(f"Syncing {playlist_name}")
    downloader.fetch(playlist_url)

    tracks = list(library.all_tracks())

    for t in tracks:
        metadata.add_playlist(t.file, playlist_name)

    playlist_service.update(playlist_name, tracks)
    
    # Clean up temporary directory after each playlist
    tmp_dir = cfg.music / ".tmp"
    if FileSystemService.remove_directory(tmp_dir):
        LoggingService.cleanup("Cleaned up temporary files")

LoggingService.success("Sync complete")
