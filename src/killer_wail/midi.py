"""MIDI channel mapping for Orca-c → Bitwig.

Orca-c's `:` operator sends MIDI with the format:
    :channel octave note velocity length

Where channel is a single hex char 0-f mapping to MIDI channels 1-16.

This module provides:
- A config-driven channel map (channel → track name/instrument)
- Pattern generation helpers that apply correct channel assignments
- Validation of channel usage in .orca files
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

# Orca uses hex 0-f for MIDI channels (maps to MIDI 1-16)
ORCA_CHANNELS = "0123456789abcdef"
CHANNEL_COUNT = 16

# Regex to find MIDI send operators in orca grids
# The `:` operator reads the cell to its right as: channel, octave, note [, velocity, length]
MIDI_PATTERN = re.compile(r":([0-9a-fA-F])(\d)([A-Ga-g])")


@dataclass
class ChannelMapping:
    """Maps an Orca MIDI channel to a Bitwig track."""

    channel: int         # 0-15 (Orca hex char maps to this)
    name: str            # Human-readable name (e.g. "Kick", "Bass")
    instrument: str = "" # Bitwig instrument/plugin name (documentation only)
    color: str = ""      # Optional color label for reference

    @property
    def orca_char(self) -> str:
        """The hex character used in Orca patterns for this channel."""
        return format(self.channel, "x")

    def __str__(self) -> str:
        label = f"ch{self.channel} ({self.orca_char}): {self.name}"
        if self.instrument:
            label += f" [{self.instrument}]"
        return label


@dataclass
class ChannelMap:
    """Complete channel mapping configuration."""

    mappings: list[ChannelMapping]

    def by_channel(self, channel: int) -> ChannelMapping | None:
        for m in self.mappings:
            if m.channel == channel:
                return m
        return None

    def by_name(self, name: str) -> ChannelMapping | None:
        name_lower = name.lower()
        for m in self.mappings:
            if m.name.lower() == name_lower:
                return m
        return None

    def to_dict(self) -> dict:
        return {
            "channels": [
                {
                    "channel": m.channel,
                    "name": m.name,
                    **({"instrument": m.instrument} if m.instrument else {}),
                    **({"color": m.color} if m.color else {}),
                }
                for m in self.mappings
            ]
        }

    @classmethod
    def from_dict(cls, data: dict) -> ChannelMap:
        mappings = []
        for ch in data.get("channels", []):
            mappings.append(ChannelMapping(
                channel=ch["channel"],
                name=ch["name"],
                instrument=ch.get("instrument", ""),
                color=ch.get("color", ""),
            ))
        return cls(mappings=mappings)

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)

    @classmethod
    def load(cls, path: Path) -> ChannelMap:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Channel map not found: {path}")
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)


def default_channel_map() -> ChannelMap:
    """A sensible default mapping for a basic Bitwig setup."""
    return ChannelMap(mappings=[
        ChannelMapping(0, "Kick"),
        ChannelMapping(1, "Snare"),
        ChannelMapping(2, "HiHat"),
        ChannelMapping(3, "Perc"),
        ChannelMapping(4, "Bass"),
        ChannelMapping(5, "Lead"),
        ChannelMapping(6, "Pad"),
        ChannelMapping(7, "FX"),
    ])


def scan_channels(content: str) -> set[int]:
    """Scan orca file content for MIDI channel usage.

    Returns set of channel numbers (0-15) found in `:` operators.
    """
    channels = set()
    for match in MIDI_PATTERN.finditer(content):
        ch_char = match.group(1).lower()
        channels.add(int(ch_char, 16))
    return channels


def scan_file(path: Path) -> set[int]:
    """Scan an .orca file for MIDI channel usage."""
    return scan_channels(Path(path).read_text())


def replace_channel(content: str, old_channel: int, new_channel: int) -> str:
    """Replace all occurrences of one MIDI channel with another in orca content.

    Only replaces channels in `:` MIDI operator contexts.
    """
    old_char = format(old_channel, "x")
    new_char = format(new_channel, "x")

    def _replace(match: re.Match) -> str:
        ch = match.group(1).lower()
        if ch == old_char:
            return f":{new_char}{match.group(2)}{match.group(3)}"
        return match.group(0)

    return MIDI_PATTERN.sub(_replace, content)
