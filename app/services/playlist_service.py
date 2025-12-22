class PlaylistService:
    def __init__(self, playlist_dir):
        self.playlist_dir = playlist_dir

    def update(self, playlist_name, tracks):
        m3u = self.playlist_dir / f"{playlist_name}.m3u8"
        existing = set()

        if m3u.exists():
            existing = set(
                line.strip()
                for line in m3u.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )

        with m3u.open("a", encoding="utf-8") as f:
            for t in tracks:
                rel = f"../music/{t.file.name}"
                if rel not in existing:
                    f.write(rel + "\n")
