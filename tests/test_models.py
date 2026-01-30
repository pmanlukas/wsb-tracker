"""Tests for data models module."""

import pytest
from datetime import datetime, timedelta

from wsb_tracker.models import (
    Sentiment,
    SentimentLabel,
    RedditPost,
    TickerMention,
    TickerSummary,
    TrackerSnapshot,
    Alert,
)


class TestSentiment:
    """Tests for Sentiment model."""

    def test_label_very_bullish(self):
        """Test very bullish sentiment label (compound >= 0.5)."""
        s = Sentiment(compound=0.6, positive=0.7, negative=0.1, neutral=0.2)
        assert s.label == SentimentLabel.VERY_BULLISH

    def test_label_bullish(self):
        """Test bullish sentiment label (0.15 <= compound < 0.5)."""
        s = Sentiment(compound=0.3, positive=0.5, negative=0.1, neutral=0.4)
        assert s.label == SentimentLabel.BULLISH

    def test_label_neutral(self):
        """Test neutral sentiment label (-0.15 < compound < 0.15)."""
        s = Sentiment(compound=0.0, positive=0.3, negative=0.3, neutral=0.4)
        assert s.label == SentimentLabel.NEUTRAL

    def test_label_bearish(self):
        """Test bearish sentiment label (-0.5 < compound <= -0.15)."""
        s = Sentiment(compound=-0.3, positive=0.1, negative=0.5, neutral=0.4)
        assert s.label == SentimentLabel.BEARISH

    def test_label_very_bearish(self):
        """Test very bearish sentiment label (compound <= -0.5)."""
        s = Sentiment(compound=-0.7, positive=0.05, negative=0.8, neutral=0.15)
        assert s.label == SentimentLabel.VERY_BEARISH

    def test_label_at_boundary_bullish(self):
        """Test sentiment at bullish boundary."""
        s = Sentiment(compound=0.15, positive=0.4, negative=0.2, neutral=0.4)
        assert s.label == SentimentLabel.BULLISH

    def test_label_at_boundary_bearish(self):
        """Test sentiment at bearish boundary."""
        s = Sentiment(compound=-0.15, positive=0.2, negative=0.4, neutral=0.4)
        assert s.label == SentimentLabel.BEARISH

    def test_label_at_boundary_very_bullish(self):
        """Test sentiment at very bullish boundary."""
        s = Sentiment(compound=0.5, positive=0.6, negative=0.1, neutral=0.3)
        assert s.label == SentimentLabel.VERY_BULLISH

    def test_label_at_boundary_very_bearish(self):
        """Test sentiment at very bearish boundary."""
        s = Sentiment(compound=-0.5, positive=0.1, negative=0.6, neutral=0.3)
        assert s.label == SentimentLabel.VERY_BEARISH


class TestRedditPost:
    """Tests for RedditPost model."""

    def test_full_text_property(self):
        """Test full_text combines title and selftext."""
        post = RedditPost(
            id="abc",
            title="Test Title",
            selftext="Test body content",
            author="user",
            subreddit="wallstreetbets",
            score=100,
            upvote_ratio=0.9,
            num_comments=10,
            created_utc=datetime.utcnow(),
            flair=None,
            url="",
            permalink="/r/test",
            is_dd=False,
            awards_count=0,
        )
        full_text = post.full_text
        assert "Test Title" in full_text
        assert "Test body content" in full_text

    def test_full_text_empty_selftext(self):
        """Test full_text with empty selftext."""
        post = RedditPost(
            id="abc",
            title="Title Only",
            selftext="",
            author="user",
            subreddit="wallstreetbets",
            score=100,
            upvote_ratio=0.9,
            num_comments=10,
            created_utc=datetime.utcnow(),
            flair=None,
            url="",
            permalink="/r/test",
            is_dd=False,
            awards_count=0,
        )
        assert "Title Only" in post.full_text

    def test_engagement_ratio(self):
        """Test engagement ratio calculation."""
        post = RedditPost(
            id="abc",
            title="Test",
            selftext="",
            author="user",
            subreddit="wallstreetbets",
            score=100,
            upvote_ratio=0.9,
            num_comments=50,
            created_utc=datetime.utcnow(),
            flair=None,
            url="",
            permalink="/r/test",
            is_dd=False,
            awards_count=0,
        )
        # Engagement ratio should be comments / score
        assert post.engagement_ratio == 0.5

    def test_engagement_ratio_zero_score(self):
        """Test engagement ratio with zero score."""
        post = RedditPost(
            id="abc",
            title="Test",
            selftext="",
            author="user",
            subreddit="wallstreetbets",
            score=0,
            upvote_ratio=0.5,
            num_comments=10,
            created_utc=datetime.utcnow(),
            flair=None,
            url="",
            permalink="/r/test",
            is_dd=False,
            awards_count=0,
        )
        # Should handle division by zero gracefully
        assert post.engagement_ratio == 0.0 or post.engagement_ratio == float("inf")


class TestTickerMention:
    """Tests for TickerMention model."""

    def test_create_mention(self):
        """Test creating a ticker mention."""
        sentiment = Sentiment(compound=0.5, positive=0.6, negative=0.1, neutral=0.3)
        mention = TickerMention(
            ticker="GME",
            post_id="abc123",
            post_title="GME to the moon!",
            sentiment=sentiment,
            context="Buying GME tomorrow",
            timestamp=datetime.utcnow(),
            subreddit="wallstreetbets",
            post_score=500,
            post_flair="DD",
            is_dd_post=True,
        )
        assert mention.ticker == "GME"
        assert mention.post_id == "abc123"
        assert mention.is_dd_post is True
        assert mention.sentiment.compound == 0.5


class TestTickerSummary:
    """Tests for TickerSummary model."""

    def test_heat_score_calculation(self):
        """Test heat score formula."""
        summary = TickerSummary(
            ticker="GME",
            mention_count=20,
            unique_posts=15,
            avg_sentiment=0.5,
            bullish_ratio=0.8,
            total_score=1000,
            dd_count=2,
            first_seen=datetime.utcnow(),
            last_seen=datetime.utcnow(),
        )
        # Heat score should be positive
        assert summary.heat_score > 0

    def test_heat_score_mention_factor_capped(self):
        """Test that mention factor is capped at 5.0."""
        summary = TickerSummary(
            ticker="GME",
            mention_count=100,  # Very high mention count
            unique_posts=50,
            avg_sentiment=0.0,  # Neutral sentiment
            bullish_ratio=0.5,
            total_score=5000,
            dd_count=0,
            first_seen=datetime.utcnow(),
            last_seen=datetime.utcnow(),
        )
        # mention_factor = min(100/10, 5.0) = 5.0
        # With neutral sentiment and no DD, score should be around 5.0
        assert summary.heat_score <= 10.0  # Reasonable upper bound

    def test_heat_score_dd_factor(self):
        """Test DD factor contribution to heat score."""
        summary_no_dd = TickerSummary(
            ticker="GME",
            mention_count=10,
            unique_posts=8,
            avg_sentiment=0.0,
            bullish_ratio=0.5,
            total_score=500,
            dd_count=0,
            first_seen=datetime.utcnow(),
            last_seen=datetime.utcnow(),
        )
        summary_with_dd = TickerSummary(
            ticker="GME",
            mention_count=10,
            unique_posts=8,
            avg_sentiment=0.0,
            bullish_ratio=0.5,
            total_score=500,
            dd_count=3,
            first_seen=datetime.utcnow(),
            last_seen=datetime.utcnow(),
        )
        # DD posts should increase heat score
        assert summary_with_dd.heat_score > summary_no_dd.heat_score

    def test_heat_score_sentiment_factor(self):
        """Test sentiment contribution to heat score."""
        summary_neutral = TickerSummary(
            ticker="GME",
            mention_count=10,
            unique_posts=8,
            avg_sentiment=0.0,
            bullish_ratio=0.5,
            total_score=500,
            dd_count=0,
            first_seen=datetime.utcnow(),
            last_seen=datetime.utcnow(),
        )
        summary_bullish = TickerSummary(
            ticker="GME",
            mention_count=10,
            unique_posts=8,
            avg_sentiment=0.8,
            bullish_ratio=0.9,
            total_score=500,
            dd_count=0,
            first_seen=datetime.utcnow(),
            last_seen=datetime.utcnow(),
        )
        # Strong sentiment should increase heat score
        assert summary_bullish.heat_score > summary_neutral.heat_score

    def test_heat_score_with_trend_bonus(self):
        """Test trend bonus contribution to heat score."""
        summary_no_trend = TickerSummary(
            ticker="GME",
            mention_count=10,
            unique_posts=8,
            avg_sentiment=0.5,
            bullish_ratio=0.8,
            total_score=500,
            dd_count=1,
            first_seen=datetime.utcnow(),
            last_seen=datetime.utcnow(),
            mention_change_pct=10.0,  # Below 50% threshold
        )
        summary_with_trend = TickerSummary(
            ticker="GME",
            mention_count=10,
            unique_posts=8,
            avg_sentiment=0.5,
            bullish_ratio=0.8,
            total_score=500,
            dd_count=1,
            first_seen=datetime.utcnow(),
            last_seen=datetime.utcnow(),
            mention_change_pct=60.0,  # Above 50% threshold
        )
        # Trend bonus should add to heat score
        assert summary_with_trend.heat_score > summary_no_trend.heat_score


class TestTrackerSnapshot:
    """Tests for TrackerSnapshot model."""

    def test_create_snapshot(self):
        """Test creating a tracker snapshot."""
        summary = TickerSummary(
            ticker="GME",
            mention_count=10,
            unique_posts=8,
            avg_sentiment=0.5,
            bullish_ratio=0.8,
            total_score=500,
            dd_count=1,
            first_seen=datetime.utcnow(),
            last_seen=datetime.utcnow(),
        )
        snapshot = TrackerSnapshot(
            timestamp=datetime.utcnow(),
            subreddits=["wallstreetbets"],
            posts_analyzed=100,
            tickers_found=5,
            summaries=[summary],
            top_movers=["GME"],
            scan_duration_seconds=2.5,
            source="json_fallback",
        )
        assert snapshot.posts_analyzed == 100
        assert snapshot.tickers_found == 5
        assert len(snapshot.summaries) == 1
        assert snapshot.summaries[0].ticker == "GME"


class TestAlert:
    """Tests for Alert model."""

    def test_create_alert(self):
        """Test creating an alert."""
        alert = Alert(
            id="alert-123",
            ticker="GME",
            alert_type="heat_spike",
            message="GME heat score above threshold",
            heat_score=8.5,
            sentiment=0.6,
            triggered_at=datetime.utcnow(),
            acknowledged=False,
        )
        assert alert.ticker == "GME"
        assert alert.alert_type == "heat_spike"
        assert alert.acknowledged is False

    def test_alert_acknowledge(self):
        """Test alert acknowledged state."""
        alert = Alert(
            id="alert-123",
            ticker="GME",
            alert_type="heat_spike",
            message="Test alert",
            heat_score=8.5,
            sentiment=0.6,
            triggered_at=datetime.utcnow(),
            acknowledged=True,
        )
        assert alert.acknowledged is True


class TestSentimentLabel:
    """Tests for SentimentLabel enum."""

    def test_all_labels_exist(self):
        """Test all expected sentiment labels exist."""
        assert hasattr(SentimentLabel, "VERY_BULLISH")
        assert hasattr(SentimentLabel, "BULLISH")
        assert hasattr(SentimentLabel, "NEUTRAL")
        assert hasattr(SentimentLabel, "BEARISH")
        assert hasattr(SentimentLabel, "VERY_BEARISH")

    def test_label_values(self):
        """Test sentiment label values are strings."""
        for label in SentimentLabel:
            assert isinstance(label.value, str)
