import re
from typing import Iterator, List, Union


class SelectMixin:
    """
    Optimized mixin for handling SELECT clause operations with improved
    performance, validation, and advanced column handling.
    """

    # Pre-compiled regex for SQL identifier validation
    _VALID_IDENTIFIER = re.compile(
        r"^[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*$"
    )
    _VALID_EXPRESSION = re.compile(r"^[\w\s\(\)\.,\*\+\-\/=<>\'\"]+$")

    def __init__(self):
        self._select_columns: List[str] = []
        self._select_distinct: bool = False
        self._column_aliases: dict[str, str] = {}

    def select(self, *columns: Union[str, List[str], None]) -> "SelectMixin":
        """
        Specify columns to select with enhanced functionality.

        Args:
            *columns: Variable arguments accepting:
                - No arguments (select all: *)
                - Single string column or expression
                - List of columns/expressions
                - Multiple comma-separated columns

        Returns:
            Self for method chaining

        Examples:
            .select()  # SELECT *
            .select("name", "age")  # SELECT name, age
            .select(["name", "age"])  # SELECT name, age
            .select("users.name", "COUNT(*) as total")  # SELECT users.name, COUNT(*) as total
        """
        if not columns:
            self._select_columns = ["*"]
            self._column_aliases.clear()
            return self

        # Flatten and process all column arguments efficiently
        flattened_cols = list(self._flatten_columns(columns))

        # Process columns and extract aliases
        processed_cols = []
        self._column_aliases.clear()

        for col in flattened_cols:
            col = col.strip()
            if not col:
                continue

            # Handle column aliases (e.g., "name AS user_name" or "name user_name")
            alias_match = re.match(r"^(.+?)\s+(?:AS\s+)?(\w+)$", col, re.IGNORECASE)
            if alias_match:
                column_expr, alias = alias_match.groups()
                self._column_aliases[alias] = column_expr.strip()
                processed_cols.append(col)
            else:
                processed_cols.append(col)

        self._select_columns = processed_cols
        return self

    def _flatten_columns(self, columns) -> Iterator[str]:
        """
        Efficiently flatten column arguments into individual column strings.

        Args:
            columns: Mixed column arguments

        Yields:
            Individual column strings
        """
        for col in columns:
            if isinstance(col, str):
                # Handle comma-separated columns in single string
                if "," in col:
                    yield from (c.strip() for c in col.split(","))
                else:
                    yield col
            elif isinstance(col, (list, tuple)):
                # Recursively flatten nested lists/tuples
                yield from self._flatten_columns(col)
            elif col is not None:
                # Convert other types to string
                yield str(col)

    def select_distinct(self, *columns: Union[str, List[str], None]) -> "SelectMixin":
        """
        Select distinct columns.

        Args:
            *columns: Columns to select (same format as select())

        Returns:
            Self for method chaining
        """
        self.select(*columns)
        self._select_distinct = True
        return self

    # def add_column(self, column: str, alias: Optional[str] = None) -> 'SelectMixin':
    #     """
    #     Add a single column to existing selection.

    #     Args:
    #         column: Column name or expression
    #         alias: Optional alias for the column

    #     Returns:
    #         Self for method chaining
    #     """
    #     if not column or not column.strip():
    #         raise ValueError("Column cannot be empty")

    #     # Initialize with * if no columns selected yet
    #     if not self._select_columns or self._select_columns == ["*"]:
    #         self._select_columns = []

    #     formatted_col = column.strip()
    #     if alias:
    #         formatted_col = f"{formatted_col} AS {alias}"
    #         self._column_aliases[alias] = column.strip()

    #     self._select_columns.append(formatted_col)
    #     return self

    # # def remove_column(self, column_or_alias: str) -> 'SelectMixin':
    # #     """
    # #     Remove a column from selection by column name or alias.

    # #     Args:
    # #         column_or_alias: Column name/expression or alias to remove

    # #     Returns:
    # #         Self for method chaining
    # #     """
    # #     if not self._select_columns:
    # #         return self

    #     # Create new list excluding the specified column
    #     new_columns = []
    #     for col in self._select_columns:
    #         col_lower = col.lower()
    #         target_lower = column_or_alias.lower()

    #         # Check if this column should be removed (by name or alias)
    #         should_remove = (
    #             target_lower in col_lower or
    #             any(alias.lower() == target_lower for alias in self._column_aliases.keys())
    #         )

    #         if not should_remove:
    #             new_columns.append(col)

    #     self._select_columns = new_columns

    #     # Clean up aliases
    #     self._column_aliases = {
    #         k: v for k, v in self._column_aliases.items()
    #         if k.lower() != column_or_alias.lower()
    #     }

    #     return self

    # def has_column(self, column_or_alias: str) -> bool:
    #     """
    #     Check if a column or alias exists in the selection.

    #     Args:
    #         column_or_alias: Column name/expression or alias to check

    #     Returns:
    #         True if column exists, False otherwise
    #     """
    #     if not self._select_columns:
    #         return False

    #     target_lower = column_or_alias.lower()

    #     # Check direct column matches
    #     for col in self._select_columns:
    #         if target_lower in col.lower():
    #             return True

    #     # Check alias matches
    #     return any(alias.lower() == target_lower for alias in self._column_aliases.keys())

    # def get_selected_columns(self) -> List[str]:
    #     """
    #     Get a copy of currently selected columns.

    #     Returns:
    #         List of selected columns
    #     """
    #     return self._select_columns.copy()

    # def get_column_aliases(self) -> dict[str, str]:
    #     """
    #     Get a copy of column aliases.

    #     Returns:
    #         Dictionary mapping alias to original column expression
    #     """
    #     return self._column_aliases.copy()

    # def _validate_columns(self, columns: List[str]) -> None:
    #     """
    #     Validate column names and expressions for basic SQL injection protection.

    #     Args:
    #         columns: List of column names/expressions to validate

    #     Raises:
    #         ValueError: If any column contains potentially dangerous content
    #     """
    #     dangerous_patterns = [
    #         'drop', 'delete', 'insert', 'update', 'create', 'alter',
    #         'exec', 'execute', 'sp_', 'xp_'
    #     ]

    #     for col in columns:
    #         col_lower = col.lower()

    #         # Skip validation for wildcard and common functions
    #         if col in ('*', 'COUNT(*)', 'MAX(*)', 'MIN(*)', 'AVG(*)', 'SUM(*)'):
    #             continue

    #         # Check for dangerous keywords
    #         if any(pattern in col_lower for pattern in dangerous_patterns):
    #             raise ValueError(f"Potentially dangerous column expression: {col}")

    def _render_select(self) -> str:
        """
        Render the SELECT clause with optimizations.

        Returns:
            Formatted SELECT SQL clause
        """
        if not self._select_columns:
            return "SELECT *"

        # Use set to track duplicates efficiently for large column lists
        seen = set()
        unique_columns = []

        for col in self._select_columns:
            col_normalized = col.lower().strip()
            if col_normalized not in seen:
                seen.add(col_normalized)
                unique_columns.append(col)

        # Build SELECT clause
        cols_sql = ", ".join(unique_columns)

        if self._select_distinct:
            return f"SELECT DISTINCT {cols_sql}"
        else:
            return f"SELECT {cols_sql}"

    def reset_select(self) -> None:
        """Reset select clause and all related state."""
        self._select_columns.clear()
        self._select_distinct = False
        self._column_aliases.clear()

    # Fix the typo in original reset method
    # def reset(self) -> None:
    #     """Reset select clause (alias for reset_select)."""
    #     self.reset_select()

    # def count(self) -> int:
    #     """
    #     Get the number of selected columns.

    #     Returns:
    #         Number of columns in selection
    #     """
    #     return len(self._select_columns)

    # def is_select_all(self) -> bool:
    #     """
    #     Check if selecting all columns (*).

    #     Returns:
    #         True if selecting all columns, False otherwise
    #     """
    #     return self._select_columns == ["*"] or not self._select_columns

    # def __len__(self) -> int:
    #     """Return the number of selected columns."""
    #     return len(self._select_columns)

    # def __bool__(self) -> bool:
    #     """Return True if there are selected columns."""
    #     return bool(self._select_columns)

    # def __contains__(self, column: str) -> bool:
    #     """Check if a column is in the selection."""
    #     return self.has_column(column)

    # def __iter__(self) -> Iterator[str]:
    #     """Iterate over selected columns."""
    #     return iter(self._select_columns)
