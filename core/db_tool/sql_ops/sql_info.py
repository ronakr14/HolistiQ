from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass
class SQLInfo:
    query: str
    file_path: Optional[str]
    query_index: Optional[str]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    success: bool
    rows_affected: Optional[int]
    result_data: Optional[list[dict[str, Any]]]
    error_message: Optional[str]
    execution_time_ms: Optional[float]

    @property
    def duration_ms(self) -> Optional[float]:

        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return self.execution_time_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": str(self.file_path),
            "query_index": self.query_index,
            "query_preview": (
                self.query[:100] + "..." if len(self.query) > 100 else self.query
            ),
            "success": self.success,
            "rows_affected": self.rows_affected,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message,
            "timestamp": self.start_time.isoformat() if self.start_time else None,
        }
