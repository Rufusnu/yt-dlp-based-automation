"""
Orchestrates the playlist synchronization workflow.
"""
from pathlib import Path
from app.container import ServiceContainer
from app.results import DownloadResult


class SyncOrchestrator:
    """Handles the complete sync workflow for playlists."""
    
    def __init__(self, container: ServiceContainer):
        self.container = container
        self.download_service = container.get('download')
        self.library_service = container.get('library')
        self.playlist_service = container.get('playlist')
        self.metadata_service = container.get('metadata')
        self.database_service = container.get('database')
        self.filesystem_service = container.get('filesystem')
        self.logging_service = container.get('logging')
        self.config = container.config
    
    def prepare_environment(self):
        """Ensure required directories exist."""
        self.filesystem_service.ensure_directory(self.config.music)
        self.filesystem_service.ensure_directory(self.config.playlists)
    
    def sync_all_playlists(self):
        """
        Sync all configured playlists.
        
        Tracks success/failure for each playlist and reports detailed summary.
        Continues syncing remaining playlists even if one fails.
        """
        self.prepare_environment()
        
        total_playlists = len(self.config.playlist_urls)
        successful = []
        failed = []
        
        self.logging_service.progress(f"Starting sync for {total_playlists} playlist(s)...")
        
        for idx, playlist_url in enumerate(self.config.playlist_urls, 1):
            self.logging_service.progress(f"\n{'='*60}")
            self.logging_service.progress(f"Playlist {idx}/{total_playlists}")
            self.logging_service.progress(f"{'='*60}")
            
            result = self.sync_single_playlist(playlist_url)
            
            if result.success:
                playlist_name = result.data.get('playlist_name', 'Unknown')
                successful.append(playlist_name)
            else:
                playlist_name = result.data.get('playlist_name', 'Unknown') if result.data else 'Unknown'
                failed.append((playlist_name, result.error or 'Unknown error'))
        
        # Final summary
        self.logging_service.progress(f"\n{'='*60}")
        self.logging_service.progress("SYNC SUMMARY")
        self.logging_service.progress(f"{'='*60}")
        self.logging_service.progress(f"Total playlists: {total_playlists}")
        self.logging_service.success(f"✅ Successful: {len(successful)}")
        
        if failed:
            self.logging_service.error(f"❌ Failed: {len(failed)}")
            for playlist_name, error in failed:
                self.logging_service.error(f"   - {playlist_name}: {error}")
        
        if len(successful) == total_playlists:
            self.logging_service.success("\n✅ All playlists synced successfully!")
        elif len(successful) > 0:
            self.logging_service.warning(
                f"\n⚠️  Sync completed with {len(failed)} error(s)"
            )
        else:
            self.logging_service.error("\n❌ All playlists failed to sync")
    
    def sync_single_playlist(self, playlist_url: str) -> DownloadResult:
        """
        Sync a single playlist with database-backed deduplication.
        
        Pipeline with validation at each step - aborts if any critical step fails.
        
        Workflow:
        0. Validate environment setup
        1. Get playlist name (critical - abort if fails)
        2. Query platform for complete track list with source IDs (critical)
        3. Check database for existing tracks (fast dedup)
        4. Download only new tracks
        5. Add new files to database with source_id
        6. Update playlist membership in database + file metadata
        7. Generate m3u8 from database (fast)
        8. Validate m3u8 file
        """
        from app.results import DownloadResult, OperationStatus
        from app.services.database_service import TrackRecord, DatabaseService
        
        # Determine platform for source_id prefix
        platform = self._detect_platform(playlist_url)
        
        # PHASE 0: Validate environment
        if not self.config.music.exists():
            self.logging_service.error("❌ Music directory does not exist - cannot proceed")
            return DownloadResult(
                success=False,
                operation="sync_aborted",
                status=OperationStatus.FAILED,
                error="Music directory not found"
            )
        
        # PHASE 1: Get playlist name (CRITICAL)
        self.logging_service.progress("Getting playlist metadata...")
        playlist_name, name_error = self.download_service.get_playlist_name(playlist_url)
        
        if name_error:
            self.logging_service.error(
                f"❌ Failed to fetch playlist name: {name_error}\n"
                f"   Aborting sync - cannot proceed without playlist name."
            )
            return DownloadResult(
                success=False,
                operation="sync_aborted",
                status=OperationStatus.FAILED,
                error=f"Playlist name fetch failed: {name_error}"
            )
        
        self.logging_service.progress(
            self.logging_service._format_message(
                'sync_start',
                playlist_name=playlist_name
            )
        )
        
        # PHASE 2: Query platform for complete track list (CRITICAL)
        self.logging_service.progress(f"Fetching track list from platform...")
        tracks_info, tracks_error = self.download_service.get_playlist_tracks(playlist_url)
        
        if tracks_error:
            self.logging_service.error(
                f"❌ Failed to fetch track list: {tracks_error}\n"
                f"   Aborting sync for '{playlist_name}' - cannot proceed without track metadata."
            )
            return DownloadResult(
                success=False,
                operation="sync_aborted",
                status=OperationStatus.FAILED,
                error=f"Track fetch failed: {tracks_error}",
                data={"playlist_name": playlist_name}
            )
        
        if not tracks_info:
            self.logging_service.error(
                f"❌ No tracks found in playlist '{playlist_name}'\n"
                f"   Aborting sync - empty playlist or parsing error."
            )
            return DownloadResult(
                success=False,
                operation="sync_aborted",
                status=OperationStatus.FAILED,
                error="No tracks found in playlist",
                data={"playlist_name": playlist_name}
            )
        
        total_tracks = len(tracks_info)
        self.logging_service.progress(f"✓ Found {total_tracks} track(s) in playlist")
        
        # PHASE 3: Check database for existing tracks (FAST DEDUP)
        self.logging_service.progress(f"Checking database for existing tracks...")
        
        # Build source IDs for all tracks
        source_ids = [
            DatabaseService.make_source_id(platform, track.video_id) 
            for track in tracks_info if track.video_id
        ]
        
        # Batch lookup in database
        existing_by_source_id = {}
        if self.database_service and source_ids:
            existing_by_source_id = self.database_service.get_file_paths_by_source_ids(source_ids)
        
        # Categorize tracks
        tracks_to_download = []
        tracks_already_have = []
        
        for track in tracks_info:
            source_id = DatabaseService.make_source_id(platform, track.video_id) if track.video_id else None
            
            if source_id and source_id in existing_by_source_id:
                # Already have this track (verified by source_id) - just update playlist membership
                tracks_already_have.append((track, existing_by_source_id[source_id], source_id))
            else:
                # No source_id match - must download
                # NOTE: We intentionally do NOT use fuzzy filename matching here.
                # Fuzzy matching causes false positives (e.g., "The Creator" matching 
                # "Tyler, The Creator - WHARF TALK"). Source ID is the only reliable 
                # deduplication method. If a track has no source_id in the database,
                # yt-dlp's archive will prevent re-downloading it anyway.
                tracks_to_download.append((track, source_id))
        
        self.logging_service.progress(
            f"✓ Database check: {len(tracks_already_have)} existing, "
            f"{len(tracks_to_download)} to download"
        )
        
        # PHASE 4: Update playlist membership for existing tracks
        if tracks_already_have:
            self.logging_service.progress(f"Updating playlist membership for existing tracks...")
            update_count = 0
            
            for idx, (track, file_path, source_id) in enumerate(tracks_already_have, 1):
                if idx == 1 or idx == len(tracks_already_have) or idx % 20 == 0:
                    self.logging_service.progress(
                        f"  [{idx}/{len(tracks_already_have)}] Updating membership..."
                    )
                
                try:
                    # Update file metadata
                    path = Path(file_path)
                    if path.exists():
                        self.metadata_service.add_playlist(path, playlist_name)
                    
                    # Update database
                    if self.database_service:
                        self.database_service.add_playlist_to_track(file_path, playlist_name)
                        update_count += 1
                except Exception:
                    pass
            
            self.logging_service.progress(f"✓ Updated {update_count} track(s) playlist membership")
        
        # PHASE 5: Download new tracks
        new_files_added = []
        
        if tracks_to_download:
            self.logging_service.progress(f"Downloading {len(tracks_to_download)} new track(s)...")
            
            # Snapshot files before download
            files_before = set(self.config.music.glob("*.*"))
            
            # Download
            download_result = self.download_service.fetch(playlist_url)
            
            if not download_result.success:
                self.logging_service.warning(
                    f"⚠️  Download had errors: {download_result.error}\n"
                    f"   Continuing with sync - some tracks may not have downloaded."
                )
            else:
                self.logging_service.progress(f"✓ Download phase completed")
            
            # Find new files
            files_after = set(self.config.music.glob("*.*"))
            new_files = files_after - files_before
            new_files_list = [
                f for f in new_files 
                if f.suffix.lower() in ['.opus', '.mp3', '.m4a', '.ogg', '.flac', '.webm']
            ]
            
            # PHASE 6: Add new files to database and tag them
            if new_files_list:
                self.logging_service.progress(f"Processing {len(new_files_list)} new file(s)...")
                
                for idx, file in enumerate(new_files_list, 1):
                    if idx == 1 or idx == len(new_files_list) or idx % 5 == 0:
                        self.logging_service.progress(
                            f"  [{idx}/{len(new_files_list)}] Processing new files..."
                        )
                    
                    try:
                        # Find matching track info to get source_id
                        source_id = self._find_source_id_for_file(file, tracks_to_download)
                        
                        # Tag file with playlist
                        self.metadata_service.add_playlist(file, playlist_name)
                        
                        # Store source_id in file metadata
                        if source_id:
                            self.metadata_service.set_source_id(file, source_id)
                        
                        # Add to database
                        if self.database_service:
                            title, artist = self.metadata_service.get_title_artist(file)
                            record = TrackRecord(
                                file_path=str(file),
                                title=title,
                                artist=artist,
                                source_id=source_id,
                                playlists={playlist_name},
                                file_hash=DatabaseService.compute_file_hash(file),
                            )
                            self.database_service.upsert_track(record)
                        
                        new_files_added.append(file)
                        
                    except Exception as e:
                        self.logging_service.warning(f"⚠️  Error processing {file.name}: {e}")
                
                self.logging_service.progress(f"✓ Processed {len(new_files_added)} new file(s)")
        else:
            self.logging_service.progress(f"✓ No new tracks to download")
        
        # PHASE 7: Generate m3u8 from database (FAST)
        self.logging_service.progress(f"Generating playlist...")
        
        if self.database_service:
            playlist_result = self.playlist_service.generate_from_database(playlist_name)
        else:
            playlist_result = self.playlist_service.generate_from_metadata(playlist_name)
        
        if not playlist_result.success:
            self.logging_service.error(
                f"❌ Failed to generate m3u8 file for '{playlist_name}'\n"
                f"   Error: {playlist_result.error}"
            )
            return DownloadResult(
                success=False,
                operation="sync_failed",
                status=OperationStatus.FAILED,
                error=f"Playlist generation failed: {playlist_result.error}",
                data={"playlist_name": playlist_name}
            )
        
        self.logging_service.log_result(playlist_result)
        
        # PHASE 8: Validate m3u8 was created correctly
        validation_success = self._validate_playlist(playlist_name)
        
        if not validation_success:
            self.logging_service.error(
                f"❌ Playlist validation failed for '{playlist_name}'\n"
                f"   M3u8 file may be empty or corrupted."
            )
            return DownloadResult(
                success=False,
                operation="sync_failed",
                status=OperationStatus.FAILED,
                error="Playlist validation failed",
                data={"playlist_name": playlist_name}
            )
        
        # Cleanup temporary files
        self._cleanup_temp_directory()
        
        # Calculate final playlist size
        final_playlist_count = 0
        if self.database_service:
            final_playlist_count = len(self.database_service.get_tracks_in_playlist(playlist_name))
        
        # Calculate failed downloads (can't be negative)
        attempted_downloads = len(tracks_to_download)
        successful_downloads = len(new_files_added)
        failed_downloads = max(0, attempted_downloads - successful_downloads)
        
        # Show sync summary
        sync_stats = {
            'playlist_name': playlist_name,
            'youtube_tracks': len(tracks_info),
            'existing_tracks': len(tracks_already_have),
            'downloaded': successful_downloads,
            'failed': failed_downloads,
            'playlist_tracks': final_playlist_count,
        }
        self.show_sync_summary(sync_stats)
        
        # Success!
        self.logging_service.success(f"✅ Sync completed successfully for '{playlist_name}'")
        return DownloadResult(
            success=True,
            operation="sync_complete",
            status=OperationStatus.SUCCESS,
            data={
                "playlist_name": playlist_name,
                "tracks_total": len(tracks_info),
                "existing_tracks": len(tracks_already_have),
                "new_files": len(new_files_added)
            }
        )
    
    def _detect_platform(self, url: str) -> str:
        """Detect platform from URL."""
        url_lower = url.lower()
        if 'youtube.com' in url_lower or 'youtu.be' in url_lower or 'music.youtube.com' in url_lower:
            return 'youtube'
        elif 'soundcloud.com' in url_lower:
            return 'soundcloud'
        return 'unknown'
    
    def _find_source_id_for_file(self, file: Path, tracks_to_download: list) -> str:
        """Try to match a downloaded file to its source_id."""
        from app.services.database_service import DatabaseService
        
        filename_lower = file.stem.lower()
        
        for track, source_id in tracks_to_download:
            # Simple matching - check if track title is in filename
            if track.title and track.title.lower() in filename_lower:
                return source_id
            if track.expected_filename and track.expected_filename.lower() in filename_lower:
                return source_id
        
        return None
    
    def _cleanup_temp_directory(self):
        """Remove temporary download directory."""
        tmp_dir = self.config.music / ".tmp"
        if self.filesystem_service.remove_directory(tmp_dir):
            self.logging_service.cleanup(
                self.logging_service._format_message('cleanup_temp')
            )
    
    def _validate_playlist(self, playlist_name: str):
        """Validate that m3u8 file exists and has content."""
        m3u8_path = self.config.playlists / f"{playlist_name}.m3u8"
        
        if not m3u8_path.exists():
            self.logging_service.error(
                f"❌ Validation failed: m3u8 file not created for {playlist_name}"
            )
            return False
        
        # Check if m3u8 has actual track entries (not just empty/comments)
        try:
            content = m3u8_path.read_text(encoding='utf-8')
            track_lines = [
                line for line in content.splitlines() 
                if line.strip() and not line.startswith('#')
            ]
            
            if not track_lines:
                self.logging_service.warning(
                    f"⚠️  m3u8 file exists but has no tracks: {playlist_name}"
                )
                return False
            
            self.logging_service.progress(
                f"✓ Validated: {len(track_lines)} track(s) in {playlist_name}.m3u8"
            )
            return True
            
        except Exception as e:
            self.logging_service.error(
                f"❌ Error validating {playlist_name}.m3u8: {e}"
            )
            return False
    
    def regenerate_all_playlists(self):
        """
        Regenerate m3u8 files from database (or metadata as fallback).
        
        This does NOT query YouTube - uses local data only.
        Use this to rebuild m3u8 files from local library.
        """
        self.prepare_environment()
        
        if self.database_service:
            self.logging_service.progress("Generating playlists from database...")
            results = self.playlist_service.generate_all_from_database()
        else:
            self.logging_service.progress("Scanning all files for playlist metadata...")
            results = self.playlist_service.generate_all_from_metadata()
        
        if not results:
            self.logging_service.warning("No playlists found")
            return
        
        self.logging_service.progress(f"Found {len(results)} unique playlist(s)")
        
        # Log results
        for playlist_name, result in results.items():
            self.logging_service.progress(f"  {playlist_name}")
            self.logging_service.log_result(result)
            self._validate_playlist(playlist_name)
        
        self.logging_service.success("✅ All playlists regenerated")
    
    def rebuild_database(self):
        """
        Rebuild the database from file metadata.
        
        Scans all audio files, reads their metadata (playlists, source_id),
        and rebuilds the database. Use this if database is lost or corrupted.
        """
        if not self.database_service:
            self.logging_service.error("❌ Database service not available")
            return
        
        from app.services.database_service import TrackRecord, DatabaseService
        
        self.logging_service.progress("Rebuilding database from file metadata...")
        self.logging_service.progress("This will scan all files and read their metadata tags.")
        
        # Clear existing database
        old_count = self.database_service.get_track_count()
        if old_count > 0:
            self.logging_service.progress(f"Clearing {old_count} existing database entries...")
            self.database_service.clear_all()
        
        # Scan all audio files
        audio_extensions = {'.opus', '.mp3', '.m4a', '.ogg', '.flac', '.webm'}
        audio_files = [
            f for f in self.config.music.glob("*.*") 
            if f.suffix.lower() in audio_extensions
        ]
        
        total_files = len(audio_files)
        self.logging_service.progress(f"Found {total_files} audio file(s) to scan...")
        
        added = 0
        errors = 0
        
        for idx, file in enumerate(audio_files, 1):
            if idx == 1 or idx == total_files or idx % 50 == 0:
                self.logging_service.progress(f"  [{idx}/{total_files}] Scanning files...")
            
            try:
                # Read metadata from file
                playlists, source_id = self.metadata_service.get_all_metadata(file)
                title, artist = self.metadata_service.get_title_artist(file)
                
                # Create record
                record = TrackRecord(
                    file_path=str(file),
                    title=title,
                    artist=artist,
                    source_id=source_id,
                    playlists=playlists,
                    file_hash=DatabaseService.compute_file_hash(file),
                )
                
                self.database_service.add_track(record)
                added += 1
                
            except Exception as e:
                errors += 1
        
        # Summary
        self.logging_service.progress(f"\n{'='*60}")
        self.logging_service.progress("DATABASE REBUILD COMPLETE")
        self.logging_service.progress(f"{'='*60}")
        self.logging_service.progress(f"Files scanned: {total_files}")
        self.logging_service.success(f"✅ Tracks added: {added}")
        
        if errors > 0:
            self.logging_service.warning(f"⚠️  Errors: {errors}")
        
        # Show playlist summary
        all_playlists = self.database_service.get_all_playlists()
        if all_playlists:
            self.logging_service.progress(f"\nPlaylists found in metadata: {len(all_playlists)}")
            for playlist in sorted(all_playlists):
                count = len(self.database_service.get_tracks_in_playlist(playlist))
                self.logging_service.progress(f"  - {playlist}: {count} track(s)")
        
        self.logging_service.success("\n✅ Database rebuild complete!")
    
    def show_database_stats(self, detailed: bool = False):
        """
        Show comprehensive library and database statistics.
        
        Args:
            detailed: If True, show additional breakdowns (file formats, etc.)
        """
        if not self.database_service:
            self.logging_service.error("❌ Database service not available")
            return
        
        from pathlib import Path
        from collections import Counter
        
        track_count = self.database_service.get_track_count()
        playlists = self.database_service.get_all_playlists()
        all_tracks = self.database_service.get_all_tracks()
        
        # Count tracks with source_id
        with_source_id = sum(1 for t in all_tracks if t.source_id)
        
        # Count by platform
        platforms = Counter()
        for t in all_tracks:
            if t.source_id:
                platform = t.source_id.split(":")[0] if ":" in t.source_id else "unknown"
                platforms[platform] += 1
        
        # File format breakdown
        format_counts = Counter()
        total_size_bytes = 0
        for t in all_tracks:
            path = Path(t.file_path)
            if path.exists():
                format_counts[path.suffix.lower()] += 1
                total_size_bytes += path.stat().st_size
        
        # Convert to human-readable size
        if total_size_bytes >= 1024**3:
            size_str = f"{total_size_bytes / (1024**3):.2f} GB"
        elif total_size_bytes >= 1024**2:
            size_str = f"{total_size_bytes / (1024**2):.2f} MB"
        else:
            size_str = f"{total_size_bytes / 1024:.2f} KB"
        
        # Print stats
        self.logging_service.progress(f"\n{'='*60}")
        self.logging_service.progress("📊 LIBRARY STATISTICS")
        self.logging_service.progress(f"{'='*60}")
        
        # Track counts
        self.logging_service.progress(f"\n📁 Library Overview:")
        self.logging_service.progress(f"   Total tracks: {track_count}")
        self.logging_service.progress(f"   Total size: {size_str}")
        self.logging_service.progress(f"   Total playlists: {len(playlists)}")
        
        # Source tracking
        self.logging_service.progress(f"\n🔗 Source Tracking:")
        self.logging_service.progress(f"   Tracks with source_id: {with_source_id}/{track_count} ({100*with_source_id//max(1,track_count)}%)")
        if platforms:
            for platform, count in platforms.most_common():
                self.logging_service.progress(f"   - {platform}: {count}")
        
        # File formats
        if format_counts:
            self.logging_service.progress(f"\n🎵 File Formats:")
            for fmt, count in format_counts.most_common():
                self.logging_service.progress(f"   - {fmt}: {count}")
        
        # Playlists breakdown
        if playlists:
            self.logging_service.progress(f"\n📋 Playlists:")
            for playlist in sorted(playlists):
                count = len(self.database_service.get_tracks_in_playlist(playlist))
                self.logging_service.progress(f"   - {playlist}: {count} track(s)")
        
        # Detailed stats if requested
        if detailed:
            # Tracks in multiple playlists
            multi_playlist = [t for t in all_tracks if len(t.playlists) > 1]
            if multi_playlist:
                self.logging_service.progress(f"\n🔄 Multi-Playlist Tracks:")
                self.logging_service.progress(f"   Tracks in multiple playlists: {len(multi_playlist)}")
            
            # Orphaned tracks (no playlist)
            orphaned = [t for t in all_tracks if not t.playlists]
            if orphaned:
                self.logging_service.progress(f"\n⚠️  Orphaned Tracks (no playlist tag):")
                self.logging_service.progress(f"   Count: {len(orphaned)}")
        
        self.logging_service.progress(f"\n{'='*60}")
    
    def show_sync_summary(self, stats: dict):
        """
        Show a summary after sync operations.
        
        Args:
            stats: Dictionary with sync statistics
        """
        self.logging_service.progress(f"\n{'='*60}")
        self.logging_service.progress("📊 SYNC SUMMARY")
        self.logging_service.progress(f"{'='*60}")
        
        if 'playlist_name' in stats:
            self.logging_service.progress(f"   Playlist: {stats['playlist_name']}")
        
        if 'youtube_tracks' in stats:
            self.logging_service.progress(f"   Tracks on YouTube: {stats['youtube_tracks']}")
        
        if 'existing_tracks' in stats:
            self.logging_service.progress(f"   Already in library: {stats['existing_tracks']}")
        
        if 'downloaded' in stats:
            self.logging_service.progress(f"   Newly downloaded: {stats['downloaded']}")
        
        if 'failed' in stats:
            self.logging_service.progress(f"   Failed/unavailable: {stats['failed']}")
        
        if 'playlist_tracks' in stats:
            self.logging_service.progress(f"   Final playlist size: {stats['playlist_tracks']}")
        
        self.logging_service.progress(f"{'='*60}")
    
    def list_orphaned_tracks(self):
        """
        List all tracks that have no playlist assignment.
        
        Returns:
            List of orphaned track records
        """
        if not self.database_service:
            self.logging_service.error("❌ Database service not available")
            return []
        
        all_tracks = self.database_service.get_all_tracks()
        orphaned = [t for t in all_tracks if not t.playlists]
        
        if not orphaned:
            self.logging_service.success("✅ No orphaned tracks found - all tracks are in playlists!")
            return []
        
        self.logging_service.progress(f"\n{'='*60}")
        self.logging_service.progress(f"⚠️  ORPHANED TRACKS ({len(orphaned)} files)")
        self.logging_service.progress(f"{'='*60}")
        self.logging_service.progress("These tracks have no playlist tag in their metadata:\n")
        
        for idx, track in enumerate(orphaned, 1):
            title = track.title or "Unknown"
            artist = track.artist or "Unknown"
            filename = Path(track.file_path).name
            
            # Show artist - title if available, otherwise filename
            if artist and artist != "Unknown" and title and title != "Unknown":
                display = f"{artist} - {title}"
            else:
                display = filename
            
            self.logging_service.progress(f"  {idx:3}. {display}")
        
        self.logging_service.progress(f"\n{'='*60}")
        self.logging_service.progress("To fix orphaned tracks, run:")
        self.logging_service.progress("  python main.py fix-orphans --playlist \"PlaylistName\"")
        self.logging_service.progress("  python main.py fix-orphans --delete")
        self.logging_service.progress(f"{'='*60}")
        
        return orphaned
    
    def fix_orphaned_tracks(self, playlist_name: str = None, delete: bool = False):
        """
        Fix orphaned tracks by either assigning them to a playlist or deleting them.
        
        Args:
            playlist_name: Name of playlist to assign orphans to (creates if needed)
            delete: If True, delete the orphaned files instead
        """
        if not self.database_service:
            self.logging_service.error("❌ Database service not available")
            return
        
        from app.services.database_service import TrackRecord, DatabaseService
        
        all_tracks = self.database_service.get_all_tracks()
        orphaned = [t for t in all_tracks if not t.playlists]
        
        if not orphaned:
            self.logging_service.success("✅ No orphaned tracks to fix!")
            return
        
        self.logging_service.progress(f"Found {len(orphaned)} orphaned track(s)")
        
        if delete:
            # Delete orphaned files
            self.logging_service.progress(f"Deleting {len(orphaned)} orphaned file(s)...")
            deleted = 0
            errors = 0
            
            for track in orphaned:
                try:
                    file_path = Path(track.file_path)
                    if file_path.exists():
                        file_path.unlink()
                        deleted += 1
                    # Remove from database
                    self.database_service.remove_track(track.file_path)
                except Exception as e:
                    self.logging_service.warning(f"⚠️  Failed to delete {track.file_path}: {e}")
                    errors += 1
            
            self.logging_service.success(f"✅ Deleted {deleted} file(s)")
            if errors:
                self.logging_service.warning(f"⚠️  {errors} error(s) occurred")
        
        elif playlist_name:
            # Assign to playlist
            self.logging_service.progress(f"Assigning {len(orphaned)} track(s) to '{playlist_name}'...")
            assigned = 0
            errors = 0
            
            for idx, track in enumerate(orphaned, 1):
                if idx == 1 or idx == len(orphaned) or idx % 10 == 0:
                    self.logging_service.progress(f"  [{idx}/{len(orphaned)}] Processing...")
                
                try:
                    file_path = Path(track.file_path)
                    
                    # Update file metadata
                    if file_path.exists():
                        self.metadata_service.add_playlist(file_path, playlist_name)
                    
                    # Update database
                    track.playlists.add(playlist_name)
                    self.database_service.upsert_track(track)
                    assigned += 1
                    
                except Exception as e:
                    self.logging_service.warning(f"⚠️  Failed to process {track.file_path}: {e}")
                    errors += 1
            
            self.logging_service.success(f"✅ Assigned {assigned} track(s) to '{playlist_name}'")
            if errors:
                self.logging_service.warning(f"⚠️  {errors} error(s) occurred")
            
            # Regenerate the playlist m3u8
            self.logging_service.progress(f"Regenerating {playlist_name}.m3u8...")
            result = self.playlist_service.generate_from_database(playlist_name)
            self.logging_service.log_result(result)
        
        else:
            self.logging_service.error("❌ Must specify --playlist NAME or --delete")
    
    def verify_playlist(self, playlist_url: str, fix: bool = False):
        """
        Verify a playlist's local tracks against YouTube and optionally fix discrepancies.
        
        This will:
        1. Fetch the current track list from YouTube
        2. Compare with local database
        3. Report tracks that are:
           - In YouTube but not local (missing)
           - In local but not YouTube (stale)
        4. If fix=True, remove stale playlist tags from files
        
        Args:
            playlist_url: URL of the playlist to verify
            fix: If True, remove stale playlist memberships
        """
        if not self.database_service:
            self.logging_service.error("❌ Database service not available")
            return
        
        from app.services.database_service import DatabaseService
        
        # Determine platform
        platform = self._detect_platform(playlist_url)
        
        # Get playlist name
        self.logging_service.progress("Fetching playlist info from YouTube...")
        playlist_name, name_error = self.download_service.get_playlist_name(playlist_url)
        if name_error:
            self.logging_service.error(f"❌ Failed to fetch playlist: {name_error}")
            return
        
        # Get tracks from YouTube
        tracks_info, tracks_error = self.download_service.get_playlist_tracks(playlist_url)
        if tracks_error:
            self.logging_service.error(f"❌ Failed to fetch tracks: {tracks_error}")
            return
        
        # Build set of YouTube source_ids
        youtube_source_ids = set()
        for track in tracks_info:
            if track.video_id:
                source_id = DatabaseService.make_source_id(platform, track.video_id)
                youtube_source_ids.add(source_id)
        
        # Get local tracks for this playlist
        local_tracks = self.database_service.get_tracks_in_playlist(playlist_name)
        local_source_ids = {t.source_id for t in local_tracks if t.source_id}
        
        # Find discrepancies
        missing_from_local = youtube_source_ids - local_source_ids  # In YT, not local
        stale_local = local_source_ids - youtube_source_ids  # In local, not YT
        
        # Report
        self.logging_service.progress(f"\n{'='*60}")
        self.logging_service.progress(f"📋 PLAYLIST VERIFICATION: {playlist_name}")
        self.logging_service.progress(f"{'='*60}")
        self.logging_service.progress(f"   YouTube tracks: {len(youtube_source_ids)}")
        self.logging_service.progress(f"   Local tracks: {len(local_tracks)}")
        self.logging_service.progress(f"   Missing from local: {len(missing_from_local)}")
        self.logging_service.progress(f"   Stale (removed from YT): {len(stale_local)}")
        
        # Show stale tracks
        if stale_local:
            self.logging_service.progress(f"\n⚠️  Tracks tagged locally but not in YouTube playlist:")
            stale_tracks = [t for t in local_tracks if t.source_id in stale_local]
            for t in stale_tracks:
                self.logging_service.progress(f"   - {t.artist} - {t.title}")
            
            if fix:
                # Ask for user confirmation before removing playlist tags
                self.logging_service.warning(f"\n⚠️  This will remove the '{playlist_name}' tag from {len(stale_tracks)} file(s).")
                self.logging_service.warning(f"   This action modifies file metadata and cannot be undone automatically.")
                
                try:
                    confirm = input(f"\nAre you sure you want to remove these playlist tags? [y/N]: ").strip().lower()
                except EOFError:
                    confirm = 'n'
                
                if confirm != 'y':
                    self.logging_service.progress("❌ Operation cancelled by user.")
                    return
                
                self.logging_service.progress(f"\nRemoving stale playlist tags...")
                removed = 0
                for track in stale_tracks:
                    try:
                        file_path = Path(track.file_path)
                        
                        # Remove from file metadata
                        if file_path.exists():
                            self.metadata_service.remove_playlist(file_path, playlist_name)
                        
                        # Update database
                        track.playlists.discard(playlist_name)
                        self.database_service.upsert_track(track)
                        removed += 1
                    except Exception as e:
                        self.logging_service.warning(f"⚠️  Failed to update {track.file_path}: {e}")
                
                self.logging_service.success(f"✅ Removed {removed} stale playlist tag(s)")
                
                # Regenerate m3u8
                self.logging_service.progress(f"Regenerating {playlist_name}.m3u8...")
                result = self.playlist_service.generate_from_database(playlist_name)
                self.logging_service.log_result(result)
            else:
                self.logging_service.progress(f"\nTo fix, run: python main.py verify --url \"...\" --fix")
        
        if missing_from_local:
            self.logging_service.progress(f"\n📥 {len(missing_from_local)} track(s) need to be downloaded")
            self.logging_service.progress(f"   Run sync to download them: python main.py sync --url \"...\"")
        
        if not stale_local and not missing_from_local:
            self.logging_service.success(f"\n✅ Playlist is fully synced!")
        
        self.logging_service.progress(f"{'='*60}")
    
    # ==================== Ambiguous Match Queue ====================
    
    def show_ambiguous_queue(self):
        """Show all unresolved ambiguous matches for manual review."""
        queue = self.download_service.get_ambiguous_queue()
        
        if not queue:
            self.logging_service.success("✅ No ambiguous matches to review!")
            return
        
        self.logging_service.progress(f"\n{'='*60}")
        self.logging_service.progress(f"⚠️  AMBIGUOUS MATCHES REQUIRING REVIEW: {len(queue)}")
        self.logging_service.progress(f"{'='*60}")
        
        for i, entry in enumerate(queue, 1):
            track = entry['track']
            self.logging_service.progress(f"\n[{i}] {track['artist']} - {track['title']}")
            self.logging_service.progress(f"    Playlist: {entry['playlist']}")
            self.logging_service.progress(f"    Video ID: {track['video_id']}")
            self.logging_service.progress(f"    Expected: {track['expected_filename']}.*")
            self.logging_service.progress(f"    Reason: {entry['reason']}")
            if entry.get('candidates'):
                self.logging_service.progress(f"    Candidates:")
                for c in entry['candidates']:
                    self.logging_service.progress(f"      - {c}")
            self.logging_service.progress(f"    Added: {entry['timestamp']}")
        
        self.logging_service.progress(f"\n{'='*60}")
        self.logging_service.progress("To resolve, use: python main.py resolve-ambiguous")
    
    def resolve_ambiguous_interactive(self):
        """Interactively resolve ambiguous matches."""
        queue = self.download_service.get_ambiguous_queue()
        
        if not queue:
            self.logging_service.success("✅ No ambiguous matches to review!")
            return
        
        self.logging_service.progress(f"\nResolving {len(queue)} ambiguous match(es)...\n")
        
        for entry in queue:
            track = entry['track']
            
            print(f"\n{'='*60}")
            print(f"Track: {track['artist']} - {track['title']}")
            print(f"Playlist: {entry['playlist']}")
            print(f"Video ID: {track['video_id']}")
            print(f"Expected filename: {track['expected_filename']}.*")
            print(f"Reason: {entry['reason']}")
            
            candidates = entry.get('candidates', [])
            if candidates:
                print(f"\nPotential matches:")
                for idx, c in enumerate(candidates, 1):
                    print(f"  [{idx}] {Path(c).name}")
            
            print(f"\nOptions:")
            print(f"  [s] Skip - don't assign to this playlist")
            print(f"  [d] Download - download from YouTube")
            if candidates:
                print(f"  [1-{len(candidates)}] Assign to the numbered file")
            print(f"  [p] Enter path manually")
            print(f"  [q] Quit - resolve remaining later")
            
            choice = input("\nChoice: ").strip().lower()
            
            if choice == 'q':
                print("Exiting. Remaining matches saved for later.")
                break
            elif choice == 's':
                self.download_service.resolve_ambiguous_match(
                    track['video_id'], entry['playlist'], None, 'skip'
                )
                print("✓ Skipped")
            elif choice == 'd':
                self.download_service.resolve_ambiguous_match(
                    track['video_id'], entry['playlist'], None, 'download'
                )
                print("✓ Marked for download on next sync")
            elif choice == 'p':
                path = input("Enter file path: ").strip()
                if Path(path).exists():
                    self._assign_track_to_playlist(
                        Path(path), entry['playlist'], track['video_id']
                    )
                    self.download_service.resolve_ambiguous_match(
                        track['video_id'], entry['playlist'], path, 'assign'
                    )
                    print(f"✓ Assigned to {entry['playlist']}")
                else:
                    print(f"✗ File not found: {path}")
            elif choice.isdigit() and candidates:
                idx = int(choice) - 1
                if 0 <= idx < len(candidates):
                    path = candidates[idx]
                    self._assign_track_to_playlist(
                        Path(path), entry['playlist'], track['video_id']
                    )
                    self.download_service.resolve_ambiguous_match(
                        track['video_id'], entry['playlist'], path, 'assign'
                    )
                    print(f"✓ Assigned to {entry['playlist']}")
                else:
                    print("Invalid choice")
            else:
                print("Invalid choice, skipping for now")
        
        self.logging_service.success("\n✅ Ambiguous match resolution complete!")
    
    def _assign_track_to_playlist(self, file_path: Path, playlist_name: str, 
                                   source_id: str = None):
        """Helper to assign a track to a playlist."""
        if not file_path.exists():
            return
        
        # Update file metadata
        self.metadata_service.add_playlist(file_path, playlist_name)
        
        # Update database if available
        if self.database_service:
            track = self.database_service.get_track_by_path(str(file_path))
            if track:
                track.playlists.add(playlist_name)
                self.database_service.upsert_track(track)

