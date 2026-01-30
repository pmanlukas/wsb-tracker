"""Pydantic data models for WSB Tracker.

This module defines all core data structures used throughout the application,
including sentiment analysis results, Reddit posts, ticker mentions, and
aggregated summaries.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, computed_field


class SentimentLabel(str, Enum):
    """Sentiment classification labels based on compound score thresholds.

    Thresholds (from spec):
    - very_bullish: compound >= 0.5
    - bullish: compound >= 0.15
    - neutral: -0.15 < compound < 0.15
    - bearish: compound <= -0.15
    - very_bearish: compound <= -0.5
    """
    VERY_BULLISH = "very_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    VERY_BEARISH = "very_bearish"


class Sentiment(BaseModel):
    """Sentiment analysis result from VADER with custom WSB lexicon.

    Attributes:
        compound: Overall sentiment score from -1.0 (most negative) to 1.0 (most positive)
        positive: Proportion of text that is positive (0.0 to 1.0)
        negative: Proportion of text that is negative (0.0 to 1.0)
        neutral: Proportion of text that is neutral (0.0 to 1.0)
    """
    compound: float = Field(..., ge=-1.0, le=1.0, description="VADER compound score")
    positive: float = Field(..., ge=0.0, le=1.0, description="Positive proportion")
    negative: float = Field(..., ge=0.0, le=1.0, description="Negative proportion")
    neutral: float = Field(..., ge=0.0, le=1.0, description="Neutral proportion")

    @computed_field
    @property
    def label(self) -> SentimentLabel:
        """Classify sentiment based on compound score thresholds."""
        if self.compound >= 0.5:
            return SentimentLabel.VERY_BULLISH
        elif self.compound >= 0.15:
            return SentimentLabel.BULLISH
        elif self.compound <= -0.5:
            return SentimentLabel.VERY_BEARISH
        elif self.compound <= -0.15:
            return SentimentLabel.BEARISH
        return SentimentLabel.NEUTRAL


class RedditPost(BaseModel):
    """Represents a Reddit post from r/wallstreetbets or similar subreddits.

    Attributes:
        id: Reddit's unique post identifier
        title: Post title
        selftext: Post body content (empty for link posts)
        author: Username of the post author
        subreddit: Subreddit name without r/ prefix
        score: Net upvotes (upvotes - downvotes)
        upvote_ratio: Ratio of upvotes to total votes (0.0 to 1.0)
        num_comments: Number of comments on the post
        created_utc: UTC timestamp when post was created
        flair: Post flair text (e.g., "DD", "YOLO", "Gain")
        url: Full URL to the post
        permalink: Reddit permalink path
        is_dd: Whether this is a Due Diligence post (quality indicator)
        awards_count: Total number of Reddit awards received
    """
    id: str = Field(..., description="Reddit post ID")
    title: str = Field(..., description="Post title")
    selftext: str = Field(default="", description="Post body content")
    author: str = Field(..., description="Post author username")
    subreddit: str = Field(default="wallstreetbets", description="Subreddit name")
    score: int = Field(default=0, description="Net upvotes")
    upvote_ratio: float = Field(default=0.5, ge=0.0, le=1.0, description="Upvote ratio")
    num_comments: int = Field(default=0, ge=0, description="Comment count")
    created_utc: datetime = Field(..., description="Creation timestamp (UTC)")
    flair: Optional[str] = Field(default=None, description="Post flair")
    url: str = Field(default="", description="Full post URL")
    permalink: str = Field(..., description="Reddit permalink")
    is_dd: bool = Field(default=False, description="Is Due Diligence post")
    awards_count: int = Field(default=0, ge=0, description="Number of awards")

    @computed_field
    @property
    def engagement_ratio(self) -> float:
        """Calculate engagement ratio (comments per upvote).

        Higher values indicate more discussion relative to votes,
        which can signal controversial or engaging content.
        """
        if self.score <= 0:
            return float(self.num_comments) if self.num_comments > 0 else 0.0
        return self.num_comments / self.score

    @computed_field
    @property
    def full_text(self) -> str:
        """Combine title and body for full text analysis."""
        if self.selftext:
            return f"{self.title} {self.selftext}"
        return self.title


class TickerMention(BaseModel):
    """A single ticker symbol mention extracted from a post.

    Represents one occurrence of a stock ticker being mentioned,
    along with the context and sentiment of that mention.

    Attributes:
        ticker: Stock ticker symbol (1-5 uppercase letters)
        post_id: ID of the Reddit post containing the mention
        post_title: Title of the post for context
        sentiment: Sentiment analysis result for the mention context
        context: Text surrounding the ticker mention (~50 chars each side)
        timestamp: When the post was created
        subreddit: Source subreddit
        post_score: Score of the containing post
        post_flair: Flair of the containing post
    """
    ticker: str = Field(..., min_length=1, max_length=5, pattern=r"^[A-Z]+$")
    post_id: str = Field(..., description="Reddit post ID")
    post_title: str = Field(..., description="Post title for context")
    sentiment: Sentiment = Field(..., description="Sentiment of mention context")
    context: str = Field(..., max_length=500, description="Text around mention")
    timestamp: datetime = Field(..., description="Post creation time")
    subreddit: str = Field(default="wallstreetbets", description="Source subreddit")
    post_score: int = Field(default=0, description="Post score")
    post_flair: Optional[str] = Field(default=None, description="Post flair")
    is_dd_post: bool = Field(default=False, description="From DD post")


class TickerSummary(BaseModel):
    """Aggregated summary statistics for a single ticker.

    Combines multiple mentions into a summary with metrics
    for ranking and trend analysis.

    Attributes:
        ticker: Stock ticker symbol
        mention_count: Total number of mentions in time window
        unique_posts: Number of unique posts mentioning ticker
        avg_sentiment: Average compound sentiment score
        sentiment_std: Standard deviation of sentiment (volatility)
        bullish_ratio: Percentage of mentions with positive sentiment
        total_score: Sum of all post scores mentioning ticker
        dd_count: Number of Due Diligence posts mentioning ticker
        avg_engagement: Average engagement ratio of posts
        first_seen: Earliest mention timestamp
        last_seen: Most recent mention timestamp
        mention_change_pct: Percent change vs previous period
        sentiment_change: Sentiment change vs previous period
    """
    ticker: str = Field(..., min_length=1, max_length=5, pattern=r"^[A-Z]+$")
    mention_count: int = Field(..., ge=0, description="Total mentions")
    unique_posts: int = Field(..., ge=0, description="Unique post count")
    avg_sentiment: float = Field(..., ge=-1.0, le=1.0, description="Average sentiment")
    sentiment_std: float = Field(default=0.0, ge=0.0, description="Sentiment volatility")
    bullish_ratio: float = Field(default=0.0, ge=0.0, le=1.0, description="Bullish mention %")
    total_score: int = Field(default=0, description="Sum of post scores")
    dd_count: int = Field(default=0, ge=0, description="DD post count")
    avg_engagement: float = Field(default=0.0, ge=0.0, description="Avg engagement")
    first_seen: datetime = Field(..., description="First mention time")
    last_seen: datetime = Field(..., description="Last mention time")
    mention_change_pct: Optional[float] = Field(default=None, description="Mention trend %")
    sentiment_change: Optional[float] = Field(default=None, description="Sentiment trend")

    @computed_field
    @property
    def heat_score(self) -> float:
        """Calculate composite heat score for ranking tickers.

        The heat score combines multiple factors to identify
        "interesting" trading opportunities:

        - Mention velocity (capped at 5x weight)
        - Sentiment strength (absolute value, regardless of direction)
        - DD presence (quality indicator)
        - Engagement level
        - Trending bonus for rapid growth

        Returns:
            Float score typically ranging from 0 to ~10.5
        """
        # Factor 1: Mention velocity (capped at 5x weight)
        mention_factor = min(self.mention_count / 10, 5.0)

        # Factor 2: Sentiment strength (absolute value, regardless of direction)
        sentiment_factor = abs(self.avg_sentiment) * 2

        # Factor 3: DD presence (quality indicator, up to 1.5 bonus)
        dd_factor = min(self.dd_count, 3) * 0.5

        # Factor 4: Engagement level
        engagement_factor = min(self.avg_engagement, 1.0)

        # Factor 5: Trending bonus
        trend_bonus = 0.0
        if self.mention_change_pct is not None and self.mention_change_pct > 50:
            trend_bonus = 1.0

        return round(
            mention_factor + sentiment_factor + dd_factor + engagement_factor + trend_bonus,
            2
        )

    @computed_field
    @property
    def sentiment_label(self) -> SentimentLabel:
        """Get sentiment label from average sentiment."""
        if self.avg_sentiment >= 0.5:
            return SentimentLabel.VERY_BULLISH
        elif self.avg_sentiment >= 0.15:
            return SentimentLabel.BULLISH
        elif self.avg_sentiment <= -0.5:
            return SentimentLabel.VERY_BEARISH
        elif self.avg_sentiment <= -0.15:
            return SentimentLabel.BEARISH
        return SentimentLabel.NEUTRAL


class TrackerSnapshot(BaseModel):
    """Point-in-time snapshot of tracker results.

    Captures the state of a single scan cycle, including
    all discovered tickers and their summaries.

    Attributes:
        timestamp: When the snapshot was taken
        subreddits: List of subreddits scanned
        posts_analyzed: Number of posts processed
        tickers_found: Number of unique tickers discovered
        summaries: List of ticker summaries (sorted by heat score)
        top_movers: Tickers with biggest changes vs previous snapshot
    """
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    subreddits: list[str] = Field(default_factory=lambda: ["wallstreetbets"])
    posts_analyzed: int = Field(default=0, ge=0, description="Posts scanned")
    tickers_found: int = Field(default=0, ge=0, description="Unique tickers")
    summaries: list[TickerSummary] = Field(default_factory=list)
    top_movers: list[str] = Field(default_factory=list, description="Trending tickers")
    scan_duration_seconds: float = Field(default=0.0, ge=0.0, description="Scan time")
    source: str = Field(default="json_fallback", description="Data source used")


class Alert(BaseModel):
    """Alert triggered by unusual ticker activity.

    Attributes:
        id: Unique alert identifier
        ticker: Ticker that triggered the alert
        alert_type: Type of alert (heat_spike, sentiment_shift, volume_surge)
        message: Human-readable alert message
        heat_score: Heat score at time of alert
        sentiment: Sentiment at time of alert
        triggered_at: When the alert was triggered
        acknowledged: Whether the alert has been acknowledged
    """
    id: str = Field(..., description="Alert ID")
    ticker: str = Field(..., description="Ticker symbol")
    alert_type: str = Field(..., description="Alert type")
    message: str = Field(..., description="Alert message")
    heat_score: float = Field(..., ge=0.0, description="Heat score")
    sentiment: float = Field(..., ge=-1.0, le=1.0, description="Sentiment")
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    acknowledged: bool = Field(default=False, description="Is acknowledged")
