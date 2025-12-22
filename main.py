import sys
from app.config import Config
from app.container import ServiceContainer
from app.orchestrator import SyncOrchestrator

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
    elif command == "sync":
        pass  # Continue to sync
    else:
        show_usage()
        sys.exit(1)

# Execute sync workflow
orchestrator = SyncOrchestrator(container)
orchestrator.sync_all_playlists()
