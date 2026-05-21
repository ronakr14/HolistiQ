import re
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple, Union


class UpdateMixin:
    """
    Optimized mixin for handling UPDATE operations with improved performance,
    safety features, and parameter management.
    """

    # Pre-compiled regex for column name validation
    _VALID_COLUMN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*$")

    def __init__(self):
        # Use OrderedDict to preserve column order for deterministic SQL
        self._update_values: OrderedDict[str, Any] = OrderedDict()
        self._unsafe_update_allowed: bool = False
        self._conditional_updates: List[Tuple[str, Dict[str, Any]]] = []
        self._update_options: Dict[str, Any] = {}

    def update(
        self, values: Union[Dict[str, Any], str], value: Any = None
    ) -> "UpdateMixin":
        """
        Add update key-value pairs with enhanced functionality.

        Args:
            values: Dictionary of column-value pairs, or single column name
            value: Value for single column (when values is string)

        Returns:
            Self for method chaining

        Examples:
            .update({"name": "John", "age": 30})
            .update("status", "active")
        """
        if isinstance(values, str):
            if value is None:
                raise ValueError(
                    "Value required when specifying single column as string"
                )
            values = {values: value}
        elif not isinstance(values, dict):
            raise TypeError("Values must be dict or column name string")

        if not values:
            raise ValueError("Update values cannot be empty")

        # Validate column names for basic security
        self._validate_columns(list(values.keys()))

        # Update values, preserving order
        for column, val in values.items():
            self._update_values[column] = val

        return self

    def update_if(self, condition: str, values: Dict[str, Any]) -> "UpdateMixin":
        """
        Add conditional update using CASE statements.

        Args:
            condition: SQL condition for the CASE statement
            values: Dictionary of column-value pairs to update if condition is true

        Returns:
            Self for method chaining

        Example:
            .update_if("status = 'pending'", {"processed_at": "NOW()"})
        """
        if not condition or not condition.strip():
            raise ValueError("Condition cannot be empty")
        if not values:
            raise ValueError("Values cannot be empty")

        self._conditional_updates.append((condition.strip(), values))
        return self

    def allow_full_table_update(self, allow: bool = True) -> "UpdateMixin":
        """
        Explicitly allow unsafe full-table updates (no WHERE clause).

        Args:
            allow: Whether to allow full table updates

        Returns:
            Self for method chaining
        """
        self._unsafe_update_allowed = allow
        return self

    def set_option(self, key: str, value: Any) -> "UpdateMixin":
        """
        Set update-specific options (e.g., for different SQL dialects).

        Args:
            key: Option key
            value: Option value

        Returns:
            Self for method chaining
        """
        self._update_options[key] = value
        return self

    def _validate_columns(self, columns: List[str]) -> None:
        """
        Validate column names for basic SQL injection protection.

        Args:
            columns: List of column names to validate

        Raises:
            ValueError: If any column name is invalid
        """
        for column in columns:
            if not column or not isinstance(column, str):
                raise ValueError(f"Column name must be non-empty string: {column}")

            column = column.strip()
            if not self._VALID_COLUMN.match(column):
                raise ValueError(f"Invalid column name: {column}")

    def _generate_set_clauses(
        self, param_prefix: str = "upd"
    ) -> Tuple[List[str], Dict[str, Any]]:
        """
        Generate SET clauses with optimized parameter handling.

        Args:
            param_prefix: Prefix for parameter names

        Returns:
            Tuple of (set_clauses, parameters)
        """
        if not self._update_values:
            raise ValueError("No values provided for update")

        set_clauses = []
        params = {}
        param_counter = 0

        # Process regular updates
        for column, value in self._update_values.items():
            param_name = f"{param_prefix}_{param_counter}"
            set_clauses.append(f"{column} = :{param_name}")
            params[param_name] = value
            param_counter += 1

        # Process conditional updates
        for condition, values in self._conditional_updates:
            for column, value in values.items():
                param_name = f"{param_prefix}_{param_counter}"
                case_expr = (
                    f"CASE WHEN {condition} THEN :{param_name} ELSE {column} END"
                )
                params[param_name] = value
                param_counter += 1

                set_clauses.append(f"{column} = {case_expr}")

        return set_clauses, params

    def _render_update(
        self,
        full_table_name: str,
        where_sql: str = "",
        where_params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Render UPDATE SQL with optimized parameter handling.

        Args:
            full_table_name: Full table name (with schema if needed)
            where_sql: WHERE clause SQL
            where_params: WHERE clause parameters

        Returns:
            Tuple of (SQL, parameters)
        """
        if not self._update_values and not self._conditional_updates:
            raise ValueError("No values provided for update")

        # Generate SET clauses and parameters
        set_clauses, update_params = self._generate_set_clauses()

        if not set_clauses:
            raise ValueError("No valid SET clauses generated")

        set_clause = ", ".join(set_clauses)

        # Safety check for WHERE clause
        has_where = where_sql and where_sql.strip()
        if not has_where and not self._unsafe_update_allowed:
            raise ValueError(
                "Unsafe update detected! WHERE clause is missing. "
                "Use .allow_full_table_update(True) to explicitly allow full table updates."
            )

        # Build SQL
        sql_parts = [f"UPDATE {full_table_name}", f"SET {set_clause}"]

        if has_where:
            sql_parts.append(where_sql)

        sql = " ".join(sql_parts)

        # Combine parameters (update params + where params)
        all_params = update_params.copy()
        if where_params:
            # Check for parameter name conflicts
            conflicts = set(all_params.keys()) & set(where_params.keys())
            if conflicts:
                raise ValueError(f"Parameter name conflicts detected: {conflicts}")
            all_params.update(where_params)

        return sql, all_params

    def get_update_info(self) -> Dict[str, Any]:
        """
        Get information about the current update operation.

        Returns:
            Dictionary with update operation details
        """
        return {
            "column_count": len(self._update_values),
            "columns": list(self._update_values.keys()),
            "has_conditional_updates": len(self._conditional_updates) > 0,
            "conditional_update_count": len(self._conditional_updates),
            "unsafe_update_allowed": self._unsafe_update_allowed,
            "options": self._update_options.copy(),
        }

    def reset_update(self) -> None:
        """Reset all update-related state."""
        self._update_values.clear()
        self._conditional_updates.clear()
        self._unsafe_update_allowed = False
        self._update_options.clear()
