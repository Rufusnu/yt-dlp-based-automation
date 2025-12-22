class ArchiveService:
    def __init__(self, archive_file):
        self.archive_file = archive_file
        self.archive_file.touch(exist_ok=True)
