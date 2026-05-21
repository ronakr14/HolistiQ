# querybuilder/mixins/where.py

import itertools
import re
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple, Union


class WhereMixin:
    """
    Optimized mixin for handling WHERE clause operations with improved performance,
    safety features, and enhanced functionality.
    """

    # Expanded operator support with case-insensitive matching
    _allowed_operators = frozenset(
        {
            "=",
            "!=",
            "<>",
            "<",
            ">",
            "<=",
            ">=",
            "LIKE",
            "ILIKE",
            "NOT LIKE",
            "NOT ILIKE",
            "IN",
            "NOT IN",
            "BETWEEN",
            "NOT BETWEEN",
            "IS NULL",
            "IS NOT NULL",
            "REGEXP",
            "NOT REGEXP",
            "RLIKE",
            "SIMILAR TO",
            "NOT SIMILAR TO",
        }
    )

    # Pre-compiled regex for column validation
    _VALID_COLUMN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*$")
    _FUNCTION_PATTERN = re.compile(
        r"^[a-zA-Z_][a-zA-Z0-9_]*\s*\([^)]*\)(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*$"
    )

    def __init__(self):
        # Stack of condition groups with OrderedDict for deterministic ordering
        self._where_groups: List[List[Tuple[str, Dict[str, Any], str]]] = [[]]
        self._param_counter = itertools.count()
        self._group_stack: List[str] = []  # Track group types for better debugging
        self._cached_conditions: Dict[str, Tuple[str, Dict[str, Any]]] = {}

    def where(
        self,
        column: Union[str, Dict[str, Any]],
        operator: Optional[str] = None,
        value: Any = None,
    ) -> "WhereMixin":
        """
        Add a WHERE condition with enhanced flexibility.

        Args:
            column: Column name, function expression, or dict of conditions
            operator: SQL operator (=, !=, <, >, etc.)
            value: Value to compare against

        Returns:
            Self for method chaining

        Examples:
            .where("age", ">", 18)
            .where("name", "LIKE", "%john%")
            .where({"status": "active", "age": [">", 18]})
        """
        if isinstance(column, dict):
            return self._where_dict(column)

        if operator is None:
            raise ValueError("Operator is required when column is a string")

        return self._where_single(column, operator, value, "AND")

    def or_where(
        self,
        column: Union[str, Dict[str, Any]],
        operator: Optional[str] = None,
        value: Any = None,
    ) -> "WhereMixin":
        """
        Add an OR WHERE condition.

        Args:
            column: Column name, function expression, or dict of conditions
            operator: SQL operator
            value: Value to compare against

        Returns:
            Self for method chaining
        """
        if isinstance(column, dict):
            # For dict input with OR, we need to group conditions
            self.begin_group()
            first = True
            for col, val in column.items():
                if isinstance(val, (list, tuple)) and len(val) == 2:
                    op, v = val
                else:
                    op, v = "=", val

                if first:
                    self.where(col, op, v)
                    first = False
                else:
                    self.or_where(col, op, v)
            return self.end_group()

        if operator is None:
            raise ValueError("Operator is required when column is a string")

        return self._where_single(column, operator, value, "OR")

    def where_in(self, column: str, values: List[Any]) -> "WhereMixin":
        """Convenient method for IN conditions."""
        return self.where(column, "IN", values)

    def where_not_in(self, column: str, values: List[Any]) -> "WhereMixin":
        """Convenient method for NOT IN conditions."""
        return self.where(column, "NOT IN", values)

    def where_null(self, column: str) -> "WhereMixin":
        """Convenient method for IS NULL conditions."""
        return self.where(column, "IS NULL")

    def where_not_null(self, column: str) -> "WhereMixin":
        """Convenient method for IS NOT NULL conditions."""
        return self.where(column, "IS NOT NULL")

    def where_between(self, column: str, start: Any, end: Any) -> "WhereMixin":
        """Convenient method for BETWEEN conditions."""
        return self.where(column, "BETWEEN", [start, end])

    def where_like(
        self, column: str, pattern: str, case_sensitive: bool = True
    ) -> "WhereMixin":
        """Convenient method for LIKE conditions."""
        operator = "LIKE" if case_sensitive else "ILIKE"
        return self.where(column, operator, pattern)

    def where_function(
        self, function_expr: str, operator: str, value: Any
    ) -> "WhereMixin":
        """
        Add a function-based WHERE condition with enhanced validation.

        Args:
            function_expr: SQL function expression
            operator: SQL operator
            value: Value to compare against

        Returns:
            Self for method chaining
        """
        self._validate_function_expression(function_expr)
        return self._where_single(function_expr, operator, value, "AND")

    def where_raw(
        self, raw_sql: str, params: Optional[Dict[str, Any]] = None
    ) -> "WhereMixin":
        """
        Add a raw SQL condition with optional parameters.

        Args:
            raw_sql: Raw SQL condition
            params: Optional parameters for the raw SQL

        Returns:
            Self for method chaining
        """
        if not raw_sql or not raw_sql.strip():
            raise ValueError("Raw SQL cannot be empty")

        # Basic validation to prevent obvious SQL injection attempts
        dangerous_keywords = ["drop", "delete", "insert", "update", "create", "alter"]
        raw_lower = raw_sql.lower()
        if any(keyword in raw_lower for keyword in dangerous_keywords):
            raise ValueError(
                f"Potentially dangerous SQL detected in raw condition: {raw_sql}"
            )

        self._add_condition(raw_sql.strip(), params or {}, "AND")
        return self

    def _where_dict(self, conditions: Dict[str, Any]) -> "WhereMixin":
        """Process dictionary of conditions efficiently."""
        for column, value in conditions.items():
            if isinstance(value, (list, tuple)) and len(value) == 2:
                operator, val = value
                self.where(column, operator, val)
            else:
                self.where(column, "=", value)
        return self

    def _where_single(
        self, column: str, operator: str, value: Any, conjunction: str
    ) -> "WhereMixin":
        """Process single WHERE condition with caching."""
        operator = operator.upper()
        if operator not in self._allowed_operators:
            raise ValueError(
                f"Unsupported operator: {operator}. Allowed: {sorted(self._allowed_operators)}"
            )

        # Create cache key for identical conditions
        cache_key = f"{column}::{operator}::{str(value)}"
        if cache_key in self._cached_conditions:
            sql_cond, params = self._cached_conditions[cache_key]
            # Create new params with unique names to avoid conflicts
            new_params = {}
            for param_name, param_value in params.items():
                new_param_name = f"w_{next(self._param_counter)}"
                new_params[new_param_name] = param_value
                sql_cond = sql_cond.replace(f":{param_name}", f":{new_param_name}", 1)
        else:
            sql_cond, params = self._build_condition(column, operator, value)
            # Cache the condition template (without unique param names)
            if len(self._cached_conditions) < 100:  # Limit cache size
                self._cached_conditions[cache_key] = (sql_cond, params)

        self._add_condition(sql_cond, params, conjunction)
        return self

    @contextmanager
    def group(self):
        """
        Context manager for grouping conditions.

        Example:
            with query.group():
                query.where("status", "=", "active")
                query.or_where("status", "=", "pending")
        """
        self.begin_group()
        try:
            yield self
        finally:
            self.end_group()

    def begin_group(self, group_type: str = "standard") -> "WhereMixin":
        """
        Start a new grouped condition with enhanced tracking.

        Args:
            group_type: Type of group for debugging purposes

        Returns:
            Self for method chaining
        """
        self._where_groups.append([])
        self._group_stack.append(group_type)
        return self

    def end_group(self) -> "WhereMixin":
        """
        Close the last group with improved error handling.

        Returns:
            Self for method chaining
        """
        if len(self._where_groups) < 2:
            raise RuntimeError("No group to end. Call begin_group() first.")

        group = self._where_groups.pop()
        # group_type = self._group_stack.pop()

        if not group:
            # Empty group, ignore
            return self

        group_sql, group_params = self._combine_conditions(group)
        # Wrap group in parentheses
        group_sql = f"({group_sql})"
        # Add group condition to previous group with AND by default
        self._add_condition(group_sql, group_params, "AND")
        return self

    def _validate_column_name(self, column: str) -> None:
        """Validate column name for basic security."""
        if not column or not isinstance(column, str):
            raise ValueError("Column name must be a non-empty string")

        column = column.strip()
        if not (
            self._VALID_COLUMN.match(column) or self._FUNCTION_PATTERN.match(column)
        ):
            # Allow some common SQL functions and expressions
            if not any(
                pattern in column.lower() for pattern in ["(", ")", "case", "when"]
            ):
                raise ValueError(f"Invalid column name or expression: {column}")

    def _validate_function_expression(self, function_expr: str) -> None:
        """Validate function expression for basic security."""
        if not function_expr or not function_expr.strip():
            raise ValueError("Function expression cannot be empty")

        # Basic validation - should contain parentheses
        if "(" not in function_expr or ")" not in function_expr:
            raise ValueError("Function expression must contain parentheses")

    def _add_condition(self, sql_cond: str, params: Dict[str, Any], conj: str) -> None:
        """Add condition to current group with parameter conflict detection."""
        group = self._where_groups[-1]

        # Check for parameter conflicts within the same group
        existing_params = set()
        for _, existing_params_dict, _ in group:
            existing_params.update(existing_params_dict.keys())

        param_conflicts = existing_params.intersection(params.keys())
        if param_conflicts:
            raise ValueError(f"Parameter name conflicts detected: {param_conflicts}")

        if group:
            group.append((sql_cond, params, conj))
        else:
            # First condition in group — conjunction is ignored
            group.append((sql_cond, params, "AND"))

    def _build_condition(
        self, col: str, op: str, val: Any
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build parameterized SQL condition with optimized parameter handling.

        Args:
            col: Column name or expression
            op: SQL operator
            val: Value to compare against

        Returns:
            Tuple of (SQL condition, parameters)
        """
        self._validate_column_name(col)

        base_param_name = f"w_{next(self._param_counter)}"
        op = op.upper()

        if op in {"IS NULL", "IS NOT NULL"}:
            return f"{col} {op}", {}

        elif op in {"IN", "NOT IN"}:
            if not isinstance(val, (list, tuple, set)):
                raise ValueError(f"Value for {op} must be a list, tuple, or set")
            if not val:
                # Handle empty IN/NOT IN
                return f"1 = {'0' if op == 'IN' else '1'}", {}

            placeholders = []
            params = {}
            for i, v in enumerate(val):
                param_name = f"{base_param_name}_{i}"
                placeholders.append(f":{param_name}")
                params[param_name] = v

            placeholders_sql = ", ".join(placeholders)
            return f"{col} {op} ({placeholders_sql})", params

        elif op in {"BETWEEN", "NOT BETWEEN"}:
            if not (isinstance(val, (list, tuple)) and len(val) == 2):
                raise ValueError(
                    f"{op} value must be a tuple/list of exactly two elements"
                )

            p1 = f"{base_param_name}_start"
            p2 = f"{base_param_name}_end"
            return f"{col} {op} :{p1} AND :{p2}", {p1: val[0], p2: val[1]}

        else:
            # Standard binary operators
            return f"{col} {op} :{base_param_name}", {base_param_name: val}

    def _combine_conditions(
        self, conditions: List[Tuple[str, Dict[str, Any], str]]
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Combine conditions with optimized parameter merging.

        Args:
            conditions: List of condition tuples

        Returns:
            Tuple of (combined SQL, merged parameters)
        """
        if not conditions:
            return "", {}

        sql_parts = []
        all_params = {}

        for idx, (sql, params, conj) in enumerate(conditions):
            # Add conjunction prefix for all conditions after the first
            if idx > 0:
                sql_parts.append(f" {conj} {sql}")
            else:
                sql_parts.append(sql)

            # Merge parameters with conflict detection
            param_conflicts = set(all_params.keys()).intersection(params.keys())
            if param_conflicts:
                raise ValueError(
                    f"Parameter conflicts in condition combination: {param_conflicts}"
                )

            all_params.update(params)

        combined_sql = "".join(sql_parts)
        return combined_sql, all_params

    def _render_where(self) -> Tuple[str, Dict[str, Any]]:
        """
        Render complete WHERE clause with validation.

        Returns:
            Tuple of (WHERE SQL, parameters)
        """
        if len(self._where_groups) != 1:
            unclosed_groups = len(self._where_groups) - 1
            group_types = (
                self._group_stack[-unclosed_groups:]
                if self._group_stack
                else ["unknown"]
            )
            raise RuntimeError(
                f"Unclosed groups in WHERE clause: {unclosed_groups} groups of types {group_types}. "
                f"Call end_group() {unclosed_groups} time(s)."
            )

        group = self._where_groups[0]
        if not group:
            return "", {}

        where_sql, params = self._combine_conditions(group)
        return f"WHERE {where_sql}", params

    def get_where_info(self) -> Dict[str, Any]:
        """
        Get information about the current WHERE clause state.

        Returns:
            Dictionary with WHERE clause details
        """
        all_conditions = []
        all_params = {}

        for group in self._where_groups:
            for sql, params, conj in group:
                all_conditions.append((sql, conj))
                all_params.update(params)

        return {
            "condition_count": sum(len(group) for group in self._where_groups),
            "group_count": len(self._where_groups),
            "open_groups": len(self._where_groups) - 1,
            "parameter_count": len(all_params),
            "has_conditions": bool(all_conditions),
            "group_stack": self._group_stack.copy(),
            "cache_size": len(self._cached_conditions),
        }

    def reset_where(self) -> None:
        """Reset all WHERE-related state."""
        self._where_groups = [[]]
        self._param_counter = itertools.count()
        self._group_stack.clear()
        self._cached_conditions.clear()
