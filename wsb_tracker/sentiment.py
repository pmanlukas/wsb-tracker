"""Sentiment analysis using VADER with custom WSB/financial lexicon.

This module extends VADER's rule-based sentiment analyzer with
WSB-specific vocabulary including meme stock terminology, emojis,
and financial slang for more accurate sentiment detection.
"""

import re
from typing import Optional

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from wsb_tracker.models import Sentiment, SentimentLabel


class WSBSentimentAnalyzer:
    """VADER-based sentiment analyzer with WSB-specific lexicon.

    Extends VADER with:
    - Bullish terms: moon, tendies, squeeze, diamond hands, rockets
    - Bearish terms: dump, rug pull, bagholder, tank, crash
    - Emoji preprocessing for common trading emojis
    - Context-aware analysis weighted toward ticker mentions

    Usage:
        analyzer = WSBSentimentAnalyzer()
        sentiment = analyzer.analyze("$GME to the moon! 🚀🚀🚀")
        print(f"Compound: {sentiment.compound}, Label: {sentiment.label}")
    """

    # Custom WSB lexicon additions
    # Values range from -4.0 (most negative) to +4.0 (most positive)
    WSB_LEXICON: dict[str, float] = {
        # ===== BULLISH TERMS =====
        # Extreme bullish (3.0-4.0)
        "moon": 3.0,
        "mooning": 3.5,
        "moonshot": 3.5,
        "rockets": 3.0,
        "rocket": 2.5,
        "tendies": 2.5,
        "squeeze": 2.0,
        "squeezing": 2.5,
        "gamma squeeze": 3.0,
        "short squeeze": 3.0,
        "diamond hands": 2.5,
        "diamondhands": 2.5,
        "💎🙌": 3.0,
        "free money": 3.0,
        "cant go tits up": 2.5,
        "literally cannot go tits up": 3.0,
        "infinite money glitch": 3.0,

        # Strong bullish (2.0-2.9)
        "bullish": 3.0,
        "very bullish": 3.5,
        "extremely bullish": 4.0,
        "super bullish": 3.5,
        "undervalued": 2.0,
        "breakout": 2.0,
        "breaking out": 2.5,
        "printing": 2.0,
        "printer": 1.5,
        "brrrr": 2.0,
        "brrr": 2.0,
        "lambo": 2.5,
        "lambos": 2.5,
        "wen lambo": 2.0,
        "yacht": 2.0,
        "tendies": 2.5,
        "gainz": 2.0,
        "gains": 2.0,
        "gain porn": 2.5,
        "profit": 1.5,
        "profits": 1.5,
        "green": 1.5,
        "ripping": 2.5,
        "rips": 2.0,
        "rip": 2.0,
        "parabolic": 2.5,

        # Moderate bullish (1.0-1.9)
        "apes": 1.5,
        "ape": 1.0,
        "apes together strong": 2.0,
        "strong": 1.5,
        "buying": 1.5,
        "bought": 1.0,
        "buy": 1.0,
        "long": 1.0,
        "calls": 1.5,
        "call options": 1.5,
        "accumulating": 1.5,
        "hodl": 2.0,
        "hodling": 2.0,
        "hold": 1.0,
        "holding": 1.0,
        "loading": 1.5,
        "loaded": 1.5,
        "btfd": 1.5,
        "buy the dip": 1.5,
        "dip buying": 1.5,
        "support": 1.0,
        "bounce": 1.5,
        "recovery": 1.5,
        "rally": 2.0,
        "rallying": 2.0,
        "upside": 1.5,
        "winner": 1.5,

        # ===== BEARISH TERMS =====
        # Extreme bearish (-3.0 to -4.0)
        "bearish": -3.0,
        "very bearish": -3.5,
        "extremely bearish": -4.0,
        "super bearish": -3.5,
        "rug pull": -3.5,
        "rugpull": -3.5,
        "rugged": -3.5,
        "scam": -3.0,
        "fraud": -3.5,
        "ponzi": -3.5,
        "guh": -3.5,  # Famous WSB loss sound
        "rekt": -3.0,
        "wrecked": -2.5,
        "blown up": -3.0,
        "blew up": -3.0,
        "worthless": -3.0,
        "zero": -2.5,

        # Strong bearish (-2.0 to -2.9)
        "dump": -2.5,
        "dumping": -3.0,
        "dumped": -2.5,
        "crash": -3.0,
        "crashing": -3.5,
        "crashed": -3.0,
        "tank": -2.5,
        "tanking": -3.0,
        "tanked": -2.5,
        "drilling": -2.5,
        "drill": -2.0,
        "drilled": -2.5,
        "bleeding": -2.0,
        "red": -1.5,
        "bags": -2.0,
        "bagholder": -2.5,
        "bagholding": -2.5,
        "bag holder": -2.5,
        "bag holding": -2.5,
        "loss porn": -2.0,
        "loss": -2.0,
        "losses": -2.0,
        "paper hands": -2.0,
        "paperhands": -2.0,
        "overvalued": -1.5,
        "bubble": -2.0,
        "manipulation": -2.0,
        "manipulated": -2.0,

        # Moderate bearish (-1.0 to -1.9)
        "puts": -1.5,
        "put options": -1.5,
        "short": -1.0,
        "shorting": -1.5,
        "shorted": -1.0,
        "sell": -1.0,
        "selling": -1.5,
        "sold": -1.0,
        "downside": -1.5,
        "resistance": -0.5,
        "pullback": -1.0,
        "correction": -1.5,
        "dip": -0.5,  # Can be bullish context (buy the dip)
        "expire worthless": -2.5,
        "expired worthless": -2.5,
        "theta": -1.0,  # Theta decay hurts options buyers
        "iv crush": -2.0,
        "margin call": -3.0,
        "margin called": -3.0,
        "priced in": -0.5,

        # ===== NEUTRAL/CONTEXTUAL =====
        "dd": 1.0,  # Due diligence, slightly positive
        "due diligence": 1.0,
        "research": 0.5,
        "analysis": 0.5,
        "yolo": 0.5,  # Slightly positive (conviction)
        "fomo": 0.0,  # Neutral, fear but also interest
        "fud": -0.5,  # Fear, uncertainty, doubt
        "sec": -0.5,  # Regulatory concerns
        "earnings": 0.0,
        "er": 0.0,
        "options": 0.0,
        "shares": 0.0,
        "stock": 0.0,
        "position": 0.0,
        "entry": 0.0,
        "exit": 0.0,
    }

    # Emoji to text mapping for preprocessing
    EMOJI_MAP: dict[str, str] = {
        "🚀": " rocket moon ",
        "🌙": " moon ",
        "🌕": " moon ",
        "💎": " diamond ",
        "🙌": " hands ",
        "💎🙌": " diamond hands ",
        "🦍": " ape ",
        "🦧": " ape ",
        "📈": " bullish rising ",
        "📉": " bearish falling ",
        "💰": " money profit ",
        "💵": " money ",
        "💸": " money ",
        "🔥": " hot fire ",
        "💩": " bad terrible ",
        "🐻": " bear bearish ",
        "🐂": " bull bullish ",
        "🐃": " bull bullish ",
        "🌈🐻": " gay bear bearish ",
        "🤡": " clown stupid ",
        "🎰": " gamble gambling ",
        "🎲": " gamble gambling ",
        "⬆️": " up bullish ",
        "⬇️": " down bearish ",
        "✅": " good positive ",
        "❌": " bad negative ",
        "🟢": " green bullish ",
        "🔴": " red bearish ",
        "⚠️": " warning caution ",
        "🏦": " bank ",
        "💼": " business ",
        "📊": " chart analysis ",
        "🎯": " target ",
        "🔒": " locked secure ",
        "💀": " dead rekt ",
        "☠️": " dead rekt ",
        "😂": " funny ",
        "🤣": " funny ",
        "😭": " crying sad ",
        "🥲": " sad ",
        "😱": " scared ",
        "🤯": " mind blown ",
        "🤑": " money greedy ",
        "🥳": " celebrating ",
        "🎉": " celebrating ",
    }

    def __init__(self, custom_lexicon: Optional[dict[str, float]] = None) -> None:
        """Initialize analyzer with optional custom lexicon additions.

        Args:
            custom_lexicon: Additional word -> sentiment score mappings
        """
        self.analyzer = SentimentIntensityAnalyzer()

        # Update VADER lexicon with WSB terms
        for word, score in self.WSB_LEXICON.items():
            self.analyzer.lexicon[word] = score

        # Add any custom terms
        if custom_lexicon:
            for word, score in custom_lexicon.items():
                self.analyzer.lexicon[word] = score

    def analyze(self, text: str) -> Sentiment:
        """Analyze sentiment of text.

        Args:
            text: Input text to analyze

        Returns:
            Sentiment object with compound and component scores
        """
        # Preprocess text (emojis, normalization)
        processed = self._preprocess(text)

        # Get VADER scores
        scores = self.analyzer.polarity_scores(processed)

        return Sentiment(
            compound=scores["compound"],
            positive=scores["pos"],
            negative=scores["neg"],
            neutral=scores["neu"],
        )

    def analyze_with_context(
        self,
        text: str,
        ticker: Optional[str] = None,
    ) -> Sentiment:
        """Analyze sentiment with optional ticker context weighting.

        When a ticker is provided, sentences containing that ticker
        are weighted more heavily (60%) than the overall text (40%).

        Args:
            text: Input text to analyze
            ticker: Optional ticker symbol for context weighting

        Returns:
            Sentiment object, potentially context-weighted
        """
        # Get overall sentiment
        overall = self.analyze(text)

        # If ticker provided, weight sentences containing it
        if ticker:
            ticker_sentiment = self._analyze_ticker_context(text, ticker)
            if ticker_sentiment:
                # Blend: 40% overall, 60% ticker-specific
                blended_compound = (overall.compound * 0.4) + (ticker_sentiment.compound * 0.6)
                return Sentiment(
                    compound=max(-1.0, min(1.0, blended_compound)),
                    positive=overall.positive,
                    negative=overall.negative,
                    neutral=overall.neutral,
                )

        return overall

    def _preprocess(self, text: str) -> str:
        """Preprocess text for sentiment analysis.

        - Convert emojis to text equivalents
        - Normalize whitespace
        - Handle common abbreviations

        Args:
            text: Raw input text

        Returns:
            Preprocessed text
        """
        # Convert emojis to text
        for emoji, replacement in self.EMOJI_MAP.items():
            text = text.replace(emoji, replacement)

        # Handle common WSB writing patterns
        # "MOOOOON" -> "moon moon moon" (intensifier)
        text = re.sub(r'([a-zA-Z])\1{3,}', r'\1\1\1', text)

        # Handle "!!!!!" intensifiers (VADER handles this, but clean up excess)
        text = re.sub(r'!{4,}', '!!!', text)

        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def _analyze_ticker_context(
        self,
        text: str,
        ticker: str,
    ) -> Optional[Sentiment]:
        """Analyze sentiment of sentences containing the ticker.

        Args:
            text: Full text
            ticker: Ticker symbol to find

        Returns:
            Sentiment of ticker-containing sentences, or None if not found
        """
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)

        # Find sentences containing the ticker
        ticker_upper = ticker.upper()
        ticker_patterns = [
            ticker_upper,
            f"${ticker_upper}",
        ]

        ticker_sentences = []
        for sentence in sentences:
            sentence_upper = sentence.upper()
            if any(pattern in sentence_upper for pattern in ticker_patterns):
                ticker_sentences.append(sentence)

        if not ticker_sentences:
            return None

        # Analyze combined ticker sentences
        combined = " ".join(ticker_sentences)
        return self.analyze(combined)

    def get_label(self, compound: float) -> SentimentLabel:
        """Get sentiment label from compound score.

        Args:
            compound: VADER compound score (-1 to 1)

        Returns:
            SentimentLabel enum value
        """
        if compound >= 0.5:
            return SentimentLabel.VERY_BULLISH
        elif compound >= 0.15:
            return SentimentLabel.BULLISH
        elif compound <= -0.5:
            return SentimentLabel.VERY_BEARISH
        elif compound <= -0.15:
            return SentimentLabel.BEARISH
        return SentimentLabel.NEUTRAL

    def add_lexicon_word(self, word: str, score: float) -> None:
        """Add a word to the lexicon.

        Args:
            word: Word or phrase to add
            score: Sentiment score (-4 to 4)
        """
        self.analyzer.lexicon[word.lower()] = max(-4.0, min(4.0, score))


# Module-level singleton
_analyzer: Optional[WSBSentimentAnalyzer] = None


def get_analyzer() -> WSBSentimentAnalyzer:
    """Get or create global analyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = WSBSentimentAnalyzer()
    return _analyzer


def analyze_sentiment(text: str) -> Sentiment:
    """Analyze sentiment using global analyzer.

    Convenience function for simple usage.

    Args:
        text: Input text to analyze

    Returns:
        Sentiment object with scores
    """
    return get_analyzer().analyze(text)


def analyze_sentiment_for_ticker(text: str, ticker: str) -> Sentiment:
    """Analyze sentiment with ticker context weighting.

    Convenience function for ticker-specific analysis.

    Args:
        text: Input text to analyze
        ticker: Ticker symbol for context weighting

    Returns:
        Sentiment object, weighted toward ticker mentions
    """
    return get_analyzer().analyze_with_context(text, ticker)
