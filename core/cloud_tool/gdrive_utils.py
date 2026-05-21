# gdrive_pool.py
"""
GDriveServicePool
=================

A pragmatic **dual-mode** pool of blocking Google Drive client objects that can be used
both from synchronous code and from async event-loops.

- Provide a single pool implementation that supports:
  * synchronous usage (blocking callers)
  * asynchronous usage (non-blocking callers) by running blocking operations in threads
- Use a fixed set of independent `googleapiclient` *service* objects (one per pool slot)
to reduce contention and avoid sharing internal client state across threads.
- Keep the API minimal and explicit:
    * `create_sync()` — blocking factory for scripts/workers
    * `create_async()` — non-blocking factory usable in async startup
    * `get()` / `run_sync()` — sync usage helpers
    * `acquire()` / `run_async()` — async usage helpers

Examples

**1. Simple sync usage (script / worker):**
```python
pool = GDriveServicePool.create_sync(pool_size=4)
svc = pool.get()

# build a blocking request
request = svc.files().create(body={"name": "hello.txt"}, media_body=media).execute

# run directly on the current thread (blocking)
result = pool.run_sync(request)
print(result["id"])
```

**2. Async usage in FastAPI / aiohttp (non-blocking event loop):**
```python
# startup: create pool without blocking event loop
pool = await GDriveServicePool.create_async(pool_size=4)

# inside an async endpoint
async def upload_handler(...):
    # acquire the client (non-blocking)
    svc = await pool.acquire()
    # build the blocking request (cheap synchronous operation)
    req = svc.files().create(body={"name": "x.txt"}, media_body=media, fields="id").execute
    # execute in a thread so we don't block the event loop
    res = await pool.run_async(req)
    return {"id": res["id"]}
```

**3. Acquire and pass the service to a helper function that performs the RPC:**
```python
async def handler(pool, path):
    svc = await pool.acquire()
    # pass svc to a pure-business-logic helper
    return await upload_helper(svc, path)

async def upload_helper(svc, path):
    def do_upload():
        media = MediaFileUpload(path)
        return svc.files().create(body={"name": Path(path).name}, media_body=media).execute()
    return await asyncio.to_thread(do_upload)
```
"""
from __future__ import annotations

import asyncio
import os
import threading
from pathlib import Path
from typing import Any, Callable

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from libs.mixers.logger_mixin import get_logger
from libs.utils.retry_utils import retry

logger = get_logger("Gdrive", component="Utils")


class GDriveServicePool:
    """A pool object constructed with an existing list of blocking Google API service
    objects.
    """

    def __init__(self, services: list[Any]):
        """
        Initializes a GDriveServicePool object with a list of existing blocking Google API
        service objects.

        Args:
            services (list[Any]): A non-empty list of blocking Google API service objects.

        Raises:
            ValueError: If the services list is empty.

        """
        if not services:
            raise ValueError("services list must be non-empty")
        self._services: list[Any] = services

        # rotation state for sync callers
        self._sync_idx = 0
        self._sync_lock = threading.Lock()

        # rotation state for async callers
        self._async_idx = 0
        self._async_lock = asyncio.Lock()

        logger.debug(f"Created GDriveServicePool with {len(self._services)} services")

    # -------------------------
    # Factories
    # -------------------------
    @classmethod
    def create_sync(cls, pool_size: int = 8) -> "GDriveServicePool":
        """
        Build `pool_size` blocking service objects synchronously (blocking call).
        Use this in CLI / worker / non-async startup paths.

        Args:
            pool_size (int, optional): The number of service objects to create in the pool.
                Defaults to 8.

        Returns:
            GDriveServicePool: A GDriveServicePool object with the specified number of service objects.
        """
        services = [_get_service() for _ in range(pool_size)]
        return cls(services)

    @classmethod
    async def create_async(cls, pool_size: int = 8) -> "GDriveServicePool":
        """
        Asynchronous factory that constructs `pool_size` blocking service objects
        without blocking the event loop by using `asyncio.to_thread()`.

        Args:
            pool_size (int, optional): The number of service objects to create in the pool.
                Defaults to 8.

        Returns:
            GDriveServicePool: A GDriveServicePool object with the specified number of service objects.
        """
        tasks = [asyncio.to_thread(_get_service) for _ in range(pool_size)]
        services = await asyncio.gather(*tasks)
        return cls(services)

    # -------------------------
    # Sync API (for sync code)
    # -------------------------
    def get(self) -> Any:
        """
        Acquire a blocking Google Drive API service object from the pool.

        This method is thread-safe and will return a service object from the pool in a
        round-robin manner. The returned service object is a blocking Google API client
        object that can be used for synchronous API calls.

        Returns:
            Any: A blocking Google Drive API service object from the pool.

        """
        with self._sync_lock:
            service = self._services[self._sync_idx]
            self._sync_idx = (self._sync_idx + 1) % len(self._services)
        logger.debug(f"Acquired service {service}")
        return service

    def run_sync(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """
        Run a blocking function synchronously using a service object from the pool.

        This method is thread-safe and will return the result of the function call.

        Args:
            func (Callable[..., Any]): The blocking function to call.
            *args (Any): The positional arguments to pass to the function.
            **kwargs (Any): The keyword arguments to pass to the function.

        Returns:
            Any: The result of the function call.
        """
        return func(*args, **kwargs)

    # -------------------------
    # Async API (for async code)
    # -------------------------
    async def acquire(self) -> Any:
        """
        Acquire a non-blocking Google Drive API service object from the pool.

        This method is thread-safe and will return a service object from the pool in a
        round-robin manner. The returned service object is a non-blocking Google API client
        object that can be used for asynchronous API calls.

        Returns:
            Any: A non-blocking Google Drive API service object from the pool.
        """
        async with self._async_lock:
            service = self._services[self._async_idx]
            self._async_idx = (self._async_idx + 1) % len(self._services)
        logger.debug(f"Acquired service {service}")
        return service

    async def run_async(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """
        Run a non-blocking function asynchronously using a service object from the pool.

        This method is thread-safe and will return the result of the function call.

        Args:
            func (Callable[..., Any]): The non-blocking function to call.
            *args (Any): The positional arguments to pass to the function.
            **kwargs (Any): The keyword arguments to pass to the function.

        """
        return await asyncio.to_thread(func, *args, **kwargs)


@retry()
def _get_service() -> Any:
    """
    Authenticate with Google Drive API using OAuth Desktop credentials.

    Returns:
        Any: Google Drive API v3 service instance
    """
    logger.debug("Fetching and validating credentials...")

    credential_folder = Path(".").resolve() / ".credentials/gdrive"
    credential_file = credential_folder / "credentials.json"
    token_file = credential_folder / "token.json"
    scopes = [os.getenv("GDRIVE_SCOPES")]

    creds = None
    if os.path.exists(token_file):
        logger.debug("Loading existing credentials")
        creds = Credentials.from_authorized_user_file(token_file, scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.debug("Refreshing expired credentials")
            creds.refresh(Request())
        else:
            logger.debug("Creating new credentials")
            if not os.path.exists(credential_file):
                raise FileNotFoundError(
                    f"credentials.json not found. Create OAuth Desktop credentials and place at {credential_folder}."
                )
            logger.debug("Launching OAuth flow...")
            flow = InstalledAppFlow.from_client_secrets_file(credential_file, scopes)
            creds = flow.run_local_server(port=0)
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    logger.debug("Credentials/Tokens validation complete.")
    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    logger.info(f"Authenticated with client_id: {creds.client_id[:6]}...")
    return service
