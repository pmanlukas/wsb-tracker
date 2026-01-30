"""Tests for configuration module."""

import pytest
from pathlib import Path
from unittest.mock import patch

from wsb_tracker.config import Settings, get_settings, reset_settings, configure_settings


class TestSettings:
    """Tests for Settings class."""

    def setup_method(self):
        """Reset settings before each test."""
        reset_settings()

    def teardown_method(self):
        """Reset settings after each test."""
        reset_settings()

    def test_default_values(self):
        """Test default configuration values."""
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings()
            assert settings.scan_limit == 100
            assert settings.min_score == 10
            assert settings.request_delay == 2.0
            assert "wallstreetbets" in settings.subreddits

    def test_db_path_expansion(self):
        """Test that ~ is expanded in db_path."""
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings()
            assert "~" not in str(settings.db_path)
            assert settings.db_path.is_absolute()

    def test_output_dir_expansion(self):
        """Test that ~ is expanded in output_dir."""
        with patch.dict("os.environ", {"WSB_OUTPUT_DIR": "~/wsb-output"}, clear=True):
            settings = Settings()
            assert "~" not in str(settings.output_dir)
            assert settings.output_dir.is_absolute()

    def test_env_variable_override_scan_limit(self, monkeypatch):
        """Test environment variable overrides for scan_limit."""
        monkeypatch.setenv("WSB_SCAN_LIMIT", "200")
        settings = Settings()
        assert settings.scan_limit == 200

    def test_env_variable_override_request_delay(self, monkeypatch):
        """Test environment variable overrides for request_delay."""
        monkeypatch.setenv("WSB_REQUEST_DELAY", "5.0")
        settings = Settings()
        assert settings.request_delay == 5.0

    def test_env_variable_override_min_score(self, monkeypatch):
        """Test environment variable overrides for min_score."""
        monkeypatch.setenv("WSB_MIN_SCORE", "50")
        settings = Settings()
        assert settings.min_score == 50

    def test_validation_scan_limit_minimum(self, monkeypatch):
        """Test scan_limit validation (minimum 10)."""
        monkeypatch.setenv("WSB_SCAN_LIMIT", "5")
        with pytest.raises(ValueError):
            Settings()

    def test_validation_scan_limit_maximum(self, monkeypatch):
        """Test scan_limit validation (maximum 500)."""
        monkeypatch.setenv("WSB_SCAN_LIMIT", "1000")
        with pytest.raises(ValueError):
            Settings()

    def test_validation_request_delay_minimum(self, monkeypatch):
        """Test request_delay validation (minimum 0.5)."""
        monkeypatch.setenv("WSB_REQUEST_DELAY", "0.1")
        with pytest.raises(ValueError):
            Settings()

    def test_validation_request_delay_maximum(self, monkeypatch):
        """Test request_delay validation (maximum 10.0)."""
        monkeypatch.setenv("WSB_REQUEST_DELAY", "20.0")
        with pytest.raises(ValueError):
            Settings()

    def test_has_reddit_credentials_false_by_default(self):
        """Test reddit credentials detection when not set."""
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings()
            assert settings.has_reddit_credentials is False

    def test_has_reddit_credentials_true_when_set(self, monkeypatch):
        """Test reddit credentials detection when set."""
        monkeypatch.setenv("WSB_REDDIT_CLIENT_ID", "test_id")
        monkeypatch.setenv("WSB_REDDIT_CLIENT_SECRET", "test_secret")
        settings = Settings()
        assert settings.has_reddit_credentials is True

    def test_has_reddit_credentials_false_with_partial(self, monkeypatch):
        """Test reddit credentials detection with only ID set."""
        monkeypatch.setenv("WSB_REDDIT_CLIENT_ID", "test_id")
        settings = Settings()
        assert settings.has_reddit_credentials is False

    def test_subreddits_as_list(self):
        """Test that subreddits is converted to list."""
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings()
            subreddits_list = settings.subreddits_list
            assert isinstance(subreddits_list, list)
            assert "wallstreetbets" in subreddits_list

    def test_subreddits_multiple(self, monkeypatch):
        """Test multiple subreddits parsing."""
        monkeypatch.setenv("WSB_SUBREDDITS", "wallstreetbets,stocks,investing")
        settings = Settings()
        subreddits_list = settings.subreddits_list
        assert len(subreddits_list) == 3
        assert "wallstreetbets" in subreddits_list
        assert "stocks" in subreddits_list
        assert "investing" in subreddits_list

    def test_reddit_user_agent_default(self):
        """Test default user agent."""
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings()
            assert "wsb-tracker" in settings.reddit_user_agent.lower()

    def test_enable_alerts_default(self):
        """Test default alert setting."""
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings()
            assert settings.enable_alerts is True

    def test_enable_alerts_override(self, monkeypatch):
        """Test alert setting override."""
        monkeypatch.setenv("WSB_ENABLE_ALERTS", "false")
        settings = Settings()
        assert settings.enable_alerts is False

    def test_alert_threshold_default(self):
        """Test default alert threshold."""
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings()
            assert settings.alert_threshold == 80.0

    def test_alert_threshold_validation_minimum(self, monkeypatch):
        """Test alert threshold minimum validation."""
        monkeypatch.setenv("WSB_ALERT_THRESHOLD", "-10")
        with pytest.raises(ValueError):
            Settings()

    def test_alert_threshold_validation_maximum(self, monkeypatch):
        """Test alert threshold maximum validation."""
        monkeypatch.setenv("WSB_ALERT_THRESHOLD", "150")
        with pytest.raises(ValueError):
            Settings()


class TestGetSettings:
    """Tests for get_settings function."""

    def setup_method(self):
        """Reset settings before each test."""
        reset_settings()

    def teardown_method(self):
        """Reset settings after each test."""
        reset_settings()

    def test_singleton_pattern(self):
        """Test that get_settings returns same instance."""
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_reset_settings_clears_singleton(self):
        """Test that reset_settings clears the singleton."""
        s1 = get_settings()
        reset_settings()
        s2 = get_settings()
        assert s1 is not s2


class TestConfigureSettings:
    """Tests for configure_settings function."""

    def setup_method(self):
        """Reset settings before each test."""
        reset_settings()

    def teardown_method(self):
        """Reset settings after each test."""
        reset_settings()

    def test_configure_settings_overrides(self):
        """Test that configure_settings properly overrides defaults."""
        custom_settings = Settings(scan_limit=50, min_score=5)
        configure_settings(custom_settings)

        settings = get_settings()
        assert settings.scan_limit == 50
        assert settings.min_score == 5

    def test_configure_settings_persists(self):
        """Test that configured settings persist across get_settings calls."""
        custom_settings = Settings(request_delay=3.0)
        configure_settings(custom_settings)

        # Multiple calls should return same configured settings
        s1 = get_settings()
        s2 = get_settings()
        assert s1.request_delay == 3.0
        assert s2.request_delay == 3.0
        assert s1 is s2


class TestSettingsValidation:
    """Tests for settings field validation."""

    def setup_method(self):
        """Reset settings before each test."""
        reset_settings()

    def teardown_method(self):
        """Reset settings after each test."""
        reset_settings()

    def test_scan_sort_validation(self, monkeypatch):
        """Test scan_sort accepts only valid values."""
        valid_sorts = ["hot", "new", "rising", "top"]
        for sort in valid_sorts:
            monkeypatch.setenv("WSB_SCAN_SORT", sort)
            settings = Settings()
            assert settings.scan_sort == sort

    def test_min_mentions_to_track_default(self):
        """Test default min_mentions_to_track value."""
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings()
            assert settings.min_mentions_to_track >= 1

    def test_data_retention_days_default(self):
        """Test default data_retention_days value."""
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings()
            assert settings.data_retention_days >= 1
