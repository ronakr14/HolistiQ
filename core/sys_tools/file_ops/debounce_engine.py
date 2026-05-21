import fnmatch
import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional

from watchdog.events import FileSystemEventHandler

from libs.dev_ops.sync.gdrive.sync_engine import SyncEngine

logger = logging.getLogger(__name__)


class DebouncedHandler(FileSystemEventHandler):
    def __init__(
        self,
        engine: SyncEngine,
        local_debounce_seconds: float = 1.0,
        ignore_patterns: Optional[list] = None,
    ):
        """
        Initialize a DebouncedHandler for file system events.

        Parameters
        ----------
        engine : SyncEngine
            The engine to use for synchronization
        local_debounce_seconds : float, optional
            The number of seconds to wait before processing a file system event.
            Defaults to 1.0.
        ignore_patterns : Optional[list], optional
            A list of patterns to ignore when processing file system events.
            Defaults to None.
        """
        super().__init__()
        self.engine = engine
        self._pending = {}
        self.ignore_patterns = ignore_patterns
        self._lock = threading.Lock()
        self._worker = threading.Thread(
            target=self._process_loop,
            args=(local_debounce_seconds, ignore_patterns),
            daemon=True,
        )
        logger.info("[Watcher]: Watcher initalized")
        self._worker.start()

    def on_created(self, event):
        """
        Handle a file system created event.

        Parameters
        ----------
        event : watchdog.events.FileSystemEvent
            The file system event to handle.

        Returns
        -------
        None
        """
        logger.debug(f"[Watcher]: File created: {event.src_path}")
        if event.is_directory:
            return
        self._enqueue(event.src_path, "created")

    def on_deleted(self, event):
        logger.debug(f"[Watcher]: File deleted: {event.src_path}")
        if event.is_directory:
            return
        self._enqueue(event.src_path, "deleted")

    def on_moved(self, event):
        logger.debug(f"[Watcher]: File moved: {event.src_path} -> {event.dest_path}")
        if event.is_directory:
            return
        # treat as delete + create
        self._enqueue(event.dest_path, "moved", event.src_path)

    def on_modified(self, event):
        logger.debug(f"[Watcher]: File modified: {event.src_path}")
        if event.is_directory:
            return
        self._enqueue(event.src_path, "modified")

    def _is_ignored(self, rel: str) -> bool:
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(rel, pattern):
                logger.debug(f"[WATCHER]: Ignoring file: {rel}")
                return True
        return False

    def _enqueue(self, path: str, op: str, src_path: Optional[str] = None):
        LOCAL_ROOT = Path(os.getenv("LOCAL_SYNC_FOLDER"))
        rel = os.path.relpath(path, LOCAL_ROOT)
        rel = rel.replace("\\", "/")
        if rel.startswith(".."):
            logger.debug("[Watcher]: Ignoring folders without files.")
            return
        if self._is_ignored(rel):
            return

        if src_path:
            src_path = os.path.relpath(src_path, LOCAL_ROOT)
            src_path = src_path.replace("\\", "/")
            if src_path.startswith(".."):
                logger.debug("[Watcher]: Ignoring folders without files.")
                return
            if self._is_ignored(src_path):
                return

        with self._lock:
            self._pending[rel] = {
                "op": op,
                "src": src_path,
                "time": time.time(),
            }
        logger.warning(f"[WATCHER]: Job queued: {op}: {rel}")

    def _process_loop(
        self,
        local_debounce_seconds: float = 1.0,
        ignore_patterns: Optional[list] = None,
    ):
        logger.debug("[WATCHER]: Starting Jobs queued")
        while True:
            now = time.time()
            to_run = []
            with self._lock:
                for rel, entry in list(self._pending.items()):
                    if now - entry["time"] >= local_debounce_seconds:
                        to_run.append((rel, entry))
                        del self._pending[rel]
            for rel, entry in to_run:
                op = entry["op"]
                src = entry.get("src")
                logger.info(f"[WATCHER]: Implementing {op} operation on {rel}.")
                try:
                    if op in ["created", "deleted", "modified"]:
                        self.engine.handle_local_sync(op, rel, entry)
                        # self.engine.handle_local_create(rel, ignore_patterns)
                    elif op == "moved":
                        self.engine.handle_local_sync("created", rel, entry)
                        self.engine.handle_local_sync("deleted", src, entry)
                        # self.engine.handle_local_create(rel, ignore_patterns)
                        # self.engine.handle_local_delete(src)
                    logger.info(
                        f"[WATCHER]: Changes implemented for {op} operation on {rel}"
                    )
                except Exception:
                    logger.exception("[WATCHER]: Exception while implementing changes")
            time.sleep(0.3)
