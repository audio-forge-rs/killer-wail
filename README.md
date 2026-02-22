# killer-wail

Hot-swap orchestrator for [Orca-c](https://github.com/hundredrabbits/Orca-c) → Bitwig Studio on macOS.

Programmatically swap Orca patterns and auto-reload without touching the TUI. Map MIDI channels to Bitwig tracks for multi-instrument livecoding.

## Why?

Orca-c has **no IPC, no file watching, and no external control**. It reads its file once at startup and only reloads when you manually press Ctrl+O. killer-wail solves this by running Orca-c inside tmux and using `tmux send-keys` to simulate the reload keystrokes. File writes use atomic temp-file-then-rename to prevent Orca from reading partial data.

## Prerequisites

- **macOS** (tested on macOS 15+)
- **tmux** — `brew install tmux`
- **Orca-c** — build from [hundredrabbits/Orca-c](https://github.com/hundredrabbits/Orca-c) and ensure the `orca` binary is in your PATH
- **Python 3.10+**
- **Bitwig Studio** with MIDI input configured

## Install

```bash
pip install -e ".[dev]"
```

This installs the `kw` CLI command.

## Quick Start

```bash
# 1. Start Orca-c in a tmux session with your pattern
kw start src/orca/simple/kick.orca --bpm 120

# 2. Attach to see Orca running (optional)
tmux attach -t orca

# 3. Hot-swap a different pattern (from another terminal)
kw swap src/orca/patterns/four-on-floor.orca

# 4. Or watch a file for auto-reload on save
kw watch src/orca/simple/kick.orca

# 5. Stop when done
kw stop
```

## Commands

| Command | Description |
|---------|-------------|
| `kw start [FILE] [--bpm N]` | Start Orca-c in a tmux session |
| `kw stop` | Stop the Orca-c session |
| `kw status` | Show session status |
| `kw swap FILE [-t TARGET]` | Hot-swap an .orca file into the running session |
| `kw watch [PATH]` | Watch for file changes and auto-reload |
| `kw channels [--init]` | Show or create the MIDI channel map |
| `kw scan FILE` | Scan a file for MIDI channel usage |

## MIDI Channel Mapping

Orca's `:` operator sends MIDI: `:channel octave note [velocity] [length]`

The channel is a single hex character (0-f) mapping to MIDI channels 1-16. killer-wail provides a channel map config to track which channel goes to which Bitwig track:

```bash
# Create a default channel map
kw channels --init

# Show the mapping
kw channels
```

This creates `channels.yml`:

```yaml
channels:
- channel: 0
  name: Kick
- channel: 1
  name: Snare
- channel: 2
  name: HiHat
- channel: 3
  name: Perc
- channel: 4
  name: Bass
- channel: 5
  name: Lead
- channel: 6
  name: Pad
- channel: 7
  name: FX
```

Edit this to match your Bitwig track layout. Each Bitwig track should have its MIDI input set to receive from the corresponding channel.

### Bitwig Setup

1. Create an instrument track for each channel you want to use
2. Set each track's MIDI input to "Orca-c" (or your virtual MIDI port name)
3. Set the MIDI channel filter on each track to match the channel map
4. Arm the tracks for recording

### Scanning Patterns

```bash
$ kw scan src/orca/patterns/four-on-floor.orca
four-on-floor.orca: uses 3 MIDI channel(s)
  ch0 (0) → Kick
  ch1 (1) → Snare
  ch2 (2) → HiHat
```

## Watch Mode

Watch mode monitors a file or directory and auto-reloads Orca-c whenever a `.orca` file changes:

```bash
# Watch a specific file
kw watch src/orca/simple/kick.orca

# Watch a directory (reloads on any .orca change)
kw watch src/orca/simple/
```

Events are debounced (150ms) to handle editors that trigger multiple writes.

## Pattern Files

```
src/orca/
├── simple/              Single-instrument patterns
│   ├── kick.orca
│   ├── snare.orca
│   └── hihat.orca
└── patterns/            Multi-channel patterns
    └── four-on-floor.orca
```

## How It Works

1. `kw start` launches Orca-c in a detached tmux session
2. `kw swap` atomically overwrites the target .orca file (temp file + `os.replace`), then sends `Ctrl+O` → `Enter` to Orca-c via `tmux send-keys` — Orca's open dialog pre-populates with the current filename, so Enter re-reads from disk
3. `kw watch` uses [watchdog](https://github.com/gorakhargosh/watchdog) to monitor file changes and triggers the same reload

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run a specific test module
pytest tests/test_midi.py -v
```

## Timing Notes

- The 0.1ms offset you apply in Bitwig compensates for MIDI timing jitter
- After recording a MIDI clip in Bitwig, press Q to quantize
- For tightest timing: use lower BPM subdivisions in Orca and quantize in Bitwig
