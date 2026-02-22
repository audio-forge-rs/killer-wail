"""Tests for the tmux session manager."""

from unittest.mock import patch, MagicMock
from pathlib import Path
import subprocess

import pytest

from killer_wail.session import (
    SessionConfig,
    SessionError,
    is_running,
    require_tmux,
    start,
    status,
    stop,
    send_keys,
    trigger_reload,
)


class TestSessionConfig:
    def test_default_command(self):
        cfg = SessionConfig()
        assert cfg.orca_command() == ["orca", "--strict-timing"]

    def test_command_with_bpm(self):
        cfg = SessionConfig(bpm=140)
        cmd = cfg.orca_command()
        assert "--bpm" in cmd
        assert "140" in cmd

    def test_command_with_file(self, tmp_path):
        f = tmp_path / "test.orca"
        f.touch()
        cfg = SessionConfig(file_path=f)
        cmd = cfg.orca_command()
        assert str(f) in cmd

    def test_command_without_strict_timing(self):
        cfg = SessionConfig(strict_timing=False)
        assert "--strict-timing" not in cfg.orca_command()


class TestRequireTmux:
    @patch("killer_wail.session.shutil.which", return_value="/usr/local/bin/tmux")
    def test_found(self, mock_which):
        assert require_tmux() == "/usr/local/bin/tmux"

    @patch("killer_wail.session.shutil.which", return_value=None)
    def test_not_found(self, mock_which):
        with pytest.raises(SessionError, match="tmux is not installed"):
            require_tmux()


class TestIsRunning:
    @patch("killer_wail.session._run")
    def test_running(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        assert is_running("orca") is True

    @patch("killer_wail.session._run")
    def test_not_running(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        assert is_running("orca") is False


class TestStart:
    @patch("killer_wail.session.time.sleep")
    @patch("killer_wail.session.is_running")
    @patch("killer_wail.session._run")
    @patch("killer_wail.session.shutil.which")
    def test_start_success(self, mock_which, mock_run, mock_is_running, mock_sleep):
        mock_which.return_value = "/usr/local/bin/orca"
        mock_is_running.side_effect = [False, True]  # not running, then running
        start()
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "tmux" in call_args
        assert "new-session" in call_args

    @patch("killer_wail.session.is_running", return_value=True)
    @patch("killer_wail.session.shutil.which", return_value="/usr/local/bin/tmux")
    def test_start_already_running(self, mock_which, mock_is_running):
        with pytest.raises(SessionError, match="already running"):
            start()

    @patch("killer_wail.session.is_running", return_value=False)
    @patch("killer_wail.session.shutil.which")
    def test_start_orca_not_found(self, mock_which, mock_is_running):
        mock_which.side_effect = lambda x: "/usr/local/bin/tmux" if x == "tmux" else None
        with pytest.raises(SessionError, match="not found in PATH"):
            start()

    @patch("killer_wail.session.is_running", return_value=False)
    @patch("killer_wail.session.shutil.which", return_value="/usr/bin/orca")
    def test_start_file_not_found(self, mock_which, mock_is_running):
        cfg = SessionConfig(file_path=Path("/nonexistent/file.orca"))
        with pytest.raises(SessionError, match="not found"):
            start(cfg)


class TestStop:
    @patch("killer_wail.session._run")
    @patch("killer_wail.session.is_running", return_value=True)
    def test_stop_success(self, mock_is_running, mock_run):
        stop()
        mock_run.assert_called_once()

    @patch("killer_wail.session.is_running", return_value=False)
    def test_stop_not_running(self, mock_is_running):
        with pytest.raises(SessionError, match="No session"):
            stop()


class TestSendKeys:
    @patch("killer_wail.session._run")
    @patch("killer_wail.session.is_running", return_value=True)
    def test_send_keys(self, mock_is_running, mock_run):
        send_keys("C-o")
        mock_run.assert_called_once_with(
            ["tmux", "send-keys", "-t", "orca", "C-o"]
        )

    @patch("killer_wail.session.is_running", return_value=False)
    def test_send_keys_no_session(self, mock_is_running):
        with pytest.raises(SessionError):
            send_keys("C-o")


class TestTriggerReload:
    @patch("killer_wail.session.time.sleep")
    @patch("killer_wail.session.send_keys")
    @patch("killer_wail.session.is_running", return_value=True)
    def test_reload_sends_ctrl_o_then_enter(self, mock_is_running, mock_send, mock_sleep):
        trigger_reload()
        assert mock_send.call_count == 2
        calls = [c[0][0] for c in mock_send.call_args_list]
        assert calls == ["C-o", "Enter"]

    @patch("killer_wail.session.is_running", return_value=False)
    def test_reload_no_session(self, mock_is_running):
        with pytest.raises(SessionError):
            trigger_reload()


class TestStatus:
    @patch("killer_wail.session._run")
    @patch("killer_wail.session.is_running", return_value=True)
    def test_status_running(self, mock_is_running, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="orca 120x40\n")
        info = status()
        assert info["running"] is True
        assert info["command"] == "orca"

    @patch("killer_wail.session.is_running", return_value=False)
    def test_status_not_running(self, mock_is_running):
        info = status()
        assert info["running"] is False
