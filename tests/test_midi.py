"""Tests for the MIDI channel mapping module."""

from pathlib import Path

import pytest

from killer_wail.midi import (
    ChannelMap,
    ChannelMapping,
    default_channel_map,
    replace_channel,
    scan_channels,
    scan_file,
)


class TestChannelMapping:
    def test_orca_char(self):
        assert ChannelMapping(0, "Kick").orca_char == "0"
        assert ChannelMapping(10, "Lead").orca_char == "a"
        assert ChannelMapping(15, "FX").orca_char == "f"

    def test_str(self):
        m = ChannelMapping(0, "Kick", instrument="Drum Machine")
        s = str(m)
        assert "ch0" in s
        assert "Kick" in s
        assert "Drum Machine" in s


class TestChannelMap:
    def test_by_channel(self):
        cmap = default_channel_map()
        assert cmap.by_channel(0).name == "Kick"
        assert cmap.by_channel(99) is None

    def test_by_name(self):
        cmap = default_channel_map()
        assert cmap.by_name("kick").channel == 0
        assert cmap.by_name("KICK").channel == 0
        assert cmap.by_name("nonexistent") is None

    def test_roundtrip_dict(self):
        original = default_channel_map()
        data = original.to_dict()
        restored = ChannelMap.from_dict(data)
        assert len(restored.mappings) == len(original.mappings)
        for a, b in zip(original.mappings, restored.mappings):
            assert a.channel == b.channel
            assert a.name == b.name

    def test_save_and_load(self, tmp_path):
        cmap = default_channel_map()
        path = tmp_path / "channels.yml"
        cmap.save(path)
        loaded = ChannelMap.load(path)
        assert len(loaded.mappings) == len(cmap.mappings)
        assert loaded.mappings[0].name == "Kick"

    def test_load_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            ChannelMap.load(tmp_path / "missing.yml")


class TestScanChannels:
    def test_simple_kick(self):
        content = "D4..........\n.:05C.......\n"
        channels = scan_channels(content)
        assert channels == {0}

    def test_multiple_channels(self):
        content = ":03C....\n:15E....\n:27G....\n"
        channels = scan_channels(content)
        assert channels == {0, 1, 2}

    def test_no_midi(self):
        content = "D4..........\n............\n"
        assert scan_channels(content) == set()

    def test_hex_channels(self):
        content = ":a3C....\n:f5E....\n"
        channels = scan_channels(content)
        assert channels == {10, 15}


class TestScanFile:
    def test_scan_real_kick(self):
        path = Path("src/orca/simple/kick.orca")
        if path.exists():
            channels = scan_file(path)
            assert 0 in channels


class TestReplaceChannel:
    def test_basic_replace(self):
        content = ":03C....\n"
        result = replace_channel(content, 0, 1)
        assert result == ":13C....\n"

    def test_only_replaces_target(self):
        content = ":03C....\n:15E....\n"
        result = replace_channel(content, 0, 2)
        assert ":23C" in result
        assert ":15E" in result  # channel 1 unchanged

    def test_no_match(self):
        content = ":03C....\n"
        result = replace_channel(content, 5, 6)
        assert result == content  # unchanged
