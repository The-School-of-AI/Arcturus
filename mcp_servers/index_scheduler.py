"""
RAG Index Scheduler - Cross-platform file watching and indexing queue management.

This module provides:
- Real-time file system watching via watchdog (works on Linux/Windows/macOS)
- Priority-based indexing queue
- Atomic ledger management for tracking indexed files
- 30-minute reconciliation as backup to catch missed changes
"""

import json
import hashlib
import queue
import threading
import time
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, field, asdict


def _log(msg: str):
    """Log to stderr to avoid breaking MCP JSON-RPC protocol."""
    print(msg, file=sys.stderr)


try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent, FileDeletedEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = object


# =============================================================================
# LEDGER MANAGEMENT
# =============================================================================

@dataclass
class FileEntry:
    """Represents a file's indexing status in the ledger."""
    hash: Optional[str] = None
    status: str = "pending"  # pending | indexing | complete | error
    indexed_at: Optional[str] = None
    chunk_count: int = 0
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "FileEntry":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class IndexLedger:
    """
    Manages the indexing ledger with atomic save operations.
    
    The ledger tracks:
    - Which files have been indexed
    - Their content hashes (to detect modifications)
    - Their indexing status (pending/indexing/complete/error)
    - When they were last indexed
    """
    
    VERSION = 2
    
    def __init__(self, ledger_path: Path):
        self.path = ledger_path
        self.lock = threading.RLock()
        self._data: Dict[str, Any] = {
            "version": self.VERSION,
            "last_reconcile": None,
            "files": {}
        }
        self._load()
    
    def _load(self):
        """Load ledger from disk, with migration from old cache format."""
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                if data.get("version") == self.VERSION:
                    self._data = data
                else:
                    # Future version migration would go here
                    self._data = data
            except Exception as e:
                _log(f"[IndexLedger] Failed to load ledger: {e}")
        else:
            # Check for old cache file and migrate
            old_cache = self.path.parent / "doc_index_cache.json"
            if old_cache.exists():
                self._migrate_from_old_cache(old_cache)
    
    def _migrate_from_old_cache(self, old_path: Path):
        """Migrate from legacy doc_index_cache.json format."""
        try:
            old_data = json.loads(old_path.read_text())
            # Old format: {"path": "hash", ...}
            for rel_path, file_hash in old_data.items():
                self._data["files"][rel_path] = FileEntry(
                    hash=file_hash,
                    status="complete",
                    indexed_at=datetime.utcnow().isoformat() + "Z",
                    chunk_count=0  # Unknown from old format
                ).to_dict()
            self._save()
            _log(f"[IndexLedger] Migrated {len(old_data)} entries from legacy cache")
            # Rename old file as backup
            old_path.rename(old_path.with_suffix(".json.bak"))
        except Exception as e:
            _log(f"[IndexLedger] Migration failed: {e}")
    
    def _save(self):
        """Atomically save ledger to disk using temp file + rename pattern."""
        tmp_path = self.path.with_suffix('.tmp')
        try:
            tmp_path.write_text(json.dumps(self._data, indent=2))
            tmp_path.replace(self.path)  # Atomic on all platforms
        except Exception as e:
            _log(f"[IndexLedger] Save failed: {e}")
            if tmp_path.exists():
                tmp_path.unlink()
    
    def get(self, rel_path: str) -> Optional[FileEntry]:
        """Get entry for a file path."""
        with self.lock:
            data = self._data["files"].get(rel_path)
            return FileEntry.from_dict(data) if data else None
    
    def set(self, rel_path: str, entry: FileEntry):
        """Set entry for a file path and save."""
        with self.lock:
            self._data["files"][rel_path] = entry.to_dict()
            self._save()
    
    def remove(self, rel_path: str):
        """Remove entry for a file path and save."""
        with self.lock:
            if rel_path in self._data["files"]:
                del self._data["files"][rel_path]
                self._save()
    
    def set_status(self, rel_path: str, status: str, error: Optional[str] = None):
        """Update just the status of a file."""
        with self.lock:
            if rel_path in self._data["files"]:
                self._data["files"][rel_path]["status"] = status
                if error is not None:
                    self._data["files"][rel_path]["error"] = error
                self._save()
    
    def mark_complete(self, rel_path: str, file_hash: str, chunk_count: int):
        """Mark a file as successfully indexed."""
        with self.lock:
            self._data["files"][rel_path] = FileEntry(
                hash=file_hash,
                status="complete",
                indexed_at=datetime.utcnow().isoformat() + "Z",
                chunk_count=chunk_count,
                error=None
            ).to_dict()
            self._save()
    
    def mark_pending(self, rel_path: str):
        """Mark a file as pending indexing."""
        with self.lock:
            existing = self._data["files"].get(rel_path, {})
            self._data["files"][rel_path] = FileEntry(
                hash=existing.get("hash"),
                status="pending",
                indexed_at=existing.get("indexed_at"),
                chunk_count=existing.get("chunk_count", 0),
                error=None
            ).to_dict()
            self._save()
    
    def mark_error(self, rel_path: str, error: str):
        """Mark a file as failed to index."""
        with self.lock:
            existing = self._data["files"].get(rel_path, {})
            self._data["files"][rel_path] = FileEntry(
                hash=existing.get("hash"),
                status="error",
                indexed_at=existing.get("indexed_at"),
                chunk_count=existing.get("chunk_count", 0),
                error=error
            ).to_dict()
            self._save()
    
    def update_reconcile_time(self):
        """Update the last reconciliation timestamp."""
        with self.lock:
            self._data["last_reconcile"] = datetime.utcnow().isoformat() + "Z"
            self._save()
    
    def all_files(self) -> Dict[str, FileEntry]:
        """Get all file entries."""
        with self.lock:
            return {
                path: FileEntry.from_dict(data) 
                for path, data in self._data["files"].items()
            }
    
    def get_by_status(self, status: str) -> Dict[str, FileEntry]:
        """Get all files with a specific status."""
        with self.lock:
            return {
                path: FileEntry.from_dict(data)
                for path, data in self._data["files"].items()
                if data.get("status") == status
            }
    
    def needs_indexing(self, rel_path: str, current_hash: str) -> bool:
        """Check if a file needs (re)indexing based on hash comparison."""
        with self.lock:
            entry = self._data["files"].get(rel_path)
            if not entry:
                return True  # New file
            if entry.get("status") in ("pending", "error"):
                return True  # Previously failed or pending
            if entry.get("hash") != current_hash:
                return True  # Content changed
            return False


# =============================================================================
# FILE SYSTEM WATCHER
# =============================================================================

class DataDirHandler(FileSystemEventHandler):
    """
    Watchdog event handler that queues file system events for processing.
    
    Filters out:
    - Hidden files/directories (starting with .)
    - System directories (__pycache__, .git, etc.)
    - Index directory itself
    """
    
    def __init__(self, scheduler: "IndexScheduler"):
        super().__init__()
        self.scheduler = scheduler
    
    def _should_skip(self, path: str) -> bool:
        """Check if path should be ignored."""
        path_obj = Path(path)
        
        # Skip hidden files/folders
        if path_obj.name.startswith('.'):
            return True
        
        # Skip by extension
        if path_obj.suffix.lower() in self.scheduler.SKIP_EXTENSIONS:
            return True
        
        # Skip directories in skip list
        parts = path_obj.parts
        for part in parts:
            if part in self.scheduler.SKIP_DIRS:
                return True
        
        return False
    
    def _get_rel_path(self, abs_path: str) -> Optional[str]:
        """Convert absolute path to relative path from data directory."""
        try:
            return str(Path(abs_path).relative_to(self.scheduler.data_dir))
        except ValueError:
            return None
    
    def on_created(self, event):
        if event.is_directory or self._should_skip(event.src_path):
            return
        
        rel_path = self._get_rel_path(event.src_path)
        if rel_path:
            _log(f"[Watcher] File created: {rel_path}")
            self.scheduler.enqueue(rel_path, "index", priority=2)
    
    def on_modified(self, event):
        if event.is_directory or self._should_skip(event.src_path):
            return
        
        rel_path = self._get_rel_path(event.src_path)
        if rel_path:
            _log(f"[Watcher] File modified: {rel_path}")
            self.scheduler.enqueue(rel_path, "index", priority=3)
    
    def on_deleted(self, event):
        if event.is_directory or self._should_skip(event.src_path):
            return
        
        rel_path = self._get_rel_path(event.src_path)
        if rel_path:
            _log(f"[Watcher] File deleted: {rel_path}")
            self.scheduler.enqueue(rel_path, "delete", priority=1)


# =============================================================================
# INDEX SCHEDULER
# =============================================================================

@dataclass(order=True)
class IndexJob:
    """A job in the indexing queue."""
    priority: int
    path: str = field(compare=False)
    action: str = field(compare=False)  # "index" | "delete"
    timestamp: float = field(default_factory=time.time, compare=False)


class IndexScheduler:
    """
    Central scheduler for RAG document indexing.
    
    Manages:
    - File system watching for real-time change detection
    - Priority queue for indexing jobs
    - Worker thread for processing jobs
    - Periodic reconciliation (30 min) as backup
    
    Usage:
        scheduler = IndexScheduler(data_dir, index_dir)
        scheduler.start()
        
        # Queue files manually
        scheduler.enqueue("docs/file.pdf", "index", priority=3)
        
        # Trigger full scan
        scheduler.trigger_full_scan()
        
        # Shutdown
        scheduler.stop()
    """
    
    RECONCILE_INTERVAL = 1800  # 30 minutes
    DEBOUNCE_SECONDS = 300.0  # Wait 5m of silence before indexing
    
    # File extensions to skip during scanning
    SKIP_EXTENSIONS = {
        '.mp4', '.mov', '.wav', '.mp3', 
        '.bin', '.exe', '.pyc', '.pyo', '.swp', '.tmp', '.lock'
    }
    SKIP_DIRS = {
        '.git', '.github', 'node_modules', '__pycache__', 
        'mcp_repos', 'faiss_index', '.DS_Store'
    }
    
    def __init__(
        self, 
        data_dir: Path, 
        index_dir: Path,
        process_callback: Optional[Callable] = None,
        delete_callback: Optional[Callable] = None
    ):
        self.data_dir = Path(data_dir)
        self.index_dir = Path(index_dir)
        self.ledger = IndexLedger(index_dir / "ledger.json")
        
        # Callbacks for actual indexing work
        self.process_callback = process_callback
        self.delete_callback = delete_callback
        
        # Queue and threading
        self.queue: queue.PriorityQueue[IndexJob] = queue.PriorityQueue()
        self.stop_event = threading.Event()
        self.worker_thread: Optional[threading.Thread] = None
        self.reconciler_thread: Optional[threading.Thread] = None
        self.debouncer_thread: Optional[threading.Thread] = None
        self.observer: Optional[Observer] = None
        
        # Debounce tracking
        self.pending_debounce: Dict[str, float] = {}  # rel_path -> deadline_timestamp
        self._debounce_lock = threading.Lock()
        
        # Status tracking
        self._status_lock = threading.Lock()
        self._current_file: Optional[str] = None
        self._queue_size: int = 0
        self._processed_count: int = 0
        self._active: bool = False
    
    def start(self):
        """Start the scheduler (watcher, worker, debouncer, reconciler)."""
        _log("[Scheduler] Starting RAG Index Scheduler...")
        
        self.stop_event.clear()
        self._active = True
        
        # Start file watcher
        if WATCHDOG_AVAILABLE:
            self._start_watcher()
        else:
            _log("[Scheduler] WARNING: watchdog not installed, file watching disabled")
        
        # Start worker thread
        self._start_worker()
        
        # Start debouncer thread
        self._start_debouncer()
        
        # Start reconciler thread
        self._start_reconciler()
        
        _log("[Scheduler] All services started")
    
    def stop(self):
        """Stop all scheduler threads gracefully."""
        _log("[Scheduler] Stopping...")
        self.stop_event.set()
        self._active = False
        
        # Stop watcher
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)
        
        # Wake up worker to exit
        self.queue.put(IndexJob(priority=0, path="", action="shutdown"))
        
        # Wait for threads
        if self.worker_thread:
            self.worker_thread.join(timeout=10)
        if self.reconciler_thread:
            self.reconciler_thread.join(timeout=5)
        if self.debouncer_thread:
            self.debouncer_thread.join(timeout=5)
            
        # Process anything currently pending in debounce?
        # Ideally we might flush them, but for now we'll let them drop to avoid partial state issues.
        
        _log("[Scheduler] Stopped")
    
    def _start_watcher(self):
        """Start the file system watcher."""
        if not WATCHDOG_AVAILABLE:
            return
        
        try:
            handler = DataDirHandler(self)
            self.observer = Observer()
            self.observer.schedule(handler, str(self.data_dir), recursive=True)
            self.observer.start()
            _log(f"[Scheduler] File watcher started on {self.data_dir}")
        except Exception as e:
            _log(f"[Scheduler] Failed to start file watcher: {e}")
    
    def _start_worker(self):
        """Start the worker thread that processes the queue."""
        def worker_loop():
            while not self.stop_event.is_set():
                try:
                    job = self.queue.get(timeout=1)
                    
                    if job.action == "shutdown":
                        break
                    
                    with self._status_lock:
                        self._current_file = job.path
                    
                    self._process_job(job)
                    
                    with self._status_lock:
                        self._current_file = None
                        self._processed_count += 1
                    
                    self.queue.task_done()
                    
                except queue.Empty:
                    continue
                except Exception as e:
                    _log(f"[Worker] Error processing job: {e}")
        
        self.worker_thread = threading.Thread(target=worker_loop, daemon=True, name="IndexWorker")
        self.worker_thread.start()
        _log("[Scheduler] Worker thread started")

    def _start_debouncer(self):
        """Start the thread that manages debounced indexing jobs."""
        def debouncer_loop():
            while not self.stop_event.is_set():
                time.sleep(1.0) # Check every second
                
                now = time.time()
                ready_files = []
                
                with self._debounce_lock:
                    # Identify files whose deadline has passed
                    # We iterate a copy of keys to modify dict during iteration if needed
                    for path, deadline in list(self.pending_debounce.items()):
                        if now >= deadline:
                            ready_files.append(path)
                            del self.pending_debounce[path]
                
                # Move ready files to the actual processing queue
                for path in ready_files:
                    _log(f"[Debouncer] Cooldown finished for {path}, queuing job.")
                    # Use priority 5 (default)
                    job = IndexJob(priority=5, path=path, action="index")
                    self.queue.put(job)
                    
                    # Mark as pending in ledger now that it's officially queued
                    self.ledger.mark_pending(path)

        self.debouncer_thread = threading.Thread(target=debouncer_loop, daemon=True, name="Debouncer")
        self.debouncer_thread.start()
        _log(f"[Scheduler] Debouncer started (delay={self.DEBOUNCE_SECONDS}s)")
    
    def _start_reconciler(self):
        """Start the periodic reconciliation thread."""
        def reconcile_loop():
            while not self.stop_event.is_set():
                # Wait for interval or stop signal
                if self.stop_event.wait(self.RECONCILE_INTERVAL):
                    break
                
                _log("[Reconciler] Running periodic reconciliation...")
                self._reconcile()
        
        self.reconciler_thread = threading.Thread(target=reconcile_loop, daemon=True, name="Reconciler")
        self.reconciler_thread.start()
        _log(f"[Scheduler] Reconciler started (every {self.RECONCILE_INTERVAL}s)")
    
    def enqueue(self, rel_path: str, action: str, priority: int = 5):
        """
        Add a file to the indexing queue.
        
        Priority levels:
        - 1: Highest (deletions)
        - 2: File watcher creates
        - 3: File watcher modifies, manual single-file trigger
        - 5: Default (Debounced updates)
        - 8: Reconciler discovered files
        - 10: Lowest
        """
        # Immediate actions (Deletes, or high priority creates if we want)
        # We also skip debounce if priority is explicitly high (e.g. initial scan or manual trigger)
        # But 'modified' events from watcher usually come in as priority 3. 
        # Let's say we debounce 'index' actions unless they are priority 1 or 2 (creates).
        
        if action == "delete":
            # Deletes are always immediate
            job = IndexJob(priority=priority, path=rel_path, action=action)
            self.queue.put(job)
            return

        if action == "index":
            # If it's a "create" (might be priority 2) or manual force, maybe we still want to debounce?
            # Actually, the user's main pain point is modification of existing files.
            # Let's debounce ALL 'index' actions for simplicity and consistency.
            # If you want to force immediate, you'd need a flag, but for now, debounce is safer.
            
            with self._debounce_lock:
                # Set new deadline: now + DEBOUNCE_SECONDS
                deadline = time.time() + self.DEBOUNCE_SECONDS
                self.pending_debounce[rel_path] = deadline
                # _log(f"[Scheduler] Debounced {rel_path} until {datetime.fromtimestamp(deadline).strftime('%H:%M:%S')}")

        with self._status_lock:
            self._queue_size = self.queue.qsize()  # Note: doesn't include pending_debounce items
    
    def trigger_full_scan(self, priority: int = 3):
        """
        Trigger a full filesystem scan and queue any new/modified files.
        Resets the reconciler timer.
        """
        _log("[Scheduler] Full scan triggered")
        count = 0
        
        for rel_path in self._scan_filesystem():
            abs_path = self.data_dir / rel_path
            if abs_path.exists():
                file_hash = self._compute_hash(abs_path)
                if self.ledger.needs_indexing(rel_path, file_hash):
                    # For full scan, we enqueue. This will go through debounce logic.
                    # This is actually GOOD because if a scan happens while user is typing, we won't race.
                    self.enqueue(rel_path, "index", priority=priority)
                    count += 1
        
        # Check for deleted files
        for rel_path in list(self.ledger.all_files().keys()):
            abs_path = self.data_dir / rel_path
            if not abs_path.exists():
                self.enqueue(rel_path, "delete", priority=1)
                count += 1
        
        _log(f"[Scheduler] Queued {count} files for processing")
        return count
    
    def _scan_filesystem(self):
        """Scan data directory and yield relative paths of indexable files."""
        if not self.data_dir.exists():
            return
        
        for root, dirs, files in os.walk(self.data_dir):
            # Filter directories in-place
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS and not d.startswith('.')]
            
            for filename in files:
                if filename.startswith('.'):
                    continue
                
                file_path = Path(root) / filename
                if file_path.suffix.lower() in self.SKIP_EXTENSIONS:
                    continue
                
                try:
                    yield str(file_path.relative_to(self.data_dir))
                except ValueError:
                    continue
    
    def _compute_hash(self, path: Path) -> str:
        """Compute MD5 hash of file contents."""
        try:
            return hashlib.md5(path.read_bytes()).hexdigest()
        except Exception:
            return ""
    
    def _process_job(self, job: IndexJob):
        """Process a single indexing job."""
        if job.action == "delete":
            self._handle_delete(job.path)
        elif job.action == "index":
            self._handle_index(job.path)
    
    def _handle_delete(self, rel_path: str):
        """Handle file deletion - remove from ledger and FAISS."""
        _log(f"[Worker] Deleting: {rel_path}")
        
        try:
            if self.delete_callback:
                self.delete_callback(rel_path)
            self.ledger.remove(rel_path)
        except Exception as e:
            _log(f"[Worker] Delete failed for {rel_path}: {e}")
    
    def _handle_index(self, rel_path: str):
        """Handle file indexing."""
        abs_path = self.data_dir / rel_path
        
        if not abs_path.exists():
            # File was deleted before we could process it
            self.ledger.remove(rel_path)
            return
        
        _log(f"[Worker] Indexing: {rel_path}")
        self.ledger.set_status(rel_path, "indexing")
        
        try:
            file_hash = self._compute_hash(abs_path)
            
            # Check if we actually need to reindex
            entry = self.ledger.get(rel_path)
            if entry and entry.status == "complete" and entry.hash == file_hash:
                _log(f"[Worker] Skipping (unchanged): {rel_path}")
                return
            
            if self.process_callback:
                result = self.process_callback(abs_path, rel_path)
                chunk_count = result.get("chunk_count", 0) if result else 0
            else:
                chunk_count = 0
            
            self.ledger.mark_complete(rel_path, file_hash, chunk_count)
            _log(f"[Worker] Completed: {rel_path} ({chunk_count} chunks)")
            
        except Exception as e:
            error_msg = str(e)[:200]  # Truncate error message
            _log(f"[Worker] Error indexing {rel_path}: {error_msg}")
            self.ledger.mark_error(rel_path, error_msg)
    
    def _reconcile(self):
        """Run reconciliation - compare filesystem to ledger and queue discrepancies."""
        try:
            fs_files = set(self._scan_filesystem())
            ledger_files = set(self.ledger.all_files().keys())
            
            queued = 0
            
            # New files not in ledger
            for f in fs_files - ledger_files:
                self.enqueue(f, "index", priority=8)
                queued += 1
            
            # Deleted files still in ledger
            for f in ledger_files - fs_files:
                self.enqueue(f, "delete", priority=8)
                queued += 1
            
            # Check for modified files
            for f in fs_files & ledger_files:
                abs_path = self.data_dir / f
                if abs_path.exists():
                    current_hash = self._compute_hash(abs_path)
                    if self.ledger.needs_indexing(f, current_hash):
                        self.enqueue(f, "index", priority=8)
                        queued += 1
            
            self.ledger.update_reconcile_time()
            _log(f"[Reconciler] Completed. Queued {queued} files.")
            
        except Exception as e:
            _log(f"[Reconciler] Error: {e}")
    
    def get_status(self) -> dict:
        """Get current scheduler status for API."""
        with self._status_lock:
            pending = len(self.ledger.get_by_status("pending"))
            errors = len(self.ledger.get_by_status("error"))
            
            with self._debounce_lock:
                debouncing_count = len(self.pending_debounce)

            return {
                "active": self._active and (self._current_file is not None or self.queue.qsize() > 0 or debouncing_count > 0),
                "queue_size": self.queue.qsize(),
                "debouncing_files": debouncing_count,
                "current_file": self._current_file or "",
                "processed_count": self._processed_count,
                "pending_files": pending,
                "error_files": errors,
                "total_indexed": len(self.ledger.get_by_status("complete"))
            }
    
    def get_file_status(self, rel_path: str) -> Optional[dict]:
        """Get status of a specific file."""
        entry = self.ledger.get(rel_path)
        if entry:
            return entry.to_dict()
        return None


# =============================================================================
# MODULE-LEVEL SINGLETON
# =============================================================================

_scheduler_instance: Optional[IndexScheduler] = None
_scheduler_lock = threading.Lock()


def get_scheduler() -> Optional[IndexScheduler]:
    """Get the global scheduler instance."""
    return _scheduler_instance


def init_scheduler(data_dir: Path, index_dir: Path, **kwargs) -> IndexScheduler:
    """Initialize and start the global scheduler instance."""
    global _scheduler_instance
    
    with _scheduler_lock:
        if _scheduler_instance is not None:
            _scheduler_instance.stop()
        
        _scheduler_instance = IndexScheduler(data_dir, index_dir, **kwargs)
        _scheduler_instance.start()
    
    return _scheduler_instance


def shutdown_scheduler():
    """Shutdown the global scheduler instance."""
    global _scheduler_instance
    
    with _scheduler_lock:
        if _scheduler_instance:
            _scheduler_instance.stop()
            _scheduler_instance = None

