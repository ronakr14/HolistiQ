# querybuilder/core/execute.py

import asyncio
import logging
import time
from functools import wraps
from typing import Optional, Union

import pandas as pd
import sqlalchemy
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from libs.encryptors.safe_string import SafeConnectionString
from libs.sql_ops.core.normalize_sql import normalize_sql

logger = logging.getLogger(__name__)


# Optimized retry decorator with exponential backoff and jitter
def with_execution_retry(
    retries: int = 3, delay: float = 0.5, backoff: float = 2, max_delay: float = 30.0
):
    """
    Retry decorator with exponential backoff and jitter to prevent thundering herd.

    Args:
        retries: Number of retry attempts
        delay: Initial delay between retries
        backoff: Backoff multiplier
        max_delay: Maximum delay to prevent excessive waiting
    """

    def decorator(func):
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                import random

                _delay = delay
                last_exception = None

                for attempt in range(retries + 1):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        if attempt == retries:  # Last attempt
                            raise

                        # Add jitter to prevent thundering herd
                        jitter = random.uniform(0.1, 0.3) * _delay
                        sleep_time = min(_delay + jitter, max_delay)
                        await asyncio.sleep(sleep_time)
                        _delay *= backoff

                if last_exception is not None:
                    raise last_exception  # Should never reach here
                else:
                    raise Exception("Unknown error occurred during retry attempts.")

            return async_wrapper
        else:

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                import random

                _delay = delay
                last_exception = None

                for attempt in range(retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        if attempt == retries:  # Last attempt
                            raise

                        # Add jitter to prevent thundering herd
                        jitter = random.uniform(0.1, 0.3) * _delay
                        sleep_time = min(_delay + jitter, max_delay)
                        time.sleep(sleep_time)
                        _delay *= backoff

                if last_exception is not None:
                    raise last_exception  # Should never reach here
                else:
                    raise Exception("Unknown error occurred during retry attempts.")

            return sync_wrapper

    return decorator


class QueryExecutor:
    """
    Optimized query executor with connection pooling and improved performance.
    """

    def __init__(
        self,
        db_conn: Union[str, "SafeConnectionString", Engine],
        as_dataframe: bool = False,
        pool_size: int = 10,
        max_overflow: int = 20,
    ):
        """
        Initializes the QueryExecutor with the given database connection, pooling settings, and optional settings for dataframe conversion.

        Args:
            db_conn (Union[str, "SafeConnectionString", Engine]): Database connection string or a pre-initialized SQLAlchemy Engine.
            as_dataframe (bool, optional): If True, will return query results as pandas DataFrames. Defaults to False.
            pool_size (int, optional): The size of the database connection pool. Defaults to 10.
            max_overflow (int, optional): The maximum number of connections to allow in the pool before raising an error. Defaults to 20.

        Raises:
            ValueError: If the database connection string is invalid or the engine is not supported.
        """
        self._engine = self._resolve_engine(db_conn, pool_size, max_overflow)
        self._async_engine: Optional[AsyncEngine] = None
        self._as_dataframe = as_dataframe

    @property
    def db_engine(self):
        """Database engine with optimized connection pooling settings.

        Returns:
            Engine: The underlying database engine.
        """
        logger.debug("Accessing db_engine")
        return self._engine

    def _resolve_engine(self, db_conn, pool_size: int, max_overflow: int) -> Engine:
        """
        Resolves the database engine from the given connection configuration.

        Args:
            db_conn (Union[str, "SafeConnectionString", Engine]): Database connection string or a pre-initialized SQLAlchemy Engine.
            pool_size (int): The size of the database connection pool.
            max_overflow (int): The maximum number of connections to allow in the pool before raising an error.

        Returns:
            Engine: The underlying database engine.

        Raises:
            ValueError: If the database connection string is invalid or the engine is not supported.
        """
        engine_kwargs = {
            "pool_size": pool_size,
            "max_overflow": max_overflow,
            "pool_pre_ping": True,  # Validates connections before use
            "pool_recycle": 3600,  # Recycle connections after 1 hour
        }

        if isinstance(db_conn, str):
            return sqlalchemy.create_engine(db_conn, **engine_kwargs)
        if hasattr(db_conn, "url"):
            return sqlalchemy.create_engine(db_conn.url, **engine_kwargs)
        if isinstance(db_conn, Engine):
            return db_conn
        raise ValueError(f"Unsupported connection type: {type(db_conn)}")

    @property
    def async_engine(self) -> AsyncEngine:
        """
        Asynchronous database engine with optimized connection pooling settings.

        Returns:
            AsyncEngine: The underlying asynchronous database engine.

        Notes:
            The async engine is created lazily by converting the sync URL to an async URL.
            The pool size, max overflow, pool pre-ping, and pool recycle settings are inherited from the sync engine.
        """
        if not self._async_engine:
            # Convert sync URL to async URL
            url = str(self._engine.url)
            async_map = {
                "sqlite:": "sqlite+aiosqlite:",
                "postgresql:": "postgresql+asyncpg:",
                # "mysql:": "mysql+aiomysql:",
            }
            for sync_prefix, async_prefix in async_map.items():
                if url.startswith(sync_prefix):
                    url = url.replace(sync_prefix, async_prefix)
                    break

            self._async_engine = create_async_engine(
                url,
                pool_size=self._engine.pool.size(),  # type: ignore
                max_overflow=self._engine.pool.overflow(),  # type: ignore
                pool_pre_ping=True,
                pool_recycle=3600,
            )
        return self._async_engine

    def _is_select(self, query: str) -> bool:
        """Determines if a query is a SELECT query.

        Args:
            query (str): SQL query to check.

        Returns:
            bool: True if the query is a SELECT query, False otherwise.
        """
        return query.strip().lower().startswith(("select", "with", "(select"))

    def _log_query(self, query: str, params: Optional[dict], async_mode: bool = False):
        """Logs a query and its parameters.

        Args:
            query (str): SQL query to log.
            params (Optional[dict]): Parameters to log.
            async_mode (bool, optional): Whether the query is executed asynchronously. Defaults to False.

        Notes:
            The query is truncated to 200 characters and an ellipsis is added if the query is longer than 200 characters.
            The parameters are masked if they are strings longer than 20 characters.
        """
        if not logger.isEnabledFor(logging.DEBUG):
            return
        mode = "async" if async_mode else "sync"

        logger.debug(
            f"Executing Query ({mode}): {query[:200]}{'...' if len(query) > 200 else ''}"
        )
        if params:
            masked_params = {
                k: "***" if isinstance(v, str) and len(str(v)) > 20 else v
                for k, v in params.items()
            }
            logger.debug(f"Params: {masked_params}")

    def _process_rows(self, rows: list[dict]) -> Union[pd.DataFrame, list[dict]]:
        """
        Process query results into a DataFrame or list of dictionaries.

        Args:
            rows (list[dict]): Query results

        Returns:
            Union[pd.DataFrame, list[dict]]: DataFrame if self._as_dataframe is True, list of dictionaries otherwise
        """
        if not rows:
            return pd.DataFrame() if self._as_dataframe else []
        return pd.DataFrame.from_records(rows) if self._as_dataframe else rows

    @with_execution_retry(retries=3, delay=0.5, backoff=2, max_delay=30.0)
    def execute_sync(
        self, query: str, params: Optional[dict] = None
    ) -> Union[pd.DataFrame, list[dict], int]:
        """
        Execute query synchronously with optimized connection handling.

        Args:
            query: SQL query to execute
            params: Query parameters

        Returns:
            DataFrame/list for SELECT queries, rowcount for others
        """
        self._log_query(query, params)
        query = normalize_sql(sql=query, dialect=self._engine.dialect.name.lower())

        with self._engine.begin() as conn:
            result = conn.execute(text(query), params or {})
            return (
                self._process_rows(result.mappings().all())
                if self._is_select(query)
                else result.rowcount
            )

    @with_execution_retry(retries=3, delay=0.5, backoff=2, max_delay=30.0)
    async def execute_async(
        self, query: str, params: Optional[dict] = None
    ) -> Union[pd.DataFrame, list[dict], int]:
        """
        Execute query asynchronously with optimized connection handling.

        Args:
            query: SQL query to execute
            params: Query parameters

        Returns:
            DataFrame/list for SELECT queries, rowcount for others
        """
        self._log_query(query, params, async_mode=True)

        query = normalize_sql(sql=query, dialect=self._engine.dialect.name.lower())

        async with self.async_engine.begin() as conn:
            result = await conn.execute(text(query), params or {})
            return (
                self._process_rows(result.mappings().all())
                if self._is_select(query)
                else result.rowcount
            )

    def execute_batch_sync(
        self, queries: list[tuple]
    ) -> list[Union[pd.DataFrame, list[dict], int]]:
        """
        Execute multiple queries in a single transaction synchronously.

        Args:
            queries: list of (query, params) tuples

        Returns:
            list of results for each query
        """
        results = []

        with self._engine.begin() as conn:
            for query, params in queries:
                self._log_query(query, params)
                result = conn.execute(text(query), params or {})
                results.append(
                    self._process_rows(result.mappings().all())
                    if self._is_select(query)
                    else result.rowcount
                )
        return results

    async def execute_batch_async(
        self, queries: list[tuple]
    ) -> list[Union[pd.DataFrame, list[dict], int]]:
        """
        Execute multiple queries in a single transaction asynchronously.

        Args:
            queries: list of (query, params) tuples

        Returns:
            list of results for each query
        """
        results = []
        async with self.async_engine.begin() as conn:
            for query, params in queries:
                self._log_query(query, params, async_mode=True)
                result = await conn.execute(text(query), params or {})
                results.append(
                    self._process_rows(result.mappings().all())
                    if self._is_select(query)
                    else result.rowcount
                )
        return results

    async def close(self):
        """Clean up async engine resources."""
        if self._async_engine:
            await self._async_engine.dispose()

    def dispose(self):
        """Cleanup sync engine resources."""
        try:
            self._engine.dispose()
        except Exception:
            pass  # Ignore cleanup errors
