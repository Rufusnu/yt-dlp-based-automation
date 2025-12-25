from pathlib import Path
from typing import List, TYPE_CHECKING, Dict, Optional
import re
from app.results import PlaylistResult, OperationStatus

if TYPE_CHECKING:
    from app.services.download_service import TrackInfo
    from app.services.metadata_service import MetadataService
    from app.services.database_service import DatabaseService

class PlaylistService:
    def __init__(self, playlist_dir: Path, music_dir: Path, metadata_service=None, database_service=None):
        self.playlist_dir = playlist_dir
        self.music_dir = music_dir
        self.metadata_service = metadata_service
        self.database_service = database_service
    
    @staticmethod
    def _sanitize_playlist_name(name: str) -> str:
        """
        Sanitize playlist name for use as filename.
        Skip names that look like URLs or paths.
        """
        # Skip if it looks like a URL
        if name.startswith(('http://', 'https://', 'www.')):
            return None
        # Skip if it contains path separators (except emoji/unicode)
        if '/' in name and not any(ord(c) > 127 for c in name):
            return None
        # Replace invalid filename characters
        name = re.sub(r'[<>:"|?*]', '', name)
        return name

    # ==================== Database-backed methods (PREFERRED) ====================
    
    def generate_from_database(self, playlist_name: str) -> PlaylistResult:
        """
        Generate m3u8 from database (fast - no file scanning).
        
        This is the PREFERRED method when database is available.
        Falls back to metadata scanning if database unavailable.
        """
        if not self.database_service:
            # Fallback to metadata scanning
            return self.generate_from_metadata(playlist_name)
        
        m3u = self.playlist_dir / f"{playlist_name}.m3u8"
        
        # Query database for tracks in this playlist
        tracks = self.database_service.get_tracks_in_playlist(playlist_name)
        
        # Filter to only existing files
        matching_files = []
        for track in tracks:
            file_path = Path(track.file_path)
            if file_path.exists():
                matching_files.append(file_path)
        
        # Write m3u8
        with m3u.open("w", encoding="utf-8") as f:
            for file in sorted(matching_files, key=lambda p: p.name.lower()):
                rel = "../music/" + file.name
                f.write(rel + "\n")
        
        return PlaylistResult(
            success=True,
            operation="playlist_updated",
            status=OperationStatus.SUCCESS,
            playlist_name=playlist_name,
            track_count=len(matching_files),
            data={"playlist_name": playlist_name, "track_count": len(matching_files)}
        )
    
    def generate_all_from_database(self) -> Dict[str, PlaylistResult]:
        """
        Generate m3u8 for all playlists in the database (fast).
        
        Returns:
            Dict mapping playlist_name -> PlaylistResult
        """
        if not self.database_service:
            # Fallback to metadata scanning
            return self.generate_all_from_metadata()
        
        results = {}
        all_playlists = self.database_service.get_all_playlists()
        
        for playlist_name in all_playlists:
            # Skip invalid playlist names
            sanitized = self._sanitize_playlist_name(playlist_name)
            if not sanitized:
                continue
            
            results[playlist_name] = self.generate_from_database(playlist_name)
        
        return results

    # ==================== Metadata-backed methods (FALLBACK) ====================

    def generate_from_metadata(self, playlist_name: str) -> PlaylistResult:
        """
        Generate m3u8 by scanning all files and reading metadata.
        
        This is the PRIMARY method for m3u8 generation.
        - Reads playlist membership from file metadata
        - Independent of YouTube availability
        - Preserves historical playlist membership
        """
        if not self.metadata_service:
            return PlaylistResult(
                success=False,
                operation="playlist_updated",
                status=OperationStatus.FAILED,
                playlist_name=playlist_name,
                track_count=0,
                error="MetadataService not available"
            )
        
        m3u = self.playlist_dir / f"{playlist_name}.m3u8"
        
        # Scan all audio files in music directory
        audio_extensions = {'.opus', '.mp3', '.m4a', '.ogg', '.flac', '.webm'}
        matching_files = []
        
        for file in self.music_dir.glob("*.*"):
            if file.suffix.lower() not in audio_extensions:
                continue
            
            # Read playlists from metadata
            playlists = self.metadata_service.get_playlists(file)
            
            # Check if this file belongs to current playlist
            if playlist_name in playlists:
                matching_files.append(file)
        
        # Write m3u8
        with m3u.open("w", encoding="utf-8") as f:
            for file in sorted(matching_files):  # Sort for consistent ordering
                rel = "../music/" + file.name
                f.write(rel + "\n")
        
        return PlaylistResult(
            success=True,
            operation="playlist_updated",
            status=OperationStatus.SUCCESS,
            playlist_name=playlist_name,
            track_count=len(matching_files),
            data={"playlist_name": playlist_name, "track_count": len(matching_files)}
        )
    
    def generate_all_from_metadata(self) -> Dict[str, PlaylistResult]:
        """
        Scan all files and generate m3u8 for every unique playlist found in metadata.
        
        Returns:
            Dict mapping playlist_name -> PlaylistResult
        """
        if not self.metadata_service:
            return {}
        
        # Collect all unique playlist names from all files
        all_playlists = set()
        audio_extensions = {'.opus', '.mp3', '.m4a', '.ogg', '.flac', '.webm'}
        
        for file in self.music_dir.glob("*.*"):
            if file.suffix.lower() not in audio_extensions:
                continue
            playlists = self.metadata_service.get_playlists(file)
            all_playlists.update(playlists)
        
        # Generate m3u8 for each valid playlist
        results = {}
        for playlist_name in all_playlists:
            # Skip invalid playlist names (URLs, paths, etc.)
            sanitized = self._sanitize_playlist_name(playlist_name)
            if not sanitized:
                continue
            
            results[playlist_name] = self.generate_from_metadata(playlist_name)
        
        return results

    def update_from_tracks(self, playlist_name: str, track_files: List[Path]) -> PlaylistResult:
        """
        LEGACY: Generate m3u8 from a list of track file paths.
        Kept for backwards compatibility.
        """
        m3u = self.playlist_dir / f"{playlist_name}.m3u8"
        
        with m3u.open("w", encoding="utf-8") as f:
            track_count = 0
            for track_file in track_files:
                if track_file and track_file.exists():
                    try:
                        rel = "../music/" + track_file.name
                        f.write(rel + "\n")
                        track_count += 1
                    except ValueError:
                        pass
        
        return PlaylistResult(
            success=True,
            operation="playlist_updated",
            status=OperationStatus.SUCCESS,
            playlist_name=playlist_name,
            track_count=track_count,
            data={"playlist_name": playlist_name, "track_count": track_count}
        )

    def update(self, playlist_name, tracks) -> PlaylistResult:
        """
        LEGACY: Generate m3u8 from Track objects (filesystem-based).
        Kept for backwards compatibility.
        """
        m3u = self.playlist_dir / f"{playlist_name}.m3u8"
        
        with m3u.open("w", encoding="utf-8") as f:
            track_count = 0
            for t in tracks:
                try:
                    rel = "../" + str(t.file.relative_to(self.playlist_dir.parent))
                    rel = rel.replace("\\", "/")
                    f.write(rel + "\n")
                    track_count += 1
                except ValueError:
                    pass
        
        return PlaylistResult(
            success=True,
            operation="playlist_updated",
            status=OperationStatus.SUCCESS,
            playlist_name=playlist_name,
            track_count=track_count,
            data={"playlist_name": playlist_name, "track_count": track_count}
        )
