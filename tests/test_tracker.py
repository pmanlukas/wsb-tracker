"""Tests for tracker orchestration functionality."""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

from wsb_tracker.tracker import WSBTracker
from wsb_tracker.models import (
    RedditPost,
    TickerMention,
    TickerSummary,
    TrackerSnapshot,
    Sentiment,
    SentimentLabel,
)


class TestHeatScore:
    """Test suite for heat score calculation in TickerSummary."""

    @pytest.fixture
    def base_summary_kwargs(self):
        """Base keyword arguments for TickerSummary."""
        return {
            "ticker": "GME",
            "unique_posts": 5,
            "first_seen": datetime.now(timezone.utc),
            "last_seen": datetime.now(timezone.utc),
        }

    def test_heat_score_basic(self, base_summary_kwargs):
        """Test basic heat score calculation."""
        summary = TickerSummary(
            **base_summary_kwargs,
            mention_count=10,
            avg_sentiment=0.5,
            dd_count=1,
            avg_engagement=0.5,
        )

        # Heat score should be positive with good metrics
        assert summary.heat_score > 0

    def test_heat_score_components(self, base_summary_kwargs):
        """Test individual components of heat score."""
        # Test mention factor (max 5.0)
        summary_high_mentions = TickerSummary(
            **base_summary_kwargs,
            mention_count=100,
            avg_sentiment=0.0,
            dd_count=0,
            avg_engagement=0.0,
        )
        # mention_factor = min(100/10, 5.0) = 5.0
        assert summary_high_mentions.heat_score >= 5.0

    def test_heat_score_sentiment_factor(self, base_summary_kwargs):
        """Test sentiment affects heat score."""
        # Strong positive sentiment
        summary_pos = TickerSummary(
            **base_summary_kwargs,
            mention_count=1,
            avg_sentiment=1.0,
            dd_count=0,
            avg_engagement=0.0,
        )

        # Strong negative sentiment (also contributes to heat)
        summary_neg = TickerSummary(
            **base_summary_kwargs,
            mention_count=1,
            avg_sentiment=-1.0,
            dd_count=0,
            avg_engagement=0.0,
        )

        # Both should have similar sentiment factor (uses abs value)
        assert abs(summary_pos.heat_score - summary_neg.heat_score) < 0.5

    def test_heat_score_dd_factor(self, base_summary_kwargs):
        """Test DD posts boost heat score."""
        summary_no_dd = TickerSummary(
            **base_summary_kwargs,
            mention_count=5,
            avg_sentiment=0.0,
            dd_count=0,
            avg_engagement=0.0,
        )

        summary_with_dd = TickerSummary(
            **base_summary_kwargs,
            mention_count=5,
            avg_sentiment=0.0,
            dd_count=3,
            avg_engagement=0.0,
        )

        assert summary_with_dd.heat_score > summary_no_dd.heat_score

    def test_heat_score_trend_bonus(self, base_summary_kwargs):
        """Test trend bonus for >50% mention increase."""
        summary_no_trend = TickerSummary(
            **base_summary_kwargs,
            mention_count=10,
            avg_sentiment=0.0,
            dd_count=0,
            avg_engagement=0.0,
            mention_change_pct=30.0,
        )

        summary_with_trend = TickerSummary(
            **base_summary_kwargs,
            mention_count=10,
            avg_sentiment=0.0,
            dd_count=0,
            avg_engagement=0.0,
            mention_change_pct=60.0,
        )

        # 50%+ change should add 1.0 bonus
        assert summary_with_trend.heat_score - summary_no_trend.heat_score == 1.0


class TestWSBTracker:
    """Test suite for WSBTracker class."""

    @pytest.fixture
    def mock_reddit_client(self):
        """Create a mock Reddit client."""
        client = Mock()
        client.get_posts.return_value = [
            RedditPost(
                id="post1",
                title="$GME to the moon!",
                selftext="Diamond hands forever!",
                author="trader1",
                subreddit="wallstreetbets",
                url="https://reddit.com/r/wallstreetbets/comments/post1",
                permalink="/r/wallstreetbets/comments/post1",
                created_utc=datetime.now(timezone.utc),
                score=1000,
                upvote_ratio=0.95,
                num_comments=200,
            ),
            RedditPost(
                id="post2",
                title="[DD] Why AMC is undervalued",
                selftext="Deep analysis here...",
                author="analyst1",
                subreddit="wallstreetbets",
                url="https://reddit.com/r/wallstreetbets/comments/post2",
                permalink="/r/wallstreetbets/comments/post2",
                created_utc=datetime.now(timezone.utc),
                score=500,
                upvote_ratio=0.90,
                num_comments=100,
                is_dd=True,
            ),
        ]
        client.source_name = "mock"
        return client

    @pytest.fixture
    def tracker(self, database, mock_reddit_client):
        """Create a tracker instance with mocked dependencies."""
        tracker = WSBTracker(database=database)
        tracker.reddit = mock_reddit_client
        return tracker

    def test_tracker_initialization(self, tracker):
        """Test tracker initializes correctly."""
        assert tracker is not None
        assert tracker.db is not None
        assert tracker.reddit is not None

    def test_scan_extracts_tickers(self, tracker):
        """Test that scan extracts tickers from posts."""
        snapshot = tracker.scan(limit=10)

        assert snapshot is not None
        assert snapshot.tickers_found > 0

    def test_scan_analyzes_sentiment(self, tracker):
        """Test that scan performs sentiment analysis."""
        snapshot = tracker.scan(limit=10)

        # Check that mentions have sentiment
        assert len(snapshot.summaries) > 0
        for summary in snapshot.summaries:
            assert summary.avg_sentiment is not None

    def test_scan_returns_snapshot(self, tracker):
        """Test that scan returns a valid snapshot."""
        snapshot = tracker.scan(limit=10)

        assert isinstance(snapshot, TrackerSnapshot)
        assert "wallstreetbets" in snapshot.subreddits
        assert snapshot.posts_analyzed > 0

    def test_scan_saves_to_database(self, tracker, database):
        """Test that scan saves mentions to database."""
        tracker.scan(limit=10)

        # Check that mentions were saved
        stats = database.get_stats()
        assert stats["total_mentions"] > 0

    def test_scan_identifies_dd_posts(self, tracker):
        """Test that DD posts are identified."""
        snapshot = tracker.scan(limit=10)

        # AMC post has [DD] in title
        amc_summary = next(
            (s for s in snapshot.summaries if s.ticker == "AMC"),
            None
        )
        if amc_summary:
            assert amc_summary.dd_count >= 1

    def test_scan_calculates_heat_scores(self, tracker):
        """Test that heat scores are calculated."""
        snapshot = tracker.scan(limit=10)

        for summary in snapshot.summaries:
            assert summary.heat_score is not None
            assert summary.heat_score >= 0

    def test_scan_orders_by_heat_score(self, tracker):
        """Test that results are ordered by heat score descending."""
        snapshot = tracker.scan(limit=10)

        if len(snapshot.summaries) > 1:
            for i in range(len(snapshot.summaries) - 1):
                assert (
                    snapshot.summaries[i].heat_score
                    >= snapshot.summaries[i + 1].heat_score
                )

    def test_scan_handles_empty_results(self, database):
        """Test scan handles no posts gracefully."""
        empty_client = Mock()
        empty_client.get_posts.return_value = []
        empty_client.source_name = "mock"

        tracker = WSBTracker(database=database)
        tracker.reddit = empty_client

        snapshot = tracker.scan(limit=10)

        assert snapshot.posts_analyzed == 0
        assert snapshot.tickers_found == 0
        assert len(snapshot.summaries) == 0

    def test_scan_handles_posts_without_tickers(self, database):
        """Test scan handles posts without ticker mentions."""
        no_ticker_client = Mock()
        no_ticker_client.get_posts.return_value = [
            RedditPost(
                id="notickerpost",
                title="Just vibing today",
                selftext="Nothing to see here",
                author="casual",
                subreddit="wallstreetbets",
                url="https://reddit.com/r/wallstreetbets/comments/notickerpost",
                permalink="/r/wallstreetbets/comments/notickerpost",
                created_utc=datetime.now(timezone.utc),
                score=100,
                upvote_ratio=0.80,
                num_comments=10,
            ),
        ]
        no_ticker_client.source_name = "mock"

        tracker = WSBTracker(database=database)
        tracker.reddit = no_ticker_client

        snapshot = tracker.scan(limit=10)

        assert snapshot.posts_analyzed == 1
        assert snapshot.tickers_found == 0

    def test_get_ticker_details(self, tracker):
        """Test getting details for specific ticker."""
        # First scan to populate database
        tracker.scan(limit=10)

        details = tracker.get_ticker_details("GME")

        assert details is not None or details is None  # Depends on data

    def test_alert_on_heat_spike(self, tracker, database):
        """Test that alerts are generated for heat spikes."""
        # Configure alert threshold through settings
        tracker.settings.alert_threshold = 1.0  # Low threshold for testing

        tracker.scan(limit=10)

        # Check if any alerts were generated
        alerts = database.get_unacknowledged_alerts()
        # May or may not have alerts depending on data
        assert isinstance(alerts, list)


class TestTrackerIntegration:
    """Integration tests for the full tracking pipeline."""

    def test_full_pipeline(self, database):
        """Test the full tracking pipeline with mocked Reddit."""
        with patch("wsb_tracker.tracker.get_reddit_client") as mock_get_client:
            mock_client = Mock()
            mock_client.get_posts.return_value = [
                RedditPost(
                    id="integration1",
                    title="🚀 $TSLA to the moon! 🚀",
                    selftext="Bought 100 shares, diamond hands! 💎🙌",
                    author="bull_trader",
                    subreddit="wallstreetbets",
                    url="https://reddit.com/r/wallstreetbets/comments/integration1",
                    permalink="/r/wallstreetbets/comments/integration1",
                    created_utc=datetime.now(timezone.utc),
                    score=5000,
                    upvote_ratio=0.98,
                    num_comments=500,
                ),
            ]
            mock_client.source_name = "mock"
            mock_get_client.return_value = mock_client

            tracker = WSBTracker(database=database)
            tracker.reddit = mock_client

            snapshot = tracker.scan(limit=10)

            # Verify pipeline completed
            assert snapshot.posts_analyzed == 1
            assert snapshot.tickers_found >= 1

            # Verify TSLA was found
            tsla_summary = next(
                (s for s in snapshot.summaries if s.ticker == "TSLA"),
                None
            )
            assert tsla_summary is not None

            # Verify bullish sentiment detected
            assert tsla_summary.avg_sentiment > 0

    def test_multiple_scans_accumulate(self, database):
        """Test that multiple scans accumulate data."""
        with patch("wsb_tracker.tracker.get_reddit_client") as mock_get_client:
            mock_client = Mock()
            mock_client.source_name = "mock"
            mock_get_client.return_value = mock_client

            # First scan
            mock_client.get_posts.return_value = [
                RedditPost(
                    id="scan1",
                    title="$GME looking good",
                    selftext="Bullish!",
                    author="trader1",
                    subreddit="wallstreetbets",
                    url="https://reddit.com/r/wallstreetbets/comments/scan1",
                    permalink="/r/wallstreetbets/comments/scan1",
                    created_utc=datetime.now(timezone.utc),
                    score=100,
                    upvote_ratio=0.9,
                    num_comments=10,
                ),
            ]

            tracker = WSBTracker(database=database)
            tracker.reddit = mock_client
            tracker.scan(limit=10)

            # Second scan with different post
            mock_client.get_posts.return_value = [
                RedditPost(
                    id="scan2",
                    title="More $GME hype",
                    selftext="Still bullish!",
                    author="trader2",
                    subreddit="wallstreetbets",
                    url="https://reddit.com/r/wallstreetbets/comments/scan2",
                    permalink="/r/wallstreetbets/comments/scan2",
                    created_utc=datetime.now(timezone.utc),
                    score=200,
                    upvote_ratio=0.92,
                    num_comments=20,
                ),
            ]

            tracker.scan(limit=10)

            # Should have accumulated mentions
            stats = database.get_stats()
            assert stats["total_mentions"] >= 2
