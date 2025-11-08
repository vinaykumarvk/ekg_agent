"""Google Drive helpers for listing and downloading files."""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account

from api.settings import settings


SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
FOLDER_ID_PATTERN = re.compile(r"/folders/([a-zA-Z0-9-_]+)")


@dataclass
class DriveFile:
    id: str
    name: str
    mime_type: str
    size: int
    modified_time: str


class GoogleDriveClient:
    def __init__(self) -> None:
        self._service = None
        self._lock = asyncio.Lock()

    async def _get_service(self):
        if not settings.GOOGLE_SERVICE_ACCOUNT_FILE:
            raise HTTPException(
                status_code=400,
                detail="Google Drive integration is not configured",
            )

        async with self._lock:
            if self._service is not None:
                return self._service

            def _build():
                credentials = service_account.Credentials.from_service_account_file(
                    settings.GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES
                )
                return build("drive", "v3", credentials=credentials, cache_discovery=False)

            self._service = await asyncio.to_thread(_build)
            return self._service

    async def list_folder(self, folder_id: str) -> list[DriveFile]:
        service = await self._get_service()

        def _list() -> list[DriveFile]:
            try:
                query = f"'{folder_id}' in parents and trashed=false"
                result = (
                    service.files()
                    .list(
                        q=query,
                        fields="files(id, name, mimeType, size, modifiedTime)",
                        pageSize=1000,
                    )
                    .execute()
                )
            except HttpError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            files: list[DriveFile] = []
            for metadata in result.get("files", []):
                mime_type = metadata.get("mimeType")
                size = int(metadata.get("size", 0))
                files.append(
                    DriveFile(
                        id=metadata["id"],
                        name=metadata["name"],
                        mime_type=mime_type,
                        size=size,
                        modified_time=metadata.get("modifiedTime", ""),
                    )
                )
            return files

        return await asyncio.to_thread(_list)

    async def download_file(self, file_id: str, destination: Path) -> tuple[Path, int, str]:
        service = await self._get_service()

        def _download() -> tuple[Path, int, str]:
            try:
                request = service.files().get_media(fileId=file_id)
                metadata = (
                    service.files()
                    .get(fileId=file_id, fields="name, mimeType, size")
                    .execute()
                )
            except HttpError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            filename = metadata.get("name", file_id)
            mime_type = metadata.get("mimeType")
            size = int(metadata.get("size", 0))

            if mime_type not in settings.GOOGLE_ALLOWED_MIME_TYPES:
                raise HTTPException(status_code=400, detail=f"Unsupported file type: {mime_type}")
            if size == 0:
                raise HTTPException(status_code=400, detail="File is empty")
            if size > MAX_GOOGLE_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail="File exceeds the 100 MB limit",
                )

            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("wb") as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    if status:
                        continue
            return destination, size, filename

        return await asyncio.to_thread(_download)


def extract_folder_id(value: str) -> str:
    value = value.strip()
    if not value:
        raise HTTPException(status_code=400, detail="Folder link is required")

    match = FOLDER_ID_PATTERN.search(value)
    if match:
        return match.group(1)
    # Fallback: the user may have provided just the ID
    return value


MAX_GOOGLE_FILE_SIZE = 100 * 1024 * 1024
drive_client = GoogleDriveClient()
