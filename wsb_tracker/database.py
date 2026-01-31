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
    CREATE INDEX IF NOT EXISTS idx_mentions_sentiment ON mentions(sentiment_compound);
    CREATE INDEX IF NOT EXISTS idx_mentions_dd ON mentions(is_dd_post);

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

    -- Runtime settings (key-value store)
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    -- LLM-extracted trading ideas
    CREATE TABLE IF NOT EXISTS trading_ideas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mention_id INTEGER,
        post_id TEXT NOT NULL,
        ticker TEXT NOT NULL,

        -- Trading idea fields
        has_actionable_idea INTEGER DEFAULT 0,
        direction TEXT,           -- bullish/bearish/neutral
        conviction TEXT,          -- high/medium/low
        timeframe TEXT,           -- intraday/swing/weeks/months/long_term
        entry_price REAL,
        target_price REAL,
        stop_loss REAL,
        catalysts TEXT,           -- JSON array
        risks TEXT,               -- JSON array
        key_points TEXT,          -- JSON array
        post_type TEXT,           -- dd/yolo/gain_loss/meme/news/discussion
        quality_score REAL,
        summary TEXT,

        -- Metadata
        model_used TEXT,
        prompt_tokens INTEGER,
        completion_tokens INTEGER,
        analyzed_at DATETIME DEFAULT CURRENT_TIMESTAMP,

        -- Outcome tracking (for measuring trading idea quality)
        outcome TEXT,             -- hit_target/hit_stop/expired
        outcome_price REAL,
        outcome_date DATETIME,
        outcome_pnl_percent REAL,
        outcome_notes TEXT,

        UNIQUE(post_id, ticker)
    );

    CREATE INDEX IF NOT EXISTS idx_trading_ideas_ticker ON trading_ideas(ticker);
    CREATE INDEX IF NOT EXISTS idx_trading_ideas_post_id ON trading_ideas(post_id);
    CREATE INDEX IF NOT EXISTS idx_trading_ideas_direction ON trading_ideas(direction);
    CREATE INDEX IF NOT EXISTS idx_trading_ideas_conviction ON trading_ideas(conviction);
    CREATE INDEX IF NOT EXISTS idx_trading_ideas_analyzed_at ON trading_ideas(analyzed_at);
    CREATE INDEX IF NOT EXISTS idx_trading_ideas_quality ON trading_ideas(quality_score);

    -- LLM usage tracking for cost monitoring
    CREATE TABLE IF NOT EXISTS llm_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        provider TEXT NOT NULL,
        model TEXT NOT NULL,
        calls_count INTEGER DEFAULT 0,
        prompt_tokens_total INTEGER DEFAULT 0,
        completion_tokens_total INTEGER DEFAULT 0,
        estimated_cost_usd REAL DEFAULT 0.0,
        UNIQUE(date, provider, model)
    );

    CREATE INDEX IF NOT EXISTS idx_llm_usage_date ON llm_usage(date);
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
        # Performance optimizations
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = 10000")
        conn.execute("PRAGMA temp_store = MEMORY")
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

    def get_mentions_paginated(
        self,
        page: int = 1,
        page_size: int = 50,
        ticker: Optional[str] = None,
        subreddit: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        sentiment_min: Optional[float] = None,
        sentiment_max: Optional[float] = None,
        sort_by: str = "timestamp",
        sort_order: str = "desc",
    ) -> tuple[list[TickerMention], int]:
        """Get paginated mentions with filtering and sorting.

        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page
            ticker: Filter by ticker symbol
            subreddit: Filter by subreddit
            date_from: Filter by minimum timestamp
            date_to: Filter by maximum timestamp
            sentiment_min: Filter by minimum sentiment
            sentiment_max: Filter by maximum sentiment
            sort_by: Column to sort by
            sort_order: Sort direction ('asc' or 'desc')

        Returns:
            Tuple of (list of mentions, total count)
        """
        # Build WHERE clause
        conditions = []
        params: list[Any] = []

        if ticker:
            conditions.append("ticker = ?")
            params.append(ticker.upper())
        if subreddit:
            conditions.append("subreddit = ?")
            params.append(subreddit)
        if date_from:
            conditions.append("timestamp >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("timestamp <= ?")
            params.append(date_to)
        if sentiment_min is not None:
            conditions.append("sentiment_compound >= ?")
            params.append(sentiment_min)
        if sentiment_max is not None:
            conditions.append("sentiment_compound <= ?")
            params.append(sentiment_max)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Validate sort column to prevent SQL injection
        valid_sort_columns = {"timestamp", "ticker", "sentiment_compound", "post_score", "subreddit"}
        if sort_by not in valid_sort_columns:
            sort_by = "timestamp"
        sort_order = "DESC" if sort_order.lower() == "desc" else "ASC"

        offset = (page - 1) * page_size

        with self._get_connection() as conn:
            # Get total count
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM mentions WHERE {where_clause}",
                params,
            )
            total = cursor.fetchone()[0]

            # Get paginated results
            cursor = conn.execute(
                f"""
                SELECT * FROM mentions
                WHERE {where_clause}
                ORDER BY {sort_by} {sort_order}
                LIMIT ? OFFSET ?
                """,
                params + [page_size, offset],
            )
            rows = cursor.fetchall()

        mentions = [self._row_to_mention(row) for row in rows]
        return mentions, total

    def get_mention_by_id(self, mention_id: int) -> Optional[TickerMention]:
        """Get a single mention by ID.

        Args:
            mention_id: Database ID of the mention

        Returns:
            TickerMention or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM mentions WHERE id = ?",
                (mention_id,),
            )
            row = cursor.fetchone()

        if not row:
            return None
        return self._row_to_mention(row)

    def delete_mention(self, mention_id: int) -> bool:
        """Delete a single mention by ID.

        Args:
            mention_id: Database ID of the mention to delete

        Returns:
            True if mention was found and deleted
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM mentions WHERE id = ?",
                (mention_id,),
            )
            return cursor.rowcount > 0

    def delete_mentions_bulk(self, mention_ids: list[int]) -> int:
        """Delete multiple mentions by ID.

        Args:
            mention_ids: List of mention IDs to delete

        Returns:
            Number of mentions deleted
        """
        if not mention_ids:
            return 0

        placeholders = ",".join("?" * len(mention_ids))
        with self._get_connection() as conn:
            cursor = conn.execute(
                f"DELETE FROM mentions WHERE id IN ({placeholders})",
                mention_ids,
            )
            return cursor.rowcount

    def get_filter_options(self) -> dict[str, list[str]]:
        """Get distinct values for filter dropdowns.

        Returns:
            Dict with 'tickers' and 'subreddits' lists
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT DISTINCT ticker FROM mentions ORDER BY ticker"
            )
            tickers = [row[0] for row in cursor.fetchall()]

            cursor = conn.execute(
                "SELECT DISTINCT subreddit FROM mentions ORDER BY subreddit"
            )
            subreddits = [row[0] for row in cursor.fetchall()]

        return {"tickers": tickers, "subreddits": subreddits}

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
        mention = TickerMention(
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
        # Attach the database ID as an attribute for API use
        mention._db_id = row["id"]  # type: ignore[attr-defined]
        return mention

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
        summaries = []
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
                    MAX(timestamp) as last_seen,
                    COUNT(CASE WHEN sentiment_compound > 0.15 THEN 1 END) as bullish_count
                FROM mentions
                WHERE timestamp >= ?
                GROUP BY ticker
                HAVING mention_count >= ?
                ORDER BY mention_count DESC
                LIMIT ?
                """,
                (since, min_mentions, limit),
            )
            for row in cursor.fetchall():
                bullish_ratio = (
                    row["bullish_count"] / row["mention_count"]
                    if row["mention_count"] > 0 else 0.0
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

    # ==================== SETTINGS OPERATIONS ====================

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a setting value by key.

        Args:
            key: Setting key
            default: Default value if not found

        Returns:
            Setting value or default
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT value FROM settings WHERE key = ?",
                (key,),
            )
            row = cursor.fetchone()

        if row:
            return row[0]
        return default

    def set_setting(self, key: str, value: str) -> None:
        """Set a setting value.

        Args:
            key: Setting key
            value: Setting value
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                (key, value),
            )

    def get_all_settings(self) -> dict[str, str]:
        """Get all settings as a dict.

        Returns:
            Dict of all settings
        """
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT key, value FROM settings")
            rows = cursor.fetchall()

        return {row[0]: row[1] for row in rows}

    def set_settings(self, settings: dict[str, str]) -> None:
        """Set multiple settings at once.

        Args:
            settings: Dict of key-value pairs to save
        """
        with self._get_connection() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                [(k, v) for k, v in settings.items()],
            )

    def delete_setting(self, key: str) -> bool:
        """Delete a setting.

        Args:
            key: Setting key to delete

        Returns:
            True if setting was found and deleted
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM settings WHERE key = ?",
                (key,),
            )
            return cursor.rowcount > 0

    # ==================== TRADING IDEAS OPERATIONS ====================

    def save_trading_idea(
        self,
        post_id: str,
        ticker: str,
        has_actionable_idea: bool = False,
        direction: Optional[str] = None,
        conviction: Optional[str] = None,
        timeframe: Optional[str] = None,
        entry_price: Optional[float] = None,
        target_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        catalysts: Optional[list[str]] = None,
        risks: Optional[list[str]] = None,
        key_points: Optional[list[str]] = None,
        post_type: Optional[str] = None,
        quality_score: Optional[float] = None,
        summary: Optional[str] = None,
        model_used: Optional[str] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        mention_id: Optional[int] = None,
    ) -> int:
        """Save an LLM-extracted trading idea.

        Args:
            post_id: Reddit post ID
            ticker: Ticker symbol
            has_actionable_idea: Whether the post contains an actionable idea
            direction: bullish/bearish/neutral
            conviction: high/medium/low
            timeframe: intraday/swing/weeks/months/long_term
            entry_price: Suggested entry price
            target_price: Target price
            stop_loss: Stop loss price
            catalysts: List of catalysts
            risks: List of risk factors
            key_points: Key takeaways
            post_type: dd/yolo/gain_loss/meme/news/discussion
            quality_score: Quality score 0.0-1.0
            summary: Brief summary
            model_used: LLM model name
            prompt_tokens: Tokens used in prompt
            completion_tokens: Tokens in completion
            mention_id: Associated mention ID

        Returns:
            ID of the saved trading idea
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT OR REPLACE INTO trading_ideas
                (post_id, ticker, mention_id, has_actionable_idea, direction,
                 conviction, timeframe, entry_price, target_price, stop_loss,
                 catalysts, risks, key_points, post_type, quality_score, summary,
                 model_used, prompt_tokens, completion_tokens, analyzed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    post_id,
                    ticker.upper(),
                    mention_id,
                    int(has_actionable_idea),
                    direction,
                    conviction,
                    timeframe,
                    entry_price,
                    target_price,
                    stop_loss,
                    json.dumps(catalysts) if catalysts else None,
                    json.dumps(risks) if risks else None,
                    json.dumps(key_points) if key_points else None,
                    post_type,
                    quality_score,
                    summary,
                    model_used,
                    prompt_tokens,
                    completion_tokens,
                ),
            )
            return cursor.lastrowid or 0

    def get_trading_idea(self, post_id: str, ticker: str) -> Optional[dict[str, Any]]:
        """Get a trading idea by post_id and ticker.

        Args:
            post_id: Reddit post ID
            ticker: Ticker symbol

        Returns:
            Trading idea dict or None
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM trading_ideas WHERE post_id = ? AND ticker = ?",
                (post_id, ticker.upper()),
            )
            row = cursor.fetchone()

        if not row:
            return None
        return self._row_to_trading_idea(row)

    def get_trading_idea_by_id(self, idea_id: int) -> Optional[dict[str, Any]]:
        """Get a trading idea by ID.

        Args:
            idea_id: Database ID

        Returns:
            Trading idea dict or None
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM trading_ideas WHERE id = ?",
                (idea_id,),
            )
            row = cursor.fetchone()

        if not row:
            return None
        return self._row_to_trading_idea(row)

    def get_trading_ideas_paginated(
        self,
        page: int = 1,
        page_size: int = 50,
        ticker: Optional[str] = None,
        direction: Optional[str] = None,
        conviction: Optional[str] = None,
        post_type: Optional[str] = None,
        min_quality: Optional[float] = None,
        actionable_only: bool = False,
        hours: Optional[int] = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get paginated trading ideas with filtering.

        Args:
            page: Page number (1-indexed)
            page_size: Items per page
            ticker: Filter by ticker
            direction: Filter by direction (bullish/bearish/neutral)
            conviction: Filter by conviction (high/medium/low)
            post_type: Filter by post type
            min_quality: Minimum quality score
            actionable_only: Only return actionable ideas
            hours: Limit to ideas from last N hours

        Returns:
            Tuple of (list of ideas, total count)
        """
        conditions = []
        params: list[Any] = []

        if ticker:
            conditions.append("ticker = ?")
            params.append(ticker.upper())
        if direction:
            conditions.append("direction = ?")
            params.append(direction)
        if conviction:
            conditions.append("conviction = ?")
            params.append(conviction)
        if post_type:
            conditions.append("post_type = ?")
            params.append(post_type)
        if min_quality is not None:
            conditions.append("quality_score >= ?")
            params.append(min_quality)
        if actionable_only:
            conditions.append("has_actionable_idea = 1")
        if hours:
            since = datetime.utcnow() - timedelta(hours=hours)
            conditions.append("analyzed_at >= ?")
            params.append(since)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        offset = (page - 1) * page_size

        with self._get_connection() as conn:
            # Get total count
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM trading_ideas WHERE {where_clause}",
                params,
            )
            total = cursor.fetchone()[0]

            # Get paginated results
            cursor = conn.execute(
                f"""
                SELECT * FROM trading_ideas
                WHERE {where_clause}
                ORDER BY analyzed_at DESC
                LIMIT ? OFFSET ?
                """,
                params + [page_size, offset],
            )
            rows = cursor.fetchall()

        ideas = [self._row_to_trading_idea(row) for row in rows]
        return ideas, total

    def get_trading_ideas_by_ticker(
        self,
        ticker: str,
        hours: int = 24,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get trading ideas for a specific ticker.

        Args:
            ticker: Ticker symbol
            hours: Time window in hours
            limit: Maximum ideas to return

        Returns:
            List of trading idea dicts
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM trading_ideas
                WHERE ticker = ? AND analyzed_at >= ?
                ORDER BY analyzed_at DESC
                LIMIT ?
                """,
                (ticker.upper(), since, limit),
            )
            rows = cursor.fetchall()

        return [self._row_to_trading_idea(row) for row in rows]

    def get_trading_ideas_summary(self, hours: int = 24) -> dict[str, Any]:
        """Get summary statistics for trading ideas.

        Args:
            hours: Time window in hours

        Returns:
            Summary statistics dict
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as total_ideas,
                    SUM(CASE WHEN has_actionable_idea = 1 THEN 1 ELSE 0 END) as actionable_count,
                    SUM(CASE WHEN direction = 'bullish' THEN 1 ELSE 0 END) as bullish_count,
                    SUM(CASE WHEN direction = 'bearish' THEN 1 ELSE 0 END) as bearish_count,
                    SUM(CASE WHEN direction = 'neutral' THEN 1 ELSE 0 END) as neutral_count,
                    SUM(CASE WHEN conviction = 'high' THEN 1 ELSE 0 END) as high_conviction_count,
                    AVG(quality_score) as avg_quality
                FROM trading_ideas
                WHERE analyzed_at >= ?
                """,
                (since,),
            )
            row = cursor.fetchone()

        return {
            "total_ideas": row["total_ideas"] or 0,
            "actionable_count": row["actionable_count"] or 0,
            "bullish_count": row["bullish_count"] or 0,
            "bearish_count": row["bearish_count"] or 0,
            "neutral_count": row["neutral_count"] or 0,
            "high_conviction_count": row["high_conviction_count"] or 0,
            "avg_quality": round(row["avg_quality"] or 0, 3),
        }

    def _row_to_trading_idea(self, row: sqlite3.Row) -> dict[str, Any]:
        """Convert database row to trading idea dict."""
        result = {
            "id": row["id"],
            "mention_id": row["mention_id"],
            "post_id": row["post_id"],
            "ticker": row["ticker"],
            "has_actionable_idea": bool(row["has_actionable_idea"]),
            "direction": row["direction"],
            "conviction": row["conviction"],
            "timeframe": row["timeframe"],
            "entry_price": row["entry_price"],
            "target_price": row["target_price"],
            "stop_loss": row["stop_loss"],
            "catalysts": json.loads(row["catalysts"]) if row["catalysts"] else [],
            "risks": json.loads(row["risks"]) if row["risks"] else [],
            "key_points": json.loads(row["key_points"]) if row["key_points"] else [],
            "post_type": row["post_type"],
            "quality_score": row["quality_score"],
            "summary": row["summary"],
            "model_used": row["model_used"],
            "prompt_tokens": row["prompt_tokens"],
            "completion_tokens": row["completion_tokens"],
            "analyzed_at": row["analyzed_at"],
        }
        # Add outcome fields (may not exist in older databases)
        try:
            result["outcome"] = row["outcome"]
            result["outcome_price"] = row["outcome_price"]
            result["outcome_date"] = row["outcome_date"]
            result["outcome_pnl_percent"] = row["outcome_pnl_percent"]
            result["outcome_notes"] = row["outcome_notes"]
        except (IndexError, KeyError):
            result["outcome"] = None
            result["outcome_price"] = None
            result["outcome_date"] = None
            result["outcome_pnl_percent"] = None
            result["outcome_notes"] = None
        return result

    def update_trading_idea_outcome(
        self,
        idea_id: int,
        outcome: str,
        outcome_price: float,
        notes: str = "",
    ) -> Optional[dict[str, Any]]:
        """Record the outcome of a trading idea.

        Args:
            idea_id: ID of the trading idea
            outcome: Outcome type ('hit_target', 'hit_stop', 'expired')
            outcome_price: Price at which outcome occurred
            notes: Optional notes about the outcome

        Returns:
            Updated trading idea dict or None if not found
        """
        # First get the idea to calculate PnL
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM trading_ideas WHERE id = ?",
                (idea_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            # Calculate PnL percent if we have entry price
            pnl_percent = None
            entry_price = row["entry_price"]
            if entry_price and entry_price > 0:
                pnl_percent = ((outcome_price - entry_price) / entry_price) * 100
                # Flip sign for bearish trades
                if row["direction"] == "bearish":
                    pnl_percent = -pnl_percent

            # Update the outcome
            conn.execute(
                """
                UPDATE trading_ideas
                SET outcome = ?,
                    outcome_price = ?,
                    outcome_date = ?,
                    outcome_pnl_percent = ?,
                    outcome_notes = ?
                WHERE id = ?
                """,
                (
                    outcome,
                    outcome_price,
                    datetime.utcnow(),
                    pnl_percent,
                    notes,
                    idea_id,
                ),
            )

        # Return updated idea
        return self.get_trading_idea_by_id(idea_id)

    def get_trading_idea_by_id(self, idea_id: int) -> Optional[dict[str, Any]]:
        """Get a single trading idea by ID.

        Args:
            idea_id: ID of the trading idea

        Returns:
            Trading idea dict or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM trading_ideas WHERE id = ?",
                (idea_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_trading_idea(row)

    def get_performance_stats(self, hours: int = 720) -> dict[str, Any]:
        """Get win rate and performance statistics for trading ideas.

        Args:
            hours: Lookback period in hours (default 30 days)

        Returns:
            Performance statistics dict
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as total_ideas,
                    SUM(CASE WHEN outcome IS NOT NULL THEN 1 ELSE 0 END) as outcomes_recorded,
                    SUM(CASE WHEN outcome = 'hit_target' THEN 1 ELSE 0 END) as hit_target_count,
                    SUM(CASE WHEN outcome = 'hit_stop' THEN 1 ELSE 0 END) as hit_stop_count,
                    SUM(CASE WHEN outcome = 'expired' THEN 1 ELSE 0 END) as expired_count,
                    AVG(CASE WHEN outcome IS NOT NULL THEN outcome_pnl_percent END) as avg_pnl_percent
                FROM trading_ideas
                WHERE analyzed_at >= ?
                """,
                (since,),
            )
            row = cursor.fetchone()

            # Calculate win rate
            outcomes_recorded = row["outcomes_recorded"] or 0
            hit_target_count = row["hit_target_count"] or 0
            win_rate = (hit_target_count / outcomes_recorded * 100) if outcomes_recorded > 0 else 0

            # Get win rate by direction
            cursor = conn.execute(
                """
                SELECT
                    direction,
                    COUNT(*) as total,
                    SUM(CASE WHEN outcome = 'hit_target' THEN 1 ELSE 0 END) as wins
                FROM trading_ideas
                WHERE analyzed_at >= ? AND outcome IS NOT NULL AND direction IS NOT NULL
                GROUP BY direction
                """,
                (since,),
            )
            win_rate_by_direction = {}
            for r in cursor.fetchall():
                if r["total"] > 0:
                    win_rate_by_direction[r["direction"]] = round(r["wins"] / r["total"] * 100, 1)

            # Get win rate by conviction
            cursor = conn.execute(
                """
                SELECT
                    conviction,
                    COUNT(*) as total,
                    SUM(CASE WHEN outcome = 'hit_target' THEN 1 ELSE 0 END) as wins
                FROM trading_ideas
                WHERE analyzed_at >= ? AND outcome IS NOT NULL AND conviction IS NOT NULL
                GROUP BY conviction
                """,
                (since,),
            )
            win_rate_by_conviction = {}
            for r in cursor.fetchall():
                if r["total"] > 0:
                    win_rate_by_conviction[r["conviction"]] = round(r["wins"] / r["total"] * 100, 1)

        return {
            "total_ideas": row["total_ideas"] or 0,
            "outcomes_recorded": outcomes_recorded,
            "hit_target_count": hit_target_count,
            "hit_stop_count": row["hit_stop_count"] or 0,
            "expired_count": row["expired_count"] or 0,
            "win_rate": round(win_rate, 1),
            "win_rate_by_direction": win_rate_by_direction,
            "win_rate_by_conviction": win_rate_by_conviction,
            "avg_pnl_percent": round(row["avg_pnl_percent"] or 0, 2),
        }

    # ==================== CORRELATION OPERATIONS ====================

    def get_ticker_cooccurrence(
        self,
        hours: int = 24,
        min_cooccurrences: int = 2,
        limit: int = 50,
        ticker: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Find tickers frequently mentioned in the same posts.

        Args:
            hours: Time window in hours
            min_cooccurrences: Minimum number of co-occurrences
            limit: Maximum pairs to return
            ticker: Filter to pairs containing this ticker

        Returns:
            List of co-occurrence dicts with ticker_a, ticker_b, count, sentiment
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        with self._get_connection() as conn:
            # Build query based on whether we're filtering by ticker
            if ticker:
                cursor = conn.execute(
                    """
                    WITH post_tickers AS (
                        SELECT DISTINCT post_id, ticker, sentiment_compound
                        FROM mentions
                        WHERE timestamp >= ?
                    )
                    SELECT
                        a.ticker as ticker_a,
                        b.ticker as ticker_b,
                        COUNT(DISTINCT a.post_id) as cooccurrence_count,
                        AVG((a.sentiment_compound + b.sentiment_compound) / 2) as avg_combined_sentiment,
                        GROUP_CONCAT(DISTINCT a.post_id) as sample_post_ids
                    FROM post_tickers a
                    INNER JOIN post_tickers b
                        ON a.post_id = b.post_id
                        AND a.ticker < b.ticker
                    WHERE a.ticker = ? OR b.ticker = ?
                    GROUP BY a.ticker, b.ticker
                    HAVING COUNT(DISTINCT a.post_id) >= ?
                    ORDER BY cooccurrence_count DESC
                    LIMIT ?
                    """,
                    (since, ticker.upper(), ticker.upper(), min_cooccurrences, limit),
                )
            else:
                cursor = conn.execute(
                    """
                    WITH post_tickers AS (
                        SELECT DISTINCT post_id, ticker, sentiment_compound
                        FROM mentions
                        WHERE timestamp >= ?
                    )
                    SELECT
                        a.ticker as ticker_a,
                        b.ticker as ticker_b,
                        COUNT(DISTINCT a.post_id) as cooccurrence_count,
                        AVG((a.sentiment_compound + b.sentiment_compound) / 2) as avg_combined_sentiment,
                        GROUP_CONCAT(DISTINCT a.post_id) as sample_post_ids
                    FROM post_tickers a
                    INNER JOIN post_tickers b
                        ON a.post_id = b.post_id
                        AND a.ticker < b.ticker
                    GROUP BY a.ticker, b.ticker
                    HAVING COUNT(DISTINCT a.post_id) >= ?
                    ORDER BY cooccurrence_count DESC
                    LIMIT ?
                    """,
                    (since, min_cooccurrences, limit),
                )

            results = []
            for row in cursor.fetchall():
                sample_ids = row["sample_post_ids"].split(",")[:5] if row["sample_post_ids"] else []
                results.append({
                    "ticker_a": row["ticker_a"],
                    "ticker_b": row["ticker_b"],
                    "cooccurrence_count": row["cooccurrence_count"],
                    "avg_combined_sentiment": round(row["avg_combined_sentiment"] or 0, 4),
                    "sample_post_ids": sample_ids,
                })
            return results

    def get_ticker_sentiment_correlation(
        self,
        hours: int = 24,
        min_mentions: int = 5,
        min_shared_periods: int = 3,
        limit: int = 50,
        ticker: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Calculate sentiment correlation between ticker pairs.

        Uses hourly buckets to align time series for correlation calculation.

        Args:
            hours: Time window in hours
            min_mentions: Minimum mentions per ticker to include
            min_shared_periods: Minimum overlapping time periods
            limit: Maximum pairs to return
            ticker: Filter to pairs containing this ticker

        Returns:
            List of correlation dicts with ticker_a, ticker_b, correlation, etc.
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        with self._get_connection() as conn:
            # Build query with optional ticker filter
            ticker_filter = ""
            params = [since, min_shared_periods, limit]
            if ticker:
                ticker_filter = "WHERE a.ticker = ? OR b.ticker = ?"
                params = [since, ticker.upper(), ticker.upper(), min_shared_periods, limit]

            query = f"""
            WITH hourly_sentiment AS (
                SELECT
                    ticker,
                    strftime('%Y-%m-%d %H:00:00', timestamp) as hour_bucket,
                    AVG(sentiment_compound) as avg_sentiment,
                    COUNT(*) as mention_count
                FROM mentions
                WHERE timestamp >= ?
                GROUP BY ticker, strftime('%Y-%m-%d %H:00:00', timestamp)
                HAVING COUNT(*) >= 1
            ),
            ticker_pairs AS (
                SELECT
                    a.ticker as ticker_a,
                    b.ticker as ticker_b,
                    a.hour_bucket,
                    a.avg_sentiment as sentiment_a,
                    b.avg_sentiment as sentiment_b
                FROM hourly_sentiment a
                INNER JOIN hourly_sentiment b
                    ON a.hour_bucket = b.hour_bucket
                    AND a.ticker < b.ticker
                {ticker_filter}
            )
            SELECT
                ticker_a,
                ticker_b,
                COUNT(*) as shared_periods,
                -- Pearson correlation calculation
                CASE
                    WHEN COUNT(*) < 2 THEN 0
                    WHEN (COUNT(*) * SUM(sentiment_a * sentiment_a) - SUM(sentiment_a) * SUM(sentiment_a)) *
                         (COUNT(*) * SUM(sentiment_b * sentiment_b) - SUM(sentiment_b) * SUM(sentiment_b)) <= 0
                    THEN 0
                    ELSE
                        (COUNT(*) * SUM(sentiment_a * sentiment_b) - SUM(sentiment_a) * SUM(sentiment_b)) /
                        SQRT((COUNT(*) * SUM(sentiment_a * sentiment_a) - SUM(sentiment_a) * SUM(sentiment_a)) *
                             (COUNT(*) * SUM(sentiment_b * sentiment_b) - SUM(sentiment_b) * SUM(sentiment_b)))
                END as correlation,
                AVG(sentiment_a) as avg_sentiment_a,
                AVG(sentiment_b) as avg_sentiment_b
            FROM ticker_pairs
            GROUP BY ticker_a, ticker_b
            HAVING COUNT(*) >= ?
            ORDER BY ABS(correlation) DESC
            LIMIT ?
            """

            cursor = conn.execute(query, params)
            results = []
            for row in cursor.fetchall():
                results.append({
                    "ticker_a": row["ticker_a"],
                    "ticker_b": row["ticker_b"],
                    "correlation": round(row["correlation"] or 0, 4),
                    "shared_periods": row["shared_periods"],
                    "avg_sentiment_a": round(row["avg_sentiment_a"] or 0, 4),
                    "avg_sentiment_b": round(row["avg_sentiment_b"] or 0, 4),
                })
            return results

    def get_correlation_matrix(
        self,
        tickers: list[str],
        hours: int = 24,
    ) -> dict[str, dict[str, float]]:
        """Get NxN correlation matrix for specific tickers.

        Args:
            tickers: List of ticker symbols
            hours: Time window in hours

        Returns:
            Nested dict: matrix[ticker_a][ticker_b] = correlation
        """
        if not tickers:
            return {}

        # Get all correlations for these tickers
        correlations = self.get_ticker_sentiment_correlation(
            hours=hours,
            min_mentions=1,
            min_shared_periods=1,
            limit=1000,  # Get all pairs
        )

        # Build matrix
        matrix: dict[str, dict[str, float]] = {t: {} for t in tickers}
        for corr in correlations:
            a, b = corr["ticker_a"], corr["ticker_b"]
            if a in matrix and b in tickers:
                matrix[a][b] = corr["correlation"]
            if b in matrix and a in tickers:
                matrix[b][a] = corr["correlation"]

        return matrix

    # ==================== LLM USAGE OPERATIONS ====================

    def update_llm_usage(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        estimated_cost: float = 0.0,
    ) -> None:
        """Update LLM usage tracking for today.

        Args:
            provider: LLM provider name (e.g., 'anthropic')
            model: Model name
            prompt_tokens: Tokens used in prompt
            completion_tokens: Tokens in completion
            estimated_cost: Estimated cost in USD
        """
        today = datetime.utcnow().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            # Try to update existing row
            cursor = conn.execute(
                """
                UPDATE llm_usage
                SET calls_count = calls_count + 1,
                    prompt_tokens_total = prompt_tokens_total + ?,
                    completion_tokens_total = completion_tokens_total + ?,
                    estimated_cost_usd = estimated_cost_usd + ?
                WHERE date = ? AND provider = ? AND model = ?
                """,
                (prompt_tokens, completion_tokens, estimated_cost, today, provider, model),
            )
            if cursor.rowcount == 0:
                # Insert new row if update didn't match
                conn.execute(
                    """
                    INSERT INTO llm_usage
                    (date, provider, model, calls_count, prompt_tokens_total,
                     completion_tokens_total, estimated_cost_usd)
                    VALUES (?, ?, ?, 1, ?, ?, ?)
                    """,
                    (today, provider, model, prompt_tokens, completion_tokens, estimated_cost),
                )

    def get_llm_usage_today(self, provider: str = "anthropic") -> dict[str, Any]:
        """Get today's LLM usage stats.

        Args:
            provider: LLM provider name

        Returns:
            Usage stats dict
        """
        today = datetime.utcnow().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    SUM(calls_count) as calls,
                    SUM(prompt_tokens_total) as prompt_tokens,
                    SUM(completion_tokens_total) as completion_tokens,
                    SUM(estimated_cost_usd) as cost
                FROM llm_usage
                WHERE date = ? AND provider = ?
                """,
                (today, provider),
            )
            row = cursor.fetchone()

        return {
            "date": today,
            "calls": row["calls"] or 0,
            "prompt_tokens": row["prompt_tokens"] or 0,
            "completion_tokens": row["completion_tokens"] or 0,
            "estimated_cost_usd": round(row["cost"] or 0, 4),
        }

    def get_llm_usage_stats(self, days: int = 30) -> list[dict[str, Any]]:
        """Get LLM usage statistics for the last N days.

        Args:
            days: Number of days to include

        Returns:
            List of daily usage stats
        """
        cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    date,
                    provider,
                    model,
                    calls_count,
                    prompt_tokens_total,
                    completion_tokens_total,
                    estimated_cost_usd
                FROM llm_usage
                WHERE date >= ?
                ORDER BY date DESC, provider, model
                """,
                (cutoff,),
            )
            rows = cursor.fetchall()

        return [
            {
                "date": row["date"],
                "provider": row["provider"],
                "model": row["model"],
                "calls": row["calls_count"],
                "prompt_tokens": row["prompt_tokens_total"],
                "completion_tokens": row["completion_tokens_total"],
                "estimated_cost_usd": round(row["estimated_cost_usd"], 4),
            }
            for row in rows
        ]

    def get_llm_usage_summary(self, days: int = 30) -> dict[str, Any]:
        """Get aggregated LLM usage summary.

        Args:
            days: Number of days to include

        Returns:
            Aggregated usage summary
        """
        cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    SUM(calls_count) as total_calls,
                    SUM(prompt_tokens_total) as total_prompt_tokens,
                    SUM(completion_tokens_total) as total_completion_tokens,
                    SUM(estimated_cost_usd) as total_cost,
                    COUNT(DISTINCT date) as active_days
                FROM llm_usage
                WHERE date >= ?
                """,
                (cutoff,),
            )
            row = cursor.fetchone()

        return {
            "period_days": days,
            "active_days": row["active_days"] or 0,
            "total_calls": row["total_calls"] or 0,
            "total_prompt_tokens": row["total_prompt_tokens"] or 0,
            "total_completion_tokens": row["total_completion_tokens"] or 0,
            "total_cost_usd": round(row["total_cost"] or 0, 2),
            "avg_daily_cost": round((row["total_cost"] or 0) / max(row["active_days"] or 1, 1), 2),
        }

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

            # Delete old trading ideas
            cursor = conn.execute(
                "DELETE FROM trading_ideas WHERE analyzed_at < ?",
                (cutoff,),
            )
            deleted["trading_ideas"] = cursor.rowcount

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

            # Trading ideas stats
            cursor = conn.execute("SELECT COUNT(*) FROM trading_ideas")
            stats["total_trading_ideas"] = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT COUNT(*) FROM trading_ideas WHERE has_actionable_idea = 1"
            )
            stats["actionable_ideas"] = cursor.fetchone()[0]

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
