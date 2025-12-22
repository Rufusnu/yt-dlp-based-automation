from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Track:
    id: str
    file: Path
