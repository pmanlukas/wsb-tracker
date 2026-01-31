"""Main tracker orchestrator coordinating all components.

The WSBTracker class ties together:
- Reddit client for fetching posts
- Ticker extractor for finding stock symbols
- Sentiment analyzer for scoring mentions
- Database for persistence
- Alert system for notifications
- LLM analyzer for extracting trading ideas (optional)
"""

import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Callable, Optional, TYPE_CHECKING

from wsb_tracker.config import get_settings, Settings
from wsb_tracker.database import Database, get_database
from wsb_tracker.runtime_settings import get_runtime_settings
from wsb_tracker.models import (
    Alert,
    RedditPost,
    Sentiment,
    SentimentLabel,
    TickerMention,
    TickerSummary,
    TrackerSnapshot,
)
from wsb_tracker.reddit_client import BaseRedditClient, get_reddit_client
from wsb_tracker.sentiment import WSBSentimentAnalyzer, get_analyzer
from wsb_tracker.ticker_extractor import TickerExtractor, get_extractor

if TYPE_CHECKING:
    from wsb_tracker.llm_analyzer import TradingIdeaAnalyzer

logger = logging.getLogger(__name__)


class WSBTracker:
    """Main tracker coordinating the full analysis pipeline.

    Orchestrates:
    1. Fetch posts from Reddit
    2. Extract ticker symbols from post text
    3. Analyze sentiment for each mention
    4. Store mentions in database
    5. Aggregate into summaries with heat scores
    6. Generate alerts for interesting activity

    Usage:
        tracker = WSBTracker()
        snapshot = tracker.scan(limit=100)
        for summary in snapshot.summaries:
            print(f"{summary.ticker}: {summary.heat_score}")
    """

    def __init__(
        self,
        reddit_client: Optional[BaseRedditClient] = None,
        extractor: Optional[TickerExtractor] = None,
        analyzer: Optional[WSBSentimentAnalyzer] = None,
        database: Optional[Database] = None,
        settings: Optional[Settings] = None,
        llm_analyzer: Optional["TradingIdeaAnalyzer"] = None,
    ) -> None:
        """Initialize tracker with optional dependency injection.

        All dependencies default to singleton instances if not provided.
        Dependency injection is useful for testing.

        Args:
            reddit_client: Reddit client for fetching posts
            extractor: Ticker extractor for finding symbols
            analyzer: Sentiment analyzer
            database: Database for persistence
            settings: Configuration settings
            llm_analyzer: Optional LLM analyzer for trading ideas
        """
        self.settings = settings or get_settings()
        self.reddit = reddit_client or get_reddit_client()
        self.extractor = extractor or get_extractor()
        self.analyzer = analyzer or get_analyzer()
        self.db = database or get_database()

        # Initialize LLM analyzer if enabled
        self.llm_analyzer: Optional["TradingIdeaAnalyzer"] = llm_analyzer
        if llm_analyzer is None and self.settings.llm_enabled:
            self._init_llm_analyzer()

    def _init_llm_analyzer(self) -> None:
        """Initialize LLM analyzer if available and configured."""
        try:
            from wsb_tracker.llm_analyzer import get_analyzer as get_llm_analyzer
            self.llm_analyzer = get_llm_analyzer()
            if self.llm_analyzer.is_available():
                logger.info("LLM analyzer initialized and available")
            else:
                logger.warning("LLM analyzer initialized but not available (missing credentials?)")
                self.llm_analyzer = None
        except ImportError as e:
            logger.warning(f"LLM analyzer not available: {e}")
            self.llm_analyzer = None
        except Exception as e:
            logger.error(f"Failed to initialize LLM analyzer: {e}")
            self.llm_analyzer = None

    def scan(
        self,
        subreddits: Optional[list[str]] = None,
        limit: Optional[int] = None,
        sort: Optional[str] = None,
        min_score: Optional[int] = None,
        on_post: Optional[Callable[[RedditPost], None]] = None,
        on_mention: Optional[Callable[[TickerMention], None]] = None,
    ) -> TrackerSnapshot:
        """Run a single scan cycle.

        Fetches posts, extracts tickers, analyzes sentiment,
        stores results, and returns a snapshot.

        Args:
            subreddits: List of subreddits to scan (default: from config)
            limit: Number of posts to scan per subreddit
            sort: Sort method (hot, new, rising, top)
            min_score: Minimum post score to process
            on_post: Callback for each processed post (for progress tracking)
            on_mention: Callback for each found mention (for progress tracking)

        Returns:
            TrackerSnapshot with scan results
        """
        # Use runtime settings (which fall back to config defaults)
        runtime = get_runtime_settings()
        subreddits = subreddits or runtime.subreddits
        limit = limit if limit is not None else runtime.scan_limit
        sort = sort or runtime.scan_sort
        min_score = min_score if min_score is not None else runtime.min_score

        start_time = time.time()
        posts_analyzed = 0
        all_mentions: list[TickerMention] = []
        ticker_data: dict[str, list[TickerMention]] = {}

        # Track posts for LLM analysis
        posts_for_llm: list[tuple[RedditPost, list[TickerMention]]] = []

        # Scan each subreddit
        for subreddit in subreddits:
            for post in self.reddit.get_posts(subreddit, sort, limit):
                # Skip low-score posts
                if post.score < min_score:
                    continue

                posts_analyzed += 1

                # Progress callback
                if on_post:
                    on_post(post)

                # Extract tickers and analyze sentiment
                mentions = self._process_post(post)

                for mention in mentions:
                    all_mentions.append(mention)

                    # Group by ticker
                    if mention.ticker not in ticker_data:
                        ticker_data[mention.ticker] = []
                    ticker_data[mention.ticker].append(mention)

                    # Progress callback
                    if on_mention:
                        on_mention(mention)

                # Queue for LLM analysis if qualifying
                if mentions and self.llm_analyzer and self.llm_analyzer.should_analyze(post):
                    posts_for_llm.append((post, mentions))

        # Save mentions to database
        if all_mentions:
            self.db.save_mentions(all_mentions)

        # Run LLM analysis on qualifying posts
        llm_analyses = 0
        if posts_for_llm and self.llm_analyzer:
            logger.info(f"Running LLM analysis on {len(posts_for_llm)} qualifying posts")
            for post, mentions in posts_for_llm:
                try:
                    # Analyze each ticker mentioned in the post
                    for mention in mentions:
                        result = self.llm_analyzer.analyze_mention(mention, post)
                        if result and not result.error:
                            llm_analyses += 1
                except Exception as e:
                    logger.error(f"LLM analysis failed for post {post.id}: {e}")

            if llm_analyses > 0:
                logger.info(f"Completed {llm_analyses} LLM analyses")

        # Build ticker summaries
        summaries = self._build_summaries(ticker_data)

        # Sort by heat score
        summaries.sort(key=lambda s: s.heat_score, reverse=True)

        # Identify top movers (highest heat scores)
        top_movers = [s.ticker for s in summaries[:5] if s.heat_score >= 3.0]

        # Check for alerts
        if self.settings.enable_alerts:
            self._check_alerts(summaries)

        # Calculate scan duration
        scan_duration = round(time.time() - start_time, 2)

        # Create snapshot
        snapshot = TrackerSnapshot(
            timestamp=datetime.utcnow(),
            subreddits=subreddits,
            posts_analyzed=posts_analyzed,
            tickers_found=len(ticker_data),
            summaries=summaries,
            top_movers=top_movers,
            scan_duration_seconds=scan_duration,
            source=self.reddit.source_name,
        )

        # Save snapshot
        self.db.save_snapshot(snapshot)

        return snapshot

    def _process_post(self, post: RedditPost) -> list[TickerMention]:
        """Extract tickers and analyze sentiment for a post.

        Args:
            post: Reddit post to process

        Returns:
            List of TickerMention objects found in the post
        """
        mentions: list[TickerMention] = []

        # Extract tickers from full text
        ticker_matches = self.extractor.extract(post.full_text)

        for match in ticker_matches:
            # Analyze sentiment for this specific mention context
            sentiment = self.analyzer.analyze_with_context(
                match.context,
                match.ticker,
            )

            mention = TickerMention(
                ticker=match.ticker,
                post_id=post.id,
                post_title=post.title,
                sentiment=sentiment,
                context=match.context,
                timestamp=post.created_utc,
                subreddit=post.subreddit,
                post_score=post.score,
                post_flair=post.flair,
                is_dd_post=post.is_dd,
            )
            mentions.append(mention)

        return mentions

    def _build_summaries(
        self,
        ticker_data: dict[str, list[TickerMention]],
    ) -> list[TickerSummary]:
        """Build ticker summaries from grouped mentions.

        Args:
            ticker_data: Dict mapping ticker symbols to their mentions

        Returns:
            List of TickerSummary objects
        """
        summaries: list[TickerSummary] = []

        for ticker, mentions in ticker_data.items():
            if len(mentions) < self.settings.min_mentions_to_track:
                continue

            # Calculate aggregates
            mention_count = len(mentions)
            unique_posts = len(set(m.post_id for m in mentions))
            sentiments = [m.sentiment.compound for m in mentions]
            avg_sentiment = sum(sentiments) / mention_count

            # Calculate standard deviation for sentiment volatility
            if mention_count > 1:
                variance = sum((s - avg_sentiment) ** 2 for s in sentiments) / mention_count
                sentiment_std = variance ** 0.5
            else:
                sentiment_std = 0.0

            # Calculate bullish ratio
            bullish_count = sum(1 for s in sentiments if s > 0.15)
            bullish_ratio = bullish_count / mention_count

            # Sum scores and count DD posts
            total_score = sum(m.post_score for m in mentions)
            dd_count = sum(1 for m in mentions if m.is_dd_post)

            # Calculate average engagement
            # (Would need engagement data from posts, using score as proxy)
            avg_engagement = total_score / unique_posts if unique_posts > 0 else 0

            # Get timestamps
            timestamps = [m.timestamp for m in mentions]
            first_seen = min(timestamps)
            last_seen = max(timestamps)

            # Calculate trend vs historical baseline
            mention_change_pct, sentiment_change = self._calculate_trend(ticker)

            summary = TickerSummary(
                ticker=ticker,
                mention_count=mention_count,
                unique_posts=unique_posts,
                avg_sentiment=round(avg_sentiment, 4),
                sentiment_std=round(sentiment_std, 4),
                bullish_ratio=round(bullish_ratio, 4),
                total_score=total_score,
                dd_count=dd_count,
                avg_engagement=round(avg_engagement, 2),
                first_seen=first_seen,
                last_seen=last_seen,
                mention_change_pct=mention_change_pct,
                sentiment_change=sentiment_change,
            )
            summaries.append(summary)

        return summaries

    def _calculate_trend(
        self,
        ticker: str,
    ) -> tuple[Optional[float], Optional[float]]:
        """Calculate trend metrics vs historical baseline.

        Compares current period to previous period of same length.

        Args:
            ticker: Ticker symbol to analyze

        Returns:
            Tuple of (mention_change_pct, sentiment_change)
        """
        lookback = self.settings.lookback_hours

        # Get current and previous period summaries
        current = self.db.get_ticker_summary(ticker, hours=lookback)
        previous = self.db.get_ticker_summary(ticker, hours=lookback * 2)

        if not current or not previous:
            return None, None

        # Calculate mention change percentage
        # Need to estimate previous period only (subtract current from total)
        prev_mention_count = previous.mention_count - current.mention_count
        if prev_mention_count > 0:
            mention_change_pct = (
                (current.mention_count - prev_mention_count) / prev_mention_count * 100
            )
        else:
            mention_change_pct = 100.0 if current.mention_count > 0 else 0.0

        # Calculate sentiment change
        sentiment_change = current.avg_sentiment - previous.avg_sentiment

        return round(mention_change_pct, 2), round(sentiment_change, 4)

    def _check_alerts(self, summaries: list[TickerSummary]) -> None:
        """Check summaries against alert thresholds.

        Generates alerts for:
        - Heat score spikes above threshold
        - Significant sentiment changes
        - Mention volume spikes

        Args:
            summaries: List of ticker summaries to check
        """
        for summary in summaries:
            alerts_to_create: list[Alert] = []

            # Heat score spike
            if summary.heat_score >= self.settings.alert_min_heat_score:
                if summary.heat_score >= self.settings.alert_threshold:
                    alerts_to_create.append(Alert(
                        id=str(uuid.uuid4()),
                        ticker=summary.ticker,
                        alert_type="heat_spike",
                        message=(
                            f"${summary.ticker} heat score reached {summary.heat_score:.1f} "
                            f"({summary.mention_count} mentions, "
                            f"sentiment: {summary.avg_sentiment:+.2f})"
                        ),
                        heat_score=summary.heat_score,
                        sentiment=summary.avg_sentiment,
                        triggered_at=datetime.utcnow(),
                    ))

            # Sentiment shift
            if (
                summary.sentiment_change is not None
                and abs(summary.sentiment_change) >= self.settings.alert_sentiment_change
                and summary.mention_count >= self.settings.alert_min_mentions
            ):
                direction = "bullish" if summary.sentiment_change > 0 else "bearish"
                alerts_to_create.append(Alert(
                    id=str(uuid.uuid4()),
                    ticker=summary.ticker,
                    alert_type="sentiment_shift",
                    message=(
                        f"${summary.ticker} sentiment shifted {direction} "
                        f"({summary.sentiment_change:+.2f} change)"
                    ),
                    heat_score=summary.heat_score,
                    sentiment=summary.avg_sentiment,
                    triggered_at=datetime.utcnow(),
                ))

            # Mention volume spike
            if (
                summary.mention_change_pct is not None
                and summary.mention_change_pct >= self.settings.alert_mention_spike_pct
                and summary.mention_count >= self.settings.alert_min_mentions
            ):
                alerts_to_create.append(Alert(
                    id=str(uuid.uuid4()),
                    ticker=summary.ticker,
                    alert_type="volume_surge",
                    message=(
                        f"${summary.ticker} mention volume surged "
                        f"{summary.mention_change_pct:.0f}% "
                        f"({summary.mention_count} mentions)"
                    ),
                    heat_score=summary.heat_score,
                    sentiment=summary.avg_sentiment,
                    triggered_at=datetime.utcnow(),
                ))

            # Save alerts
            for alert in alerts_to_create:
                self.db.save_alert(alert)

    def get_ticker_details(
        self,
        ticker: str,
        hours: int = 24,
    ) -> Optional[TickerSummary]:
        """Get detailed summary for a specific ticker.

        Args:
            ticker: Ticker symbol to look up
            hours: Time window in hours

        Returns:
            TickerSummary or None if no data
        """
        summary = self.db.get_ticker_summary(ticker.upper(), hours)

        if summary:
            # Add trend data
            mention_change, sentiment_change = self._calculate_trend(ticker.upper())
            # Create new summary with trend data since TickerSummary is immutable
            return TickerSummary(
                ticker=summary.ticker,
                mention_count=summary.mention_count,
                unique_posts=summary.unique_posts,
                avg_sentiment=summary.avg_sentiment,
                sentiment_std=summary.sentiment_std,
                bullish_ratio=summary.bullish_ratio,
                total_score=summary.total_score,
                dd_count=summary.dd_count,
                avg_engagement=summary.avg_engagement,
                first_seen=summary.first_seen,
                last_seen=summary.last_seen,
                mention_change_pct=mention_change,
                sentiment_change=sentiment_change,
            )

        return None

    def get_top_tickers(
        self,
        hours: int = 24,
        limit: int = 10,
    ) -> list[TickerSummary]:
        """Get top tickers by mention count from database.

        Args:
            hours: Time window in hours
            limit: Maximum tickers to return

        Returns:
            List of TickerSummary objects sorted by heat score
        """
        summaries = self.db.get_top_tickers(
            hours=hours,
            limit=limit,
            min_mentions=self.settings.min_mentions_to_track,
        )

        # Add trend data to each summary
        enriched: list[TickerSummary] = []
        for summary in summaries:
            mention_change, sentiment_change = self._calculate_trend(summary.ticker)
            enriched.append(TickerSummary(
                ticker=summary.ticker,
                mention_count=summary.mention_count,
                unique_posts=summary.unique_posts,
                avg_sentiment=summary.avg_sentiment,
                sentiment_std=summary.sentiment_std,
                bullish_ratio=summary.bullish_ratio,
                total_score=summary.total_score,
                dd_count=summary.dd_count,
                avg_engagement=summary.avg_engagement,
                first_seen=summary.first_seen,
                last_seen=summary.last_seen,
                mention_change_pct=mention_change,
                sentiment_change=sentiment_change,
            ))

        # Sort by heat score
        enriched.sort(key=lambda s: s.heat_score, reverse=True)
        return enriched

    def get_recent_mentions(
        self,
        ticker: str,
        hours: int = 24,
        limit: int = 50,
    ) -> list[TickerMention]:
        """Get recent mentions for a specific ticker.

        Args:
            ticker: Ticker symbol
            hours: Time window in hours
            limit: Maximum mentions to return

        Returns:
            List of TickerMention objects, newest first
        """
        return self.db.get_mentions_by_ticker(ticker.upper(), hours, limit)

    def get_alerts(self, acknowledged: bool = False) -> list[Alert]:
        """Get alerts.

        Args:
            acknowledged: If False, only return unacknowledged alerts

        Returns:
            List of Alert objects
        """
        if acknowledged:
            # Would need to add a method to get all alerts
            return []
        return self.db.get_unacknowledged_alerts()

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert.

        Args:
            alert_id: Alert ID to acknowledge

        Returns:
            True if alert was found and acknowledged
        """
        return self.db.acknowledge_alert(alert_id)

    def acknowledge_all_alerts(self) -> int:
        """Acknowledge all pending alerts.

        Returns:
            Number of alerts acknowledged
        """
        return self.db.acknowledge_all_alerts()

    def cleanup(self, days: int = 30) -> dict[str, int]:
        """Clean up old data from database.

        Args:
            days: Days of data to keep

        Returns:
            Dict with counts of deleted records by table
        """
        return self.db.cleanup_old_data(days)

    def get_stats(self) -> dict:
        """Get database and tracker statistics.

        Returns:
            Dict with various statistics
        """
        return self.db.get_stats()
