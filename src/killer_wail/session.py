"""Tmux session management for Orca-c.

Orca-c has no IPC, no file watching, and no external control mechanism.
The only way to interact with it programmatically is by running it inside
a tmux session and using `tmux send-keys` to simulate keystrokes.

This module manages the tmux session lifecycle: start, stop, status, and
sending keystrokes to trigger file reloads.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


SESSION_NAME = "orca"
DEFAULT_BPM = 120


class SessionError(Exception):
    """Raised when a tmux session operation fails."""


@dataclass
class SessionConfig:
    """Configuration for an Orca-c tmux session."""

    orca_bin: str = "orca"
    session_name: str = SESSION_NAME
    bpm: int = DEFAULT_BPM
    strict_timing: bool = True
    file_path: Path | None = None

    def orca_command(self) -> list[str]:
        """Build the orca command line."""
        cmd = [self.orca_bin]
        if self.bpm != DEFAULT_BPM:
            cmd.extend(["--bpm", str(self.bpm)])
        if self.strict_timing:
            cmd.append("--strict-timing")
        if self.file_path:
            cmd.append(str(self.file_path))
        return cmd


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a subprocess, capturing output."""
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def require_tmux() -> str:
    """Verify tmux is installed and return its path."""
    path = shutil.which("tmux")
    if not path:
        raise SessionError("tmux is not installed. Install with: brew install tmux")
    return path


def is_running(session_name: str = SESSION_NAME) -> bool:
    """Check if the orca tmux session exists."""
    result = _run(["tmux", "has-session", "-t", session_name], check=False)
    return result.returncode == 0


def start(config: SessionConfig | None = None) -> None:
    """Start Orca-c in a new tmux session.

    Raises SessionError if session already exists or orca binary not found.
    """
    require_tmux()
    config = config or SessionConfig()

    if is_running(config.session_name):
        raise SessionError(
            f"Session '{config.session_name}' already running. "
            "Stop it first with: kw stop"
        )

    orca_path = shutil.which(config.orca_bin)
    if not orca_path:
        raise SessionError(
            f"Orca binary '{config.orca_bin}' not found in PATH. "
            "Build Orca-c and add it to your PATH."
        )

    if config.file_path and not config.file_path.exists():
        raise SessionError(f"Orca file not found: {config.file_path}")

    orca_cmd = " ".join(config.orca_command())
    _run([
        "tmux", "new-session",
        "-d",                           # detached
        "-s", config.session_name,      # session name
        orca_cmd,                       # command to run
    ])

    # Give orca a moment to start up
    time.sleep(0.3)

    if not is_running(config.session_name):
        raise SessionError("Orca-c session failed to start. Check your orca binary.")


def stop(session_name: str = SESSION_NAME) -> None:
    """Kill the orca tmux session."""
    if not is_running(session_name):
        raise SessionError(f"No session '{session_name}' to stop.")
    _run(["tmux", "kill-session", "-t", session_name])


def send_keys(keys: str, session_name: str = SESSION_NAME) -> None:
    """Send keystrokes to the orca tmux session.

    Args:
        keys: tmux key string (e.g. "C-o" for Ctrl+O, "Enter", literal text)
        session_name: tmux session name
    """
    if not is_running(session_name):
        raise SessionError(f"No session '{session_name}' running.")
    _run(["tmux", "send-keys", "-t", session_name, keys])


def trigger_reload(session_name: str = SESSION_NAME, settle_ms: int = 80) -> None:
    """Trigger Orca-c to reload its current file from disk.

    Sends Ctrl+O (open file dialog) then Enter (accept pre-filled filename).
    Orca-c's open dialog pre-populates with the current filename, so pressing
    Enter immediately re-reads the file from disk.

    Args:
        session_name: tmux session name
        settle_ms: milliseconds to wait between keystrokes for dialog to appear
    """
    if not is_running(session_name):
        raise SessionError(f"No session '{session_name}' running.")

    # Ctrl+O opens file dialog (pre-filled with current filename)
    send_keys("C-o", session_name)
    time.sleep(settle_ms / 1000.0)
    # Enter accepts the current filename, triggering reload from disk
    send_keys("Enter", session_name)


def status(session_name: str = SESSION_NAME) -> dict:
    """Get session status info."""
    running = is_running(session_name)
    info = {"running": running, "session_name": session_name}
    if running:
        result = _run(
            ["tmux", "display-message", "-t", session_name, "-p",
             "#{pane_current_command} #{pane_width}x#{pane_height}"],
            check=False,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(" ", 1)
            info["command"] = parts[0] if parts else "unknown"
            info["size"] = parts[1] if len(parts) > 1 else "unknown"
    return info
