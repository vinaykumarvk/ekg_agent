"""Utilities to manage OpenAI vector stores and local metadata."""
from __future__ import annotations

import asyncio
import json
import mimetypes
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict

from fastapi import HTTPException, UploadFile
from openai import OpenAI

from api.settings import settings


MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB


@dataclass
class StoredFile:
    """Metadata about a file stored in a vector store."""

    file_id: str
    filename: str
    size_bytes: int
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class VectorStoreRecord:
    name: str
    vector_store_id: str
    files: Dict[str, StoredFile] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "vector_store_id": self.vector_store_id,
            "files": {k: asdict(v) for k, v in self.files.items()},
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "VectorStoreRecord":
        files = {
            name: StoredFile(**metadata)
            for name, metadata in payload.get("files", {}).items()
        }
        return cls(
            name=payload["name"],
            vector_store_id=payload["vector_store_id"],
            files=files,
        )


class VectorStoreRegistry:
    """Persist a registry of vector stores available to the admin UI."""

    def __init__(self, path: Path):
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._records: dict[str, VectorStoreRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            payload = json.loads(self._path.read_text())
        except json.JSONDecodeError:
            payload = {}
        for name, record in payload.items():
            self._records[name] = VectorStoreRecord.from_dict(record)

    def _persist(self) -> None:
        serialized = {name: record.to_dict() for name, record in self._records.items()}
        self._path.write_text(json.dumps(serialized, indent=2, sort_keys=True))

    async def ensure_record(
        self, name: str, creator: Callable[[], Awaitable[str]]
    ) -> VectorStoreRecord:
        name = name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Vector store name is required")

        async with self._lock:
            if name in self._records:
                return self._records[name]

            vector_store_id = await creator()
            record = VectorStoreRecord(name=name, vector_store_id=vector_store_id)
            self._records[name] = record
            self._persist()
            return record

    async def update_file(
        self, vector_store_name: str, stored_file: StoredFile
    ) -> VectorStoreRecord:
        async with self._lock:
            record = self._records[vector_store_name]
            record.files[stored_file.filename] = stored_file
            self._persist()
            return record

    async def remove_file(
        self, vector_store_name: str, filename: str
    ) -> VectorStoreRecord:
        async with self._lock:
            record = self._records.get(vector_store_name)
            if not record:
                raise KeyError(vector_store_name)
            record.files.pop(filename, None)
            self._persist()
            return record

    async def list_records(self) -> list[VectorStoreRecord]:
        async with self._lock:
            return list(self._records.values())


REGISTRY = VectorStoreRegistry(Path("data/vectorstores/registry.json"))


async def create_vector_store_if_needed(client: OpenAI, name: str) -> VectorStoreRecord:
    async def _creator() -> str:
        return await asyncio.to_thread(
            lambda: client.beta.vector_stores.create(name=name).id
        )

    return await REGISTRY.ensure_record(name, _creator)


async def remove_existing_file(
    client: OpenAI, vector_store_id: str, filename: str
) -> None:
    """Remove any previous file with the same filename from the vector store."""

    filename = os.path.basename(filename)
    cursor: str | None = None

    while True:
        response = await asyncio.to_thread(
            lambda: client.beta.vector_stores.files.list(
                vector_store_id=vector_store_id, limit=100, after=cursor
            )
        )
        for file_record in response.data:
            if getattr(file_record, "filename", "") == filename:
                await asyncio.to_thread(
                    lambda: client.beta.vector_stores.files.delete(
                        vector_store_id=vector_store_id, file_id=file_record.id
                    )
                )
        if not getattr(response, "has_more", False):
            break
        cursor = getattr(response, "last_id", None)


async def upload_file_to_openai(
    client: OpenAI, vector_store_id: str, file_path: Path, filename: str
) -> StoredFile:
    """Upload a file to OpenAI and attach it to the vector store."""

    def _upload() -> Any:
        with file_path.open("rb") as handle:
            return client.files.create(
                file=(filename, handle),
                purpose="assistants",
            )

    file_obj = await asyncio.to_thread(_upload)

    batch = await asyncio.to_thread(
        lambda: client.beta.vector_stores.file_batches.create(
            vector_store_id=vector_store_id, file_ids=[file_obj.id]
        )
    )

    await wait_for_batch_completion(client, vector_store_id, batch.id)

    stat = file_path.stat()
    return StoredFile(
        file_id=file_obj.id,
        filename=filename,
        size_bytes=stat.st_size,
    )


async def wait_for_batch_completion(
    client: OpenAI, vector_store_id: str, batch_id: str, timeout_seconds: int = 300
) -> None:
    """Poll until the ingestion batch is complete or timed out."""

    deadline = datetime.utcnow().timestamp() + timeout_seconds

    while True:
        batch = await asyncio.to_thread(
            lambda: client.beta.vector_stores.file_batches.retrieve(
                vector_store_id=vector_store_id, batch_id=batch_id
            )
        )
        status = getattr(batch, "status", "unknown")
        if status in {"completed", "succeeded"}:
            return
        if status in {"failed", "cancelled"}:
            raise HTTPException(
                status_code=500,
                detail=f"Vector store ingestion failed with status: {status}",
            )
        if datetime.utcnow().timestamp() > deadline:
            raise HTTPException(
                status_code=504,
                detail="Timed out while waiting for vector store ingestion to complete",
            )
        await asyncio.sleep(2)


async def persist_upload(
    upload: UploadFile, destination_dir: Path
) -> tuple[Path, int, str]:
    """Persist an uploaded file to disk enforcing security checks."""

    destination_dir.mkdir(parents=True, exist_ok=True)

    sanitized_name = os.path.basename(upload.filename or "")
    if not sanitized_name:
        raise HTTPException(status_code=400, detail="Uploaded file must have a name")

    temp_path = destination_dir / f"{datetime.utcnow().timestamp()}_{sanitized_name}"
    size = 0

    with temp_path.open("wb") as buffer:
        while True:
            chunk = await upload.read(4 * 1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_FILE_SIZE_BYTES:
                buffer.close()
                temp_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=400,
                    detail="File exceeds the 100 MB limit",
                )
            buffer.write(chunk)

    if size == 0:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    if not is_allowed_mime_type(sanitized_name):
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="File type is not supported")

    return temp_path, size, sanitized_name


def is_allowed_mime_type(filename: str) -> bool:
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type is None:
        return False
    return mime_type in settings.GOOGLE_ALLOWED_MIME_TYPES


async def ingest_file(
    client: OpenAI, vector_store_name: str, file_path: Path, original_filename: str
) -> tuple[StoredFile, str]:
    record = await create_vector_store_if_needed(client, vector_store_name)
    filename = os.path.basename(original_filename)

    await remove_existing_file(client, record.vector_store_id, filename)

    stored = await upload_file_to_openai(
        client=client,
        vector_store_id=record.vector_store_id,
        file_path=file_path,
        filename=filename,
    )

    await REGISTRY.update_file(vector_store_name, stored)
    return stored, record.vector_store_id
