import shutil
from pathlib import Path

class FileSystemService:
    @staticmethod
    def remove_directory(directory: Path):
        """Remove a directory and all its contents"""
        if directory.exists():
            shutil.rmtree(directory)
            return True
        return False

    @staticmethod
    def ensure_directory(directory: Path):
        """Create directory if it doesn't exist"""
        directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def remove_file(file: Path):
        """Remove a single file"""
        if file.exists():
            file.unlink()
            return True
        return False
