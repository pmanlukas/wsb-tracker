"""Runtime settings that can be modified via API.

These settings override the static config values and persist in the database.
"""

from typing import Optional

from pydantic import BaseModel, Field

from wsb_tracker.database import get_database
from wsb_tracker.config import get_settings


class RuntimeSettings(BaseModel):
    """Settings that can be modified at runtime via the UI."""

    subreddits: list[str] = Field(
        default_factory=lambda: ["wallstreetbets"],
        description="List of subreddits to monitor",
    )
    scan_limit: int = Field(
        default=100,
        ge=10,
        le=500,
        description="Maximum posts to fetch per scan",
    )
    request_delay: float = Field(
        default=2.0,
        ge=0.5,
        le=10.0,
        description="Delay between API requests in seconds",
    )
    min_score: int = Field(
        default=10,
        ge=0,
        description="Minimum post score to process",
    )
    scan_sort: str = Field(
        default="hot",
        pattern=r"^(hot|new|rising|top)$",
        description="Sort order for fetching posts",
    )


def get_runtime_settings() -> RuntimeSettings:
    """Get current runtime settings from database, falling back to config.

    Returns:
        RuntimeSettings object with current values
    """
    db = get_database()
    config = get_settings()

    # Load settings from database
    db_settings = db.get_all_settings()

    # Build settings with fallbacks to config
    return RuntimeSettings(
        subreddits=db_settings.get("subreddits", config.subreddits).split(","),
        scan_limit=int(db_settings.get("scan_limit", str(config.scan_limit))),
        request_delay=float(db_settings.get("request_delay", str(config.request_delay))),
        min_score=int(db_settings.get("min_score", str(config.min_score))),
        scan_sort=db_settings.get("scan_sort", config.scan_sort),
    )


def save_runtime_settings(settings: RuntimeSettings) -> None:
    """Save runtime settings to database.

    Args:
        settings: RuntimeSettings object to persist
    """
    db = get_database()
    db.set_settings({
        "subreddits": ",".join(settings.subreddits),
        "scan_limit": str(settings.scan_limit),
        "request_delay": str(settings.request_delay),
        "min_score": str(settings.min_score),
        "scan_sort": settings.scan_sort,
    })


def reset_runtime_settings() -> RuntimeSettings:
    """Reset runtime settings to config defaults.

    Returns:
        The new RuntimeSettings based on config defaults
    """
    config = get_settings()
    settings = RuntimeSettings(
        subreddits=config.subreddit_list,
        scan_limit=config.scan_limit,
        request_delay=config.request_delay,
        min_score=config.min_score,
        scan_sort=config.scan_sort,
    )
    save_runtime_settings(settings)
    return settings


# Cache to avoid frequent DB reads
_cached_settings: Optional[RuntimeSettings] = None
_cache_valid: bool = False


def get_cached_runtime_settings() -> RuntimeSettings:
    """Get runtime settings with caching.

    Call invalidate_settings_cache() when settings are updated.

    Returns:
        RuntimeSettings object
    """
    global _cached_settings, _cache_valid

    if not _cache_valid or _cached_settings is None:
        _cached_settings = get_runtime_settings()
        _cache_valid = True

    return _cached_settings


def invalidate_settings_cache() -> None:
    """Invalidate the settings cache.

    Call this after updating settings.
    """
    global _cache_valid
    _cache_valid = False
