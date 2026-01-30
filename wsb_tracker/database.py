"""SQLite database operations for WSB Tracker.

Provides persistence for ticker mentions, snapshots, and alerts
with proper indexing for efficient time-based queries.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Generator, Optional

from wsb_tracker.config import get_settings
from wsb_tracker.models import Alert, Sentiment, TickerMention, TickerSummary, TrackerSnapshot


class Database:
    """SQLite database manager for WSB Tracker.

    Handles all persistence operations including:
    - Ticker mentions with deduplication
    - Historical snapshots
    - Alert tracking and acknowledgment
    - Data cleanup and statistics

    Usage:
        db = Database()
        db.save_mention(mention)
        summaries = db.get_top_tickers(hours=24, limit=10)
    """

    SCHEMA = """
    -- Individual ticker mentions with deduplication on (ticker, post_id)
    CREATE TABLE IF NOT EXISTS mentions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        post_id TEXT NOT NULL,
        post_title TEXT,
        subreddit TEXT NOT NULL DEFAULT 'wallstreetbets',
        sentiment_compound REAL NOT NULL,
        sentiment_positive REAL NOT NULL,
        sentiment_negative REAL NOT NULL,
        sentiment_neutral REAL NOT NULL,
        context TEXT,
        post_score INTEGER DEFAULT 0,
        post_flair TEXT,
        is_dd_post INTEGER DEFAULT 0,
        timestamp DATETIME NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(ticker, post_id)
    );

    -- Indexes for efficient queries
    CREATE INDEX IF NOT EXISTS idx_mentions_ticker ON mentions(ticker);
    CREATE INDEX IF NOT EXISTS idx_mentions_timestamp ON mentions(timestamp);
    CREATE INDEX IF NOT EXISTS idx_mentions_ticker_timestamp ON mentions(ticker, timestamp);
    CREATE INDEX IF NOT EXISTS idx_mentions_subreddit ON mentions(subreddit);

    -- Periodic snapshots for historical analysis
    CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME NOT NULL,
        subreddits TEXT NOT NULL,
        posts_analyzed INTEGER NOT NULL DEFAULT 0,
        tickers_found INTEGER NOT NULL DEFAULT 0,
        summaries TEXT NOT NULL,
        top_movers TEXT,
        scan_duration_seconds REAL DEFAULT 0.0,
        source TEXT DEFAULT 'json_fallback',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON snapshots(timestamp);

    -- Alert history for notifications
    CREATE TABLE IF NOT EXISTS alerts (
        id TEXT PRIMARY KEY,
        ticker TEXT NOT NULL,
        alert_type TEXT NOT NULL,
        message TEXT NOT NULL,
        heat_score REAL NOT NULL,
        sentiment REAL NOT NULL,
        triggered_at DATETIME NOT NULL,
        acknowledged INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_alerts_ticker ON alerts(ticker);
    CREATE INDEX IF NOT EXISTS idx_alerts_triggered_at ON alerts(triggered_at);
    CREATE INDEX IF NOT EXISTS idx_alerts_acknowledged ON alerts(acknowledged);
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file. Uses config default if not provided.
        """
        self.db_path = db_path or get_settings().db_path
        self._ensure_directory()
        self._init_schema()

    def _ensure_directory(self) -> None:
        """Ensure database directory exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _init_schema(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript(self.SCHEMA)

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get database connection with proper cleanup.

        Yields:
            SQLite connection with Row factory configured
        """
        conn = sqlite3.connect(
            self.db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ==================== MENTION OPERATIONS ====================

    def save_mention(self, mention: TickerMention) -> None:
        """Save a single ticker mention.

        Uses INSERT OR REPLACE for idempotent upserts.

        Args:
            mention: TickerMention to save
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO mentions
                (ticker, post_id, post_title, subreddit, sentiment_compound,
                 sentiment_positive, sentiment_negative, sentiment_neutral,
                 context, post_score, post_flair, is_dd_post, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mention.ticker,
                    mention.post_id,
                    mention.post_title,
                    mention.subreddit,
                    mention.sentiment.compound,
                    mention.sentiment.positive,
                    mention.sentiment.negative,
                    mention.sentiment.neutral,
                    mention.context,
                    mention.post_score,
                    mention.post_flair,
                    int(mention.is_dd_post),
                    mention.timestamp,
                ),
            )

    def save_mentions(self, mentions: list[TickerMention]) -> int:
        """Save multiple mentions in a batch.

        Args:
            mentions: List of TickerMention objects to save

        Returns:
            Number of mentions saved/updated
        """
        if not mentions:
            return 0

        with self._get_connection() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO mentions
                (ticker, post_id, post_title, subreddit, sentiment_compound,
                 sentiment_positive, sentiment_negative, sentiment_neutral,
                 context, post_score, post_flair, is_dd_post, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        m.ticker,
                        m.post_id,
                        m.post_title,
                        m.subreddit,
                        m.sentiment.compound,
                        m.sentiment.positive,
                        m.sentiment.negative,
                        m.sentiment.neutral,
                        m.context,
                        m.post_score,
                        m.post_flair,
                        int(m.is_dd_post),
                        m.timestamp,
                    )
                    for m in mentions
                ],
            )
        return len(mentions)

    def get_mentions_by_ticker(
        self,
        ticker: str,
        hours: int = 24,
        limit: int = 100,
    ) -> list[TickerMention]:
        """Get recent mentions for a specific ticker.

        Args:
            ticker: Ticker symbol to query
            hours: Time window in hours
            limit: Maximum mentions to return

        Returns:
            List of TickerMention objects, newest first
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM mentions
                WHERE ticker = ? AND timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (ticker.upper(), since, limit),
            )
            rows = cursor.fetchall()

        return [self._row_to_mention(row) for row in rows]

    def _row_to_mention(self, row: sqlite3.Row) -> TickerMention:
        """Convert database row to TickerMention model."""
        return TickerMention(
            ticker=row["ticker"],
            post_id=row["post_id"],
            post_title=row["post_title"] or "",
            sentiment=Sentiment(
                compound=row["sentiment_compound"],
                positive=row["sentiment_positive"],
                negative=row["sentiment_negative"],
                neutral=row["sentiment_neutral"],
            ),
            context=row["context"] or "",
            timestamp=row["timestamp"],
            subreddit=row["subreddit"],
            post_score=row["post_score"],
            post_flair=row["post_flair"],
            is_dd_post=bool(row["is_dd_post"]),
        )

    # ==================== SUMMARY OPERATIONS ====================

    def get_ticker_summary(
        self,
        ticker: str,
        hours: int = 24,
    ) -> Optional[TickerSummary]:
        """Get aggregated summary for a specific ticker.

        Args:
            ticker: Ticker symbol to query
            hours: Time window in hours

        Returns:
            TickerSummary or None if no data
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    ticker,
                    COUNT(*) as mention_count,
                    COUNT(DISTINCT post_id) as unique_posts,
                    AVG(sentiment_compound) as avg_sentiment,
                    SUM(CASE WHEN is_dd_post = 1 THEN 1 ELSE 0 END) as dd_count,
                    SUM(post_score) as total_score,
                    MIN(timestamp) as first_seen,
                    MAX(timestamp) as last_seen
                FROM mentions
                WHERE ticker = ? AND timestamp >= ?
                GROUP BY ticker
                """,
                (ticker.upper(), since),
            )
            row = cursor.fetchone()

        if not row:
            return None

        # Calculate bullish ratio
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    COUNT(CASE WHEN sentiment_compound > 0.15 THEN 1 END) as bullish_count,
                    COUNT(*) as total_count
                FROM mentions
                WHERE ticker = ? AND timestamp >= ?
                """,
                (ticker.upper(), since),
            )
            ratio_row = cursor.fetchone()
            bullish_ratio = (
                ratio_row["bullish_count"] / ratio_row["total_count"]
                if ratio_row["total_count"] > 0 else 0.0
            )

        return TickerSummary(
            ticker=row["ticker"],
            mention_count=row["mention_count"],
            unique_posts=row["unique_posts"],
            avg_sentiment=round(row["avg_sentiment"], 4),
            bullish_ratio=round(bullish_ratio, 4),
            total_score=row["total_score"] or 0,
            dd_count=row["dd_count"],
            first_seen=row["first_seen"],
            last_seen=row["last_seen"],
        )

    def get_top_tickers(
        self,
        hours: int = 24,
        limit: int = 10,
        min_mentions: int = 2,
    ) -> list[TickerSummary]:
        """Get top tickers by mention count.

        Args:
            hours: Time window in hours
            limit: Maximum tickers to return
            min_mentions: Minimum mentions to include

        Returns:
            List of TickerSummary objects sorted by mention count
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    ticker,
                    COUNT(*) as mention_count,
                    COUNT(DISTINCT post_id) as unique_posts,
                    AVG(sentiment_compound) as avg_sentiment,
                    SUM(CASE WHEN is_dd_post = 1 THEN 1 ELSE 0 END) as dd_count,
                    SUM(post_score) as total_score,
                    MIN(timestamp) as first_seen,
                    MAX(timestamp) as last_seen
                FROM mentions
                WHERE timestamp >= ?
                GROUP BY ticker
                HAVING mention_count >= ?
                ORDER BY mention_count DESC
                LIMIT ?
                """,
                (since, min_mentions, limit),
            )
            rows = cursor.fetchall()

        summaries = []
        for row in rows:
            # Calculate bullish ratio for each ticker
            cursor = conn.execute(
                """
                SELECT
                    COUNT(CASE WHEN sentiment_compound > 0.15 THEN 1 END) as bullish_count,
                    COUNT(*) as total_count
                FROM mentions
                WHERE ticker = ? AND timestamp >= ?
                """,
                (row["ticker"], since),
            )
            ratio_row = cursor.fetchone()
            bullish_ratio = (
                ratio_row["bullish_count"] / ratio_row["total_count"]
                if ratio_row["total_count"] > 0 else 0.0
            )

            summaries.append(TickerSummary(
                ticker=row["ticker"],
                mention_count=row["mention_count"],
                unique_posts=row["unique_posts"],
                avg_sentiment=round(row["avg_sentiment"], 4),
                bullish_ratio=round(bullish_ratio, 4),
                total_score=row["total_score"] or 0,
                dd_count=row["dd_count"],
                first_seen=row["first_seen"],
                last_seen=row["last_seen"],
            ))

        return summaries

    # ==================== SNAPSHOT OPERATIONS ====================

    def save_snapshot(self, snapshot: TrackerSnapshot) -> None:
        """Save a tracker snapshot.

        Args:
            snapshot: TrackerSnapshot to save
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO snapshots
                (timestamp, subreddits, posts_analyzed, tickers_found,
                 summaries, top_movers, scan_duration_seconds, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.timestamp,
                    json.dumps(snapshot.subreddits),
                    snapshot.posts_analyzed,
                    snapshot.tickers_found,
                    json.dumps([s.model_dump(mode="json") for s in snapshot.summaries]),
                    json.dumps(snapshot.top_movers),
                    snapshot.scan_duration_seconds,
                    snapshot.source,
                ),
            )

    def get_latest_snapshot(self) -> Optional[dict[str, Any]]:
        """Get the most recent snapshot.

        Returns:
            Snapshot data as dict, or None if no snapshots
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM snapshots ORDER BY timestamp DESC LIMIT 1"
            )
            row = cursor.fetchone()

        if not row:
            return None

        return {
            "id": row["id"],
            "timestamp": row["timestamp"],
            "subreddits": json.loads(row["subreddits"]),
            "posts_analyzed": row["posts_analyzed"],
            "tickers_found": row["tickers_found"],
            "summaries": json.loads(row["summaries"]),
            "top_movers": json.loads(row["top_movers"]) if row["top_movers"] else [],
            "scan_duration_seconds": row["scan_duration_seconds"],
            "source": row["source"],
        }

    def get_snapshots(self, hours: int = 24, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent snapshots.

        Args:
            hours: Time window in hours
            limit: Maximum snapshots to return

        Returns:
            List of snapshot dicts
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM snapshots
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (since, limit),
            )
            rows = cursor.fetchall()

        return [
            {
                "id": row["id"],
                "timestamp": row["timestamp"],
                "subreddits": json.loads(row["subreddits"]),
                "posts_analyzed": row["posts_analyzed"],
                "tickers_found": row["tickers_found"],
                "summaries": json.loads(row["summaries"]),
                "top_movers": json.loads(row["top_movers"]) if row["top_movers"] else [],
                "scan_duration_seconds": row["scan_duration_seconds"],
                "source": row["source"],
            }
            for row in rows
        ]

    # ==================== ALERT OPERATIONS ====================

    def save_alert(self, alert: Alert) -> None:
        """Save an alert.

        Args:
            alert: Alert to save
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO alerts
                (id, ticker, alert_type, message, heat_score, sentiment,
                 triggered_at, acknowledged)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert.id,
                    alert.ticker,
                    alert.alert_type,
                    alert.message,
                    alert.heat_score,
                    alert.sentiment,
                    alert.triggered_at,
                    int(alert.acknowledged),
                ),
            )

    def get_unacknowledged_alerts(self, limit: int = 50) -> list[Alert]:
        """Get all unacknowledged alerts.

        Args:
            limit: Maximum alerts to return

        Returns:
            List of Alert objects
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM alerts
                WHERE acknowledged = 0
                ORDER BY triggered_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()

        return [
            Alert(
                id=row["id"],
                ticker=row["ticker"],
                alert_type=row["alert_type"],
                message=row["message"],
                heat_score=row["heat_score"],
                sentiment=row["sentiment"],
                triggered_at=row["triggered_at"],
                acknowledged=bool(row["acknowledged"]),
            )
            for row in rows
        ]

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Mark an alert as acknowledged.

        Args:
            alert_id: ID of alert to acknowledge

        Returns:
            True if alert was found and updated
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE alerts SET acknowledged = 1 WHERE id = ?",
                (alert_id,),
            )
            return cursor.rowcount > 0

    def acknowledge_all_alerts(self) -> int:
        """Acknowledge all pending alerts.

        Returns:
            Number of alerts acknowledged
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE alerts SET acknowledged = 1 WHERE acknowledged = 0"
            )
            return cursor.rowcount

    # ==================== CLEANUP OPERATIONS ====================

    def cleanup_old_data(self, days: int = 30) -> dict[str, int]:
        """Remove data older than specified days.

        Args:
            days: Days of data to keep

        Returns:
            Dict with counts of deleted records by table
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        deleted = {}

        with self._get_connection() as conn:
            # Delete old mentions
            cursor = conn.execute(
                "DELETE FROM mentions WHERE timestamp < ?",
                (cutoff,),
            )
            deleted["mentions"] = cursor.rowcount

            # Delete old snapshots
            cursor = conn.execute(
                "DELETE FROM snapshots WHERE timestamp < ?",
                (cutoff,),
            )
            deleted["snapshots"] = cursor.rowcount

            # Delete old acknowledged alerts
            cursor = conn.execute(
                "DELETE FROM alerts WHERE triggered_at < ? AND acknowledged = 1",
                (cutoff,),
            )
            deleted["alerts"] = cursor.rowcount

            # Vacuum to reclaim space
            conn.execute("VACUUM")

        return deleted

    def get_stats(self) -> dict[str, Any]:
        """Get database statistics.

        Returns:
            Dict with various statistics
        """
        stats: dict[str, Any] = {}

        with self._get_connection() as conn:
            # Total mentions
            cursor = conn.execute("SELECT COUNT(*) FROM mentions")
            stats["total_mentions"] = cursor.fetchone()[0]

            # Unique tickers
            cursor = conn.execute("SELECT COUNT(DISTINCT ticker) FROM mentions")
            stats["unique_tickers"] = cursor.fetchone()[0]

            # Total snapshots
            cursor = conn.execute("SELECT COUNT(*) FROM snapshots")
            stats["total_snapshots"] = cursor.fetchone()[0]

            # Pending alerts
            cursor = conn.execute("SELECT COUNT(*) FROM alerts WHERE acknowledged = 0")
            stats["pending_alerts"] = cursor.fetchone()[0]

            # Date range
            cursor = conn.execute("SELECT MIN(timestamp), MAX(timestamp) FROM mentions")
            row = cursor.fetchone()
            stats["oldest_mention"] = row[0]
            stats["newest_mention"] = row[1]

        # Database file size
        if self.db_path.exists():
            stats["db_size_bytes"] = self.db_path.stat().st_size
            stats["db_size_mb"] = round(stats["db_size_bytes"] / (1024 * 1024), 2)
        else:
            stats["db_size_bytes"] = 0
            stats["db_size_mb"] = 0.0

        return stats


# Module-level singleton
_db: Optional[Database] = None


def get_database() -> Database:
    """Get or create global database instance."""
    global _db
    if _db is None:
        _db = Database()
    return _db


def reset_database() -> None:
    """Reset database singleton (useful for testing)."""
    global _db
    _db = None
