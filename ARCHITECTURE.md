# Architecture Documentation

## Overview

This project implements a **clean, service-oriented architecture** with dependency injection and result-based communication. The design prioritizes maintainability, testability, and separation of concerns.

## Design Principles

### 1. **Dependency Injection**
Services receive their dependencies through constructors rather than creating them internally.

**Benefits:**
- Easy to test (inject mocks)
- Flexible (swap implementations)
- Clear dependencies (visible in constructor)

### 2. **Result Objects Over Exceptions**
Services return structured result objects instead of throwing exceptions or logging directly.

```python
@dataclass
class OperationResult:
    success: bool
    operation: str
    status: OperationStatus
    data: Optional[dict] = None
    error: Optional[str] = None
```

**Benefits:**
- Caller decides how to handle results
- No hidden control flow (no exceptions)
- Easy to test (assert on result properties)
- Structured error information

### 3. **Separation of Concerns**

**Business Logic vs. Presentation:**
- Services contain **what** to do (business logic)
- Logging contains **how** to display it (presentation)

```python
# Service: Returns structured data
def clear_archive(self) -> CleanupResult:
    if self.filesystem.remove_file(self.archive_file):
        return CleanupResult(
            success=True,
            operation="clear_archive",
            status=OperationStatus.SUCCESS,
            data={"path": str(self.archive_file)}
        )

# Orchestrator: Decides what to log
result = cleanup.clear_archive()
logging.log_result(result)  # "✅ Cleared archive: /path/to/archive.txt"
```

### 4. **Single Responsibility Principle**
Each service has one clear purpose:

| Service | Responsibility |
|---------|---------------|
| `DatabaseService` | SQLite database for fast track lookups and deduplication |
| `DownloadService` | Download tracks via yt-dlp, filename matching |
| `LibraryService` | Discover audio files in library |
| `PlaylistService` | Generate `.m3u8` playlist files from database |
| `MetadataService` | Embed playlist tags and source IDs in audio files |
| `CleanupService` | Delete archives/downloads/playlists |
| `FileSystemService` | File/directory operations |
| `LoggingService` | Format and display messages |

## Architecture Layers

```
┌─────────────────────────────────────┐
│         CLI (main.py)               │  ← User interface
├─────────────────────────────────────┤
│      Orchestrator                   │  ← Workflow coordination
├─────────────────────────────────────┤
│      Service Container              │  ← Dependency injection
├─────────────────────────────────────┤
│      Services                       │  ← Business logic
│  ┌──────────┬──────────┬────────┐   │
│  │ Download │ Library  │ etc... │   │
│  └──────────┴──────────┴────────┘   │
├─────────────────────────────────────┤
│      Results                        │  ← Data transfer objects
├─────────────────────────────────────┤
│      Models & Config                │  ← Domain entities
└─────────────────────────────────────┘
```

### Layer Responsibilities

#### **1. CLI Layer (`main.py`)**
- Parses command-line arguments
- Creates service container
- Delegates to orchestrator
- Displays results via logging service

#### **2. Orchestration Layer (`orchestrator.py`)**
- Coordinates workflow between services
- Handles service results
- Decides success/failure of operations
- Controls execution flow

#### **3. Service Container (`container.py`)**
- Manages service instances
- Resolves dependencies
- Provides service lookup

#### **4. Service Layer**
- Implements business logic
- Returns result objects
- No UI dependencies
- Pure, testable functions

#### **5. Result Layer (`results.py`)**
- Defines operation outcomes
- Structured data transfer
- Status enumerations

#### **6. Domain Layer (`models.py`, `config.py`)**
- Domain entities (Track, Playlist)
- Configuration loading

## Key Components

### ServiceContainer

**Purpose:** Central registry for all services with dependency injection.

```python
class ServiceContainer:
    def __init__(self, config: Config):
        self.config = config
        self._services = {}
        self._initialize_services()
    
    def get(self, service_name: str):
        return self._services[service_name]
```

**Usage:**
```python
container = ServiceContainer(config)
download_service = container.get('download')
```

### SyncOrchestrator

**Purpose:** Coordinates the sync workflow.

```python
class SyncOrchestrator:
    def sync_single_playlist(self, url: str) -> DownloadResult:
        # 1. Get playlist name
        playlist_name, error = self.download_service.get_playlist_name(url)
        
        # 2. Download tracks
        download_result = self.download_service.fetch(url)
        if not download_result.success:
            return download_result  # Early exit on failure
        
        # 3. Update metadata
        tracks = list(self.library_service.all_tracks())
        for track in tracks:
            self.metadata_service.add_playlist(track.file, playlist_name)
        
        # 4. Generate playlist
        playlist_result = self.playlist_service.update(playlist_name, tracks)
        
        # 5. Cleanup
        self._cleanup_temp_directory()
        
        return download_result
```

**Responsibilities:**
- Call services in correct order
- Handle service results
- Decide whether to continue or abort
- Log progress

### Result Objects

**Purpose:** Structured communication between layers.

```python
@dataclass
class DownloadResult(OperationResult):
    playlist_name: Optional[str] = None

# Service returns result
result = DownloadResult(
    success=True,
    operation="download",
    status=OperationStatus.SUCCESS,
    data={"url": playlist_url}
)

# Orchestrator checks result
if not result.success:
    logging.error(f"Failed: {result.error}")
    return result
```

### LoggingService

**Purpose:** Centralized message formatting and display.

**Features:**
- Message templates dictionary
- Format messages with variables
- Interpret result objects
- Consistent emoji formatting

```python
MESSAGES = {
    'clear_archive_success': "Cleared archive: {path}",
    'sync_complete': "Sync complete",
}

# Format and log
message = LoggingService._format_message('sync_complete')
LoggingService.success(message)

# Or log result object directly
LoggingService.log_result(result)
```

## Data Flow

### Sync Workflow

```
User runs: python main.py sync
         ↓
    main.py creates ServiceContainer
         ↓
    Creates SyncOrchestrator
         ↓
    orchestrator.sync_all_playlists()
         ↓
    For each playlist URL:
         ↓
    ├── get_playlist_name() → (name, error)
    ├── fetch() → DownloadResult
    ├── all_tracks() → [Track, Track, ...]
    ├── add_playlist() for each track
    ├── update() → PlaylistResult
    └── cleanup_temp_directory()
         ↓
    Check all results
         ↓
    Log final status
```

### Result Flow

```
Service Layer          Orchestrator Layer       CLI Layer
─────────────          ──────────────────       ─────────
                              
download() ──Result──→ Check success ──Result──→ Log result
                       └─ If failed: early exit
                       └─ If success: continue
```

## Design Patterns

### 1. **Dependency Injection Pattern**
Services receive dependencies via constructor.

### 2. **Service Locator Pattern**
`ServiceContainer` provides centralized service lookup.

### 3. **Orchestrator Pattern**
`SyncOrchestrator` coordinates workflow without implementing business logic.

### 4. **Result Object Pattern**
Services return structured results instead of exceptions.

### 5. **Strategy Pattern**
File system operations abstracted behind `FileSystemService`.

## Extension Points

### Adding a New Service

1. **Define the service:**
```python
class NewService:
    def __init__(self, dependency1, dependency2):
        self.dep1 = dependency1
        self.dep2 = dependency2
    
    def do_something(self) -> OperationResult:
        # Implementation
        return OperationResult.success_result("new_operation")
```

2. **Register in container:**
```python
self._services['new'] = NewService(
    dependency1=self.get('dependency1'),
    dependency2=self.get('dependency2')
)
```

3. **Use in orchestrator:**
```python
new_service = self.container.get('new')
result = new_service.do_something()
self.logging_service.log_result(result)
```

### Adding a New Operation Result

```python
@dataclass
class NewResult(OperationResult):
    custom_field: str
    item_count: int
```

### Adding Message Templates

```python
# In LoggingService.MESSAGES
'new_operation_success': "Operation completed: {custom_field} ({item_count} items)",
```

## Benefits of This Architecture

✅ **Maintainability** - Clear separation makes changes isolated  
✅ **Flexibility** - Easy to swap implementations  
✅ **Debuggability** - Linear flow, no hidden control paths  
✅ **Scalability** - Add services without touching existing code  
✅ **Type Safety** - Strong typing with result objects  
✅ **Documentation** - Architecture is self-documenting  

## Trade-offs

### Advantages
- Clean, maintainable code
- Clear dependencies
- Flexible and extensible

### Disadvantages
- More files and classes (boilerplate)
- Overkill for very simple scripts
- Learning curve for contributors

**Verdict:** The architectural complexity is justified for this project's scope and future extensibility needs.

## Future Improvements

Potential enhancements while maintaining architecture:

1. **Event System** - Add event bus for cross-cutting concerns (metrics, webhooks)
2. **Configuration Validation** - Add validation service for config files
3. **Retry Logic** - Add retry decorator for download operations
4. **Progress Tracking** - Add progress reporting service
5. **Async Operations** - Add async support for parallel downloads

All can be added as new services without modifying existing code.

## Recent Architecture Changes

### Database-First Approach (Implemented)
- Added `DatabaseService` with SQLite backend for fast lookups
- Tracks identified by source IDs (e.g., `youtube:dQw4w9WgXcQ`)
- Database is a cache - can be rebuilt from file metadata
- Enables fast playlist membership queries

### Source ID Deduplication
- Primary deduplication via source IDs instead of filename matching
- Source IDs stored in file metadata (`purl` tag)
- Prevents false positives from fuzzy filename matching

### Confirmation Prompts
- Destructive operations (`clear-all`, `clear-db`, `verify --fix`) require user confirmation
- Prevents accidental data loss
