# killer-wail

## What is this?

Hot-swap orchestrator for Orca-c → Bitwig on macOS. Runs Orca-c (the C implementation: https://github.com/hundredrabbits/Orca-c) inside tmux and uses `tmux send-keys` to programmatically reload .orca files, because Orca-c has no IPC, no file watching, and no external control mechanism.

## Architecture

```
src/killer_wail/
  session.py   — tmux session lifecycle (start/stop/reload via send-keys)
  hotswap.py   — atomic file swap + trigger reload
  watcher.py   — watchdog file watcher for auto-reload
  midi.py      — MIDI channel mapping (Orca hex 0-f → Bitwig tracks)
  cli.py       — Click CLI entry point (`kw` command)

src/orca/          — .orca pattern files
  simple/          — single-instrument patterns
  patterns/        — multi-channel patterns

tests/             — pytest tests (all mocked, no tmux/orca needed to run)
channels.yml       — MIDI channel → Bitwig track mapping config
```

## Key Technical Details

- **Hot-reload mechanism**: Ctrl+O opens Orca-c's file dialog (pre-populated with current filename), then Enter re-reads from disk. We simulate this via `tmux send-keys`.
- **Atomic file writes**: temp file + `os.replace()` to avoid Orca reading partial files.
- **Debounce**: watcher ignores duplicate events within 150ms window.
- **Orca MIDI format**: `:` operator sends MIDI as `:channel octave note [velocity] [length]` where channel is hex 0-f.

## Commands

```bash
pytest tests/           # run tests
kw --help               # CLI help
kw start FILE           # start orca in tmux
kw stop                 # stop orca session
kw swap FILE            # hot-swap a file
kw watch [PATH]         # auto-reload on file changes
kw channels --init      # create default channel map
kw scan FILE            # show MIDI channels used in a file
```

## Dependencies

- Python 3.10+, click, watchdog, pyyaml
- tmux (brew install tmux)
- Orca-c binary in PATH (build from https://github.com/hundredrabbits/Orca-c)
