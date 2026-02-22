"""Tests for the file watcher module."""

import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from killer_wail.watcher import OrcaReloadHandler, watch


class TestOrcaReloadHandler:
    def _make_event(self, path: str, is_dir: bool = False):
        event = MagicMock()
        event.src_path = path
        event.is_directory = is_dir
        return event

    @patch("killer_wail.watcher.trigger_reload")
    @patch("killer_wail.watcher.is_running", return_value=True)
    def test_reloads_on_orca_change(self, mock_running, mock_reload):
        handler = OrcaReloadHandler()
        handler.on_modified(self._make_event("/tmp/test.orca"))
        mock_reload.assert_called_once()

    @patch("killer_wail.watcher.trigger_reload")
    @patch("killer_wail.watcher.is_running", return_value=True)
    def test_ignores_non_orca(self, mock_running, mock_reload):
        handler = OrcaReloadHandler()
        handler.on_modified(self._make_event("/tmp/test.txt"))
        mock_reload.assert_not_called()

    @patch("killer_wail.watcher.trigger_reload")
    @patch("killer_wail.watcher.is_running", return_value=True)
    def test_ignores_directories(self, mock_running, mock_reload):
        handler = OrcaReloadHandler()
        handler.on_modified(self._make_event("/tmp/dir", is_dir=True))
        mock_reload.assert_not_called()

    @patch("killer_wail.watcher.trigger_reload")
    @patch("killer_wail.watcher.is_running", return_value=True)
    def test_debounce(self, mock_running, mock_reload):
        handler = OrcaReloadHandler()
        handler.on_modified(self._make_event("/tmp/test.orca"))
        handler.on_modified(self._make_event("/tmp/test.orca"))  # too fast
        assert mock_reload.call_count == 1

    @patch("killer_wail.watcher.trigger_reload")
    @patch("killer_wail.watcher.is_running", return_value=True)
    def test_target_file_filter(self, mock_running, mock_reload, tmp_path):
        target = tmp_path / "target.orca"
        target.touch()
        handler = OrcaReloadHandler(target_file=target)
        handler.on_modified(self._make_event(str(tmp_path / "other.orca")))
        mock_reload.assert_not_called()
        handler.on_modified(self._make_event(str(target)))
        mock_reload.assert_called_once()

    @patch("killer_wail.watcher.trigger_reload")
    @patch("killer_wail.watcher.is_running", return_value=False)
    def test_skips_when_not_running(self, mock_running, mock_reload):
        handler = OrcaReloadHandler()
        handler.on_modified(self._make_event("/tmp/test.orca"))
        mock_reload.assert_not_called()


class TestWatch:
    def test_watch_file(self, tmp_path):
        f = tmp_path / "test.orca"
        f.write_text("test")
        observer = watch(f, session_name="test-orca")
        assert observer.is_alive()
        observer.stop()
        observer.join()

    def test_watch_directory(self, tmp_path):
        observer = watch(tmp_path, session_name="test-orca")
        assert observer.is_alive()
        observer.stop()
        observer.join()

    def test_watch_missing_path(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            watch(tmp_path / "missing")
