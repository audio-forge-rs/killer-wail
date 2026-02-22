"""CLI for killer-wail: Orca-c → Bitwig hot-swap orchestrator.

Usage:
    kw start [FILE] [--bpm N]     Start Orca-c in a tmux session
    kw stop                        Stop the Orca-c session
    kw status                      Show session status
    kw swap FILE                   Hot-swap an .orca file into the running session
    kw watch [PATH]                Watch for file changes and auto-reload
    kw channels [--init]           Show or initialize the channel map
    kw scan FILE                   Scan an .orca file for MIDI channel usage
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from killer_wail.session import (
    SessionConfig,
    SessionError,
    is_running,
    start,
    status,
    stop,
)
from killer_wail.hotswap import HotswapError, swap, validate_orca_file
from killer_wail.midi import ChannelMap, default_channel_map, scan_file

DEFAULT_CHANNEL_MAP = Path("channels.yml")
DEFAULT_ORCA_DIR = Path("src/orca")


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        stream=sys.stderr,
    )



@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.pass_context
def main(ctx: click.Context, verbose: bool) -> None:
    """killer-wail: Orca-c → Bitwig hot-swap orchestrator."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    _setup_logging(verbose)


@main.command()
@click.argument("file", required=False, type=click.Path(exists=True, path_type=Path))
@click.option("--bpm", default=120, help="Tempo in BPM (default: 120)")
@click.option("--session", default="orca", help="Tmux session name")
@click.option("--orca-bin", default="orca", help="Path to orca binary")
def start_cmd(
    file: Path | None,
    bpm: int,
    session: str,
    orca_bin: str,
) -> None:
    """Start Orca-c in a tmux session."""
    config = SessionConfig(
        orca_bin=orca_bin,
        session_name=session,
        bpm=bpm,
        file_path=file,
    )
    try:
        start(config)
        click.echo(f"Orca-c started in tmux session '{session}'")
        if file:
            click.echo(f"File: {file}")
        click.echo(f"BPM: {bpm}")
        click.echo(f"Attach with: tmux attach -t {session}")
    except SessionError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@main.command("stop")
@click.option("--session", default="orca", help="Tmux session name")
def stop_cmd(session: str) -> None:
    """Stop the Orca-c tmux session."""
    try:
        stop(session)
        click.echo(f"Stopped session '{session}'")
    except SessionError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@main.command()
@click.option("--session", default="orca", help="Tmux session name")
def status_cmd(session: str) -> None:
    """Show Orca-c session status."""
    info = status(session)
    if info["running"]:
        click.echo(f"Session '{session}': running")
        click.echo(f"  Command: {info.get('command', 'unknown')}")
        click.echo(f"  Size: {info.get('size', 'unknown')}")
    else:
        click.echo(f"Session '{session}': not running")


@main.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("--target", "-t", type=click.Path(path_type=Path), help="Target .orca file in running session")
@click.option("--session", default="orca", help="Tmux session name")
@click.option("--no-validate", is_flag=True, help="Skip file validation")
def swap_cmd(file: Path, target: Path | None, session: str, no_validate: bool) -> None:
    """Hot-swap an .orca file into the running Orca-c session."""
    if not target:
        # If source and target are the same, just reload
        target = file

    try:
        if not no_validate:
            validate_orca_file(file)
        swap(file, target, session_name=session, validate=not no_validate)
        click.echo(f"Swapped: {file} → reloaded in session '{session}'")
    except (HotswapError, SessionError) as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@main.command()
@click.argument("path", required=False, type=click.Path(exists=True, path_type=Path))
@click.option("--session", default="orca", help="Tmux session name")
def watch_cmd(path: Path | None, session: str) -> None:
    """Watch for .orca file changes and auto-reload Orca-c.

    PATH can be a specific .orca file or a directory. Defaults to src/orca/.
    """
    from killer_wail.watcher import watch_blocking

    if not path:
        path = DEFAULT_ORCA_DIR
        if not path.exists():
            path = Path(".")

    if not is_running(session):
        click.echo(f"Warning: session '{session}' not running. Start it first: kw start", err=True)

    click.echo(f"Watching {path} for changes (Ctrl+C to stop)")
    watch_blocking(path, session_name=session)


@main.command()
@click.option("--init", is_flag=True, help="Create a default channels.yml")
@click.option("--file", "-f", default=str(DEFAULT_CHANNEL_MAP), help="Channel map file path")
def channels(init: bool, file: str) -> None:
    """Show or initialize the MIDI channel map."""
    path = Path(file)

    if init:
        if path.exists():
            click.echo(f"Channel map already exists: {path}", err=True)
            raise SystemExit(1)
        cmap = default_channel_map()
        cmap.save(path)
        click.echo(f"Created default channel map: {path}")
        click.echo("Edit it to match your Bitwig track layout.")
        return

    if not path.exists():
        click.echo(f"No channel map found at {path}. Create one with: kw channels --init", err=True)
        raise SystemExit(1)

    cmap = ChannelMap.load(path)
    click.echo("Channel Map:")
    click.echo("-" * 40)
    for m in cmap.mappings:
        click.echo(f"  {m}")


@main.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("--channels-file", "-c", default=str(DEFAULT_CHANNEL_MAP), help="Channel map file")
def scan(file: Path, channels_file: str) -> None:
    """Scan an .orca file for MIDI channel usage."""
    used = scan_file(file)

    if not used:
        click.echo(f"{file.name}: no MIDI channels detected")
        return

    # Try to load channel map for labels
    cmap = None
    cmap_path = Path(channels_file)
    if cmap_path.exists():
        cmap = ChannelMap.load(cmap_path)

    click.echo(f"{file.name}: uses {len(used)} MIDI channel(s)")
    for ch in sorted(used):
        label = ""
        if cmap:
            mapping = cmap.by_channel(ch)
            if mapping:
                label = f" → {mapping.name}"
        click.echo(f"  ch{ch} ({format(ch, 'x')}){label}")


# Register subcommands with proper names
main.add_command(start_cmd, "start")
main.add_command(status_cmd, "status")
