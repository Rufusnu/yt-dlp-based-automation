from app.results import OperationResult, OperationStatus


class LoggingService:
    """Handles all console output with formatted messages."""
    
    # Message templates
    MESSAGES = {
        # Cleanup operations
        'clear_archive_success': "Cleared archive: {path}",
        'clear_archive_not_found': "Archive not found: {path}",
        'clear_downloads_success': "Cleared downloads: {path}",
        'clear_downloads_not_found': "Music directory not found: {path}",
        'clear_playlists_success': "Cleared playlists: {path}",
        'clear_playlists_not_found': "Playlists directory not found: {path}",
        'clear_all_start': "Clearing all data...",
        'clear_all_complete': "All data cleared",
        
        # Download operations
        'sync_start': "Syncing {playlist_name}",
        'playlist_name_fetch_failed': "Could not fetch playlist name: {error}",
        
        # Playlist operations
        'playlist_updated': "Updated playlist: {playlist_name} ({track_count} tracks)",
        'playlist_path_error': "Could not create relative path for {file_path}",
        
        # System operations
        'cleanup_temp': "Cleaned up temporary files",
        'sync_complete': "Sync complete",
    }
    
    @staticmethod
    def _format_message(template_key: str, **kwargs) -> str:
        """Format a message using a template."""
        template = LoggingService.MESSAGES.get(template_key, template_key)
        return template.format(**kwargs)
    
    @staticmethod
    def info(message: str):
        """Print informational message."""
        print(f"ℹ️  {message}")

    @staticmethod
    def success(message: str):
        """Print success message."""
        print(f"✅ {message}")

    @staticmethod
    def warning(message: str):
        """Print warning message."""
        print(f"⚠️  {message}")

    @staticmethod
    def error(message: str):
        """Print error message."""
        print(f"❌ {message}")

    @staticmethod
    def progress(message: str):
        """Print progress message."""
        print(f"▶ {message}")

    @staticmethod
    def cleanup(message: str):
        """Print cleanup message."""
        print(f"🗑️  {message}")
    
    @staticmethod
    def log_result(result: OperationResult):
        """Log a result based on its status and operation type."""
        message_key = f"{result.operation}_{result.status.value}"
        
        # Format message with result data
        message = LoggingService._format_message(message_key, **(result.data or {}))
        
        # Choose appropriate log level
        if result.success:
            if result.status == OperationStatus.SUCCESS:
                LoggingService.success(message)
            else:
                LoggingService.info(message)
        else:
            if result.status == OperationStatus.NOT_FOUND:
                LoggingService.info(message)
            else:
                LoggingService.warning(message)
