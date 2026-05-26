import logging
import os
import threading
import time
from pathlib import Path

from dotenv import load_dotenv
from watchdog.observers import Observer

from libs.dev_ops.sync.gdrive.debounce_engine import DebouncedHandler

# from libs.mixins.logger_mixin import setup_logging
from libs.dev_ops.sync.gdrive.state_engine import load_ignore_file
from libs.dev_ops.sync.gdrive.sync_engine import SyncEngine

IGNOREFILE = Path(r"D:\Personal\HolistiQ\.gdrive\gdrive_ignore")
DRIVESYNC_INTERVAL = 30
LOCAL_DEBOUNCE_INTERVAL = 1

# setup_logging(log_level="DEBUG")
logger = logging.getLogger(__name__)


def entrypoint(
    mode: str = "manual",
    drive_sync_interval: int = DRIVESYNC_INTERVAL,
    ignore_file: Path = IGNOREFILE,
    local_debounce_interval: int = LOCAL_DEBOUNCE_INTERVAL,
    parallel: bool = False,
):
    logger.info("=" * 60)
    logger.info(
        "Starting GDrive sync - OneDrive-like (no admin). Press Ctrl+C to stop."
    )
    logger.info("=" * 60)
    load_dotenv()
    ignore_patterns = load_ignore_file(ignore_file)
    logger.info(f"[SYNC]: Below file patterns will be ignored:\n\t{ignore_patterns}")
    engine = SyncEngine(init_parallel=parallel)
    engine.handle_initial_sync(mode, ignore_patterns=ignore_patterns)
    if mode != "auto":
        return

    event_handler = DebouncedHandler(
        engine=engine,
        local_debounce_seconds=local_debounce_interval,
        ignore_patterns=ignore_patterns,
    )
    observer = Observer()
    observer.schedule(
        event_handler, str(os.getenv("LOCAL_SYNC_FOLDER")), recursive=True
    )
    logger.info(
        f"[SYNC]: Starting local watcher on {str(os.getenv("LOCAL_SYNC_FOLDER"))}..."
    )
    observer.start()

    def remote_poller():
        while True:
            try:
                engine.handle_drive_sync()
            except Exception:
                logger.exception("[SYNC]: Remote poll error")
            time.sleep(drive_sync_interval)

    t = threading.Thread(target=remote_poller, daemon=True)
    logger.info("[SYNC]: Starting remote poll loop in another thread...")
    t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("[SYNC]: Stopping drive sync...")
        observer.stop()
        observer.join()


if __name__ == "__main__":
    entrypoint(mode="manual")
