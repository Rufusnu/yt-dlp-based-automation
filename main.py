import sys
from app.config import Config
from app.container import ServiceContainer
from app.orchestrator import SyncOrchestrator

def show_usage():
    print("""
Usage: python main.py [command] [options]

Commands:
  sync              Sync playlists (default)
    --url URL       Sync a single playlist by URL
  regenerate-playlists  Regenerate all m3u8 files from existing music folders
  clear-archive     Delete download archive only
  clear-downloads   Delete all music files only
  clear-playlists   Delete all playlist files only
  clear-all         Delete everything (archive + downloads + playlists)
    """)

# Load configuration
cfg = Config()

# Initialize service container with dependency injection
container = ServiceContainer(cfg)

# Get services
cleanup = container.get('cleanup')
logging = container.get('logging')

# Handle cleanup commands
if len(sys.argv) > 1:
    command = sys.argv[1]
    
    if command in ["-h", "--help", "help"]:
        show_usage()
        sys.exit(0)
    
    if command == "clear-archive":
        result = cleanup.clear_archive()
        logging.log_result(result)
        sys.exit(0)
    elif command == "clear-downloads":
        result = cleanup.clear_downloads()
        logging.log_result(result)
        sys.exit(0)
    elif command == "clear-playlists":
        result = cleanup.clear_playlists()
        logging.log_result(result)
        sys.exit(0)
    elif command == "clear-all":
        logging.cleanup(logging._format_message('clear_all_start'))
        results = cleanup.clear_all()
        for result in results:
            logging.log_result(result)
        logging.success(logging._format_message('clear_all_complete'))
        sys.exit(0)
    elif command == "regenerate-playlists":
        # Regenerate m3u8 files for all existing music folders
        orchestrator = SyncOrchestrator(container)
        orchestrator.regenerate_all_playlists()
        sys.exit(0)
    elif command == "sync":
        # Check for --url parameter
        if len(sys.argv) > 2 and sys.argv[2] == "--url" and len(sys.argv) > 3:
            # Sync single playlist by URL
            url = sys.argv[3]
            orchestrator = SyncOrchestrator(container)
            orchestrator.sync_single_playlist(url)
            sys.exit(0)
        # Otherwise continue to sync all playlists
    else:
        show_usage()
        sys.exit(1)

# Execute sync workflow (all playlists)
orchestrator = SyncOrchestrator(container)
orchestrator.sync_all_playlists()
