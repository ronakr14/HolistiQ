# libs/cloud_ops/gcp/gdrive_ops.py

"""
Google Drive operations
=======================

This module provides a high-level, convenience-oriented wrapper around the Google Drive API v3.
It includes folder discovery/creation, recursive traversal, file uploads/downloads, metadata updates, moving/copying, and trash operations.

It is designed for idempotent, safe operations and supports concurrency via folder-level locking.

1. Name Helpers
    * `_q_name_equals`
    * `_is_google_native`

2. Folder Operations
    * `find_folder`
    * `create_folder`
    * `ensure_folder`
    * `ensure_nested_folder`
    * `ensure_root_folder`

3. Folder Traversal
    * `list_children`
    * `walk_folder`

4. File Upload / Download
    * `drive_upload`
    * `drive_download`

5. File Management
    * `copy_file`
    * `move_to_trash`
    * `update_metadata`
    * `find_file_folder`
    * `drive_move_to_folder`

"""

import io
import json
import os
from collections import defaultdict
from pathlib import Path
from threading import Lock
from typing import Any, Optional, Tuple

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from core.infrastructure.observability.logging.logging_util import get_logger
from core.utils.datetime_utils import to_utc_iso

logger = get_logger(__name__)
_folder_locks = defaultdict(Lock)


def _q_name_equals(name: str) -> str:
    """Build a Drive query string for files with exact name match.

    Since names can contain quotes, we use json.dumps to safely quote the name.
    """
    return f"name={json.dumps(name)}"


def _is_google_native(mime: str) -> bool:
    """
    Checks if a given MIME type is a Google native format.

    Args:
        mime (str): The MIME type to check

    Returns:
        bool: True if the MIME type is a Google native format, False otherwise
    """

    return mime.startswith(os.getenv("GOOGLE_APPS_PREFIX"))


def find_folder(service, folder_name: str, parent_id: Optional[str]) -> Optional[str]:
    """Find a Google Drive folder by its name and parent folder ID.

    Args:
        service (googleapiclient.discovery.Resource): Google Drive API client object
        folder_name (str): name of the folder to search for
        parent_id (Optional[str]): ID of the parent folder to search within

    Returns:
        Optional[str]: ID of the first matching folder, or None if not found
    """

    q_parts = [
        "mimeType='application/vnd.google-apps.folder'",
        "trashed=false",
        _q_name_equals(folder_name),
    ]
    if parent_id:
        q_parts.append(f"'{parent_id}' in parents")
        logger.debug(f"Searching for folder '{folder_name}' under parent '{parent_id}'")
    else:
        logger.debug(f"Searching for folder '{folder_name}' under root")

    q = " and ".join(q_parts)

    resp = service.files().list(q=q, fields="files(id, name)", pageSize=5).execute()
    files = resp.get("files", [])
    if files:
        logger.debug(f"Found folder '{folder_name}' with ID {files[0]['id']}")
        return files[0]["id"]
    else:
        logger.debug(f"Folder '{folder_name}' not found")
        return None


def create_folder(service, folder_name: str, parent_id: Optional[str]) -> str:
    """Create a Google Drive folder with the given name under the specified parent folder ID.

    Args:
        service (googleapiclient.discovery.Resource): Google Drive API client object
        folder_name (str): name of the folder to create
        parent_id (Optional[str]): ID of the parent folder to create the folder under

    Returns:
        str: ID of the created folder, or None if creation failed
    """
    metadata = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        metadata["parents"] = [parent_id]
        logger.debug(f"Creating folder '{folder_name}' under parent '{parent_id}'")
    else:
        logger.debug(f"Creating folder '{folder_name}' under root")

    service.files().create(body=metadata, fields="id").execute()

    # Re-query to confirm creation & mitigate concurrency races
    return find_folder(service, folder_name, parent_id)


def ensure_folder(service, folder_name: str, parent_id: Optional[str]) -> str:
    """Ensures a Google Drive folder exists with the given name under the specified parent folder ID.

    If the folder does not exist, it is created. If it does exist, its ID is returned.

    Args:
        service (googleapiclient.discovery.Resource): Google Drive API client object
        folder_name (str): name of the folder to ensure
        parent_id (Optional[str]): ID of the parent folder to ensure the folder under

    Returns:
        str: ID of the ensured folder, or None if creation failed
    """
    logger.debug(f"Ensuring folder '{folder_name}' under parent '{parent_id}'")
    lock_key = (parent_id or "root", folder_name)
    with _folder_locks[lock_key]:
        folder_id = find_folder(service, folder_name, parent_id)
        if folder_id:
            return folder_id
        return create_folder(service, folder_name, parent_id)


def ensure_nested_folder(service, root_id: str, relative_dir: Path) -> str:
    """Ensures that a Google Drive folder path exists, creating folders as necessary.

    Args:
        service (googleapiclient.discovery.Resource): Google Drive API client object
        root_id (str): ID of the root folder to ensure the path under
        relative_dir (Path): relative path to ensure under the root folder

    Returns:
        str: ID of the ensured folder, or None if creation failed
    """
    logger.debug(f"Ensuring folder path '{relative_dir}' under root '{root_id}'")
    current = root_id
    # parts are nested; create/find each
    for part in relative_dir.parts:
        if part == "":
            continue
        current = ensure_folder(service, part, parent_id=current)
    return current


def ensure_root_folder(service, folder_name: str) -> str:
    """Ensures a Google Drive folder exists with the given name under the root folder.

    If the folder does not exist, it is created. If it does exist, its ID is returned.

    Args:
        service (googleapiclient.discovery.Resource): Google Drive API client object
        folder_name (str): name of the folder to ensure

    Returns:
        str: ID of the ensured folder, or None if creation failed
    """
    logger.debug(f"Ensuring root folder '{folder_name}'")
    return ensure_folder(service, folder_name, parent_id=None)


def list_children(service, parent_id: str):
    """List all files and folders that are direct children of the given parent folder.

    Args:
        service (googleapiclient.discovery.Resource): Google Drive API client object
        parent_id (str): ID of the parent folder to list children of

    Yields:
        dict: the metadata of each file/folder, containing the following keys:
            - id (str): the ID of the file/folder
            - name (str): the name of the file/folder
            - mimeType (str): the MIME type of the file/folder
            - md5Checksum (str): the MD5 checksum of the file
            - modifiedTime (str): the last modified time of the file/folder
            - parents (list[str]): the IDs of the parent folders of the file/folder
            - size (int): the size of the file in bytes
    """
    logger.debug(f"Listing children of folder '{parent_id}'")
    page_token = None
    while True:
        resp = (
            service.files()
            .list(
                q=f"'{parent_id}' in parents and trashed=false",
                fields="nextPageToken, files(id, name, mimeType, md5Checksum, modifiedTime, parents, size)",
                pageSize=1000,
                pageToken=page_token,
            )
            .execute()
        )
        for f in resp.get("files", []):
            yield f
        page_token = resp.get("nextPageToken")
        if not page_token:
            break


def walk_folder(service, parent_id: str) -> dict[str, dict[str, Any]]:
    """
    Recursively walk the Google Drive folder tree starting from the given parent ID.

    This function returns a dictionary where the keys are the relative paths of the
    files and folders, and the values are the corresponding file metadata.

    Args:
        service (googleapiclient.discovery.Resource): Google Drive API service instance
        parent_id (str): ID of the root folder to start walking from

    Returns:
        dict[str, dict[str, Any]]: A dictionary mapping relative paths to file metadata
    """
    logger.debug(f"Walking Google Drive folder tree starting from '{parent_id}'")
    out = {}
    stack = [(parent_id, Path(""))]
    while stack:
        folder_id, rel_base = stack.pop()
        for f in list_children(service, folder_id):
            p = rel_base / f["name"]
            out[str(p).replace("\\", "/")] = f
            if f["mimeType"] == "application/vnd.google-apps.folder":
                stack.append((f["id"], p))
    return out


def drive_upload(
    service, local_path: Path, parent_id: str, overwrite_file_id: Optional[str] = None
) -> Tuple[str, str, str]:
    """
    Upload a file to Google Drive, optionally overwriting an existing file.

    Args:
        service (googleapiclient.discovery.Resource): Google Drive API service instance
        local_path (pathlib.Path): local file path to upload
        parent_id (str): ID of the folder to upload to
        overwrite_file_id (str, optional): if provided, overwrite the existing file with this ID

    Returns:
        Tuple(str, str, str): File ID, MD5 checksum, and modified time
    """
    logger.debug(f"Uploading {local_path} to {parent_id}")
    media = MediaFileUpload(str(local_path), resumable=True)
    local_mtime_iso = to_utc_iso(Path(local_path).stat().st_mtime)
    metadata = {
        "name": local_path.name,
        "parents": [parent_id],
        "modifiedTime": local_mtime_iso,
    }
    if overwrite_file_id:
        logger.debug(f"overwriting {overwrite_file_id[:6]}...")
        updated = (
            service.files()
            .update(
                fileId=overwrite_file_id,
                media_body=media,
                body={"name": local_path.name, "modifiedTime": local_mtime_iso},
                fields="id, md5Checksum, modifiedTime",
            )
            .execute()
        )
        logger.info("Overwrite complete")
        return updated["id"], updated["md5Checksum"], updated["modifiedTime"]
    created = (
        service.files()
        .create(body=metadata, media_body=media, fields="id, md5Checksum, modifiedTime")
        .execute()
    )
    logger.info("Upload complete")
    return created["id"], created["md5Checksum"], created["modifiedTime"]


def drive_download(service, file_id: str, dest_path: Path):
    """
    Download a file from Google Drive to a local path.

    Args:
        service (googleapiclient.discovery.Resource): Google Drive API service instance
        file_id (str): ID of the file to download
        dest_path (pathlib.Path): local path to save the file to

    Returns:
        None
    """
    logger.debug(f"Downloading {file_id}... to {dest_path}")
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(dest_path, "wb")
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    logger.info(f"Download complete at {dest_path}")


def copy_file(service, file_id: str, new_name: str, parent_id: str) -> str:
    """
    Copy a file with a new name to a given folder on Google Drive.

    Args:
        service (googleapiclient.discovery.Resource): Google Drive API service instance
        file_id (str): ID of the file to copy
        new_name (str): name of the new file
        parent_id (str): ID of the folder to copy the file to

    Returns:
        str: ID of the newly created file
    """
    logger.debug("Copying file")
    body = {"name": new_name, "parents": [parent_id]}
    copied = service.files().copy(fileId=file_id, body=body, fields="id").execute()
    logger.info(f"Copy complete to {copied['id']}")
    return copied["id"]


def move_to_trash(service, file_id: str) -> bool:
    """
    Move a file to the trash on Google Drive.

    Args:
        service (googleapiclient.discovery.Resource): Google Drive API service instance
        file_id (str): ID of the file to move to trash

    Returns:
        bool: True if the file is successfully moved to trash, False otherwise
    """
    logger.debug("Deleting the file")
    try:
        service.files().update(fileId=file_id, body={"trashed": True}).execute()
        logger.debug(f"File {file_id} moved to trash.")
        return True
    except HttpError as e:
        logger.error(f"Failed to move {file_id} to trash: {e}")
        return False


def update_metadata(service, file_id: str, metadata: dict) -> bool:
    """
    Update the metadata of a file on Google Drive.

    Args:
        service (googleapiclient.discovery.Resource): Google Drive API service instance
        file_id (str): ID of the file to update
        metadata (dict): dictionary of metadata to update

    Returns:
        bool: True if the metadata is successfully updated, False otherwise
    """
    logger.debug("Updating file metadata")
    try:
        service.files().update(fileId=file_id, body=metadata).execute()
        logger.info(f"File {file_id} metadata updated.")
        return True
    except HttpError as e:
        logger.error(f"Failed to update {file_id} metadata: {e}")
        return False


def find_file_folder(service, filename: str, folder_id: str) -> Optional[str]:
    """
    Search for a file by its name in a given folder on Google Drive.

    Args:
        service (googleapiclient.discovery.Resource): Google Drive API service instance
        filename (str): name of the file to search for
        folder_id (str): ID of the folder to search in

    Returns:
        Optional[str]: ID of the file if found, None otherwise
    """
    logger.debug(f"Searching for file '{filename}' in folder '{folder_id}'")
    query = f"name='{filename}' and '{folder_id}' in parents"
    results = (
        service.files().list(q=query, fields="files(id, name, md5Checksum)").execute()
    )
    items = results.get("files", [])

    if items:
        logger.info(f"Found file '{filename}' with ID {items[0]['id']}")
        return items[0]
    else:
        logger.info(f"File '{filename}' not found in folder '{folder_id}'")
        return None


def drive_move_to_folder(service, file_id: str, new_parent_id: str):
    """
    Move a file to a new folder on Google Drive.

    Args:
        service (googleapiclient.discovery.Resource): Google Drive API service instance
        file_id (str): ID of the file to move
        new_parent_id (str): ID of the new folder to move the file to

    Returns:
        None
    """
    logger.debug(f"Moving file {file_id} to new folder {new_parent_id}")
    f = service.files().get(fileId=file_id, fields="parents").execute()
    old_parents = ",".join(f.get("parents", []))
    service.files().update(
        fileId=file_id, addParents=new_parent_id, removeParents=old_parents
    ).execute()
    logger.info(f"File {file_id} moved to folder {new_parent_id}")
