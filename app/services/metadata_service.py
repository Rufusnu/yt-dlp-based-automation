from mutagen.oggopus import OggOpus

class MetadataService:
    def __init__(self):
        pass
    
    def add_playlist(self, file, playlist_name):
        try:
            audio = OggOpus(file)
        except Exception:
            return

        tags = audio.tags or {}
        comments = tags.get("comment", [])

        if playlist_name not in comments:
            comments.append(playlist_name)
            tags["comment"] = comments
            audio.save()
