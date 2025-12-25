"""
SQLite database service for fast track and playlist lookups.

The database acts as a CACHE/INDEX of file metadata.
Source of truth remains the files themselves - database can always be rebuilt.
"""
import sqlite3
import hashlib
import json
from pathlib import Path
from typing import Optional, List, Set, Dict, Any
from dataclasses import dataclass
from contextlib import contextmanager


@dataclass
class TrackRecord:
    """Database record for a track."""
    file_path: str
    title: str
    artist: str
    source_id: Optional[str]  # "youtube:xxx" or "soundcloud:xxx"
    playlists: Set[str]
    file_hash: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "title": self.title,
            "artist": self.artist,
            "source_id": self.source_id,
            "playlists": list(self.playlists),
            "file_hash": self.file_hash,
        }


class DatabaseService:
    """
    SQLite database for fast track lookups.
    
    Schema:
    - tracks: Core track info with source_id for deduplication
    - Playlists stored as JSON array in tracks table (simpler than join table)
    
    The database is a CACHE. If lost, run rebuild-db to reconstruct from files.
    """
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema if needed."""
        with self._connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tracks (
                    file_path TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    artist TEXT,
                    source_id TEXT,
                    playlists TEXT DEFAULT '[]',
                    file_hash TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Index for fast source_id lookups (deduplication)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_source_id ON tracks(source_id)
            """)
            conn.commit()
    
    @contextmanager
    def _connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    # ==================== CRUD Operations ====================
    
    def add_track(self, track: TrackRecord) -> bool:
        """
        Add a new track to the database.
        Returns True if added, False if already exists.
        """
        with self._connection() as conn:
            try:
                conn.execute("""
                    INSERT INTO tracks (file_path, title, artist, source_id, playlists, file_hash)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    track.file_path,
                    track.title,
                    track.artist,
                    track.source_id,
                    json.dumps(list(track.playlists), ensure_ascii=False),
                    track.file_hash,
                ))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False  # Already exists
    
    def update_track(self, track: TrackRecord) -> bool:
        """Update an existing track."""
        with self._connection() as conn:
            cursor = conn.execute("""
                UPDATE tracks 
                SET title = ?, artist = ?, source_id = ?, playlists = ?, 
                    file_hash = ?, updated_at = CURRENT_TIMESTAMP
                WHERE file_path = ?
            """, (
                track.title,
                track.artist,
                track.source_id,
                json.dumps(list(track.playlists), ensure_ascii=False),
                track.file_hash,
                track.file_path,
            ))
            conn.commit()
            return cursor.rowcount > 0
    
    def upsert_track(self, track: TrackRecord) -> None:
        """Insert or update a track."""
        if not self.add_track(track):
            self.update_track(track)
    
    def get_track_by_path(self, file_path: str) -> Optional[TrackRecord]:
        """Get a track by its file path."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM tracks WHERE file_path = ?",
                (file_path,)
            ).fetchone()
            
            if row:
                return self._row_to_track(row)
            return None
    
    def get_track_by_source_id(self, source_id: str) -> Optional[TrackRecord]:
        """
        Find a track by its source ID (youtube:xxx, soundcloud:xxx).
        This is the key lookup for deduplication.
        """
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM tracks WHERE source_id = ?",
                (source_id,)
            ).fetchone()
            
            if row:
                return self._row_to_track(row)
            return None
    
    def delete_track(self, file_path: str) -> bool:
        """Remove a track from the database."""
        with self._connection() as conn:
            cursor = conn.execute(
                "DELETE FROM tracks WHERE file_path = ?",
                (file_path,)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    # ==================== Playlist Operations ====================
    
    def add_playlist_to_track(self, file_path: str, playlist_name: str) -> bool:
        """Add a playlist to a track's playlist list."""
        track = self.get_track_by_path(file_path)
        if not track:
            return False
        
        if playlist_name in track.playlists:
            return False  # Already in playlist
        
        track.playlists.add(playlist_name)
        return self.update_track(track)
    
    def remove_playlist_from_track(self, file_path: str, playlist_name: str) -> bool:
        """Remove a playlist from a track."""
        track = self.get_track_by_path(file_path)
        if not track or playlist_name not in track.playlists:
            return False
        
        track.playlists.discard(playlist_name)
        return self.update_track(track)
    
    def get_tracks_in_playlist(self, playlist_name: str) -> List[TrackRecord]:
        """Get all tracks belonging to a playlist."""
        with self._connection() as conn:
            # Use JSON contains for playlist lookup
            rows = conn.execute("""
                SELECT * FROM tracks 
                WHERE playlists LIKE ?
                ORDER BY title
            """, (f'%"{playlist_name}"%',)).fetchall()
            
            return [self._row_to_track(row) for row in rows]
    
    def get_all_playlists(self) -> Set[str]:
        """Get all unique playlist names in the database."""
        playlists = set()
        with self._connection() as conn:
            rows = conn.execute("SELECT playlists FROM tracks").fetchall()
            for row in rows:
                playlists.update(json.loads(row["playlists"]))
        return playlists
    
    # ==================== Bulk Operations ====================
    
    def get_all_tracks(self) -> List[TrackRecord]:
        """Get all tracks in the database."""
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM tracks ORDER BY title").fetchall()
            return [self._row_to_track(row) for row in rows]
    
    def get_track_count(self) -> int:
        """Get total number of tracks."""
        with self._connection() as conn:
            row = conn.execute("SELECT COUNT(*) as count FROM tracks").fetchone()
            return row["count"]
    
    def clear_all(self) -> int:
        """Clear all tracks from database. Returns count of deleted tracks."""
        with self._connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
            conn.execute("DELETE FROM tracks")
            conn.commit()
            return count
    
    def source_id_exists(self, source_id: str) -> bool:
        """Check if a source_id already exists (fast dedup check)."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM tracks WHERE source_id = ? LIMIT 1",
                (source_id,)
            ).fetchone()
            return row is not None
    
    def get_file_paths_by_source_ids(self, source_ids: List[str]) -> Dict[str, str]:
        """
        Batch lookup: given source_ids, return mapping of source_id -> file_path.
        Used to quickly find which tracks are already downloaded.
        """
        if not source_ids:
            return {}
        
        with self._connection() as conn:
            placeholders = ",".join("?" * len(source_ids))
            rows = conn.execute(f"""
                SELECT source_id, file_path FROM tracks 
                WHERE source_id IN ({placeholders})
            """, source_ids).fetchall()
            
            return {row["source_id"]: row["file_path"] for row in rows}
    
    # ==================== Helpers ====================
    
    def _row_to_track(self, row: sqlite3.Row) -> TrackRecord:
        """Convert a database row to TrackRecord."""
        return TrackRecord(
            file_path=row["file_path"],
            title=row["title"],
            artist=row["artist"] or "",
            source_id=row["source_id"],
            playlists=set(json.loads(row["playlists"])),
            file_hash=row["file_hash"],
        )
    
    @staticmethod
    def compute_file_hash(file_path: Path) -> str:
        """Compute MD5 hash of first 64KB of file (fast fingerprint)."""
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            hasher.update(f.read(65536))  # First 64KB
        return hasher.hexdigest()
    
    @staticmethod
    def make_source_id(platform: str, track_id: str) -> str:
        """Create a source_id string like 'youtube:dQw4w9WgXcQ'."""
        return f"{platform}:{track_id}"
