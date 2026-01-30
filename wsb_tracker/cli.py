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
from wsb_tracker.tracker import WSBTracker


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


def create_ticker_table(summaries: list[TickerSummary], title: str = "Top Tickers") -> Table:
    """Create a Rich table for ticker summaries."""
    table = Table(
        title=title,
        show_header=True,
        header_style="bold cyan",
        border_style="blue",
        title_style="bold white",
    )

    table.add_column("#", style="dim", width=3, justify="right")
    table.add_column("Ticker", style="bold white", width=7)
    table.add_column("Heat", width=8, justify="center")
    table.add_column("Mentions", width=8, justify="right")
    table.add_column("Sentiment", width=14)
    table.add_column("Trend", width=10, justify="center")
    table.add_column("DD", width=4, justify="right")
    table.add_column("Score", width=8, justify="right")

    for i, summary in enumerate(summaries, 1):
        sentiment_color = get_sentiment_color(summary.sentiment_label)
        sentiment_emoji = get_sentiment_emoji(summary.sentiment_label)

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
) -> None:
    """Show top trending tickers from database."""
    tracker = WSBTracker()
    summaries = tracker.get_top_tickers(hours=hours, limit=limit)

    if not summaries:
        console.print(f"[yellow]No data found in the last {hours} hours.[/yellow]")
        console.print("Run 'wsb scan' to collect data first.")
        raise typer.Exit(1)

    if output_json:
        output = [
            {
                "ticker": s.ticker,
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
    table = create_ticker_table(summaries)
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
