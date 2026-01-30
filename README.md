# WSB Tracker

A CLI tool to track stock ticker mentions on r/wallstreetbets with sentiment analysis and heat scoring.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **Ticker Extraction**: Intelligent extraction of stock tickers from Reddit posts using multiple strategies ($TICKER, contextual patterns, standalone symbols)
- **Sentiment Analysis**: VADER-based analysis enhanced with WSB-specific vocabulary (moon, tendies, diamond hands, etc.) and emoji support
- **Heat Score**: Composite scoring algorithm combining mentions, sentiment, DD posts, engagement, and trend momentum
- **SQLite Persistence**: Local database storage for historical tracking and trend analysis
- **Rich CLI**: Beautiful terminal output with color-coded sentiment, progress bars, and formatted tables
- **No API Keys Required**: Works out of the box using public Reddit JSON endpoints

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/pmanlukas/wsb-tracker.git
cd wsb-tracker

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the package
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

### Dependencies

- Python 3.10+
- typer[all] - CLI framework
- rich - Terminal formatting
- pydantic - Data validation
- pydantic-settings - Configuration management
- vaderSentiment - Sentiment analysis
- httpx - HTTP client
- python-dotenv - Environment configuration

## Quick Start

```bash
# Run a scan of r/wallstreetbets
wsb scan

# Watch continuously (every 5 minutes)
wsb watch --interval 300

# Check specific ticker
wsb ticker GME

# View top tickers from database
wsb top

# Export results as JSON
wsb scan --json > results.json
```

## CLI Commands

### `wsb scan`

Run a single analysis cycle on r/wallstreetbets.

```bash
wsb scan                    # Scan with default settings
wsb scan --limit 50         # Limit to 50 posts
wsb scan --subreddit stocks # Scan different subreddit
wsb scan --json             # Output as JSON
wsb scan --quiet            # Minimal output (for cron)
```

### `wsb watch`

Continuous monitoring mode with configurable interval.

```bash
wsb watch                   # Default 5 minute interval
wsb watch --interval 60     # Every 60 seconds
wsb watch --limit 25        # 25 posts per scan
```

### `wsb ticker <SYMBOL>`

Get detailed analysis for a specific ticker.

```bash
wsb ticker GME              # Show GME details
wsb ticker AAPL --hours 48  # Last 48 hours only
```

### `wsb top`

Display top tickers by heat score.

```bash
wsb top                     # Show top 10
wsb top --limit 20          # Show top 20
wsb top --hours 24          # Last 24 hours only
```

### `wsb alerts`

View and manage alerts.

```bash
wsb alerts                  # Show unacknowledged alerts
wsb alerts --all            # Show all alerts
wsb alerts --ack <id>       # Acknowledge specific alert
```

### `wsb stats`

Display database statistics.

```bash
wsb stats                   # Show database stats
```

### `wsb config`

View current configuration.

```bash
wsb config --show           # Display all settings
```

### `wsb cleanup`

Remove old data from database.

```bash
wsb cleanup --days 30       # Remove data older than 30 days
```

## Configuration

Configuration is managed through environment variables with `WSB_` prefix.

### Environment Variables

Create a `.env` file or set environment variables:

```bash
# Database
WSB_DATABASE_PATH=~/.wsb_tracker/wsb_tracker.db

# Scanning
WSB_DEFAULT_SUBREDDIT=wallstreetbets
WSB_DEFAULT_LIMIT=50
WSB_SCAN_INTERVAL=300

# Alerts
WSB_ALERT_HEAT_THRESHOLD=7.0
WSB_ALERT_SENTIMENT_CHANGE=0.3
WSB_ALERT_VOLUME_SPIKE=2.0

# Optional: Reddit API credentials (not required)
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=wsb-tracker/0.1.0
```

## Heat Score Algorithm

The heat score is a composite metric (0-10 scale) combining:

| Factor | Weight | Description |
|--------|--------|-------------|
| Mentions | 25% | Number of ticker mentions (capped at 5.0) |
| Sentiment | 20% | Absolute sentiment strength |
| DD Posts | 20% | Due diligence post count (capped at 1.5) |
| Engagement | 20% | Comment-to-upvote ratio |
| Trend | 15% | Bonus for >50% mention increase |

```
heat_score = mention_factor + sentiment_factor + dd_factor + engagement_factor + trend_bonus
```

## Sentiment Analysis

The tracker uses VADER (Valence Aware Dictionary and Sentiment Reasoner) enhanced with WSB-specific vocabulary:

### Bullish Terms
- 🚀 moon, mooning, moonshot (+3.0 to +3.5)
- tendies, squeeze, diamond hands (+2.0 to +2.5)
- bullish, breakout, rally (+2.0 to +3.0)

### Bearish Terms
- dump, crash, tank (-2.5 to -3.5)
- rug pull, bagholder, guh (-2.5 to -3.5)
- bearish, bleeding, rekt (-2.0 to -3.0)

### Emoji Support
- 🚀 → rocket/moon (bullish)
- 💎🙌 → diamond hands (bullish)
- 🐻 → bear (bearish)
- 📈 → rising (bullish)
- 📉 → falling (bearish)

## Project Structure

```
wsb-tracker/
├── wsb_tracker/
│   ├── __init__.py          # Package initialization
│   ├── models.py            # Pydantic data models
│   ├── config.py            # Configuration management
│   ├── ticker_extractor.py  # Ticker extraction logic
│   ├── sentiment.py         # Sentiment analysis
│   ├── database.py          # SQLite persistence
│   ├── reddit_client.py     # Reddit API client
│   ├── tracker.py           # Main orchestrator
│   └── cli.py               # CLI interface
├── tests/
│   ├── conftest.py          # Pytest fixtures
│   ├── test_ticker_extractor.py
│   ├── test_sentiment.py
│   ├── test_database.py
│   └── test_tracker.py
├── main.py                  # Entry point
├── pyproject.toml           # Package configuration
└── README.md
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=wsb_tracker --cov-report=html

# Run specific test file
pytest tests/test_sentiment.py -v
```

### Code Quality

```bash
# Lint with ruff
ruff check wsb_tracker tests

# Type check with mypy
mypy wsb_tracker
```

## Limitations

- **Not Financial Advice**: This tool is for informational purposes only
- **Rate Limiting**: Public Reddit endpoints have rate limits (~60 requests/minute)
- **No Real-time Data**: Relies on periodic scanning, not streaming
- **Ticker Validation**: Some false positives may occur with ambiguous symbols

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
