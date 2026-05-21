import weakref
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

from libs.utils.row_col_utils import columns_to_rows


class InsertMixin:
    """
    Optimized mixin for handling INSERT operations with improved memory usage
    and performance for large datasets.
    """

    # Class-level cache for SQL templates to avoid regenerating identical queries
    _sql_template_cache: weakref.WeakValueDictionary = weakref.WeakValueDictionary()

    def __init__(self):
        """
        Initialize InsertMixin with default values.

        Attributes:
            _insert_data: Optional[List[dict[str, Any]]]
                Insert data as a list of dictionaries.
            _insert_select: Optional[Tuple[str, dict[str, Any]]]
                Insert data as a tuple of (SQL, parameters) for INSERT FROM SELECT.
            _insert_columns: Optional[List[str]]
                Insert columns as a list of strings.
            _batch_size: int
                Default batch size for large inserts.
        """
        self._insert_data: Optional[List[Dict[str, Any]]] = None
        self._insert_select: Optional[Tuple[str, Dict[str, Any]]] = None
        self._insert_columns: Optional[List[str]] = None
        self._batch_size: int = 1000  # Default batch size for large inserts

    def insert(self, data: Dict[str, Any]) -> "InsertMixin":
        """
        Prepare single-row insert data.

        Args:
            data: Dictionary containing column-value pairs

        Returns:
            Self for method chaining
        """
        if not data:
            raise ValueError("Insert data cannot be empty")

        self._insert_data = [data]
        self._insert_select = None
        self._insert_columns = list(data.keys())
        return self

    def batch_insert(
        self,
        data: Union[List[Dict[str, Any]], Dict[str, List[Any]]],
        batch_size: Optional[int] = None,
    ) -> "InsertMixin":
        """
        Prepare multi-row insert data with optimized handling for large datasets.

        Args:
            data: List of dicts or dict of lists containing insert data
            batch_size: Optional batch size for processing large datasets

        Returns:
            Self for method chaining
        """
        if not data:
            raise ValueError("batch_insert data cannot be empty")

        # Convert columnar format to row format if needed
        if isinstance(data, dict):
            data = columns_to_rows(data=data)

        if not isinstance(data, list) or not data:
            raise ValueError("batch_insert requires non-empty list of dictionaries")

        # Validate that all rows have the same columns for consistency
        first_keys = set(data[0].keys())
        if not all(set(row.keys()) == first_keys for row in data[1:]):
            raise ValueError("All rows in batch_insert must have the same columns")

        self._insert_data = data
        self._insert_select = None
        self._insert_columns = list(data[0].keys())

        if batch_size:
            self._batch_size = batch_size

        return self

    def insert_from_select(self, select_qb) -> "InsertMixin":
        """
        Prepare insert from select query with validation.

        Args:
            select_qb: QueryBuilder instance or compatible object with to_sql() method

        Returns:
            Self for method chaining
        """
        if not hasattr(select_qb, "to_sql"):
            raise ValueError("select_qb must have a to_sql() method")

        try:
            sql, params = select_qb.to_sql()
        except Exception as e:
            raise ValueError(f"Failed to generate SQL from select_qb: {e}")

        if not sql.strip():
            raise ValueError("Generated SQL cannot be empty")

        self._insert_select = (sql, params)
        self._insert_data = None
        self._insert_columns = None
        return self

    def _generate_batch_params(
        self, rows: List[Dict[str, Any]], start_idx: int = 0
    ) -> Dict[str, Any]:
        """
        Generate parameters for batch insert with optimized parameter naming.

        Args:
            rows: List of row dictionaries
            start_idx: Starting index for parameter naming

        Returns:
            Dictionary of parameters
        """
        params = {}
        for row_idx, row in enumerate(rows, start_idx):
            for col in self._insert_columns:  # type: ignore
                param_name = f"i_{col}_{row_idx}"
                params[param_name] = row.get(col)  # Use get() for safer access
        return params

    def _generate_values_clause(self, num_rows: int, start_idx: int = 0) -> str:
        """
        Generate VALUES clause for INSERT statement.

        Args:
            num_rows: Number of rows to generate placeholders for
            start_idx: Starting index for parameter naming

        Returns:
            VALUES clause string
        """
        # Create template for single row placeholders
        single_row_template = (
            "("
            + ", ".join(f":i_{col}_{{row_idx}}" for col in self._insert_columns)
            + ")"
        )

        # Generate all row placeholders
        values_parts = [
            single_row_template.format(row_idx=row_idx)
            for row_idx in range(start_idx, start_idx + num_rows)
        ]

        return ", ".join(values_parts)

    def _render_insert_batched(
        self, table_name: str
    ) -> Iterator[Tuple[str, Dict[str, Any]]]:
        """
        Render insert SQL and params in batches for memory efficiency.

        Args:
            table_name: Name of the target table

        Yields:
            Tuples of (SQL, params) for each batch
        """
        if not self._insert_data or not self._insert_columns:
            raise RuntimeError("No insert data found")

        columns_sql = ", ".join(self._insert_columns)

        # Process data in batches to manage memory usage
        total_rows = len(self._insert_data)

        for i in range(0, total_rows, self._batch_size):
            batch_end = min(i + self._batch_size, total_rows)
            batch_data = self._insert_data[i:batch_end]
            batch_size = len(batch_data)

            # Generate SQL for this batch
            values_sql = self._generate_values_clause(batch_size, i)
            insert_sql = f"INSERT INTO {table_name} ({columns_sql}) VALUES {values_sql}"

            # Generate parameters for this batch
            params = self._generate_batch_params(batch_data, i)

            yield insert_sql, params

    def _render_insert(self, table_name: str) -> Tuple[str, Dict[str, Any]]:
        """
        Render insert SQL and params with optimizations.

        Args:
            table_name: Name of the target table

        Returns:
            Tuple of (SQL, parameters)
        """
        # Handle INSERT FROM SELECT
        if self._insert_select:
            sql, params = self._insert_select
            insert_sql = f"INSERT INTO {table_name} {sql}"
            return insert_sql, params or {}

        if not self._insert_data or not self._insert_columns:
            raise RuntimeError("No insert data found")

        # For small datasets, generate single SQL statement
        if len(self._insert_data) <= self._batch_size:
            columns_sql = ", ".join(self._insert_columns)
            values_sql = self._generate_values_clause(len(self._insert_data))
            insert_sql = f"INSERT INTO {table_name} ({columns_sql}) VALUES {values_sql}"
            params = self._generate_batch_params(self._insert_data)
            return insert_sql, params
        else:
            # For large datasets, caller should use render_insert_batched
            raise RuntimeError(
                f"Dataset too large ({len(self._insert_data)} rows). "
                f"Use render_insert_batched() for datasets larger than {self._batch_size} rows"
            )

    def render_insert_batched(
        self, table_name: str
    ) -> Iterator[Tuple[str, Dict[str, Any]]]:
        """
        Public method to render insert in batches for large datasets.

        Args:
            table_name: Name of the target table

        Yields:
            Tuples of (SQL, params) for each batch
        """
        yield from self._render_insert_batched(table_name)

    def get_insert_info(self) -> Dict[str, Any]:
        """
        Get information about the current insert operation.

        Returns:
            Dictionary with insert operation details
        """
        info = {
            "has_data": self._insert_data is not None,
            "has_select": self._insert_select is not None,
            "columns": self._insert_columns[:] if self._insert_columns else None,
            "row_count": len(self._insert_data) if self._insert_data else 0,
            "batch_size": self._batch_size,
        }

        if self._insert_data:
            info["requires_batching"] = len(self._insert_data) > self._batch_size

        return info

    def set_batch_size(self, batch_size: int) -> "InsertMixin":
        """
        Set the batch size for large insert operations.

        Args:
            batch_size: Number of rows per batch

        Returns:
            Self for method chaining
        """
        if batch_size <= 0:
            raise ValueError("Batch size must be positive")

        self._batch_size = batch_size
        return self

    def reset_insert(self) -> None:
        """Reset all insert-related state."""
        self._insert_data = None
        self._insert_select = None
        self._insert_columns = None
