import weakref
from typing import Any, Dict, List, Optional, Tuple, Union

from sqlalchemy.engine import Engine

from libs.encryptors.safe_string import SafeConnectionString
from libs.sql_ops.core.executor import QueryExecutor
from libs.sql_ops.querybuilder.insert_mixin import InsertMixin
from libs.sql_ops.querybuilder.select_mixin import SelectMixin
from libs.sql_ops.querybuilder.update_mixin import UpdateMixin
from libs.sql_ops.querybuilder.where_mixin import WhereMixin


class QueryBuilder(SelectMixin, WhereMixin, InsertMixin, UpdateMixin):
    """
    Optimized QueryBuilder with improved performance, caching, and enhanced functionality.
    Combines SELECT, WHERE, INSERT, and UPDATE operations with efficient execution.
    """

    # Class-level cache for compiled SQL templates
    _sql_cache: weakref.WeakValueDictionary = weakref.WeakValueDictionary()

    def __init__(
        self,
        table_name: str,
        db_conn: Union[str, "SafeConnectionString", "Engine"],
        schema: Optional[str] = None,
        as_dataframe: bool = False,
        auto_commit: bool = True,
        query_timeout: Optional[int] = None,
    ):
        # Initialize mixins efficiently
        """
        Initializes the QueryBuilder with the given database connection, pooling settings, and optional settings for dataframe conversion.

        Args:
            table_name (str): Table name.
            db_conn (Union[str, "SafeConnectionString", "Engine"]): Database connection string or a pre-initialized SQLAlchemy Engine.
            schema (Optional[str]): Schema name. Defaults to None.
            as_dataframe (bool, optional): If True, will return query results as pandas DataFrames. Defaults to False.
            auto_commit (bool, optional): If True, will automatically commit queries. Defaults to True.
            query_timeout (Optional[int], optional): Query timeout in seconds. Defaults to None.

        Raises:
            ValueError: If the database connection string is invalid or the engine is not supported.
        """
        SelectMixin.__init__(self)
        WhereMixin.__init__(self)
        InsertMixin.__init__(self)
        UpdateMixin.__init__(self)

        # Validate inputs
        if not table_name or not isinstance(table_name, str):
            raise ValueError("Table name must be a non-empty string")

        # Core attributes
        self._table_name = table_name.strip()
        self._schema = schema.strip() if schema else None
        self._db_conn = db_conn
        self._auto_commit = auto_commit
        self._query_timeout = query_timeout

        # Lazy initialization of executor
        self._executor: Optional[QueryExecutor] = None
        self._as_dataframe = as_dataframe

        # Performance optimizations
        self._full_table_name_cached: Optional[str] = None
        self._last_sql_cache: Optional[Tuple[str, Dict[str, Any]]] = None

        # Query state tracking
        self._query_type: Optional[str] = None
        self._is_dirty = True  # Track if query needs rebuilding

        # Additional features
        self._aliases: Dict[str, str] = {}
        self._joins: List[Tuple[str, str, str]] = []  # (type, table, condition)
        self._order_by: List[str] = []
        self._group_by: List[str] = []
        self._having: List[Tuple[str, Dict[str, Any]]] = []
        self._limit_value: Optional[int] = None
        self._offset_value: Optional[int] = None

    @property
    def executor(self) -> QueryExecutor:
        """Lazy initialization of QueryExecutor."""
        if self._executor is None:
            self._executor = QueryExecutor(
                self._db_conn, as_dataframe=self._as_dataframe
            )
        return self._executor

    def _full_table_name(self) -> str:
        """Get full table name with caching."""
        if self._full_table_name_cached is None:
            if self._schema:
                self._full_table_name_cached = f"{self._schema}.{self._table_name}"
            else:
                self._full_table_name_cached = self._table_name
        return self._full_table_name_cached

    # def alias(self, alias: str) -> 'QueryBuilder':
    #     """
    #     Add table alias for the main table.

    #     Args:
    #         alias: Alias name for the table

    #     Returns:
    #         Self for method chaining
    #     """
    #     self._aliases['main'] = alias
    #     self._invalidate_cache()
    #     return self

    # def join(self, table: str, condition: str, join_type: str = "INNER") -> 'QueryBuilder':
    #     """
    #     Add JOIN clause.

    #     Args:
    #         table: Table name to join
    #         condition: JOIN condition
    #         join_type: Type of join (INNER, LEFT, RIGHT, FULL)

    #     Returns:
    #         Self for method chaining
    #     """
    #     join_type = join_type.upper()
    #     if join_type not in {"INNER", "LEFT", "RIGHT", "FULL", "CROSS"}:
    #         raise ValueError(f"Invalid join type: {join_type}")

    #     self._joins.append((join_type, table, condition))
    #     self._invalidate_cache()
    #     return self

    # def left_join(self, table: str, condition: str) -> 'QueryBuilder':
    #     """Convenient method for LEFT JOIN."""
    #     return self.join(table, condition, "LEFT")

    # def right_join(self, table: str, condition: str) -> 'QueryBuilder':
    #     """Convenient method for RIGHT JOIN."""
    #     return self.join(table, condition, "RIGHT")

    # def order_by(self, column: str, direction: str = "ASC") -> 'QueryBuilder':
    #     """
    #     Add ORDER BY clause.

    #     Args:
    #         column: Column name or expression
    #         direction: Sort direction (ASC or DESC)

    #     Returns:
    #         Self for method chaining
    #     """
    #     direction = direction.upper()
    #     if direction not in {"ASC", "DESC"}:
    #         raise ValueError(f"Invalid order direction: {direction}")

    #     self._order_by.append(f"{column} {direction}")
    #     self._invalidate_cache()
    #     return self

    # def group_by(self, *columns: str) -> 'QueryBuilder':
    #     """
    #     Add GROUP BY clause.

    #     Args:
    #         *columns: Column names to group by

    #     Returns:
    #         Self for method chaining
    #     """
    #     self._group_by.extend(columns)
    #     self._invalidate_cache()
    #     return self

    # def having(self, condition: str, params: Optional[Dict[str, Any]] = None) -> 'QueryBuilder':
    #     """
    #     Add HAVING clause.

    #     Args:
    #         condition: HAVING condition
    #         params: Parameters for the condition

    #     Returns:
    #         Self for method chaining
    #     """
    #     self._having.append((condition, params or {}))
    #     self._invalidate_cache()
    #     return self

    # def limit(self, count: int) -> 'QueryBuilder':
    #     """
    #     Add LIMIT clause.

    #     Args:
    #         count: Maximum number of rows to return

    #     Returns:
    #         Self for method chaining
    #     """
    #     if count < 0:
    #         raise ValueError("LIMIT count must be non-negative")

    #     self._limit_value = count
    #     self._invalidate_cache()
    #     return self

    # def offset(self, count: int) -> 'QueryBuilder':
    #     """
    #     Add OFFSET clause.

    #     Args:
    #         count: Number of rows to skip

    #     Returns:
    #         Self for method chaining
    #     """
    #     if count < 0:
    #         raise ValueError("OFFSET count must be non-negative")

    #     self._offset_value = count
    #     self._invalidate_cache()
    #     return self

    def _invalidate_cache(self) -> None:
        """Mark query as dirty and clear caches."""
        self._is_dirty = True
        self._last_sql_cache = None

    def _determine_query_type(self) -> str:
        """Determine the type of query being built."""
        if hasattr(self, "_insert_data") and (self._insert_data or self._insert_select):
            return "INSERT"
        elif hasattr(self, "_update_values") and self._update_values:
            return "UPDATE"
        else:
            return "SELECT"

    # def _render_joins(self) -> str:
    #     """Render JOIN clauses."""
    #     if not self._joins:
    #         return ""

    #     join_clauses = []
    #     for join_type, table, condition in self._joins:
    #         join_clauses.append(f"{join_type} JOIN {table} ON {condition}")

    #     return " " + " ".join(join_clauses)

    # def _render_order_by(self) -> str:
    #     """Render ORDER BY clause."""
    #     if not self._order_by:
    #         return ""

    #     return f" ORDER BY {', '.join(self._order_by)}"

    # def _render_group_by(self) -> str:
    #     """Render GROUP BY clause."""
    #     if not self._group_by:
    #         return ""

    #     return f" GROUP BY {', '.join(self._group_by)}"

    # def _render_having(self) -> Tuple[str, Dict[str, Any]]:
    #     """Render HAVING clause with parameters."""
    #     if not self._having:
    #         return "", {}

    #     having_conditions = []
    #     all_params = {}

    #     for condition, params in self._having:
    #         having_conditions.append(condition)
    #         all_params.update(params)

    #     having_sql = f" HAVING {' AND '.join(having_conditions)}"
    #     return having_sql, all_params

    # def _render_limit_offset(self) -> str:
    #     """Render LIMIT and OFFSET clauses."""
    #     clauses = []

    #     if self._limit_value is not None:
    #         clauses.append(f"LIMIT {self._limit_value}")

    #     if self._offset_value is not None:
    #         clauses.append(f"OFFSET {self._offset_value}")

    #     return f" {' '.join(clauses)}" if clauses else ""

    def to_sql(self) -> Tuple[str, Dict[str, Any]]:
        """
        Generate SQL query with optimized caching and parameter handling.

        Returns:
            Tuple of (SQL string, parameters dict)
        """
        # Return cached result if available and query hasn't changed
        if not self._is_dirty and self._last_sql_cache:
            return self._last_sql_cache

        query_type = self._determine_query_type()
        self._query_type = query_type

        try:
            if query_type == "INSERT":
                sql, params = self._render_insert_query()
            elif query_type == "UPDATE":
                sql, params = self._render_update_query()
            else:
                sql, params = self._render_select_query()

            # Cache the result
            self._last_sql_cache = (sql, params)
            self._is_dirty = False

            return sql, params

        except Exception as e:
            # Clear cache on error
            self._last_sql_cache = None
            raise RuntimeError(f"Failed to generate {query_type} SQL: {str(e)}") from e

    def _render_insert_query(self) -> Tuple[str, Dict[str, Any]]:
        """Render INSERT query."""
        return self._render_insert(self._full_table_name())

    def _render_update_query(self) -> Tuple[str, Dict[str, Any]]:
        """Render UPDATE query with enhanced parameter handling."""
        where_sql, where_params = self._render_where()

        # Use the optimized update rendering that expects dict parameters
        try:
            return self._render_update(self._full_table_name(), where_sql, where_params)
        except TypeError:
            # Fallback for older UpdateMixin that expects list parameters
            where_params_list = list(where_params.values()) if where_params else []
            return self._render_update(
                self._full_table_name(), where_sql, where_params_list
            )

    def _render_select_query(self) -> Tuple[str, Dict[str, Any]]:
        """Render SELECT query with all clauses."""
        select_sql = self._render_select()

        # Build FROM clause with alias support
        table_name = self._full_table_name()
        if "main" in self._aliases:
            from_sql = f"FROM {table_name} AS {self._aliases['main']}"
        else:
            from_sql = f"FROM {table_name}"

        # Add JOIN clauses
        # joins_sql = self._render_joins()

        # Add WHERE clause
        where_sql, where_params = self._render_where()

        # # Add GROUP BY clause
        # group_by_sql = self._render_group_by()

        # # Add HAVING clause
        # having_sql, having_params = self._render_having()

        # # Add ORDER BY clause
        # order_by_sql = self._render_order_by()

        # # Add LIMIT/OFFSET clauses
        # limit_offset_sql = self._render_limit_offset()

        # Combine all SQL parts
        # sql_parts = [select_sql, from_sql, joins_sql, where_sql, group_by_sql, having_sql, order_by_sql, limit_offset_sql]
        sql_parts = [select_sql, from_sql, where_sql]
        sql = " ".join(part for part in sql_parts if part)

        # Combine all parameters
        all_params = {}
        all_params.update(where_params)
        # all_params.update(having_params)

        return sql, all_params

    def execute(self, *, async_mode: bool = False) -> Any:
        """
        Execute the query with enhanced error handling and features.

        Args:
            async_mode: Whether to execute asynchronously

        Returns:
            Query results
        """
        try:
            sql, params = self.to_sql()
            if async_mode:
                return self.executor.execute_async(sql, params)
            else:
                return self.executor.execute_sync(sql, params)

        except Exception as e:
            query_info = self.get_query_info()
            raise RuntimeError(
                f"Query execution failed for {query_info['query_type']} query on "
                f"table {self._full_table_name()}: {str(e)}"
            ) from e

    # def execute_batch(self, *, async_mode: bool = False) -> List[Any]:
    #     """
    #     Execute query in batches for large INSERT operations.

    #     Args:
    #         async_mode: Whether to execute asynchronously

    #     Returns:
    #         List of batch results
    #     """
    #     if self._determine_query_type() != "INSERT":
    #         raise ValueError("Batch execution is only supported for INSERT queries")

    #     if not hasattr(self, 'render_insert_batched'):
    #         raise ValueError("Batch execution requires optimized InsertMixin")

    #     results = []

    #     try:
    #         for sql, params in self.render_insert_batched(self._full_table_name()):
    #             if async_mode:
    #                 result = self.executor.execute_async(sql, params)
    #             else:
    #                 result = self.executor.execute_sync(sql, params)
    #             results.append(result)

    #         return results

    #     except Exception as e:
    #         raise RuntimeError(f"Batch execution failed: {str(e)}") from e

    def get_query_info(self) -> Dict[str, Any]:
        """
        Get comprehensive information about the query state.

        Returns:
            Dictionary with query information
        """
        base_info = {
            "table_name": self._table_name,
            "schema": self._schema,
            "full_table_name": self._full_table_name(),
            "query_type": self._determine_query_type(),
            "is_dirty": self._is_dirty,
            "has_cached_sql": self._last_sql_cache is not None,
            "as_dataframe": self._as_dataframe,
            "auto_commit": self._auto_commit,
        }

        #     # Add clause information
        base_info.update(
            {
                "has_joins": len(self._joins) > 0,
                "join_count": len(self._joins),
                "has_order_by": len(self._order_by) > 0,
                "has_group_by": len(self._group_by) > 0,
                "has_having": len(self._having) > 0,
                "has_limit": self._limit_value is not None,
                "has_offset": self._offset_value is not None,
                "limit_value": self._limit_value,
                "offset_value": self._offset_value,
            }
        )

        # Add mixin-specific information
        try:
            if hasattr(self, "get_where_info"):
                base_info["where_info"] = self.get_where_info()
        except Exception:
            pass

        try:
            if hasattr(self, "get_update_info"):
                base_info["update_info"] = self.get_update_info()
        except Exception:
            pass

        try:
            if hasattr(self, "get_insert_info"):
                base_info["insert_info"] = self.get_insert_info()
        except Exception:
            pass

        return base_info

    def clone(self) -> "QueryBuilder":
        """
        Create a copy of the QueryBuilder with the same configuration.

        Returns:
            New QueryBuilder instance with same settings
        """
        new_qb = QueryBuilder(
            table_name=self._table_name,
            db_conn=self._db_conn,
            schema=self._schema,
            as_dataframe=self._as_dataframe,
            auto_commit=self._auto_commit,
            query_timeout=self._query_timeout,
        )

        # Copy state (but not the actual query conditions)
        new_qb._aliases = self._aliases.copy()

        return new_qb

    def reset(self) -> "QueryBuilder":
        """
        Reset all query state with comprehensive cleanup.

        Returns:
            Self for method chaining
        """
        # Reset mixin states
        if hasattr(self, "reset_select"):
            self.reset_select()

        if hasattr(self, "reset_where"):
            self.reset_where()

        if hasattr(self, "reset_update"):
            self.reset_update()

        if hasattr(self, "reset_insert"):
            self.reset_insert()

        # Reset additional clauses
        self._joins.clear()
        self._order_by.clear()
        self._group_by.clear()
        self._having.clear()
        self._limit_value = None
        self._offset_value = None
        self._aliases.clear()

        # Reset internal state
        self._invalidate_cache()
        self._query_type = None

        return self

    async def close(self) -> None:
        """Clean up resources asynchronously."""
        if self._executor:
            await self._executor.close()

    def __del__(self):
        """Cleanup resources on deletion."""
        try:
            if self._executor:
                # Attempt cleanup, but don't fail if it doesn't work
                if hasattr(self._executor, "_engine"):
                    self._executor._engine.dispose()
        except Exception:
            pass  # Ignore cleanup errors

    def __str__(self) -> str:
        """Return string representation of the query."""
        try:
            sql, _ = self.to_sql()
            return sql
        except Exception:
            return f"QueryBuilder(table={self._full_table_name()}, type={self._determine_query_type()})"
