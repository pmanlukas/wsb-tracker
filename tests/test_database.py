"""Tests for database functionality."""

import pytest
from datetime import datetime, timedelta, timezone

from wsb_tracker.database import Database
from wsb_tracker.models import TickerMention, RedditPost, Sentiment, SentimentLabel


class TestDatabase:
    """Test suite for Database class."""

    def test_database_initialization(self, database):
        """Test database initializes correctly."""
        assert database.db_path.exists()

    def test_tables_created(self, database):
        """Test that all required tables are created."""
        import sqlite3

        with sqlite3.connect(database.db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row[0] for row in cursor.fetchall()}

        assert "mentions" in tables
        assert "snapshots" in tables
        assert "alerts" in tables

    def test_save_mention(self, database, sample_mention):
        """Test saving a single mention."""
        database.save_mention(sample_mention)

        # Verify it was saved
        with database._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM mentions WHERE ticker = ?", ("GME",))
            count = cursor.fetchone()[0]

        assert count == 1

    def test_save_mentions_bulk(self, database, multiple_mentions):
        """Test saving multiple mentions at once."""
        database.save_mentions(multiple_mentions)

        with database._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM mentions")
            count = cursor.fetchone()[0]

        assert count == 3

    def test_save_duplicate_mention(self, database, sample_mention):
        """Test that duplicate mentions are handled gracefully."""
        database.save_mention(sample_mention)
        # Saving same mention again should not raise
        database.save_mention(sample_mention)

        with database._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM mentions WHERE ticker = ?", ("GME",))
            count = cursor.fetchone()[0]

        # Should replace or ignore duplicate based on implementation
        assert count >= 1

    def test_get_ticker_summary_basic(self, database, multiple_mentions):
        """Test getting summary for a specific ticker."""
        database.save_mentions(multiple_mentions)

        summary = database.get_ticker_summary("GME")

        assert summary is not None
        assert summary.ticker == "GME"
        assert summary.mention_count == 2

    def test_get_ticker_summary_sentiment(self, database, multiple_mentions):
        """Test that sentiment is averaged correctly."""
        database.save_mentions(multiple_mentions)

        summary = database.get_ticker_summary("GME")

        # GME mentions have sentiments 0.8 and 0.6, average = 0.7
        assert summary is not None
        assert 0.65 <= summary.avg_sentiment <= 0.75

    def test_get_ticker_summary_not_found(self, database):
        """Test getting summary for non-existent ticker."""
        summary = database.get_ticker_summary("NONEXISTENT")

        assert summary is None

    def test_get_ticker_summary_time_range(self, database, sample_mention):
        """Test getting summary within time range."""
        # Save mention
        database.save_mention(sample_mention)

        # Query with time range that includes the mention
        hours = 24
        summary = database.get_ticker_summary("GME", hours=hours)

        assert summary is not None
        assert summary.mention_count == 1

    def test_get_top_tickers(self, database, multiple_mentions):
        """Test getting top tickers by mention count."""
        database.save_mentions(multiple_mentions)

        summaries = database.get_top_tickers(limit=10)

        assert len(summaries) >= 1
        # GME has 2 mentions, AMC has 1
        assert summaries[0].ticker == "GME"
        assert summaries[0].mention_count == 2

    def test_get_top_tickers_limit(self, database, multiple_mentions):
        """Test that limit is respected."""
        database.save_mentions(multiple_mentions)

        summaries = database.get_top_tickers(limit=1)

        assert len(summaries) == 1

    def test_get_top_tickers_empty(self, database):
        """Test getting top tickers when database is empty."""
        summaries = database.get_top_tickers()

        assert summaries == []

    def test_save_snapshot(self, database, multiple_mentions):
        """Test saving a tracker snapshot."""
        from wsb_tracker.models import TrackerSnapshot, TickerSummary

        database.save_mentions(multiple_mentions)

        summaries = database.get_top_tickers()
        snapshot = TrackerSnapshot(
            timestamp=datetime.now(timezone.utc),
            subreddit="wallstreetbets",
            posts_scanned=10,
            tickers_found=2,
            top_tickers=summaries,
        )

        database.save_snapshot(snapshot)

        with database._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM snapshots")
            count = cursor.fetchone()[0]

        assert count == 1

    def test_get_recent_snapshots(self, database):
        """Test retrieving recent snapshots."""
        from wsb_tracker.models import TrackerSnapshot

        # Save a few snapshots
        for i in range(3):
            snapshot = TrackerSnapshot(
                timestamp=datetime.now(timezone.utc),
                subreddit="wallstreetbets",
                posts_scanned=10 * (i + 1),
                tickers_found=i + 1,
                top_tickers=[],
            )
            database.save_snapshot(snapshot)

        snapshots = database.get_recent_snapshots(limit=2)

        assert len(snapshots) == 2

    def test_save_alert(self, database):
        """Test saving an alert."""
        from wsb_tracker.models import Alert

        alert = Alert(
            timestamp=datetime.now(timezone.utc),
            alert_type="heat_spike",
            ticker="GME",
            message="GME heat score spiked to 8.5",
            severity="high",
        )

        database.save_alert(alert)

        with database._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM alerts")
            count = cursor.fetchone()[0]

        assert count == 1

    def test_get_unacknowledged_alerts(self, database):
        """Test getting unacknowledged alerts."""
        from wsb_tracker.models import Alert

        # Save acknowledged and unacknowledged alerts
        alert1 = Alert(
            timestamp=datetime.now(timezone.utc),
            alert_type="heat_spike",
            ticker="GME",
            message="Test 1",
            acknowledged=False,
        )
        alert2 = Alert(
            timestamp=datetime.now(timezone.utc),
            alert_type="heat_spike",
            ticker="AMC",
            message="Test 2",
            acknowledged=True,
        )

        database.save_alert(alert1)
        database.save_alert(alert2)

        alerts = database.get_unacknowledged_alerts()

        # Should only return unacknowledged
        assert len(alerts) == 1
        assert alerts[0].ticker == "GME"

    def test_acknowledge_alert(self, database):
        """Test acknowledging an alert."""
        from wsb_tracker.models import Alert

        alert = Alert(
            timestamp=datetime.now(timezone.utc),
            alert_type="heat_spike",
            ticker="GME",
            message="Test",
            acknowledged=False,
        )
        database.save_alert(alert)

        # Get the alert ID
        alerts = database.get_unacknowledged_alerts()
        alert_id = alerts[0].id

        # Acknowledge it
        database.acknowledge_alert(alert_id)

        # Should no longer appear in unacknowledged
        alerts = database.get_unacknowledged_alerts()
        assert len(alerts) == 0

    def test_cleanup_old_data(self, database, sample_mention):
        """Test cleanup of old data."""
        # Save a mention
        database.save_mention(sample_mention)

        # Cleanup data older than 0 days (everything)
        database.cleanup_old_data(days=0)

        with database._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM mentions")
            count = cursor.fetchone()[0]

        assert count == 0

    def test_cleanup_preserves_recent(self, database, sample_mention):
        """Test that cleanup preserves recent data."""
        database.save_mention(sample_mention)

        # Cleanup data older than 30 days
        database.cleanup_old_data(days=30)

        with database._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM mentions")
            count = cursor.fetchone()[0]

        # Recent mention should be preserved
        assert count == 1

    def test_get_stats(self, database, multiple_mentions):
        """Test getting database statistics."""
        database.save_mentions(multiple_mentions)

        stats = database.get_stats()

        assert "total_mentions" in stats
        assert stats["total_mentions"] == 3
        assert "unique_tickers" in stats
        assert stats["unique_tickers"] == 2  # GME and AMC

    def test_context_manager(self, temp_db_path):
        """Test database as context manager."""
        with Database(temp_db_path) as db:
            assert db.db_path.exists()

    def test_mention_with_dd_post(self, database):
        """Test tracking DD posts."""
        from wsb_tracker.models import TickerMention, Sentiment

        # Create a DD post mention
        dd_mention = TickerMention(
            ticker="GME",
            post_id="dd123",
            post_title="[DD] Deep dive into GME",
            post_url="https://reddit.com/r/wallstreetbets/comments/dd123",
            subreddit="wallstreetbets",
            author="analyst",
            timestamp=datetime.now(timezone.utc),
            sentiment=Sentiment(compound=0.5, positive=0.5, negative=0.1, neutral=0.4),
            context="Deep dive analysis",
            confidence=0.95,
            has_dollar_sign=True,
            is_dd_post=True,
            upvotes=500,
            comment_count=100,
        )

        database.save_mention(dd_mention)
        summary = database.get_ticker_summary("GME")

        assert summary is not None
        assert summary.dd_count == 1

    def test_engagement_calculation(self, database):
        """Test that engagement ratio is tracked."""
        from wsb_tracker.models import TickerMention, Sentiment

        mention = TickerMention(
            ticker="GME",
            post_id="eng123",
            post_title="High engagement post",
            post_url="https://reddit.com/r/wallstreetbets/comments/eng123",
            subreddit="wallstreetbets",
            author="poster",
            timestamp=datetime.now(timezone.utc),
            sentiment=Sentiment(compound=0.5, positive=0.5, negative=0.1, neutral=0.4),
            context="Test",
            confidence=0.95,
            has_dollar_sign=True,
            upvotes=1000,
            comment_count=500,
            engagement_ratio=0.5,  # 500/1000
        )

        database.save_mention(mention)
        summary = database.get_ticker_summary("GME")

        assert summary is not None
        assert summary.avg_engagement > 0
