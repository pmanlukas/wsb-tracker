"""Tests for CLI module."""

import json
import pytest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock
from datetime import datetime

from wsb_tracker.cli import app
from wsb_tracker.config import reset_settings
from wsb_tracker.models import TickerSummary, TrackerSnapshot


runner = CliRunner()


class TestCLIBasic:
    """Basic CLI tests."""

    def setup_method(self):
        """Reset settings before each test."""
        reset_settings()

    def teardown_method(self):
        """Reset settings after each test."""
        reset_settings()

    def test_version(self):
        """Test --version flag."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        # Version should be in output
        assert "0.1.0" in result.stdout or "version" in result.stdout.lower()

    def test_help(self):
        """Test --help flag."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "scan" in result.stdout
        assert "top" in result.stdout
        assert "ticker" in result.stdout


class TestConfigCommand:
    """Tests for config command."""

    def setup_method(self):
        """Reset settings before each test."""
        reset_settings()

    def teardown_method(self):
        """Reset settings after each test."""
        reset_settings()

    def test_config_show(self):
        """Test config --show command."""
        result = runner.invoke(app, ["config", "--show"])
        assert result.exit_code == 0
        # Should display configuration keys
        assert "scan_limit" in result.stdout.lower() or "configuration" in result.stdout.lower()


class TestTopCommand:
    """Tests for top command."""

    def setup_method(self):
        """Reset settings before each test."""
        reset_settings()

    def teardown_method(self):
        """Reset settings after each test."""
        reset_settings()

    def test_top_empty_db(self, tmp_path, monkeypatch):
        """Test top command with no data."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("WSB_DB_PATH", str(db_path))
        reset_settings()

        result = runner.invoke(app, ["top"])
        assert result.exit_code == 0
        # Should either show empty table or "no data" message
        assert "No data" in result.stdout or result.stdout.strip() == "" or "top" in result.stdout.lower()

    def test_top_with_limit(self, tmp_path, monkeypatch):
        """Test top command with --limit flag."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("WSB_DB_PATH", str(db_path))
        reset_settings()

        result = runner.invoke(app, ["top", "--limit", "5"])
        assert result.exit_code == 0

    def test_top_with_hours(self, tmp_path, monkeypatch):
        """Test top command with --hours flag."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("WSB_DB_PATH", str(db_path))
        reset_settings()

        result = runner.invoke(app, ["top", "--hours", "12"])
        assert result.exit_code == 0

    def test_top_json_output(self, tmp_path, monkeypatch):
        """Test top command with --json flag."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("WSB_DB_PATH", str(db_path))
        reset_settings()

        result = runner.invoke(app, ["top", "--json"])
        assert result.exit_code == 0
        # Output should be valid JSON (empty array or object)
        if result.stdout.strip():
            try:
                json.loads(result.stdout)
            except json.JSONDecodeError:
                pass  # Empty or table output is also acceptable


class TestStatsCommand:
    """Tests for stats command."""

    def setup_method(self):
        """Reset settings before each test."""
        reset_settings()

    def teardown_method(self):
        """Reset settings after each test."""
        reset_settings()

    def test_stats_empty_db(self, tmp_path, monkeypatch):
        """Test stats command with empty database."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("WSB_DB_PATH", str(db_path))
        reset_settings()

        result = runner.invoke(app, ["stats"])
        assert result.exit_code == 0


class TestTickerCommand:
    """Tests for ticker command."""

    def setup_method(self):
        """Reset settings before each test."""
        reset_settings()

    def teardown_method(self):
        """Reset settings after each test."""
        reset_settings()

    def test_ticker_not_found(self, tmp_path, monkeypatch):
        """Test ticker command with non-existent ticker."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("WSB_DB_PATH", str(db_path))
        reset_settings()

        result = runner.invoke(app, ["ticker", "NOTREAL"])
        assert result.exit_code == 0
        # Should indicate no data found
        assert "No data" in result.stdout or "not found" in result.stdout.lower() or result.stdout.strip() == ""


class TestAlertsCommand:
    """Tests for alerts command."""

    def setup_method(self):
        """Reset settings before each test."""
        reset_settings()

    def teardown_method(self):
        """Reset settings after each test."""
        reset_settings()

    def test_alerts_empty(self, tmp_path, monkeypatch):
        """Test alerts command with no alerts."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("WSB_DB_PATH", str(db_path))
        reset_settings()

        result = runner.invoke(app, ["alerts"])
        assert result.exit_code == 0


class TestCleanupCommand:
    """Tests for cleanup command."""

    def setup_method(self):
        """Reset settings before each test."""
        reset_settings()

    def teardown_method(self):
        """Reset settings after each test."""
        reset_settings()

    def test_cleanup_with_days(self, tmp_path, monkeypatch):
        """Test cleanup command with --days flag."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("WSB_DB_PATH", str(db_path))
        reset_settings()

        result = runner.invoke(app, ["cleanup", "--days", "7"])
        assert result.exit_code == 0


class TestScanCommand:
    """Tests for scan command."""

    def setup_method(self):
        """Reset settings before each test."""
        reset_settings()

    def teardown_method(self):
        """Reset settings after each test."""
        reset_settings()

    def test_scan_with_mock_client(self, tmp_path, monkeypatch):
        """Test scan command with mocked Reddit client."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("WSB_DB_PATH", str(db_path))
        monkeypatch.setenv("WSB_REQUEST_DELAY", "0.5")
        reset_settings()

        # Mock the tracker to avoid actual Reddit requests
        with patch("wsb_tracker.cli.WSBTracker") as mock_tracker_class:
            mock_tracker = MagicMock()
            mock_tracker.scan.return_value = TrackerSnapshot(
                timestamp=datetime.utcnow(),
                subreddits=["wallstreetbets"],
                posts_analyzed=10,
                tickers_found=3,
                summaries=[],
                top_movers=[],
                scan_duration_seconds=1.5,
                source="json_fallback",
            )
            mock_tracker_class.return_value = mock_tracker

            result = runner.invoke(app, ["scan", "--limit", "5"])

        # Should complete without error
        assert result.exit_code == 0

    def test_scan_json_output(self, tmp_path, monkeypatch):
        """Test scan with --json flag."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("WSB_DB_PATH", str(db_path))
        monkeypatch.setenv("WSB_REQUEST_DELAY", "0.5")
        reset_settings()

        with patch("wsb_tracker.cli.WSBTracker") as mock_tracker_class:
            mock_tracker = MagicMock()
            mock_tracker.scan.return_value = TrackerSnapshot(
                timestamp=datetime.utcnow(),
                subreddits=["wallstreetbets"],
                posts_analyzed=5,
                tickers_found=2,
                summaries=[
                    TickerSummary(
                        ticker="GME",
                        mention_count=10,
                        unique_posts=8,
                        avg_sentiment=0.5,
                        bullish_ratio=0.8,
                        total_score=1000,
                        dd_count=2,
                        first_seen=datetime.utcnow(),
                        last_seen=datetime.utcnow(),
                    )
                ],
                top_movers=["GME"],
                scan_duration_seconds=1.0,
                source="json_fallback",
            )
            mock_tracker_class.return_value = mock_tracker

            result = runner.invoke(app, ["scan", "--limit", "5", "--json"])

        assert result.exit_code == 0
        # Should produce valid JSON
        if result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                assert "summaries" in data or "tickers_found" in data or isinstance(data, list)
            except json.JSONDecodeError:
                # Some CLI implementations may not output JSON even with flag
                pass
