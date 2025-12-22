class LoggingService:
    @staticmethod
    def info(message: str):
        """Print informational message"""
        print(f"ℹ️  {message}")

    @staticmethod
    def success(message: str):
        """Print success message"""
        print(f"✅ {message}")

    @staticmethod
    def warning(message: str):
        """Print warning message"""
        print(f"⚠️  {message}")

    @staticmethod
    def error(message: str):
        """Print error message"""
        print(f"❌ {message}")

    @staticmethod
    def progress(message: str):
        """Print progress message"""
        print(f"▶ {message}")

    @staticmethod
    def cleanup(message: str):
        """Print cleanup message"""
        print(f"🗑️  {message}")
