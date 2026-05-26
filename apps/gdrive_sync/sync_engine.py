import logging
import os
from pathlib import Path
from typing import Optional

from libs.cloud_ops.gcp.gdrive_ops import (
    GDriveServicePool,
    ensure_drive_root,
    get_service,
    is_google_native,
    walk_drive,
)
from libs.dev_ops.sync.gdrive.gdrive_engine import (
    DrivePathResolver,
    process_drive_file,
    process_gdrive_delete,
    process_init_drive_to_local,
)
from libs.dev_ops.sync.gdrive.local_engine import (
    ensure_local_root_presence,
    process_init_local_to_drive,
    process_local_delete,
    process_local_file,
    walk_local,
)
from libs.dev_ops.sync.gdrive.state_engine import load_state, save_state
from libs.utils.parallel_utils import execute_parallel_mixed, get_optimal_worker_count

logger = logging.getLogger(__name__)


class SyncEngine:
    def __init__(self, init_parallel: bool = False):
        logger.info("[ENGINE]: Engine initalized")
        self.service = (
            GDriveServicePool(pool_size=get_optimal_worker_count(8))
            if init_parallel
            else get_service()
        )
        self.state = load_state()
        self.initial_sync = self.state.get("initial_sync", False)
        self.known = self.state.get("files", {})  # rel -> dict
        self.drive_root_id = self.state.get("drive_root_id")
        self.last_change_token = self.state.get("last_change_token")
        self.local_root = Path(os.getenv("LOCAL_SYNC_FOLDER"))
        self.local_conflict = self.local_root / "Conflicts"
        # ensure local dirs
        ensure_local_root_presence(self.local_root, self.local_conflict)
        # ensure drive root if not present
        if not self.drive_root_id:
            service = self.service
            if hasattr(self.service, "get"):
                service = self.service.get()
            r_root = ensure_drive_root(service)
            self.drive_root_id = r_root
            self.state["drive_root_id"] = r_root
            save_state(self.state)
        logger.info(f"[ENGINE]: drive root: {self.drive_root_id[:6]} present.")

    def full_pull_index(self, ignore_patterns: Optional[list] = None):
        logger.debug("[ENGINE]: Fetching local and drive indexes.")
        # Build current indexes
        service = self.service
        if hasattr(self.service, "get"):
            service = self.service.get()

        tasks = [
            (
                walk_local,
                (),
                {"root": self.local_root, "ignore_patterns": ignore_patterns},
            ),
            (walk_drive, (), {"service": service, "root_id": self.drive_root_id}),
        ]
        results = execute_parallel_mixed(tasks)
        local_index, drive_index_all = results[0], results[1]

        # filter out folders
        drive_index = {
            rel: meta
            for rel, meta in drive_index_all.items()
            if meta.get("mimeType") != "application/vnd.google-apps.folder"
        }
        return local_index, drive_index

    def persist(self):
        logger.debug("[ENGINE]: Persisting current state")
        self.state["files"] = self.known
        self.state["drive_root_id"] = self.drive_root_id
        self.state["last_change_token"] = self.last_change_token
        save_state(self.state)

    def handle_initial_sync(self, mode: str, ignore_patterns: Optional[list] = None):
        logger.info("[ENGINE]: Handling intial sync")
        local_index, drive_index = self.full_pull_index(ignore_patterns)
        if mode.lower() in ["upload", "manual", "auto"]:
            self.known = process_init_local_to_drive(
                self.service,
                self.known,
                local_index,
                drive_index,
                self.local_root,
                self.local_conflict,
                self.drive_root_id,
            )
        if mode.lower() in ["download", "manual", "auto"]:
            self.known = process_init_drive_to_local(
                self.service,
                self.known,
                local_index,
                drive_index,
                self.local_root,
                self.local_conflict,
                self.drive_root_id,
            )
        self.persist()
        return

    def handle_local_sync(self, op, rel_path, entry):
        logger.debug("[ENGINE]: Managing local changes...")
        service = self.service
        if hasattr(self.service, "get"):
            service = self.service.get()

        if op in ["created", "modified"]:
            print(op, rel_path, entry)
            local_p = self.local_root / rel_path
            local_meta = {
                "mtime": local_p.stat().st_mtime,
                "size": local_p.stat().st_size,
            }
            drive_meta = {}
            result = process_local_file(
                service,
                rel_path,
                local_meta,
                self.known,
                drive_meta,
                self.local_root,
                self.local_conflict,
                self.drive_root_id,
            )
            rel_path, new_meta = result["state_update"]
            self.known[rel_path] = new_meta
        elif op == "deleted":
            self.known = process_local_delete(
                service, rel_path, self.known, self.drive_root_id
            )
        self.persist()

    def handle_drive_sync(self):
        logger.debug("[ENGINE]: Polling for gdrive changes...")
        service = self.service
        if hasattr(self.service, "get"):
            service = self.service.get()

        resolver = DrivePathResolver(service, root_id=self.drive_root_id)

        # Get startPageToken if not present
        if not self.last_change_token:
            logger.debug("[ENGINE]: No start token, initializing...")
            resp = service.changes().getStartPageToken().execute()
            token = resp.get("startPageToken")
            self.last_change_token = token
            self.state["last_change_token"] = token
            save_state(self.state)
            logger.info(f"[ENGINE]: Initialized start token: {token}")
            return

        # iterate through changes pages
        page_token = self.last_change_token
        new_token = page_token
        while True:
            resp = (
                service.changes()
                .list(
                    pageToken=page_token,
                    spaces="drive",
                    fields="nextPageToken,newStartPageToken,changes(fileId,file(name),file(mimeType),file(modifiedTime),removed, file(size), file(parents), file(md5Checksum), file(trashed))",
                    pageSize=1000,
                )
                .execute()
            )
            changes = resp.get("changes", [])
            logger.debug("[ENGINE]: Received changes page")
            for c in changes:
                logger.warning(f"c: {c}")

                # Each change corresponds to a file anywhere in the Drive. We only care if it is inside our remote_root tree.
                if c.get("removed") or c.get("file").get("trashed"):
                    logger.debug(f"[ENGINE]: File - {c} removed from remote.")

                    # File was removed from drive (trashed or deleted)
                    # There is limited file metadata in this case; we must attempt to resolve by comparing known map
                    self.known = process_gdrive_delete(c, self.known, self.local_root)
                else:
                    logger.info("[ENGINE]: File modified on remote.")
                    file_meta = c.get("file")
                    file_meta["id"] = c.get("fileId")
                    if not file_meta:
                        logger.debug("[ENGINE]: File metadata missing.")
                        continue

                    # Determine relative path: need to walk remote tree to map ID -> rel
                    rel_path = resolver.get_relpath(file_meta.get("id", ""))

                    if not rel_path:
                        # If file not under our remote root, ignore
                        continue

                    # If file was added/modified -> download or update local
                    if (
                        file_meta.get("mimeType")
                        == "application/vnd.google-apps.folder"
                    ):
                        logger.debug(
                            f"[ENGINE]: Google folder changed: {rel_path} (skip auto-download)"
                        )
                        continue
                    if is_google_native(file_meta.get("mimeType")):
                        logger.debug(
                            f"[ENGINE]: Google-native file changed: {rel_path} (skip auto-update)"
                        )
                        continue

                    # now compare hash and times and apply
                    local_p = self.local_root / rel_path
                    local_exists = local_p.exists()
                    local_meta = {}
                    if local_exists:
                        local_meta = {
                            rel_path: {
                                "mtime": local_p.stat().st_mtime,
                                "size": local_p.stat().st_size,
                            }
                        }
                    result = process_drive_file(
                        service,
                        rel_path,
                        file_meta,
                        self.known,
                        local_meta,
                        self.local_root,
                        self.local_conflict,
                        self.drive_root_id,
                    )
                    rel_path, new_meta = result["state_update"]
                    self.known[rel_path] = new_meta
                    self.persist()
                    continue

            # update page token pointers
            if resp.get("newStartPageToken"):
                new_token = resp.get("newStartPageToken")
            if resp.get("nextPageToken"):
                page_token = resp.get("nextPageToken")
            else:
                break

        # persist last token
        if new_token:
            self.last_change_token = new_token
            self.state["last_change_token"] = new_token
            save_state(self.state)
            logger.info(f"[ENGINE] Updated change token -> {new_token}")
