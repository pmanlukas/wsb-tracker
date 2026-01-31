"""Pydantic models for LLM-based trading idea analysis.

Defines structured output formats for Claude's analysis of Reddit posts,
including trading ideas, sentiment, and metadata.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TradeDirection(str, Enum):
    """Direction of the trading idea."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class ConvictionLevel(str, Enum):
    """Conviction level of the trading idea."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Timeframe(str, Enum):
    """Expected timeframe for the trade."""

    INTRADAY = "intraday"
    SWING = "swing"  # Days to 2 weeks
    WEEKS = "weeks"  # 2-8 weeks
    MONTHS = "months"  # 2-6 months
    LONG_TERM = "long_term"  # 6+ months


class PostType(str, Enum):
    """Type of Reddit post."""

    DD = "dd"  # Due Diligence
    YOLO = "yolo"  # High-risk bet
    GAIN_LOSS = "gain_loss"  # Gain/loss porn
    MEME = "meme"  # Meme post
    NEWS = "news"  # News-based post
    DISCUSSION = "discussion"  # General discussion
    QUESTION = "question"  # Question post
    OTHER = "other"


class TradingIdea(BaseModel):
    """Structured trading idea extracted from a Reddit post.

    This model represents the LLM's analysis of a single post-ticker combination.
    """

    # Core identification
    ticker: str = Field(description="Stock ticker symbol")
    post_id: str = Field(description="Reddit post ID")

    # Whether post contains actionable trading idea
    has_actionable_idea: bool = Field(
        default=False,
        description="Whether the post contains an actionable trading idea",
    )

    # Trading direction and conviction
    direction: Optional[TradeDirection] = Field(
        default=None,
        description="Trading direction: bullish, bearish, or neutral",
    )
    conviction: Optional[ConvictionLevel] = Field(
        default=None,
        description="How confident the poster seems in their thesis",
    )
    timeframe: Optional[Timeframe] = Field(
        default=None,
        description="Expected timeframe for the trade",
    )

    # Price targets (optional, only if mentioned)
    entry_price: Optional[float] = Field(
        default=None,
        description="Suggested entry price if mentioned",
    )
    target_price: Optional[float] = Field(
        default=None,
        description="Price target if mentioned",
    )
    stop_loss: Optional[float] = Field(
        default=None,
        description="Stop loss level if mentioned",
    )

    # Analysis details
    catalysts: list[str] = Field(
        default_factory=list,
        description="List of potential catalysts mentioned",
    )
    risks: list[str] = Field(
        default_factory=list,
        description="List of risk factors mentioned",
    )
    key_points: list[str] = Field(
        default_factory=list,
        description="Key takeaways from the post",
    )

    # Post classification
    post_type: Optional[PostType] = Field(
        default=None,
        description="Type of post (DD, YOLO, meme, etc.)",
    )
    quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Quality score from 0.0 to 1.0 based on analysis depth",
    )

    # Summary
    summary: Optional[str] = Field(
        default=None,
        description="1-2 sentence summary of the trading idea",
    )


class LLMAnalysisResult(BaseModel):
    """Complete result from LLM analysis including metadata."""

    # The extracted trading idea
    idea: TradingIdea

    # Metadata
    model_used: str = Field(description="Name of the LLM model used")
    prompt_tokens: int = Field(default=0, description="Tokens used in the prompt")
    completion_tokens: int = Field(default=0, description="Tokens in the completion")
    analyzed_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the analysis was performed",
    )

    # Error tracking
    error: Optional[str] = Field(
        default=None,
        description="Error message if analysis failed",
    )

    @property
    def total_tokens(self) -> int:
        """Total tokens used for this analysis."""
        return self.prompt_tokens + self.completion_tokens

    @property
    def estimated_cost_usd(self) -> float:
        """Estimate cost based on Claude Sonnet pricing.

        Pricing (as of 2024):
        - Input: $3.00 per million tokens
        - Output: $15.00 per million tokens
        """
        input_cost = (self.prompt_tokens / 1_000_000) * 3.00
        output_cost = (self.completion_tokens / 1_000_000) * 15.00
        return round(input_cost + output_cost, 6)


class LLMUsageStats(BaseModel):
    """Daily LLM usage statistics for cost monitoring."""

    date: str = Field(description="Date in YYYY-MM-DD format")
    provider: str = Field(default="anthropic", description="LLM provider")
    model: str = Field(description="Model name")
    calls_count: int = Field(default=0, description="Number of API calls")
    prompt_tokens_total: int = Field(default=0, description="Total prompt tokens")
    completion_tokens_total: int = Field(default=0, description="Total completion tokens")
    estimated_cost_usd: float = Field(default=0.0, description="Estimated cost in USD")

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.prompt_tokens_total + self.completion_tokens_total

    @property
    def avg_tokens_per_call(self) -> float:
        """Average tokens per API call."""
        if self.calls_count == 0:
            return 0.0
        return self.total_tokens / self.calls_count


class LLMStatus(BaseModel):
    """Current LLM configuration and status."""

    enabled: bool = Field(description="Whether LLM analysis is enabled")
    has_credentials: bool = Field(description="Whether API key is configured")
    model: str = Field(description="Current model being used")
    min_post_score: int = Field(description="Minimum post score for analysis")
    analyze_dd_only: bool = Field(description="Whether to only analyze DD posts")
    max_daily_calls: int = Field(description="Maximum daily API calls")
    today_calls: int = Field(default=0, description="Calls made today")
    today_cost: float = Field(default=0.0, description="Estimated cost today")
    daily_limit_reached: bool = Field(
        default=False,
        description="Whether daily limit has been reached",
    )


class AnalyzeRequest(BaseModel):
    """Request to manually analyze a post."""

    post_id: str = Field(description="Reddit post ID to analyze")
    ticker: Optional[str] = Field(
        default=None,
        description="Specific ticker to analyze (optional)",
    )
    force: bool = Field(
        default=False,
        description="Force re-analysis even if cached",
    )


class AnalyzeResponse(BaseModel):
    """Response from manual analysis request."""

    success: bool
    ideas: list[TradingIdea] = Field(default_factory=list)
    error: Optional[str] = None
    tokens_used: int = 0
    cached: bool = False
