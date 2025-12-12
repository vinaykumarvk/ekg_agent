"""
SQLite-based Task Store for async question processing.

Stores tasks with their status and results, enabling:
- Submit questions without waiting for answers
- Check status of pending tasks
- Retrieve completed answers later
- List all tasks

Features:
- Local SQLite for fast operations
- GCS backup for persistence across Cloud Run cold starts
- Automatic sync on startup and after writes
"""

import sqlite3
import json
import uuid
import threading
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

log = logging.getLogger("ekg_agent")


class TaskStore:
    """Thread-safe SQLite task store with GCS backup for Cloud Run persistence."""
    
    # Task statuses
    STATUS_QUEUED = "queued"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    
    def __init__(self, db_path: str = None, gcs_path: str = None):
        """
        Initialize the task store.
        
        Args:
            db_path: Path to local SQLite database file. 
                     Defaults to /tmp/ekg_tasks.db
            gcs_path: GCS path for backup (e.g., gs://bucket/tasks/ekg_tasks.db)
                     If provided, syncs with GCS on startup and after writes.
                     Defaults to TASK_STORE_GCS_PATH env var.
        """
        # Local database path
        if db_path is None:
            db_path = "/tmp/ekg_tasks.db"
        
        self.db_path = db_path
        self.gcs_path = gcs_path or os.getenv("TASK_STORE_GCS_PATH")
        self._local = threading.local()
        self._gcs_client = None
        self._sync_lock = threading.Lock()
        
        # Download from GCS if available (cold start recovery)
        if self.gcs_path:
            self._download_from_gcs()
        
        self._init_db()
        log.info(f"TaskStore initialized at: {self.db_path}" + 
                 (f" (GCS backup: {self.gcs_path})" if self.gcs_path else " (local only)"))
    
    def _get_gcs_client(self):
        """Get or create GCS client."""
        if self._gcs_client is None:
            try:
                from google.cloud import storage
                self._gcs_client = storage.Client()
            except ImportError:
                log.warning("google-cloud-storage not installed, GCS backup disabled")
                self.gcs_path = None
            except Exception as e:
                log.warning(f"Failed to create GCS client: {e}")
                self.gcs_path = None
        return self._gcs_client
    
    def _parse_gcs_path(self) -> tuple:
        """Parse GCS path into bucket and blob name."""
        if not self.gcs_path or not self.gcs_path.startswith("gs://"):
            return None, None
        path_parts = self.gcs_path[5:].split("/", 1)
        if len(path_parts) != 2:
            return None, None
        return path_parts[0], path_parts[1]
    
    def _download_from_gcs(self):
        """Download database from GCS on cold start."""
        if not self.gcs_path:
            return
        
        bucket_name, blob_name = self._parse_gcs_path()
        if not bucket_name:
            return
        
        try:
            client = self._get_gcs_client()
            if not client:
                return
            
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            if blob.exists():
                blob.download_to_filename(self.db_path)
                log.info(f"Downloaded task database from GCS: {self.gcs_path}")
            else:
                log.info(f"No existing task database in GCS, starting fresh")
        except Exception as e:
            log.warning(f"Failed to download from GCS: {e}")
    
    def _upload_to_gcs(self):
        """Upload database to GCS (called after writes)."""
        if not self.gcs_path:
            return
        
        bucket_name, blob_name = self._parse_gcs_path()
        if not bucket_name:
            return
        
        # Use lock to prevent concurrent uploads
        if not self._sync_lock.acquire(blocking=False):
            return  # Skip if another upload is in progress
        
        try:
            client = self._get_gcs_client()
            if not client:
                return
            
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            blob.upload_from_filename(self.db_path)
            log.debug(f"Uploaded task database to GCS: {self.gcs_path}")
        except Exception as e:
            log.warning(f"Failed to upload to GCS: {e}")
        finally:
            self._sync_lock.release()
    
    def _upload_to_gcs_async(self):
        """Upload to GCS in background thread."""
        if not self.gcs_path:
            return
        thread = threading.Thread(target=self._upload_to_gcs, daemon=True)
        thread.start()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                question TEXT NOT NULL,
                domain TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                result TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            )
        """)
        # Index for faster status queries
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_status 
            ON tasks(status, created_at DESC)
        """)
        conn.commit()
    
    def create_task(
        self,
        question: str,
        domain: str,
        mode: str = "balanced"
    ) -> str:
        """
        Create a new task and return its ID.
        
        Args:
            question: The user's question
            domain: Domain (e.g., 'wealth_management')
            mode: Answer mode ('concise', 'balanced', 'deep')
            
        Returns:
            task_id: Unique identifier for the task
        """
        task_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        conn = self._get_connection()
        conn.execute(
            """
            INSERT INTO tasks (task_id, question, domain, mode, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, question, domain, mode, self.STATUS_QUEUED, now, now)
        )
        conn.commit()
        
        # Sync to GCS in background
        self._upload_to_gcs_async()
        
        log.info(f"Task created: {task_id} - {question[:50]}...")
        return task_id
    
    def update_status(
        self,
        task_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        Update task status and optionally set result or error.
        
        Args:
            task_id: Task identifier
            status: New status
            result: Result dict (for completed tasks)
            error: Error message (for failed tasks)
            
        Returns:
            True if task was updated, False if not found
        """
        now = datetime.utcnow().isoformat()
        completed_at = now if status in (self.STATUS_COMPLETED, self.STATUS_FAILED) else None
        
        result_json = json.dumps(result) if result else None
        
        conn = self._get_connection()
        cursor = conn.execute(
            """
            UPDATE tasks 
            SET status = ?, result = ?, error = ?, updated_at = ?, completed_at = ?
            WHERE task_id = ?
            """,
            (status, result_json, error, now, completed_at, task_id)
        )
        conn.commit()
        
        updated = cursor.rowcount > 0
        if updated:
            log.info(f"Task {task_id} updated to status: {status}")
            # Sync to GCS in background
            self._upload_to_gcs_async()
        return updated
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get task by ID.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Task dict or None if not found
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM tasks WHERE task_id = ?",
            (task_id,)
        )
        row = cursor.fetchone()
        
        if row is None:
            return None
        
        task = dict(row)
        # Parse result JSON
        if task.get('result'):
            try:
                task['result'] = json.loads(task['result'])
            except json.JSONDecodeError:
                pass
        
        return task
    
    def list_tasks(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List tasks, optionally filtered by status.
        
        Args:
            status: Filter by status (optional)
            limit: Max tasks to return
            offset: Pagination offset
            
        Returns:
            List of task dicts (without full results for efficiency)
        """
        conn = self._get_connection()
        
        if status:
            cursor = conn.execute(
                """
                SELECT task_id, question, domain, mode, status, error, 
                       created_at, updated_at, completed_at
                FROM tasks 
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (status, limit, offset)
            )
        else:
            cursor = conn.execute(
                """
                SELECT task_id, question, domain, mode, status, error,
                       created_at, updated_at, completed_at
                FROM tasks 
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset)
            )
        
        return [dict(row) for row in cursor.fetchall()]
    
    def delete_task(self, task_id: str) -> bool:
        """
        Delete a task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            True if deleted, False if not found
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "DELETE FROM tasks WHERE task_id = ?",
            (task_id,)
        )
        conn.commit()
        
        deleted = cursor.rowcount > 0
        if deleted:
            self._upload_to_gcs_async()
        return deleted
    
    def cleanup_old_tasks(self, days: int = 7) -> int:
        """
        Delete tasks older than specified days.
        
        Args:
            days: Delete tasks older than this many days
            
        Returns:
            Number of tasks deleted
        """
        from datetime import timedelta
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        
        conn = self._get_connection()
        cursor = conn.execute(
            "DELETE FROM tasks WHERE created_at < ?",
            (cutoff,)
        )
        conn.commit()
        
        deleted = cursor.rowcount
        if deleted > 0:
            log.info(f"Cleaned up {deleted} tasks older than {days} days")
            self._upload_to_gcs_async()
        return deleted
    
    def get_stats(self) -> Dict[str, int]:
        """Get task statistics."""
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT status, COUNT(*) as count
            FROM tasks
            GROUP BY status
        """)
        
        stats = {row['status']: row['count'] for row in cursor.fetchall()}
        stats['total'] = sum(stats.values())
        return stats


# Global task store instance
_task_store: Optional[TaskStore] = None


def get_task_store() -> TaskStore:
    """Get or create the global task store instance."""
    global _task_store
    if _task_store is None:
        _task_store = TaskStore()
    return _task_store
