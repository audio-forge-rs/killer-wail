"""File watcher for auto-reloading Orca-c on .orca file changes.

Uses watchdog to monitor a file or directory. When an .orca file is
modified, triggers a hot-swap reload in the running Orca-c session.

Supports two modes:
- Single file watch: monitors one .orca file for changes
- Directory watch: monitors a directory for any .orca file changes
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer

from killer_wail.session import is_running, trigger_reload

log = logging.getLogger(__name__)

# Debounce: ignore events within this window (seconds)
DEBOUNCE_SECONDS = 0.15


class OrcaReloadHandler(FileSystemEventHandler):
    """Watchdog handler that triggers Orca-c reload on .orca file changes."""

    def __init__(
        self,
        target_file: Path | None = None,
        session_name: str = "orca",
        settle_ms: int = 80,
    ):
        super().__init__()
        self.target_file = target_file.resolve() if target_file else None
        self.session_name = session_name
        self.settle_ms = settle_ms
        self._last_reload = 0.0

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return

        path = Path(str(event.src_path))

        # Only react to .orca files
        if path.suffix != ".orca":
            return

        # If watching a specific file, only react to that file
        if self.target_file and path.resolve() != self.target_file:
            return

        # Debounce: editors often trigger multiple write events
        now = time.monotonic()
        if now - self._last_reload < DEBOUNCE_SECONDS:
            return
        self._last_reload = now

        if not is_running(self.session_name):
            log.warning("Orca session '%s' not running, skipping reload", self.session_name)
            return

        log.info("File changed: %s — reloading Orca-c", path.name)
        try:
            trigger_reload(session_name=self.session_name, settle_ms=self.settle_ms)
        except Exception:
            log.exception("Failed to trigger reload")


def watch(
    path: Path,
    session_name: str = "orca",
    settle_ms: int = 80,
) -> Observer:
    """Start watching a file or directory for .orca changes.

    Args:
        path: File or directory to watch
        session_name: tmux session name for Orca-c
        settle_ms: ms between Ctrl+O and Enter keystrokes

    Returns:
        The running Observer (call .stop() to shut down)
    """
    path = Path(path).resolve()

    if path.is_file():
        watch_dir = path.parent
        target_file = path
    elif path.is_dir():
        watch_dir = path
        target_file = None
    else:
        raise FileNotFoundError(f"Watch target not found: {path}")

    handler = OrcaReloadHandler(
        target_file=target_file,
        session_name=session_name,
        settle_ms=settle_ms,
    )

    observer = Observer()
    observer.schedule(handler, str(watch_dir), recursive=False)
    observer.start()

    what = target_file.name if target_file else f"{watch_dir}/*.orca"
    log.info("Watching %s for changes (session: %s)", what, session_name)

    return observer


def watch_blocking(
    path: Path,
    session_name: str = "orca",
    settle_ms: int = 80,
) -> None:
    """Watch for changes, blocking until KeyboardInterrupt."""
    observer = watch(path, session_name=session_name, settle_ms=settle_ms)
    try:
        while observer.is_alive():
            observer.join(timeout=1.0)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
