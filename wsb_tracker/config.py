"""Configuration management using pydantic-settings.

Loads settings from environment variables with WSB_ prefix,
with fallback to .env file. Supports both Reddit API credentials
(when available) and credential-free operation using public JSON endpoints.
"""

import os
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings can be configured via environment variables with WSB_ prefix,
    or through a .env file in the current directory.

    Example:
        WSB_SCAN_LIMIT=100
        WSB_MIN_SCORE=10
        REDDIT_CLIENT_ID=your_id  # Note: no WSB_ prefix for Reddit credentials
    """

    model_config = SettingsConfigDict(
        env_prefix="WSB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Reddit API Credentials (optional - uses different prefix)
    reddit_client_id: Optional[str] = Field(
        default=None,
        validation_alias="REDDIT_CLIENT_ID",
        description="Reddit API client ID (optional)",
    )
    reddit_client_secret: Optional[str] = Field(
        default=None,
        validation_alias="REDDIT_CLIENT_SECRET",
        description="Reddit API client secret (optional)",
    )
    reddit_user_agent: str = Field(
        default="wsb-tracker/0.1.0 (https://github.com/pmanlukas/wsb-tracker)",
        validation_alias="REDDIT_USER_AGENT",
        description="User agent for Reddit API/JSON requests",
    )

    # Database Configuration
    db_path: Path = Field(
        default=Path.home() / ".wsb-tracker" / "wsb_tracker.db",
        description="Path to SQLite database file",
    )

    # Scanning Settings
    scan_limit: int = Field(
        default=100,
        ge=10,
        le=500,
        description="Number of posts to scan per request",
    )
    min_score: int = Field(
        default=10,
        ge=0,
        description="Minimum post score to process",
    )
    scan_sort: str = Field(
        default="hot",
        pattern=r"^(hot|new|rising|top)$",
        description="Sort method for fetching posts",
    )
    subreddits: str = Field(
        default="wallstreetbets,stocks,investing,options,stockmarket,pennystocks,SPACs,smallstreetbets,thetagang,Vitards,weedstocks",
        description="Comma-separated list of subreddits to monitor",
    )

    # Rate Limiting
    request_delay: float = Field(
        default=2.0,
        ge=0.5,
        le=10.0,
        description="Delay between API requests in seconds",
    )

    # Alert Configuration
    enable_alerts: bool = Field(
        default=True,
        description="Enable/disable alert system",
    )
    alert_threshold: float = Field(
        default=80.0,
        ge=0.0,
        le=100.0,
        description="Heat score threshold for alerts",
    )
    alert_min_mentions: int = Field(
        default=5,
        ge=1,
        description="Minimum mentions to trigger alert",
    )
    alert_sentiment_change: float = Field(
        default=0.3,
        ge=0.0,
        le=2.0,
        description="Sentiment change threshold for alerts",
    )
    alert_mention_spike_pct: float = Field(
        default=100.0,
        ge=0.0,
        description="Mention spike percentage for alerts",
    )
    alert_min_heat_score: float = Field(
        default=3.0,
        ge=0.0,
        description="Minimum heat score for alerts",
    )

    # Analysis Settings
    min_mentions_to_track: int = Field(
        default=2,
        ge=1,
        description="Minimum mentions to include ticker in results",
    )
    lookback_hours: int = Field(
        default=24,
        ge=1,
        le=720,
        description="Hours to look back for trend comparison (max 30 days = 720 hours)",
    )

    # Output Settings
    json_output: bool = Field(
        default=False,
        description="Default to JSON output format",
    )
    output_dir: Path = Field(
        default=Path("output"),
        description="Directory for exported files",
    )

    # Discord Webhook (optional)
    discord_webhook_url: Optional[str] = Field(
        default=None,
        description="Discord webhook URL for notifications",
    )

    # LLM Configuration
    llm_enabled: bool = Field(
        default=False,
        description="Enable LLM-based trading idea extraction",
    )
    anthropic_api_key: Optional[str] = Field(
        default=None,
        description="Anthropic API key for Claude",
    )
    llm_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Claude model to use for analysis",
    )
    llm_min_post_score: int = Field(
        default=50,
        ge=0,
        description="Minimum post score to trigger LLM analysis",
    )
    llm_analyze_dd_only: bool = Field(
        default=False,
        description="Only analyze DD (Due Diligence) posts",
    )
    llm_max_daily_calls: int = Field(
        default=100,
        ge=0,
        description="Maximum LLM API calls per day (0 = unlimited)",
    )
    llm_cache_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Hours to cache LLM analysis results",
    )

    @property
    def has_llm_credentials(self) -> bool:
        """Check if LLM API credentials are configured."""
        return bool(self.get_anthropic_api_key())

    def get_anthropic_api_key(self) -> Optional[str]:
        """Get Anthropic API key from config or environment.

        Checks both WSB_ANTHROPIC_API_KEY and ANTHROPIC_API_KEY env vars.
        """
        if self.anthropic_api_key:
            return self.anthropic_api_key
        # Fall back to checking ANTHROPIC_API_KEY directly
        return os.environ.get("ANTHROPIC_API_KEY")

    @field_validator("db_path", mode="before")
    @classmethod
    def expand_db_path(cls, v: str | Path) -> Path:
        """Expand ~ in database path."""
        return Path(v).expanduser()

    @field_validator("output_dir", mode="before")
    @classmethod
    def expand_output_dir(cls, v: str | Path) -> Path:
        """Expand ~ in output directory path."""
        return Path(v).expanduser()

    @property
    def has_reddit_credentials(self) -> bool:
        """Check if Reddit API credentials are configured.

        Returns True only if both client_id and client_secret are set.
        """
        return bool(self.reddit_client_id and self.reddit_client_secret)

    @property
    def subreddit_list(self) -> list[str]:
        """Get subreddits as a list."""
        return [s.strip() for s in self.subreddits.split(",") if s.strip()]

    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)


# Global settings singleton
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create settings singleton.

    Returns:
        Settings instance with values loaded from environment/config.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset settings singleton (useful for testing)."""
    global _settings
    _settings = None


def configure_settings(**kwargs: object) -> Settings:
    """Create settings with custom values (useful for testing).

    Args:
        **kwargs: Settings attributes to override.

    Returns:
        New Settings instance with overridden values.
    """
    global _settings
    _settings = Settings(**kwargs)  # type: ignore[arg-type]
    return _settings
