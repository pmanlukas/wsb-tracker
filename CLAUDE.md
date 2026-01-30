# WSB Tracker - Project Guide

## Project Overview
CLI tool that monitors r/wallstreetbets for stock ticker mentions, analyzes sentiment using VADER with WSB-specific lexicon, and surfaces trending tickers via a heat score algorithm.

## Quick Commands
```bash
# Development
pip install -e ".[dev]"    # Install with dev dependencies
pytest -v --cov=wsb_tracker # Run tests with coverage
ruff check wsb_tracker tests # Lint code

# CLI Usage
wsb scan --limit 50        # Scan Reddit for mentions
wsb top                    # Show trending tickers
wsb ticker GME             # Details for specific ticker
wsb stats                  # Database statistics
wsb watch --interval 300   # Continuous monitoring
```

## Architecture

### Key Modules
- `cli.py` - Typer CLI with Rich output (entry point: `wsb`)
- `tracker.py` - Main orchestrator, coordinates scanning pipeline
- `reddit_client.py` - Reddit API (JSONClient for public access, PRAWClient with credentials)
- `database.py` - SQLite persistence with context manager pattern
- `sentiment.py` - VADER + custom WSB lexicon (moon, tendies, diamond hands, etc.)
- `ticker_extractor.py` - Regex-based ticker extraction with exclusion lists

### Data Flow
```
Reddit → JSONClient → RedditPost → TickerExtractor → TickerMention
                                 → SentimentAnalyzer → Sentiment
                                                    ↓
                                              Database → TickerSummary (with heat_score)
```

### Heat Score Formula
```python
mention_factor = min(mention_count / 10, 5.0)      # 0-5 points
sentiment_factor = abs(avg_sentiment) * 2          # 0-2 points
dd_factor = min(dd_count, 3) * 0.5                 # 0-1.5 points
trend_bonus = 1.0 if mention_change_pct > 50 else 0
```

## Database Schema
- `mentions` - Individual ticker mentions (ticker, post_id unique)
- `snapshots` - Point-in-time scan results (JSON-serialized summaries)
- `alerts` - Triggered alerts with acknowledgment status

## Configuration
Environment variables with `WSB_` prefix (loaded from `.env`):
- `WSB_DB_PATH` - Database location (default: `~/.wsb-tracker/wsb_tracker.db`)
- `WSB_SCAN_LIMIT` - Posts per scan (default: 100)
- `WSB_SUBREDDITS` - Comma-separated subreddits
- `WSB_REDDIT_CLIENT_ID/SECRET` - Optional PRAW credentials

## Testing
```bash
pytest tests/test_database.py -v     # Database operations
pytest tests/test_sentiment.py -v    # Sentiment analysis
pytest tests/test_tracker.py -v      # Integration tests
```

Test fixtures in `conftest.py` provide: `temp_db_path`, `test_db`, `sample_post`, `sample_mention`

## Common Patterns

### Adding new CLI command
```python
# In cli.py
@app.command()
def my_command(
    option: int = typer.Option(10, help="Description"),
) -> None:
    tracker = WSBTracker()
    # ... implementation
    console.print(table)  # Use Rich for output
```

### Database queries
```python
# Always use context manager
with self._get_connection() as conn:
    cursor = conn.execute("SELECT ...", (params,))
    rows = cursor.fetchall()
# Connection auto-closes after block
```

## Known Issues
- Reddit JSON API has rate limits (~60 req/min) - respect `request_delay` setting
- Single-letter tickers require `$` prefix to avoid false positives
