"""Tests for the hot-swap module."""

from pathlib import Path
from unittest.mock import patch

import pytest

from killer_wail.hotswap import (
    HotswapError,
    atomic_copy,
    swap,
    swap_content,
    validate_orca_file,
)


class TestValidateOrcaFile:
    def test_valid_file(self, tmp_path):
        f = tmp_path / "test.orca"
        f.write_text("D4..........\n.:05C.......\n")
        validate_orca_file(f)  # should not raise

    def test_file_not_found(self, tmp_path):
        with pytest.raises(HotswapError, match="not found"):
            validate_orca_file(tmp_path / "missing.orca")

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.orca"
        f.write_text("")
        with pytest.raises(HotswapError, match="empty"):
            validate_orca_file(f)

    def test_not_rectangular(self, tmp_path):
        f = tmp_path / "bad.orca"
        f.write_text("abc\nab\n")
        with pytest.raises(HotswapError, match="not rectangular"):
            validate_orca_file(f)

    def test_single_line(self, tmp_path):
        f = tmp_path / "one.orca"
        f.write_text("D4..........\n")
        validate_orca_file(f)  # should not raise

    def test_directory(self, tmp_path):
        with pytest.raises(HotswapError, match="Not a file"):
            validate_orca_file(tmp_path)


class TestAtomicCopy:
    def test_basic_copy(self, tmp_path):
        src = tmp_path / "src.orca"
        dst = tmp_path / "dst.orca"
        src.write_text("hello")
        atomic_copy(src, dst)
        assert dst.read_text() == "hello"

    def test_overwrites_existing(self, tmp_path):
        src = tmp_path / "src.orca"
        dst = tmp_path / "dst.orca"
        src.write_text("new")
        dst.write_text("old")
        atomic_copy(src, dst)
        assert dst.read_text() == "new"

    def test_creates_parent_dirs(self, tmp_path):
        src = tmp_path / "src.orca"
        dst = tmp_path / "sub" / "dir" / "dst.orca"
        src.write_text("content")
        atomic_copy(src, dst)
        assert dst.read_text() == "content"


class TestSwap:
    @patch("killer_wail.hotswap.trigger_reload")
    def test_swap_different_files(self, mock_reload, tmp_path):
        src = tmp_path / "new.orca"
        target = tmp_path / "current.orca"
        src.write_text("D4..........\n.:05C.......\n")
        target.write_text("old content.\n")
        swap(src, target, session_name="orca")
        assert target.read_text() == "D4..........\n.:05C.......\n"
        mock_reload.assert_called_once()

    @patch("killer_wail.hotswap.trigger_reload")
    def test_swap_same_file_just_reloads(self, mock_reload, tmp_path):
        f = tmp_path / "test.orca"
        f.write_text("D4..........\n.:05C.......\n")
        swap(f, f, session_name="orca")
        mock_reload.assert_called_once()

    @patch("killer_wail.hotswap.trigger_reload")
    def test_swap_validates_by_default(self, mock_reload, tmp_path):
        src = tmp_path / "bad.orca"
        target = tmp_path / "current.orca"
        src.write_text("")  # empty = invalid
        target.write_text("ok..........\n")
        with pytest.raises(HotswapError, match="empty"):
            swap(src, target)

    @patch("killer_wail.hotswap.trigger_reload")
    def test_swap_skip_validation(self, mock_reload, tmp_path):
        src = tmp_path / "weird.orca"
        target = tmp_path / "current.orca"
        src.write_text("")
        target.write_text("ok..........\n")
        swap(src, target, validate=False)  # should not raise
        mock_reload.assert_called_once()


class TestSwapContent:
    @patch("killer_wail.hotswap.trigger_reload")
    def test_writes_and_reloads(self, mock_reload, tmp_path):
        target = tmp_path / "out.orca"
        swap_content("D4..........\n", target, session_name="orca")
        assert target.read_text() == "D4..........\n"
        mock_reload.assert_called_once()

    @patch("killer_wail.hotswap.trigger_reload")
    def test_creates_parent_dirs(self, mock_reload, tmp_path):
        target = tmp_path / "sub" / "out.orca"
        swap_content("content\n", target, session_name="orca")
        assert target.read_text() == "content\n"
