"""
Result objects for service operations.
"""
from dataclasses import dataclass
from typing import Any, Optional
from enum import Enum


class OperationStatus(Enum):
    """Status codes for operations."""
    SUCCESS = "success"
    FAILED = "failed"
    NOT_FOUND = "not_found"
    SKIPPED = "skipped"


@dataclass
class OperationResult:
    """Generic result object for service operations."""
    success: bool
    operation: str
    status: OperationStatus
    data: Optional[dict] = None
    error: Optional[str] = None
    
    @classmethod
    def success_result(cls, operation: str, data: dict = None):
        """Create a successful result."""
        return cls(
            success=True,
            operation=operation,
            status=OperationStatus.SUCCESS,
            data=data or {}
        )
    
    @classmethod
    def failed_result(cls, operation: str, error: str, data: dict = None):
        """Create a failed result."""
        return cls(
            success=False,
            operation=operation,
            status=OperationStatus.FAILED,
            error=error,
            data=data or {}
        )
    
    @classmethod
    def not_found_result(cls, operation: str, data: dict = None):
        """Create a not found result."""
        return cls(
            success=False,
            operation=operation,
            status=OperationStatus.NOT_FOUND,
            data=data or {}
        )


@dataclass
class DownloadResult(OperationResult):
    """Result for download operations."""
    playlist_name: Optional[str] = None


@dataclass
class CleanupResult(OperationResult):
    """Result for cleanup operations."""
    cleanup_type: Optional[str] = None
    path: Optional[str] = None


@dataclass
class PlaylistResult(OperationResult):
    """Result for playlist operations."""
    playlist_name: Optional[str] = None
    track_count: int = 0
