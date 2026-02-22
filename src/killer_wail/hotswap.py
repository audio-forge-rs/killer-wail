"""Hot-swap Orca-c program files from outside the TUI.

Since Orca-c reads its file only at startup or when the user explicitly
opens a file (Ctrl+O), hot-swapping works in two steps:

1. Overwrite the .orca file on disk (atomic via temp file + rename)
2. Send Ctrl+O → Enter to Orca-c via tmux to trigger a reload

This module handles both the file operations and the reload trigger.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from killer_wail.session import trigger_reload


class HotswapError(Exception):
    """Raised when a hot-swap operation fails."""


def validate_orca_file(path: Path) -> None:
    """Basic validation that a file looks like an orca program.

    Orca files are plain text grids. We check:
    - File exists and is readable
    - File is not empty
    - All lines have consistent length (rectangular grid)
    """
    if not path.exists():
        raise HotswapError(f"File not found: {path}")
    if not path.is_file():
        raise HotswapError(f"Not a file: {path}")

    content = path.read_text()
    if not content.strip():
        raise HotswapError(f"File is empty: {path}")

    lines = content.rstrip("\n").split("\n")
    lengths = {len(line) for line in lines}
    if len(lengths) > 1:
        raise HotswapError(
            f"Orca grid is not rectangular: line lengths vary {sorted(lengths)} "
            f"in {path}"
        )


def atomic_copy(src: Path, dst: Path) -> None:
    """Atomically replace dst with contents of src.

    Uses write-to-temp-then-rename to avoid Orca-c reading a partially
    written file.
    """
    dst_dir = dst.parent
    dst_dir.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=dst_dir, suffix=".orca.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(src.read_text())
        os.replace(tmp_path, dst)
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def swap(
    source: Path,
    target: Path,
    session_name: str = "orca",
    validate: bool = True,
    settle_ms: int = 80,
) -> None:
    """Hot-swap an orca file and trigger reload.

    Args:
        source: New .orca file to load
        target: The .orca file Orca-c currently has open
        session_name: tmux session name for Orca-c
        validate: Whether to validate the source file first
        settle_ms: ms to wait for Orca dialog between keystrokes
    """
    source = Path(source).resolve()
    target = Path(target).resolve()

    if validate:
        validate_orca_file(source)

    # If source and target are the same file, just trigger reload
    if source != target:
        atomic_copy(source, target)

    trigger_reload(session_name=session_name, settle_ms=settle_ms)


def swap_content(
    content: str,
    target: Path,
    session_name: str = "orca",
    settle_ms: int = 80,
) -> None:
    """Write content directly to the target file and trigger reload.

    Useful for programmatically generated patterns.
    """
    target = Path(target).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=target.parent, suffix=".orca.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(tmp_path, target)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    trigger_reload(session_name=session_name, settle_ms=settle_ms)
