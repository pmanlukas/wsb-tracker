"""Typer CLI interface with Rich terminal output.

Provides commands:
- scan: Run a single analysis cycle
- watch: Continuous monitoring mode
- ticker: Get details for a specific ticker
- top: Show top tickers from database
- alerts: View and manage alerts
- stats: Show database statistics
- config: View configuration
- cleanup: Remove old data
- serve: Start API server
- refresh-tickers: Refresh local ticker database
- validate-ticker: Check if a ticker is valid
- cleanup-db: Remove invalid tickers from mentions
"""

import json
import sys
import time
from datetime import datetime
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich.text import Text

from wsb_tracker import __version__
from wsb_tracker.config import get_settings
from wsb_tracker.database import get_database
from wsb_tracker.models import SentimentLabel, TickerSummary, TrackerSnapshot
from wsb_tracker.ticker_info import get_ticker_info_service, TickerInfo
from wsb_tracker.tracker import WSBTracker
from wsb_tracker.ticker_database import get_ticker_database, TickerDatabase
from wsb_tracker.openfigi import validate_ticker_openfigi


# Create CLI app
app = typer.Typer(
    name="wsb",
    help="Track stock ticker mentions on r/wallstreetbets with sentiment analysis.",
    add_completion=False,
    no_args_is_help=True,
)

# Rich console for pretty output
console = Console()


# ==================== HELPER FUNCTIONS ====================


def get_sentiment_color(label: SentimentLabel) -> str:
    """Get Rich color for sentiment label."""
    colors = {
        SentimentLabel.VERY_BULLISH: "bold green",
        SentimentLabel.BULLISH: "green",
        SentimentLabel.NEUTRAL: "yellow",
        SentimentLabel.BEARISH: "red",
        SentimentLabel.VERY_BEARISH: "bold red",
    }
    return colors.get(label, "white")


def get_sentiment_emoji(label: SentimentLabel) -> str:
    """Get emoji for sentiment label."""
    emojis = {
        SentimentLabel.VERY_BULLISH: "🚀",
        SentimentLabel.BULLISH: "📈",
        SentimentLabel.NEUTRAL: "➖",
        SentimentLabel.BEARISH: "📉",
        SentimentLabel.VERY_BEARISH: "💀",
    }
    return emojis.get(label, "")


def format_heat_score(score: float) -> Text:
    """Format heat score with color coding."""
    if score >= 8.0:
        style = "bold red"
        icon = "🔥🔥"
    elif score >= 6.0:
        style = "red"
        icon = "🔥"
    elif score >= 4.0:
        style = "yellow"
        icon = "🌡️"
    elif score >= 2.0:
        style = "cyan"
        icon = "📊"
    else:
        style = "dim"
        icon = "❄️"

    return Text(f"{icon} {score:.1f}", style=style)


def format_trend(change_pct: Optional[float]) -> str:
    """Format trend percentage with arrow."""
    if change_pct is None:
        return "—"
    if change_pct > 50:
        return f"[green]▲ {change_pct:+.0f}%[/green]"
    elif change_pct > 0:
        return f"[green]▲ {change_pct:+.0f}%[/green]"
    elif change_pct < -50:
        return f"[red]▼ {change_pct:.0f}%[/red]"
    elif change_pct < 0:
        return f"[red]▼ {change_pct:.0f}%[/red]"
    return "→ 0%"


def create_ticker_table(
    summaries: list[TickerSummary],
    title: str = "Top Tickers",
    show_info: bool = True,
) -> Table:
    """Create a Rich table for ticker summaries.

    Args:
        summaries: List of ticker summaries to display
        title: Table title
        show_info: Whether to show name and type columns (uses ticker info service)
    """
    table = Table(
        title=title,
        show_header=True,
        header_style="bold cyan",
        border_style="blue",
        title_style="bold white",
    )

    table.add_column("#", style="dim", width=3, justify="right")
    table.add_column("Ticker", style="bold white", width=7)
    if show_info:
        table.add_column("Name", style="white", width=22, no_wrap=True)
        table.add_column("Type", style="dim cyan", width=6)
    table.add_column("Heat", width=8, justify="center")
    table.add_column("Mentions", width=8, justify="right")
    table.add_column("Sentiment", width=14)
    table.add_column("Trend", width=10, justify="center")
    table.add_column("DD", width=4, justify="right")
    table.add_column("Score", width=8, justify="right")

    # Fetch ticker info for all tickers if showing info
    ticker_info_map: dict[str, TickerInfo] = {}
    if show_info:
        service = get_ticker_info_service()
        for summary in summaries:
            ticker_info_map[summary.ticker] = service.get_info(summary.ticker)

    for i, summary in enumerate(summaries, 1):
        sentiment_color = get_sentiment_color(summary.sentiment_label)
        sentiment_emoji = get_sentiment_emoji(summary.sentiment_label)

        if show_info:
            info = ticker_info_map.get(summary.ticker)
            name = info.name if info else summary.ticker
            # Truncate long names
            if len(name) > 20:
                name = name[:19] + "…"
            sec_type = info.security_type if info else "?"
            # Abbreviate type for display
            type_abbrev = {
                "Stock": "Stock",
                "ETF": "ETF",
                "Index": "Index",
                "Crypto": "Crypto",
                "Unknown": "?",
                "Mutual Fund": "Fund",
                "Currency": "FX",
                "Futures": "Fut",
                "Options": "Opt",
            }.get(sec_type, sec_type[:5])

            table.add_row(
                str(i),
                f"${summary.ticker}",
                name,
                type_abbrev,
                format_heat_score(summary.heat_score),
                str(summary.mention_count),
                Text(
                    f"{sentiment_emoji} {summary.avg_sentiment:+.2f}",
                    style=sentiment_color,
                ),
                format_trend(summary.mention_change_pct),
                str(summary.dd_count) if summary.dd_count > 0 else "—",
                f"{summary.total_score:,}",
            )
        else:
            table.add_row(
                str(i),
                f"${summary.ticker}",
                format_heat_score(summary.heat_score),
                str(summary.mention_count),
                Text(
                    f"{sentiment_emoji} {summary.avg_sentiment:+.2f}",
                    style=sentiment_color,
                ),
                format_trend(summary.mention_change_pct),
                str(summary.dd_count) if summary.dd_count > 0 else "—",
                f"{summary.total_score:,}",
            )

    return table


def create_snapshot_panel(snapshot: TrackerSnapshot) -> Panel:
    """Create a summary panel for scan results."""
    content = Text()
    content.append("✓ Scan Complete\n", style="bold green")
    content.append(f"  Subreddits: {', '.join(snapshot.subreddits)}\n")
    content.append(f"  Posts analyzed: {snapshot.posts_analyzed}\n")
    content.append(f"  Tickers found: {snapshot.tickers_found}\n")
    content.append(f"  Duration: {snapshot.scan_duration_seconds:.1f}s\n")
    content.append(f"  Source: {snapshot.source}\n")
    content.append(f"  Time: {snapshot.timestamp.strftime('%Y-%m-%d %H:%M:%S')} UTC")

    return Panel(content, title="[bold]Scan Summary[/bold]", border_style="green")


# ==================== CLI COMMANDS ====================


@app.command()
def scan(
    limit: int = typer.Option(
        None, "--limit", "-l",
        help="Number of posts to scan (default: from config)",
    ),
    sort: str = typer.Option(
        None, "--sort", "-s",
        help="Sort method: hot, new, rising, top (default: from config)",
    ),
    subreddits: Optional[str] = typer.Option(
        None, "--subreddits", "-r",
        help="Comma-separated subreddits to scan",
    ),
    min_score: int = typer.Option(
        None, "--min-score", "-m",
        help="Minimum post score to process",
    ),
    top: int = typer.Option(
        15, "--top", "-t",
        help="Number of top tickers to display",
    ),
    output_json: bool = typer.Option(
        False, "--json", "-j",
        help="Output results as JSON",
    ),
    quiet: bool = typer.Option(
        False, "--quiet", "-q",
        help="Minimal output for cron jobs",
    ),
) -> None:
    """Scan r/wallstreetbets for ticker mentions.

    Fetches posts, extracts ticker symbols, analyzes sentiment,
    and displays a ranked table of interesting opportunities.
    """
    settings = get_settings()
    tracker = WSBTracker()

    # Parse subreddits
    subreddit_list = None
    if subreddits:
        subreddit_list = [s.strip() for s in subreddits.split(",")]

    # Use defaults from config if not specified
    limit = limit or settings.scan_limit
    sort = sort or settings.scan_sort
    min_score = min_score if min_score is not None else settings.min_score

    if output_json:
        # JSON output mode - no progress display
        snapshot = tracker.scan(
            subreddits=subreddit_list,
            limit=limit,
            sort=sort,
            min_score=min_score,
        )
        output = {
            "timestamp": snapshot.timestamp.isoformat(),
            "subreddits": snapshot.subreddits,
            "posts_analyzed": snapshot.posts_analyzed,
            "tickers_found": snapshot.tickers_found,
            "scan_duration_seconds": snapshot.scan_duration_seconds,
            "source": snapshot.source,
            "top_tickers": [
                {
                    "ticker": s.ticker,
                    "heat_score": s.heat_score,
                    "mention_count": s.mention_count,
                    "avg_sentiment": s.avg_sentiment,
                    "sentiment_label": s.sentiment_label.value,
                    "dd_count": s.dd_count,
                    "total_score": s.total_score,
                    "mention_change_pct": s.mention_change_pct,
                }
                for s in snapshot.summaries[:top]
            ],
        }
        console.print_json(json.dumps(output, default=str))
        return

    if quiet:
        # Quiet mode for cron - tab-separated output
        snapshot = tracker.scan(
            subreddits=subreddit_list,
            limit=limit,
            sort=sort,
            min_score=min_score,
        )
        for s in snapshot.summaries[:top]:
            print(f"${s.ticker}\t{s.mention_count}\t{s.avg_sentiment:.2f}\t{s.heat_score:.1f}")
        return

    # Rich progress display
    posts_count = 0
    mentions_count = 0

    def on_post(post):
        nonlocal posts_count
        posts_count += 1

    def on_mention(mention):
        nonlocal mentions_count
        mentions_count += 1

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(
            f"[cyan]Scanning r/{subreddit_list[0] if subreddit_list else 'wallstreetbets'}...",
            total=limit,
        )

        def on_post_progress(post):
            nonlocal posts_count
            posts_count += 1
            progress.update(task, advance=1, description=(
                f"[cyan]Scanning... {posts_count} posts, {mentions_count} mentions"
            ))

        def on_mention_progress(mention):
            nonlocal mentions_count
            mentions_count += 1

        snapshot = tracker.scan(
            subreddits=subreddit_list,
            limit=limit,
            sort=sort,
            min_score=min_score,
            on_post=on_post_progress,
            on_mention=on_mention_progress,
        )

    # Display results
    console.print()
    console.print(create_snapshot_panel(snapshot))
    console.print()

    if snapshot.summaries:
        table = create_ticker_table(snapshot.summaries[:top])
        console.print(table)

        # Show top movers callout
        if snapshot.top_movers:
            movers = ", ".join(f"${t}" for t in snapshot.top_movers)
            console.print()
            console.print(Panel(
                f"[bold yellow]🔥 Hot right now:[/bold yellow] {movers}",
                border_style="yellow",
            ))
    else:
        console.print("[yellow]No tickers found in this scan.[/yellow]")

    # Show alert count
    alerts = tracker.get_alerts()
    if alerts:
        console.print()
        console.print(f"[bold red]⚠️  {len(alerts)} unacknowledged alert(s)[/bold red] - run 'wsb alerts' to view")


@app.command()
def watch(
    interval: int = typer.Option(
        60, "--interval", "-i",
        help="Minutes between scans",
    ),
    limit: int = typer.Option(
        50, "--limit", "-l",
        help="Posts to scan per cycle",
    ),
    sort: str = typer.Option(
        "new", "--sort", "-s",
        help="Sort method (new recommended for watch mode)",
    ),
    top: int = typer.Option(
        10, "--top", "-t",
        help="Number of tickers to display",
    ),
) -> None:
    """Continuously monitor for ticker mentions.

    Runs in a loop, scanning at the specified interval.
    Press Ctrl+C to stop.
    """
    tracker = WSBTracker()
    interval_seconds = interval * 60

    console.print(Panel(
        f"[bold]Watch Mode[/bold]\n"
        f"Interval: {interval} minutes | Posts: {limit} | Sort: {sort}\n"
        f"Press [bold red]Ctrl+C[/bold red] to stop",
        border_style="cyan",
    ))

    try:
        while True:
            # Run scan
            snapshot = tracker.scan(limit=limit, sort=sort)

            # Clear and redraw
            console.clear()
            console.print(f"[bold cyan]═══ WSB Tracker - Watch Mode ═══[/bold cyan]")
            console.print(
                f"Last scan: {snapshot.timestamp.strftime('%H:%M:%S')} | "
                f"Next in: {interval}m | "
                f"Posts: {snapshot.posts_analyzed} | "
                f"Tickers: {snapshot.tickers_found}"
            )
            console.print()

            if snapshot.summaries:
                table = create_ticker_table(snapshot.summaries[:top], "Current Top Tickers")
                console.print(table)
            else:
                console.print("[yellow]No tickers found[/yellow]")

            # Check for alerts
            alerts = tracker.get_alerts()
            if alerts:
                console.print()
                console.print(Panel(
                    f"[bold red]⚠️  {len(alerts)} Alert(s)[/bold red]",
                    border_style="red",
                ))
                for alert in alerts[:3]:
                    console.print(f"  • ${alert.ticker}: {alert.message}")

            console.print()
            console.print(f"[dim]Next scan at {datetime.utcnow().strftime('%H:%M:%S')} + {interval}m...[/dim]")

            # Wait for next cycle
            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        console.print("\n[yellow]Watch mode stopped.[/yellow]")


@app.command()
def ticker(
    symbol: str = typer.Argument(..., help="Ticker symbol to look up (e.g., GME)"),
    hours: int = typer.Option(
        24, "--hours", "-h",
        help="Time window in hours",
    ),
    output_json: bool = typer.Option(
        False, "--json", "-j",
        help="Output as JSON",
    ),
) -> None:
    """Get detailed analysis for a specific ticker."""
    tracker = WSBTracker()
    summary = tracker.get_ticker_details(symbol.upper(), hours)

    if not summary:
        console.print(f"[yellow]No data found for ${symbol.upper()} in the last {hours} hours.[/yellow]")
        console.print("Run 'wsb scan' to collect data first.")
        raise typer.Exit(1)

    if output_json:
        output = {
            "ticker": summary.ticker,
            "heat_score": summary.heat_score,
            "mention_count": summary.mention_count,
            "unique_posts": summary.unique_posts,
            "avg_sentiment": summary.avg_sentiment,
            "sentiment_label": summary.sentiment_label.value,
            "bullish_ratio": summary.bullish_ratio,
            "dd_count": summary.dd_count,
            "total_score": summary.total_score,
            "first_seen": summary.first_seen.isoformat(),
            "last_seen": summary.last_seen.isoformat(),
            "mention_change_pct": summary.mention_change_pct,
            "sentiment_change": summary.sentiment_change,
        }
        console.print_json(json.dumps(output, default=str))
        return

    # Rich panel display
    sentiment_color = get_sentiment_color(summary.sentiment_label)
    sentiment_emoji = get_sentiment_emoji(summary.sentiment_label)

    content = Text()
    content.append("\n")
    content.append("Heat Score: ", style="bold")
    content.append_text(format_heat_score(summary.heat_score))
    content.append("\n\n")

    content.append("Mentions: ", style="bold")
    content.append(f"{summary.mention_count}")
    content.append(f" ({summary.unique_posts} unique posts)\n")

    content.append("Sentiment: ", style="bold")
    content.append(f"{sentiment_emoji} {summary.avg_sentiment:+.3f} ", style=sentiment_color)
    content.append(f"({summary.sentiment_label.value})\n")

    content.append("Bullish Ratio: ", style="bold")
    bullish_pct = summary.bullish_ratio * 100
    content.append(f"{bullish_pct:.0f}% bullish mentions\n")

    content.append("DD Posts: ", style="bold")
    content.append(f"{summary.dd_count}\n")

    content.append("Total Score: ", style="bold")
    content.append(f"{summary.total_score:,}\n\n")

    if summary.mention_change_pct is not None:
        content.append("Trend: ", style="bold")
        content.append(format_trend(summary.mention_change_pct))
        content.append(" vs previous period\n")

    if summary.sentiment_change is not None:
        content.append("Sentiment Δ: ", style="bold")
        if summary.sentiment_change > 0:
            content.append(f"+{summary.sentiment_change:.3f}", style="green")
        elif summary.sentiment_change < 0:
            content.append(f"{summary.sentiment_change:.3f}", style="red")
        else:
            content.append("0.000")
        content.append("\n")

    content.append("\n")
    content.append(f"First seen: {summary.first_seen.strftime('%Y-%m-%d %H:%M')} UTC\n", style="dim")
    content.append(f"Last seen:  {summary.last_seen.strftime('%Y-%m-%d %H:%M')} UTC\n", style="dim")

    console.print(Panel(
        content,
        title=f"[bold]${summary.ticker}[/bold]",
        border_style="cyan",
    ))


@app.command()
def top(
    hours: int = typer.Option(
        24, "--hours", "-h",
        help="Time window in hours",
    ),
    limit: int = typer.Option(
        15, "--limit", "-l",
        help="Number of tickers to show",
    ),
    output_json: bool = typer.Option(
        False, "--json", "-j",
        help="Output as JSON",
    ),
    no_info: bool = typer.Option(
        False, "--no-info",
        help="Skip ticker name/type lookup for faster output",
    ),
) -> None:
    """Show top trending tickers from database."""
    tracker = WSBTracker()
    summaries = tracker.get_top_tickers(hours=hours, limit=limit)

    if not summaries:
        console.print(f"[yellow]No data found in the last {hours} hours.[/yellow]")
        console.print("Run 'wsb scan' to collect data first.")
        raise typer.Exit(1)

    if output_json:
        # Include ticker info in JSON output if not disabled
        ticker_info_data = {}
        if not no_info:
            service = get_ticker_info_service()
            for s in summaries:
                info = service.get_info(s.ticker)
                ticker_info_data[s.ticker] = {
                    "name": info.name,
                    "type": info.security_type,
                }

        output = [
            {
                "ticker": s.ticker,
                "name": ticker_info_data.get(s.ticker, {}).get("name", s.ticker),
                "type": ticker_info_data.get(s.ticker, {}).get("type", "Unknown"),
                "heat_score": s.heat_score,
                "mention_count": s.mention_count,
                "avg_sentiment": s.avg_sentiment,
                "sentiment_label": s.sentiment_label.value,
            }
            for s in summaries
        ]
        console.print_json(json.dumps(output, default=str))
        return

    console.print(f"\n[bold]Top {len(summaries)} Tickers[/bold] (last {hours}h)\n")
    table = create_ticker_table(summaries, show_info=not no_info)
    console.print(table)


@app.command()
def alerts(
    ack: Optional[str] = typer.Option(
        None, "--ack", "-a",
        help="Acknowledge alert by ID (use first 8 chars)",
    ),
    ack_all: bool = typer.Option(
        False, "--ack-all",
        help="Acknowledge all pending alerts",
    ),
) -> None:
    """View and manage alerts."""
    tracker = WSBTracker()

    if ack_all:
        count = tracker.acknowledge_all_alerts()
        console.print(f"[green]✓ Acknowledged {count} alert(s)[/green]")
        return

    if ack:
        # Find alert by partial ID
        alerts = tracker.get_alerts()
        for alert in alerts:
            if alert.id.startswith(ack):
                tracker.acknowledge_alert(alert.id)
                console.print(f"[green]✓ Acknowledged alert for ${alert.ticker}[/green]")
                return
        console.print(f"[red]Alert not found: {ack}[/red]")
        raise typer.Exit(1)

    # Display alerts
    alerts = tracker.get_alerts()

    if not alerts:
        console.print("[green]✓ No pending alerts[/green]")
        return

    table = Table(title="Pending Alerts", show_header=True, header_style="bold red")
    table.add_column("ID", style="dim", width=8)
    table.add_column("Ticker", style="bold")
    table.add_column("Type")
    table.add_column("Heat", justify="right")
    table.add_column("Message", max_width=40)
    table.add_column("Time", style="dim")

    for alert in alerts:
        table.add_row(
            alert.id[:8],
            f"${alert.ticker}",
            alert.alert_type.replace("_", " "),
            f"{alert.heat_score:.1f}",
            alert.message[:40] + "..." if len(alert.message) > 40 else alert.message,
            alert.triggered_at.strftime("%H:%M"),
        )

    console.print(table)
    console.print("\n[dim]Use 'wsb alerts --ack <id>' to acknowledge[/dim]")


@app.command()
def stats() -> None:
    """Show database statistics."""
    tracker = WSBTracker()
    stats = tracker.get_stats()

    table = Table(title="Database Statistics", show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Total Mentions", f"{stats.get('total_mentions', 0):,}")
    table.add_row("Unique Tickers", f"{stats.get('unique_tickers', 0):,}")
    table.add_row("Total Snapshots", f"{stats.get('total_snapshots', 0):,}")
    table.add_row("Pending Alerts", f"{stats.get('pending_alerts', 0):,}")
    table.add_row("Database Size", f"{stats.get('db_size_mb', 0):.2f} MB")

    if stats.get("oldest_mention"):
        oldest = stats["oldest_mention"]
        if isinstance(oldest, str):
            table.add_row("Oldest Data", oldest[:16])  # Already formatted string
        else:
            table.add_row("Oldest Data", oldest.strftime("%Y-%m-%d %H:%M"))
    if stats.get("newest_mention"):
        newest = stats["newest_mention"]
        if isinstance(newest, str):
            table.add_row("Newest Data", newest[:16])  # Already formatted string
        else:
            table.add_row("Newest Data", newest.strftime("%Y-%m-%d %H:%M"))

    console.print(table)


@app.command()
def config(
    show: bool = typer.Option(
        True, "--show", "-s",
        help="Show current configuration",
    ),
) -> None:
    """View current configuration."""
    settings = get_settings()

    table = Table(title="Configuration", show_header=True, header_style="bold cyan")
    table.add_column("Setting", style="bold")
    table.add_column("Value")
    table.add_column("Source", style="dim")

    table.add_row("Database Path", str(settings.db_path), "WSB_DB_PATH")
    table.add_row("Scan Limit", str(settings.scan_limit), "WSB_SCAN_LIMIT")
    table.add_row("Min Score", str(settings.min_score), "WSB_MIN_SCORE")
    table.add_row("Sort Method", settings.scan_sort, "WSB_SCAN_SORT")
    table.add_row("Subreddits", settings.subreddits, "WSB_SUBREDDITS")
    table.add_row("Request Delay", f"{settings.request_delay}s", "WSB_REQUEST_DELAY")
    table.add_row("Alert Threshold", str(settings.alert_threshold), "WSB_ALERT_THRESHOLD")
    table.add_row("Alerts Enabled", "Yes" if settings.enable_alerts else "No", "WSB_ENABLE_ALERTS")
    table.add_row(
        "Reddit API",
        "[green]Configured[/green]" if settings.has_reddit_credentials else "[yellow]Not configured[/yellow]",
        "REDDIT_CLIENT_*",
    )

    console.print(table)
    console.print("\n[dim]Configure via environment variables or .env file[/dim]")


@app.command()
def cleanup(
    days: int = typer.Option(
        30, "--days", "-d",
        help="Keep data from the last N days",
    ),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Skip confirmation prompt",
    ),
) -> None:
    """Remove old data from database."""
    if not force:
        confirm = typer.confirm(f"Delete all data older than {days} days?")
        if not confirm:
            raise typer.Abort()

    tracker = WSBTracker()
    stats_before = tracker.get_stats()
    deleted = tracker.cleanup(days)
    stats_after = tracker.get_stats()

    console.print(Panel(
        f"[green]✓ Cleanup complete[/green]\n\n"
        f"Deleted:\n"
        f"  • Mentions: {deleted.get('mentions', 0):,}\n"
        f"  • Snapshots: {deleted.get('snapshots', 0):,}\n"
        f"  • Alerts: {deleted.get('alerts', 0):,}\n\n"
        f"Database size: {stats_before.get('db_size_mb', 0):.2f} MB → "
        f"{stats_after.get('db_size_mb', 0):.2f} MB",
        title="Cleanup Results",
        border_style="green",
    ))


def _is_port_in_use(host: str, port: int) -> bool:
    """Check if a port is already in use."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def _check_existing_wsb_server(host: str, port: int) -> bool:
    """Check if WSB Tracker API is already running on this port."""
    try:
        import httpx
        response = httpx.get(f"http://{host}:{port}/api/health", timeout=2.0)
        if response.status_code == 200:
            data = response.json()
            return data.get("status") == "healthy"
    except Exception:
        pass
    return False


@app.command()
def serve(
    host: str = typer.Option(
        "127.0.0.1", "--host", "-h",
        help="Host to bind to",
    ),
    port: int = typer.Option(
        8000, "--port", "-p",
        help="Port to bind to",
    ),
    reload: bool = typer.Option(
        False, "--reload", "-r",
        help="Enable auto-reload for development",
    ),
) -> None:
    """Start the API server.

    Runs a FastAPI server that provides REST API and WebSocket endpoints
    for the WSB Tracker. Use this to power a web dashboard.

    Examples:

        wsb serve                    # Start on localhost:8000

        wsb serve --port 3000        # Use different port

        wsb serve --host 0.0.0.0     # Allow external connections

        wsb serve --reload           # Auto-reload for development
    """
    try:
        import uvicorn
    except ImportError:
        console.print(
            "[red]Error:[/red] uvicorn is not installed.\n"
            "Install API dependencies with: pip install wsb-tracker[api]"
        )
        raise typer.Exit(1)

    # Check if port is already in use
    if _is_port_in_use(host, port):
        if _check_existing_wsb_server(host, port):
            console.print(
                Panel(
                    f"[yellow]WSB Tracker API is already running on port {port}![/yellow]\n\n"
                    f"The server is healthy at: http://{host}:{port}\n"
                    f"API docs at: http://{host}:{port}/docs\n\n"
                    f"If you want to restart, stop the existing server first (Ctrl+C).",
                    title="ℹ️  Server Already Running",
                    border_style="yellow",
                )
            )
        else:
            console.print(
                Panel(
                    f"[red]Port {port} is already in use![/red]\n\n"
                    f"Another application is using this port.\n\n"
                    f"Options:\n"
                    f"  • Use a different port: [cyan]wsb serve --port {port + 1}[/cyan]\n"
                    f"  • Check what's using the port: [cyan]lsof -i :{port}[/cyan]",
                    title="⚠️  Port Conflict",
                    border_style="red",
                )
            )
        raise typer.Exit(1)

    console.print(
        Panel(
            f"[green]Starting WSB Tracker API[/green]\n\n"
            f"  URL: http://{host}:{port}\n"
            f"  API Docs: http://{host}:{port}/docs\n"
            f"  WebSocket: ws://{host}:{port}/ws\n\n"
            f"Press Ctrl+C to stop",
            title="API Server",
            border_style="green",
        )
    )

    uvicorn.run(
        "wsb_tracker.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


@app.command(name="refresh-tickers")
def refresh_tickers(
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Force refresh even if database is recent",
    ),
) -> None:
    """Refresh the local ticker database from authoritative sources.

    Downloads valid tickers from:
    - GitHub US-Stock-Symbols repository (~10,000 US stocks)
    - Adds ETFs, indices, commodities, forex, and crypto symbols

    The database is stored locally and used for fast ticker validation.
    """
    db = get_ticker_database()

    if not force and not db.needs_refresh():
        console.print("[yellow]Database is up to date (refreshed within 24h).[/yellow]")
        console.print("Use --force to refresh anyway.")
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("[cyan]Refreshing ticker database...", total=None)
        count = db.refresh()

    console.print(f"[green]✓[/green] Loaded {count:,} valid tickers into database")
    console.print(f"  Database path: {db.db_path}")


@app.command(name="validate-ticker")
def validate_ticker(
    symbol: str = typer.Argument(..., help="Ticker symbol to validate (e.g., GME)"),
    use_api: bool = typer.Option(
        True, "--api/--no-api",
        help="Use OpenFIGI API for unknown tickers",
    ),
) -> None:
    """Check if a ticker symbol is valid.

    Validates against:
    1. Local database (~10,000 US stocks, ETFs, commodities, forex, crypto)
    2. OpenFIGI API (if --api is enabled and not in local database)
    """
    symbol = symbol.upper()
    db = get_ticker_database()

    # Check local database first
    info = db.get_ticker_info(symbol)

    if info:
        console.print(f"[green]✓[/green] {symbol} is a valid ticker")
        console.print(f"  Name: {info.name or '(not available)'}")
        console.print(f"  Exchange: {info.exchange}")
        console.print(f"  Type: {info.asset_type}")
        return

    # Try OpenFIGI if enabled
    if use_api:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task(f"[cyan]Looking up {symbol} via OpenFIGI...", total=None)
            figi = validate_ticker_openfigi(symbol)

        if figi:
            console.print(f"[yellow]~[/yellow] {symbol} found via OpenFIGI (not in local database)")
            console.print(f"  Name: {figi.name}")
            console.print(f"  Exchange: {figi.exchange}")
            console.print(f"  Type: {figi.security_type}")
            console.print(f"  FIGI: {figi.figi}")
            return

    console.print(f"[red]✗[/red] {symbol} is not a valid ticker")
    raise typer.Exit(1)


@app.command(name="cleanup-db")
def cleanup_db(
    dry_run: bool = typer.Option(
        True, "--dry-run/--apply",
        help="Show what would be deleted without actually deleting",
    ),
) -> None:
    """Remove invalid tickers from the mentions database.

    This command identifies mentions in the database that reference
    tickers not found in the authoritative ticker database, and
    optionally removes them.

    Use --dry-run (default) to preview changes, --apply to execute.
    """
    db = get_ticker_database()
    tracker_db = get_database()

    # Ensure ticker database is populated
    if db.needs_refresh():
        console.print("[yellow]Ticker database needs refresh, updating first...[/yellow]")
        db.refresh()

    # Get all unique tickers from mentions
    with tracker_db._get_connection() as conn:
        cursor = conn.execute("SELECT DISTINCT ticker FROM mentions")
        all_tickers = [row[0] for row in cursor.fetchall()]

    console.print(f"Found {len(all_tickers)} unique tickers in mentions database")

    # Check each ticker
    invalid_tickers = []
    for ticker in all_tickers:
        if not db.is_valid_ticker(ticker):
            invalid_tickers.append(ticker)

    if not invalid_tickers:
        console.print("[green]✓[/green] All tickers in database are valid")
        return

    console.print(f"\n[yellow]Found {len(invalid_tickers)} invalid tickers:[/yellow]")

    # Show table of invalid tickers
    table = Table(show_header=True, header_style="bold")
    table.add_column("Ticker", style="bold red")
    table.add_column("Status")

    for ticker in sorted(invalid_tickers)[:50]:  # Show first 50
        table.add_row(ticker, "Invalid - not in authoritative database")

    if len(invalid_tickers) > 50:
        table.add_row("...", f"({len(invalid_tickers) - 50} more)")

    console.print(table)

    if dry_run:
        console.print("\n[dim]This is a dry run. Use --apply to remove these tickers.[/dim]")
        return

    # Actually delete
    confirm = typer.confirm(f"Delete {len(invalid_tickers)} invalid ticker mentions?")
    if not confirm:
        raise typer.Abort()

    deleted_count = 0
    with tracker_db._get_connection() as conn:
        for ticker in invalid_tickers:
            cursor = conn.execute(
                "DELETE FROM mentions WHERE ticker = ?",
                (ticker,)
            )
            deleted_count += cursor.rowcount

    console.print(f"[green]✓[/green] Deleted {deleted_count:,} mentions for {len(invalid_tickers)} invalid tickers")


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"wsb-tracker version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """WSB Tracker - Monitor r/wallstreetbets for stock ticker mentions.

    Track sentiment, find trending tickers, and identify interesting
    trading opportunities based on social media activity.

    Get started:

        wsb scan              # Run a scan

        wsb top               # View top tickers

        wsb ticker GME        # Get details for a ticker

        wsb watch             # Continuous monitoring
    """
    pass


if __name__ == "__main__":
    app()
