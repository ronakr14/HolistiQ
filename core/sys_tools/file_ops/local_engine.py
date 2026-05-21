import logging
import os
from collections import Counter
from pathlib import Path

from libs.cloud_ops.gcp.gdrive_ops import (
    drive_download,
    drive_upload,
    ensure_drive_folder_path,
    find_file_in_folder,
    move_to_trash,
    update_metadata,
)
from libs.dev_ops.sync.gdrive.state_engine import log_summary, safe_conflict_name
from libs.encryptors.file_encrypter import file_md5, file_sha256, is_file_locked
from libs.utils.datetime_utils import from_iso, to_utc_iso
from libs.utils.parallel_utils import execute_parallel_with_args

logger = logging.getLogger(__name__)


def ensure_local_root_presence(local_root: Path, local_conflict: Path):
    local_root.mkdir(parents=True, exist_ok=True)
    local_conflict.mkdir(parents=True, exist_ok=True)
    logger.info("[LOCAL-ENGINE]: Local Root folder present")


def walk_local(root: Path, ignore_patterns: list) -> dict[str, dict]:
    logger.debug("[LOCAL]: Extracting local repository content (only files).")
    out = {}
    if not root.exists():
        logger.error("[LOCAL]: Root directory does not exist")
        return out
    for p in root.rglob("*"):
        if p.is_dir():
            logger.debug(f"[LOCAL]: Skipping only directory: {p}")
            continue
        rel = str(p.relative_to(root)).replace("\\", "/")
        # skip ignored
        if any(rel.startswith(x) or x in rel for x in ignore_patterns):
            logger.debug(f"[STATE]: Skipping ignored file: {rel}")
            continue
        out[rel] = {"mtime": int(p.stat().st_mtime), "size": p.stat().st_size}
    return out


def process_init_local_to_drive(
    service, state, local_index, drive_index, local_root, local_conflict, drive_root_id
):
    if not local_index:
        logger.info("[LOCAL]: No new/modified files found on local, nothing to sync.")
        return state if state else {}

    logger.info("Starting local to drive sync...")

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
                drive_index,
                local_root,
                local_conflict,
                drive_root_id,
            )
            for rel_path, meta in local_index.items()
        ]
        results = execute_parallel_with_args(
            process_local_file,
            args_list,
            max_workers=max_workers,
            preserve_order=False,
        )
        merge_results(results, state, merged_stats)

    # Case 2: Sequential
    else:
        results = [
            process_local_file(
                service,
                rel_path,
                meta,
                state,
                drive_index,
                local_root,
                local_conflict,
                drive_root_id,
            )
            for rel_path, meta in local_index.items()
        ]
        print(results)
        merge_results(results, state, merged_stats)

    log_summary(dict(merged_stats))
    return state if state else {}


def process_local_file(
    service,
    rel_path,
    meta,
    state,
    drive_index,
    local_root,
    local_conflict,
    drive_root_id,
):
    local_p = local_root / rel_path
    state_meta = state.get(rel_path)
    drive_meta = drive_index.get(rel_path)
    local_mtime = meta.get("mtime")
    l_size = int(meta.get("size", 0))

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

    # Case 1: File new on local
    if (not state_meta and not drive_meta) or (state_meta and not drive_meta):
        logger.info(f"[LOCAL]: New file found on local - {rel_path}, uploading.")
        parent_id = (
            ensure_drive_folder_path(service, drive_root_id, Path(rel_path).parent)
            if Path(rel_path).parent != Path("")
            else drive_root_id
        )
        new_id, r_md5, remote_mtime_iso = drive_upload(service, local_p, parent_id)
        logger.info(f"[LOCAL]: [local->upload] completed at {remote_mtime_iso}.")
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
        result["stats"]["new"] += 1
        return result

    # Case 2: File exists in state/local/remote → compare
    if (not state_meta and drive_meta) or (state_meta and drive_meta):
        logger.info(f"[LOCAL]: Same file found on drive - {rel_path}, keeping latest.")

        r_size = int(drive_meta.get("size", 0))
        l_md5 = file_md5(local_p)
        r_md5 = drive_meta.get("md5Checksum")

        # Same file, only update metadata
        if l_size == r_size and l_md5 == r_md5:
            update_metadata(
                service, drive_meta["id"], {"modifiedTime": to_utc_iso(local_mtime)}
            )
            result["state_update"] = (
                rel_path,
                {
                    "drive_id": drive_meta["id"],
                    "local_mtime": local_mtime,
                    "remote_mtime": local_mtime,
                    "md5": r_md5,
                    "sha256": file_sha256(local_p),
                    "size": r_size,
                },
            )
            result["stats"]["updated"] += 1
            return result

        # Conflict → local vs remote
        if (l_size == r_size and l_md5 != r_md5) or (l_size != r_size):
            remote_mtime = from_iso(drive_meta.get("modifiedTime"))
            conflict_local = (
                local_conflict
                / Path(rel_path).parent
                / safe_conflict_name(Path(rel_path).name)
            )
            conflict_local.parent.mkdir(parents=True, exist_ok=True)

            if local_mtime > remote_mtime:
                drive_download(service, drive_meta["id"], conflict_local)
                parent_id = (
                    ensure_drive_folder_path(
                        service, drive_root_id, Path(rel_path).parent
                    )
                    if Path(rel_path).parent != Path("")
                    else drive_root_id
                )
                new_id, r_md5, remote_mtime_iso = drive_upload(
                    service, local_p, parent_id, drive_meta["id"]
                )
                logger.debug(
                    f"[LOCAL]: [conflict-remote] - {rel_path} -> {conflict_local}"
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
                        f"[LOCAL]: [conflict-local] - {rel_path} -> {conflict_local}"
                    )
                drive_download(service, drive_meta["id"], local_p)
                os.utime(local_p, (remote_mtime, remote_mtime))
                result["state_update"] = (
                    rel_path,
                    {
                        "drive_id": drive_meta["id"],
                        "local_mtime": remote_mtime,
                        "remote_mtime": remote_mtime,
                        "md5": r_md5,
                        "sha256": file_sha256(local_p),
                        "size": r_size,
                    },
                )
                result["stats"]["local_conflict"] += 1
            return result

    return result


def process_local_delete(service, rel_path, state, drive_root_id):
    logger.info("[LOCAL]: Handling local file deletion.")
    service = service
    if hasattr(service, "get"):
        service = service.get()
    # for rel_path, meta in local_index.items():
    parent_id = (
        ensure_drive_folder_path(service, drive_root_id, Path(rel_path).parent)
        if Path(rel_path).parent != Path("")
        else drive_root_id
    )
    existing = find_file_in_folder(service, Path(rel_path).name, parent_id)
    if existing:
        logger.debug(f"[LOCAL]: Moving remote file to trash: {rel_path}")
        move_to_trash(service, existing["id"])
        logger.info("[ENGINE-DELETE]: Remote file moved to trash.")
    else:
        logger.info("[LOCAL]: File not found on drive.")
    state.pop(rel_path, None)
    return state
