import logging
import os
from collections import Counter
from pathlib import Path
from typing import Optional

from libs.cloud_ops.gcp.gdrive_ops import (
    drive_download,
    drive_upload,
    ensure_drive_folder_path,
    ensure_drive_root,
)
from libs.dev_ops.sync.gdrive.state_engine import (
    get_filename_by_driveid,
    log_summary,
    safe_conflict_name,
)
from libs.encryptors.file_encrypter import file_md5, file_sha256, is_file_locked
from libs.utils.datetime_utils import from_iso
from libs.utils.parallel_utils import execute_parallel_with_args

logger = logging.getLogger(__name__)


def ensure_drive_root_presence(
    service, drive_root_id: Optional[str] = None
) -> Optional[str]:
    # ensure drive root if not present
    if not drive_root_id:
        r_root = ensure_drive_root(service)
        return r_root


def process_init_drive_to_local(
    service, state, local_index, drive_index, local_root, local_conflict, drive_root_id
):
    if not drive_index:
        logger.info("[GDRIVE]: No new/modified files found on drive, nothing to sync.")
        return state if state else {}

    logger.info("Starting drive to local sync...")

    def merge_results(results, state, merged_stats):
        for res in results:
            if res["state_update"]:
                rel_path, new_meta = res["state_update"]
                state[rel_path] = new_meta
            merged_stats.update(res["stats"])

    merged_stats = Counter()

    # Case 1: Parallel (service pool)
    if hasattr(service, "get"):
        max_workers = len(service.services)
        args_list = [
            (
                service.get(),
                rel_path,
                meta,
                state,
                local_index,
                local_root,
                local_conflict,
                drive_root_id,
            )
            for rel_path, meta in drive_index.items()
        ]
        results = execute_parallel_with_args(
            process_drive_file,
            args_list,
            max_workers=max_workers,
            preserve_order=False,
        )
        merge_results(results, state, merged_stats)

    # Case 2: Sequential
    else:
        results = [
            process_drive_file(
                service,
                rel_path,
                meta,
                state,
                local_index,
                local_root,
                local_conflict,
                drive_root_id,
            )
            for rel_path, meta in drive_index.items()
        ]
        merge_results(results, state, merged_stats)

    log_summary(dict(merged_stats))
    return state if state else {}


def process_drive_file(
    service,
    rel_path,
    meta,
    state,
    local_index,
    local_root,
    local_conflict,
    drive_root_id,
):
    local_p = local_root / rel_path
    remote_mtime_iso = meta.get("modifiedTime", None)
    remote_mtime = from_iso(remote_mtime_iso)

    result = {
        "state_update": None,  # what to merge into state
        "stats": {
            "new": 0,
            "local_conflict": 0,
            "remote_conflict": 0,
            "updated": 0,
            "skipping": 0,
        },
    }

    state_meta = state.get(rel_path)
    local_meta = local_index.get(rel_path)

    # Case 1: File new on Drive
    if (not state_meta and not local_meta) or (state_meta and not local_meta):
        logger.info(f"[GDRIVE]: New file found on drive - {rel_path}, downloading.")
        drive_download(service, meta["id"], local_p)
        os.utime(local_p, (remote_mtime, remote_mtime))
        result["state_update"] = (
            rel_path,
            {
                "drive_id": meta["id"],
                "local_mtime": remote_mtime,
                "remote_mtime": remote_mtime,
                "md5": meta.get("md5Checksum"),
                "sha256": file_sha256(local_p),
                "size": meta.get("size"),
            },
        )
        result["stats"]["new"] += 1
        return result

    # Case 2: File exists in state/local/remote → compare
    elif (not state_meta and local_meta) or (state_meta and local_meta):
        logger.info(f"[GDRIVE]: Same file found on drive - {rel_path}, keeping latest.")

        l_size = int(local_meta.get("size", 0))
        r_size = int(meta.get("size", 0))
        l_md5 = file_md5(local_p)
        r_md5 = meta.get("md5Checksum")
        local_mtime = local_meta.get("mtime")

        # Same file, only update metadata
        if l_size == r_size and l_md5 == r_md5:
            if not is_file_locked(local_p):
                logger.debug("[GDRIVE]: Local file metadata updated to match gdrive.")
                os.utime(local_p, (remote_mtime, remote_mtime))
                effective_local_mtime = remote_mtime
            else:
                logger.debug("[GDRIVE]: File locked, skipping.")
                effective_local_mtime = remote_mtime
            result["state_update"] = (
                rel_path,
                {
                    "drive_id": meta["id"],
                    "local_mtime": effective_local_mtime,
                    "remote_mtime": remote_mtime,
                    "md5": meta.get("md5Checksum"),
                    "sha256": file_sha256(local_p),
                    "size": meta.get("size"),
                },
            )
            result["stats"]["updated"] += 1
            return result

        # Conflict → local vs remote
        elif (l_size == r_size and l_md5 != r_md5) or (l_size != r_size):
            local_mtime = local_meta.get("mtime")
            conflict_local = (
                local_conflict
                / Path(rel_path).parent
                / safe_conflict_name(Path(rel_path).name)
            )
            conflict_local.parent.mkdir(parents=True, exist_ok=True)

            if local_mtime > remote_mtime:
                drive_download(service, meta["id"], conflict_local)
                parent_id = (
                    ensure_drive_folder_path(
                        service, drive_root_id, Path(rel_path).parent
                    )
                    if Path(rel_path).parent != Path("")
                    else drive_root_id
                )
                new_id, r_md5, remote_mtime_iso = drive_upload(
                    service, local_p, parent_id, meta["id"]
                )
                logger.debug(
                    f"[GDRIVE]: [conflict-remote] - {rel_path} -> {conflict_local}"
                )
                result["state_update"] = (
                    rel_path,
                    {
                        "drive_id": new_id,
                        "local_mtime": local_mtime,
                        "remote_mtime": from_iso(remote_mtime_iso),
                        "md5": r_md5,
                        "sha256": file_sha256(local_p),
                        "size": l_size,
                    },
                )
                result["stats"]["remote_conflict"] += 1
            else:
                if local_p.exists() and not is_file_locked(local_p):
                    local_p.replace(conflict_local)
                    logger.debug(
                        f"[GDRIVE]: [conflict-local] - {rel_path} -> {conflict_local}"
                    )
                drive_download(service, meta["id"], local_p)
                os.utime(local_p, (remote_mtime, remote_mtime))
                result["state_update"] = (
                    rel_path,
                    {
                        "drive_id": meta["id"],
                        "local_mtime": remote_mtime,
                        "remote_mtime": remote_mtime,
                        "md5": meta.get("md5Checksum"),
                        "sha256": file_sha256(local_p),
                        "size": meta.get("size"),
                    },
                )
                result["stats"]["local_conflict"] += 1
            return result

    return result


def process_gdrive_delete(change_entry, state, local_root):
    removed_id = change_entry.get("fileId")
    logger.info(f"[GDRIVE]: Managing remote delete {removed_id}.")
    local_rel = get_filename_by_driveid(state, removed_id)

    if local_rel:
        local_p = local_root / local_rel
        if local_p.exists():
            local_p.unlink()
            logger.debug(f"[GDRIVE]: Moving local {local_rel} -> recycle")
            # ensure known cleared
        state.pop(local_rel, None)
    return state


class DrivePathResolver:
    def __init__(self, service, root_id: str):
        self.service = service
        self.root_id = root_id
        self.cache: dict[str, tuple[str, str | None]] = {}
        # cache[file_id] = (name, parent_id)

    def fetch_metadata(self, file_id: str) -> tuple[str, str | None]:
        if file_id in self.cache:
            return self.cache[file_id]

        file = (
            self.service.files()
            .get(fileId=file_id, fields="id, name, parents")
            .execute()
        )

        name = file["name"]
        parents = file.get("parents", [])
        parent_id = parents[0] if parents else None

        self.cache[file_id] = (name, parent_id)
        return name, parent_id

    def get_relpath(self, file_id: str) -> str:
        parts = []
        current_id = file_id

        while current_id and current_id != self.root_id:
            name, parent_id = self.fetch_metadata(current_id)
            parts.append(name)
            current_id = parent_id

        parts.reverse()
        return str(Path(*parts))
