from app.results import PlaylistResult, OperationStatus

class PlaylistService:
    def __init__(self, playlist_dir):
        self.playlist_dir = playlist_dir

    def update(self, playlist_name, tracks) -> PlaylistResult:
        m3u = self.playlist_dir / f"{playlist_name}.m3u8"
        existing = set()

        if m3u.exists():
            existing = set(
                line.strip()
                for line in m3u.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith("#")
            )

        with m3u.open("a", encoding="utf-8") as f:
            added_count = 0
            for t in tracks:
                # Get relative path from playlists/ to the music file
                try:
                    rel = "../" + str(t.file.relative_to(self.playlist_dir.parent))
                    # Normalize path separators for cross-platform compatibility
                    rel = rel.replace("\\", "/")
                    if rel not in existing:
                        f.write(rel + "\n")
                        added_count += 1
                except ValueError:
                    # Skip files that can't be made relative
                    pass
        
        return PlaylistResult(
            success=True,
            operation="playlist_updated",
            status=OperationStatus.SUCCESS,
            playlist_name=playlist_name,
            track_count=len(tracks),
            data={"playlist_name": playlist_name, "track_count": len(tracks)}
        )
