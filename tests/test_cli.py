"""Tests for the CLI interface."""

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from killer_wail.cli import main


@pytest.fixture
def runner():
    return CliRunner()


class TestCLI:
    def test_help(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "killer-wail" in result.output

    def test_start_help(self, runner):
        result = runner.invoke(main, ["start", "--help"])
        assert result.exit_code == 0
        assert "--bpm" in result.output

    def test_status_not_running(self, runner):
        with patch("killer_wail.cli.status") as mock_status:
            mock_status.return_value = {"running": False, "session_name": "orca"}
            result = runner.invoke(main, ["status"])
            assert "not running" in result.output

    def test_status_running(self, runner):
        with patch("killer_wail.cli.status") as mock_status:
            mock_status.return_value = {
                "running": True,
                "session_name": "orca",
                "command": "orca",
                "size": "120x40",
            }
            result = runner.invoke(main, ["status"])
            assert "running" in result.output

    @patch("killer_wail.cli.stop")
    def test_stop_success(self, mock_stop, runner):
        result = runner.invoke(main, ["stop"])
        assert result.exit_code == 0
        assert "Stopped" in result.output

    def test_channels_init(self, runner, tmp_path):
        path = tmp_path / "channels.yml"
        result = runner.invoke(main, ["channels", "--init", "--file", str(path)])
        assert result.exit_code == 0
        assert path.exists()

    def test_channels_show(self, runner, tmp_path):
        from killer_wail.midi import default_channel_map
        path = tmp_path / "channels.yml"
        default_channel_map().save(path)
        result = runner.invoke(main, ["channels", "--file", str(path)])
        assert result.exit_code == 0
        assert "Kick" in result.output

    def test_channels_no_file(self, runner, tmp_path):
        result = runner.invoke(main, ["channels", "--file", str(tmp_path / "nope.yml")])
        assert result.exit_code == 1

    def test_scan(self, runner):
        result = runner.invoke(main, ["scan", "src/orca/simple/kick.orca"])
        assert result.exit_code == 0
        assert "ch0" in result.output

    @patch("killer_wail.cli.swap")
    @patch("killer_wail.cli.validate_orca_file")
    def test_swap_cmd(self, mock_validate, mock_swap, runner):
        result = runner.invoke(main, ["swap", "src/orca/simple/kick.orca"])
        assert result.exit_code == 0
        mock_swap.assert_called_once()
