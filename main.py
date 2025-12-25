import sys
from app.config import Config
from app.container import ServiceContainer
from app.orchestrator import SyncOrchestrator

def show_usage():
    print("""
Usage: python main.py [command] [options]

Commands:
  sync                    Sync playlists (default)
    --url URL             Sync a single playlist by URL
    --stats               Show library stats after sync
  
  stats                   Show library statistics
    --detailed            Include additional breakdowns
  
  orphans                 List orphaned tracks (no playlist tag)
  
  fix-orphans             Fix orphaned tracks
    --playlist NAME       Assign orphans to specified playlist
    --delete              Delete orphaned files (use with caution!)
  
  verify                  Compare local playlist with YouTube
    --url URL             Playlist URL to verify (required)
    --fix                 Remove stale playlist tags from files
  
  ambiguous               Show tracks that couldn't be matched automatically
  resolve-ambiguous       Interactively resolve ambiguous matches
  
  regenerate-playlists    Regenerate all m3u8 files from database/metadata
  rebuild-db              Rebuild database from file metadata (use if DB is lost)
  
  clear-archive           Delete download archive only
  clear-downloads         Delete all music files only
  clear-playlists         Delete all playlist files only
  clear-all               Delete everything (archive + downloads + playlists)
  clear-db                Clear the database only (keeps files)

Examples:
  python main.py sync --url "https://youtube.com/playlist?list=..."
  python main.py stats --detailed
  python main.py orphans
  python main.py verify --url "https://youtube.com/playlist?list=..." --fix
  python main.py ambiguous
  python main.py resolve-ambiguous
  python main.py fix-orphans --playlist "Uncategorized"
  python main.py fix-orphans --delete
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
        # Confirmation prompt for destructive action
        logging.warning("⚠️  This will delete ALL of the following:")
        logging.warning("   - Download archive (yt-dlp history)")
        logging.warning("   - All music files")
        logging.warning("   - All playlist files (m3u8)")
        logging.warning("")
        logging.warning("   Note: Database will NOT be cleared. Use 'clear-db' separately if needed.")
        
        try:
            confirm = input("\nAre you sure you want to delete everything? [y/N]: ").strip().lower()
        except EOFError:
            confirm = 'n'
        
        if confirm != 'y':
            logging.progress("❌ Operation cancelled by user.")
            sys.exit(0)
        
        logging.cleanup(logging._format_message('clear_all_start'))
        results = cleanup.clear_all()
        for result in results:
            logging.log_result(result)
        logging.success(logging._format_message('clear_all_complete'))
        sys.exit(0)
    elif command == "clear-db":
        # Clear database only
        logging.warning("⚠️  This will clear all tracks from the database.")
        logging.warning("   Files will NOT be deleted - only the database index.")
        logging.warning("   You can rebuild it with 'rebuild-db' command.")
        
        try:
            confirm = input("\nAre you sure you want to clear the database? [y/N]: ").strip().lower()
        except EOFError:
            confirm = 'n'
        
        if confirm != 'y':
            logging.progress("❌ Operation cancelled by user.")
            sys.exit(0)
        
        db = container.get('database')
        if db:
            count = db.clear_all()
            logging.success(f"✅ Cleared {count} track(s) from database.")
        else:
            logging.error("❌ Database service not available.")
        sys.exit(0)
    elif command == "regenerate-playlists":
        # Regenerate m3u8 files from database/metadata
        orchestrator = SyncOrchestrator(container)
        orchestrator.regenerate_all_playlists()
        sys.exit(0)
    elif command == "rebuild-db":
        # Rebuild database from file metadata
        orchestrator = SyncOrchestrator(container)
        orchestrator.rebuild_database()
        sys.exit(0)
    elif command in ["stats", "db-stats"]:
        # Show library/database statistics
        orchestrator = SyncOrchestrator(container)
        detailed = "--detailed" in sys.argv
        orchestrator.show_database_stats(detailed=detailed)
        sys.exit(0)
    elif command == "orphans":
        # List orphaned tracks
        orchestrator = SyncOrchestrator(container)
        orchestrator.list_orphaned_tracks()
        sys.exit(0)
    elif command == "ambiguous":
        # Show ambiguous matches queue
        orchestrator = SyncOrchestrator(container)
        orchestrator.show_ambiguous_queue()
        sys.exit(0)
    elif command == "resolve-ambiguous":
        # Interactively resolve ambiguous matches
        orchestrator = SyncOrchestrator(container)
        orchestrator.resolve_ambiguous_interactive()
        sys.exit(0)
    elif command == "verify":
        # Verify a playlist against YouTube
        if "--url" not in sys.argv:
            print("Error: verify requires --url argument")
            print("Usage: python main.py verify --url \"PLAYLIST_URL\" [--fix]")
            sys.exit(1)
        
        url_idx = sys.argv.index("--url")
        if url_idx + 1 >= len(sys.argv):
            print("Error: --url requires a URL argument")
            sys.exit(1)
        
        url = sys.argv[url_idx + 1]
        fix = "--fix" in sys.argv
        
        orchestrator = SyncOrchestrator(container)
        orchestrator.verify_playlist(url, fix=fix)
        sys.exit(0)
    elif command == "fix-orphans":
        # Fix orphaned tracks
        orchestrator = SyncOrchestrator(container)
        
        if "--delete" in sys.argv:
            # Confirm deletion
            print("⚠️  WARNING: This will permanently delete orphaned files!")
            confirm = input("Type 'yes' to confirm: ")
            if confirm.lower() == 'yes':
                orchestrator.fix_orphaned_tracks(delete=True)
            else:
                print("Cancelled.")
        elif "--playlist" in sys.argv:
            playlist_idx = sys.argv.index("--playlist")
            if playlist_idx + 1 < len(sys.argv):
                playlist_name = sys.argv[playlist_idx + 1]
                orchestrator.fix_orphaned_tracks(playlist_name=playlist_name)
            else:
                print("Error: --playlist requires a playlist name")
                sys.exit(1)
        else:
            print("Error: Must specify --playlist NAME or --delete")
            print("Run 'python main.py --help' for usage")
            sys.exit(1)
        sys.exit(0)
    elif command == "sync":
        # Check for options
        show_stats = "--stats" in sys.argv
        
        # Check for --url parameter
        if "--url" in sys.argv:
            url_idx = sys.argv.index("--url")
            if url_idx + 1 < len(sys.argv):
                url = sys.argv[url_idx + 1]
                orchestrator = SyncOrchestrator(container)
                orchestrator.sync_single_playlist(url)
                
                # Show full stats if requested
                if show_stats:
                    orchestrator.show_database_stats(detailed=False)
                
                sys.exit(0)
            else:
                print("Error: --url requires a URL argument")
                sys.exit(1)
        # Otherwise continue to sync all playlists
    else:
        show_usage()
        sys.exit(1)

# Execute sync workflow (all playlists)
orchestrator = SyncOrchestrator(container)
orchestrator.sync_all_playlists()
