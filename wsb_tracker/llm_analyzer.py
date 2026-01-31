"""LLM-based trading idea analyzer using Anthropic's Claude.

Analyzes Reddit posts to extract structured trading ideas including
direction, conviction, price targets, catalysts, and risks.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from wsb_tracker.config import get_settings
from wsb_tracker.database import get_database
from wsb_tracker.llm_models import (
    AnalyzeResponse,
    ConvictionLevel,
    LLMAnalysisResult,
    LLMStatus,
    PostType,
    Timeframe,
    TradeDirection,
    TradingIdea,
)
from wsb_tracker.models import RedditPost, TickerMention

logger = logging.getLogger(__name__)


# System prompt for structured trading idea extraction
SYSTEM_PROMPT = """You are a financial analyst assistant that extracts structured trading ideas from Reddit posts about stocks. Your job is to analyze posts from r/wallstreetbets and similar subreddits and extract actionable trading information.

For each post, you must output a JSON object with the following structure:
{
  "has_actionable_idea": boolean,  // true if the post contains a concrete trading thesis
  "direction": "bullish" | "bearish" | "neutral" | null,
  "conviction": "high" | "medium" | "low" | null,
  "timeframe": "intraday" | "swing" | "weeks" | "months" | "long_term" | null,
  "entry_price": number | null,  // only if explicitly mentioned
  "target_price": number | null,  // only if explicitly mentioned
  "stop_loss": number | null,  // only if explicitly mentioned
  "catalysts": string[],  // list of potential catalysts mentioned
  "risks": string[],  // list of risk factors mentioned
  "key_points": string[],  // 2-4 key takeaways from the post
  "post_type": "dd" | "yolo" | "gain_loss" | "meme" | "news" | "discussion" | "question" | "other",
  "quality_score": number,  // 0.0 to 1.0 based on analysis depth and quality
  "summary": string  // 1-2 sentence summary of the trading idea
}

Guidelines:
- has_actionable_idea should be true only if there's a clear thesis with reasoning
- direction should reflect the poster's view, not market consensus
- conviction is based on how confident the poster seems (language, position size mentions)
- timeframe is inferred from options expiry, catalysts mentioned, or explicit statements
- Price targets should only be filled if explicitly mentioned as numbers
- catalysts are future events that could move the stock (earnings, FDA approval, etc.)
- risks are specific concerns mentioned by the poster
- key_points should capture the main arguments (max 4 points)
- post_type: "dd" for Due Diligence analysis, "yolo" for high-risk bets, etc.
- quality_score: 0.0-0.3 for memes/low effort, 0.3-0.6 for basic analysis, 0.6-0.8 for good DD, 0.8-1.0 for exceptional research

Output ONLY the JSON object, no additional text or markdown formatting."""


def _try_import_anthropic():
    """Try to import the Anthropic SDK."""
    try:
        import anthropic

        return anthropic
    except ImportError:
        return None


class TradingIdeaAnalyzer:
    """Analyzes Reddit posts using Claude to extract trading ideas.

    Features:
    - Structured JSON output for trading ideas
    - Caching to avoid re-analyzing posts
    - Daily call limits for cost control
    - Token usage tracking
    """

    def __init__(self) -> None:
        """Initialize the analyzer."""
        self.settings = get_settings()
        self.db = get_database()
        self._client = None
        self._anthropic = None

    @property
    def client(self):
        """Lazy-load the Anthropic client."""
        if self._client is None:
            anthropic = _try_import_anthropic()
            if anthropic is None:
                raise ImportError(
                    "anthropic package not installed. "
                    "Install with: pip install wsb-tracker[llm]"
                )
            self._anthropic = anthropic
            # Get fresh settings
            settings = get_settings()
            api_key = settings.get_anthropic_api_key()
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set in environment")
            self._client = anthropic.Anthropic(api_key=api_key)
        return self._client

    def is_available(self) -> bool:
        """Check if LLM analysis is available and enabled."""
        # Get fresh settings to ensure we have latest config
        settings = get_settings()
        if not settings.llm_enabled:
            return False
        if not settings.has_llm_credentials:
            return False
        anthropic = _try_import_anthropic()
        return anthropic is not None

    def get_status(self) -> LLMStatus:
        """Get current LLM configuration and status."""
        today_usage = self.db.get_llm_usage_today()
        today_calls = today_usage["calls"]
        daily_limit_reached = (
            self.settings.llm_max_daily_calls > 0
            and today_calls >= self.settings.llm_max_daily_calls
        )

        return LLMStatus(
            enabled=self.settings.llm_enabled,
            has_credentials=self.settings.has_llm_credentials,
            model=self.settings.llm_model,
            min_post_score=self.settings.llm_min_post_score,
            analyze_dd_only=self.settings.llm_analyze_dd_only,
            max_daily_calls=self.settings.llm_max_daily_calls,
            today_calls=today_calls,
            today_cost=today_usage["estimated_cost_usd"],
            daily_limit_reached=daily_limit_reached,
        )

    def should_analyze(self, post: RedditPost) -> bool:
        """Check if a post should be analyzed.

        Args:
            post: Reddit post to check

        Returns:
            True if post meets quality criteria for analysis
        """
        if not self.is_available():
            return False

        # Check daily limit
        status = self.get_status()
        if status.daily_limit_reached:
            logger.debug(f"Daily limit reached ({status.max_daily_calls} calls)")
            return False

        # Check if DD-only mode
        # Note: RedditPost has 'is_dd', TickerMention has 'is_dd_post'
        if self.settings.llm_analyze_dd_only:
            if not post.is_dd:
                return False

        # Check minimum score threshold
        if post.score < self.settings.llm_min_post_score:
            # Exception: analyze DD posts regardless of score if not in DD-only mode
            if not post.is_dd:
                return False

        return True

    def get_cached_idea(self, post_id: str, ticker: str) -> Optional[dict]:
        """Get cached trading idea if available and not expired.

        Args:
            post_id: Reddit post ID
            ticker: Ticker symbol

        Returns:
            Cached trading idea dict or None
        """
        idea = self.db.get_trading_idea(post_id, ticker)
        if not idea:
            return None

        # Check if cache is still valid
        analyzed_at = idea.get("analyzed_at")
        if analyzed_at:
            if isinstance(analyzed_at, str):
                analyzed_at = datetime.fromisoformat(analyzed_at)
            cache_hours = self.settings.llm_cache_hours
            age_hours = (datetime.utcnow() - analyzed_at).total_seconds() / 3600
            if age_hours <= cache_hours:
                return idea

        return None

    def analyze_post(
        self,
        post: RedditPost,
        ticker: str,
        mention_id: Optional[int] = None,
        force: bool = False,
    ) -> Optional[LLMAnalysisResult]:
        """Analyze a single post for a specific ticker.

        Args:
            post: Reddit post to analyze
            ticker: Ticker symbol being analyzed
            mention_id: Optional database mention ID to link
            force: Force re-analysis even if cached

        Returns:
            LLMAnalysisResult or None if analysis failed/skipped
        """
        # Check cache first
        if not force:
            cached = self.get_cached_idea(post.id, ticker)
            if cached:
                logger.debug(f"Using cached analysis for {ticker} in post {post.id}")
                return None  # Return None since we already have it

        # Build the prompt
        prompt = self._build_prompt(post, ticker)

        try:
            # Call Claude API
            response = self.client.messages.create(
                model=self.settings.llm_model,
                max_tokens=1024,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                system=SYSTEM_PROMPT,
            )

            # Parse response
            content = response.content[0].text
            idea_data = self._parse_response(content, ticker, post.id)

            # Create result
            result = LLMAnalysisResult(
                idea=idea_data,
                model_used=self.settings.llm_model,
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                analyzed_at=datetime.utcnow(),
            )

            # Save to database
            self._save_idea(result, mention_id)

            # Track usage
            self.db.update_llm_usage(
                provider="anthropic",
                model=self.settings.llm_model,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                estimated_cost=result.estimated_cost_usd,
            )

            logger.info(
                f"Analyzed {ticker} in post {post.id}: "
                f"{idea_data.direction or 'neutral'} "
                f"({result.total_tokens} tokens, ${result.estimated_cost_usd:.4f})"
            )

            return result

        except Exception as e:
            logger.error(f"LLM analysis failed for {ticker} in {post.id}: {e}")
            return LLMAnalysisResult(
                idea=TradingIdea(ticker=ticker, post_id=post.id),
                model_used=self.settings.llm_model,
                error=str(e),
            )

    def analyze_mention(
        self,
        mention: TickerMention,
        post: RedditPost,
        force: bool = False,
    ) -> Optional[LLMAnalysisResult]:
        """Analyze a mention (convenience wrapper).

        Args:
            mention: Ticker mention to analyze
            post: Source Reddit post
            force: Force re-analysis

        Returns:
            LLMAnalysisResult or None
        """
        mention_id = getattr(mention, "_db_id", None)
        return self.analyze_post(
            post=post,
            ticker=mention.ticker,
            mention_id=mention_id,
            force=force,
        )

    def analyze_post_all_tickers(
        self,
        post: RedditPost,
        tickers: list[str],
        force: bool = False,
    ) -> AnalyzeResponse:
        """Analyze a post for multiple tickers.

        Args:
            post: Reddit post to analyze
            tickers: List of tickers to analyze
            force: Force re-analysis

        Returns:
            AnalyzeResponse with all ideas
        """
        ideas = []
        total_tokens = 0
        cached_count = 0

        for ticker in tickers:
            # Check cache
            if not force:
                cached = self.get_cached_idea(post.id, ticker)
                if cached:
                    ideas.append(TradingIdea(
                        ticker=cached["ticker"],
                        post_id=cached["post_id"],
                        has_actionable_idea=cached["has_actionable_idea"],
                        direction=TradeDirection(cached["direction"]) if cached["direction"] else None,
                        conviction=ConvictionLevel(cached["conviction"]) if cached["conviction"] else None,
                        timeframe=Timeframe(cached["timeframe"]) if cached["timeframe"] else None,
                        entry_price=cached["entry_price"],
                        target_price=cached["target_price"],
                        stop_loss=cached["stop_loss"],
                        catalysts=cached["catalysts"],
                        risks=cached["risks"],
                        key_points=cached["key_points"],
                        post_type=PostType(cached["post_type"]) if cached["post_type"] else None,
                        quality_score=cached["quality_score"] or 0.0,
                        summary=cached["summary"],
                    ))
                    cached_count += 1
                    continue

            result = self.analyze_post(post, ticker, force=force)
            if result and not result.error:
                ideas.append(result.idea)
                total_tokens += result.total_tokens

        return AnalyzeResponse(
            success=True,
            ideas=ideas,
            tokens_used=total_tokens,
            cached=cached_count > 0,
        )

    def _build_prompt(self, post: RedditPost, ticker: str) -> str:
        """Build the prompt for Claude.

        Args:
            post: Reddit post
            ticker: Ticker symbol to focus on

        Returns:
            Formatted prompt string
        """
        prompt = f"""Analyze this Reddit post for trading ideas about {ticker}.

Title: {post.title}
Subreddit: r/{post.subreddit}
Score: {post.score} upvotes
Flair: {post.flair or 'None'}

Post Content:
{post.selftext or post.title}

Focus on extracting any trading thesis, catalysts, risks, and price targets mentioned for {ticker}.
Return ONLY the JSON object with your analysis."""

        return prompt

    def _parse_response(self, content: str, ticker: str, post_id: str) -> TradingIdea:
        """Parse Claude's response into a TradingIdea.

        Args:
            content: Raw response content
            ticker: Ticker symbol
            post_id: Post ID

        Returns:
            TradingIdea object
        """
        try:
            # Clean up response - remove markdown code blocks if present
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()

            data = json.loads(content)

            # Map string values to enums
            direction = None
            if data.get("direction"):
                try:
                    direction = TradeDirection(data["direction"].lower())
                except ValueError:
                    pass

            conviction = None
            if data.get("conviction"):
                try:
                    conviction = ConvictionLevel(data["conviction"].lower())
                except ValueError:
                    pass

            timeframe = None
            if data.get("timeframe"):
                try:
                    timeframe = Timeframe(data["timeframe"].lower())
                except ValueError:
                    pass

            post_type = None
            if data.get("post_type"):
                try:
                    post_type = PostType(data["post_type"].lower())
                except ValueError:
                    pass

            return TradingIdea(
                ticker=ticker,
                post_id=post_id,
                has_actionable_idea=data.get("has_actionable_idea", False),
                direction=direction,
                conviction=conviction,
                timeframe=timeframe,
                entry_price=data.get("entry_price"),
                target_price=data.get("target_price"),
                stop_loss=data.get("stop_loss"),
                catalysts=data.get("catalysts", []),
                risks=data.get("risks", []),
                key_points=data.get("key_points", []),
                post_type=post_type,
                quality_score=data.get("quality_score", 0.0),
                summary=data.get("summary"),
            )

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            # Return minimal idea on parse failure
            return TradingIdea(
                ticker=ticker,
                post_id=post_id,
                has_actionable_idea=False,
            )

    def _save_idea(self, result: LLMAnalysisResult, mention_id: Optional[int]) -> None:
        """Save trading idea to database.

        Args:
            result: LLM analysis result
            mention_id: Optional linked mention ID
        """
        idea = result.idea
        self.db.save_trading_idea(
            post_id=idea.post_id,
            ticker=idea.ticker,
            mention_id=mention_id,
            has_actionable_idea=idea.has_actionable_idea,
            direction=idea.direction.value if idea.direction else None,
            conviction=idea.conviction.value if idea.conviction else None,
            timeframe=idea.timeframe.value if idea.timeframe else None,
            entry_price=idea.entry_price,
            target_price=idea.target_price,
            stop_loss=idea.stop_loss,
            catalysts=idea.catalysts,
            risks=idea.risks,
            key_points=idea.key_points,
            post_type=idea.post_type.value if idea.post_type else None,
            quality_score=idea.quality_score,
            summary=idea.summary,
            model_used=result.model_used,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
        )


# Module-level singleton
_analyzer: Optional[TradingIdeaAnalyzer] = None


def get_analyzer() -> TradingIdeaAnalyzer:
    """Get or create global analyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = TradingIdeaAnalyzer()
    return _analyzer


def reset_analyzer() -> None:
    """Reset analyzer singleton (useful for testing)."""
    global _analyzer
    _analyzer = None
