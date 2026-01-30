"""Pytest configuration and fixtures for WSB Tracker tests."""

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Generator

import pytest

from wsb_tracker.config import Settings, reset_settings
from wsb_tracker.database import Database, reset_database
from wsb_tracker.models import RedditPost, Sentiment, TickerMention


@pytest.fixture
def temp_db_path() -> Generator[Path, None, None]:
    """Create a temporary database file path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    yield path
    # Cleanup
    if path.exists():
        path.unlink()


@pytest.fixture
def database(temp_db_path: Path) -> Generator[Database, None, None]:
    """Create a test database instance."""
    db = Database(temp_db_path)
    yield db
    reset_database()


@pytest.fixture
def test_settings(temp_db_path: Path) -> Generator[Settings, None, None]:
    """Create test settings with temporary database."""
    reset_settings()
    settings = Settings(
        db_path=temp_db_path,
        scan_limit=10,
        min_score=0,
        request_delay=0.1,
        enable_alerts=True,
        min_mentions_to_track=1,
    )
    yield settings
    reset_settings()


@pytest.fixture
def sample_post() -> RedditPost:
    """Create a sample Reddit post for testing."""
    return RedditPost(
        id="abc123",
        title="$GME to the moon! 🚀🚀🚀 Diamond hands!",
        selftext="Just bought 100 shares of GME. This is going to squeeze!",
        author="test_user",
        subreddit="wallstreetbets",
        score=500,
        upvote_ratio=0.95,
        num_comments=100,
        created_utc=datetime.utcnow(),
        flair="DD",
        url="https://reddit.com/r/wallstreetbets/comments/abc123",
        permalink="https://reddit.com/r/wallstreetbets/comments/abc123",
        is_dd=True,
        awards_count=5,
    )


@pytest.fixture
def sample_sentiment() -> Sentiment:
    """Create a sample sentiment for testing."""
    return Sentiment(
        compound=0.75,
        positive=0.6,
        negative=0.05,
        neutral=0.35,
    )


@pytest.fixture
def sample_mention(sample_sentiment: Sentiment) -> TickerMention:
    """Create a sample ticker mention for testing."""
    return TickerMention(
        ticker="GME",
        post_id="abc123",
        post_title="$GME to the moon!",
        sentiment=sample_sentiment,
        context="Just bought 100 shares of GME. This is going to squeeze!",
        timestamp=datetime.utcnow(),
        subreddit="wallstreetbets",
        post_score=500,
        post_flair="DD",
        is_dd_post=True,
    )


@pytest.fixture
def multiple_mentions(sample_sentiment: Sentiment) -> list[TickerMention]:
    """Create multiple ticker mentions for testing."""
    base_time = datetime.utcnow()
    return [
        TickerMention(
            ticker="GME",
            post_id=f"post_{i}",
            post_title=f"GME post {i}",
            sentiment=sample_sentiment,
            context=f"GME mention context {i}",
            timestamp=base_time,
            subreddit="wallstreetbets",
            post_score=100 * i,
            post_flair="DD" if i % 2 == 0 else None,
            is_dd_post=i % 2 == 0,
        )
        for i in range(1, 6)
    ]
