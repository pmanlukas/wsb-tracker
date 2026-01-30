"""Tests for sentiment analysis functionality."""

import pytest

from wsb_tracker.sentiment import (
    WSBSentimentAnalyzer,
    analyze_sentiment,
    analyze_sentiment_for_ticker,
    get_analyzer,
)
from wsb_tracker.models import SentimentLabel


class TestWSBSentimentAnalyzer:
    """Test suite for WSBSentimentAnalyzer class."""

    def test_basic_positive_sentiment(self):
        """Test analysis of basic positive text."""
        analyzer = WSBSentimentAnalyzer()
        sentiment = analyzer.analyze("This is a great stock! I love it!")

        assert sentiment.compound > 0
        assert sentiment.positive > 0

    def test_basic_negative_sentiment(self):
        """Test analysis of basic negative text."""
        analyzer = WSBSentimentAnalyzer()
        sentiment = analyzer.analyze("This stock is terrible. I hate it.")

        assert sentiment.compound < 0
        assert sentiment.negative > 0

    def test_neutral_sentiment(self):
        """Test analysis of neutral text."""
        analyzer = WSBSentimentAnalyzer()
        sentiment = analyzer.analyze("The stock price is 50 dollars.")

        assert -0.15 < sentiment.compound < 0.15

    def test_wsb_bullish_terms(self):
        """Test WSB-specific bullish vocabulary."""
        analyzer = WSBSentimentAnalyzer()

        # Moon terminology
        sentiment = analyzer.analyze("GME is going to moon!")
        assert sentiment.compound > 0.3

        # Tendies
        sentiment = analyzer.analyze("About to get some tendies!")
        assert sentiment.compound > 0.3

        # Squeeze
        sentiment = analyzer.analyze("Short squeeze incoming!")
        assert sentiment.compound > 0.3

        # Diamond hands
        sentiment = analyzer.analyze("Diamond hands forever!")
        assert sentiment.compound > 0.3

    def test_wsb_bearish_terms(self):
        """Test WSB-specific bearish vocabulary."""
        analyzer = WSBSentimentAnalyzer()

        # Dump
        sentiment = analyzer.analyze("This stock is dumping hard.")
        assert sentiment.compound < -0.3

        # Rug pull
        sentiment = analyzer.analyze("Watch out for the rug pull.")
        assert sentiment.compound < -0.3

        # Bagholder
        sentiment = analyzer.analyze("I'm a bagholder now.")
        assert sentiment.compound < -0.3

        # Guh
        sentiment = analyzer.analyze("GUH... lost everything.")
        assert sentiment.compound < -0.3

    def test_emoji_preprocessing(self):
        """Test emoji to text conversion."""
        analyzer = WSBSentimentAnalyzer()

        # Rocket emojis should be bullish
        sentiment = analyzer.analyze("🚀🚀🚀")
        assert sentiment.compound > 0.3

        # Bear emoji should be bearish
        sentiment = analyzer.analyze("🐻🐻🐻")
        assert sentiment.compound < 0

        # Chart up should be bullish
        sentiment = analyzer.analyze("📈📈📈")
        assert sentiment.compound > 0

        # Chart down should be bearish
        sentiment = analyzer.analyze("📉📉📉")
        assert sentiment.compound < 0

    def test_diamond_hands_emoji(self):
        """Test diamond hands emoji combination."""
        analyzer = WSBSentimentAnalyzer()
        sentiment = analyzer.analyze("💎🙌 forever!")

        assert sentiment.compound > 0.3

    def test_mixed_sentiment(self):
        """Test text with mixed signals."""
        analyzer = WSBSentimentAnalyzer()
        sentiment = analyzer.analyze("GME might moon but could also dump. Risky play.")

        # Should be close to neutral due to mixed signals
        assert -0.5 < sentiment.compound < 0.5

    def test_intensifiers(self):
        """Test that repeated characters are handled."""
        analyzer = WSBSentimentAnalyzer()

        # Repeated letters like "MOOOOON" should be normalized
        sentiment = analyzer.analyze("MOOOOOOON!")
        assert sentiment.compound > 0

    def test_exclamation_marks(self):
        """Test that excessive exclamation marks don't break analysis."""
        analyzer = WSBSentimentAnalyzer()
        sentiment = analyzer.analyze("Great stock!!!!!!!!!!!")

        assert sentiment.compound > 0

    def test_sentiment_label_very_bullish(self):
        """Test very bullish label threshold."""
        analyzer = WSBSentimentAnalyzer()
        label = analyzer.get_label(0.6)

        assert label == SentimentLabel.VERY_BULLISH

    def test_sentiment_label_bullish(self):
        """Test bullish label threshold."""
        analyzer = WSBSentimentAnalyzer()
        label = analyzer.get_label(0.3)

        assert label == SentimentLabel.BULLISH

    def test_sentiment_label_neutral(self):
        """Test neutral label threshold."""
        analyzer = WSBSentimentAnalyzer()
        label = analyzer.get_label(0.0)

        assert label == SentimentLabel.NEUTRAL

    def test_sentiment_label_bearish(self):
        """Test bearish label threshold."""
        analyzer = WSBSentimentAnalyzer()
        label = analyzer.get_label(-0.3)

        assert label == SentimentLabel.BEARISH

    def test_sentiment_label_very_bearish(self):
        """Test very bearish label threshold."""
        analyzer = WSBSentimentAnalyzer()
        label = analyzer.get_label(-0.6)

        assert label == SentimentLabel.VERY_BEARISH

    def test_analyze_with_ticker_context(self):
        """Test context-aware analysis with ticker."""
        analyzer = WSBSentimentAnalyzer()
        text = "AAPL is boring. But GME is going to the moon! Incredible squeeze potential!"

        # Analysis for GME should be more positive
        gme_sentiment = analyzer.analyze_with_context(text, "GME")
        # Analysis for AAPL should be more negative
        aapl_sentiment = analyzer.analyze_with_context(text, "AAPL")

        assert gme_sentiment.compound > aapl_sentiment.compound

    def test_analyze_with_context_no_ticker_found(self):
        """Test context analysis when ticker not in text."""
        analyzer = WSBSentimentAnalyzer()
        text = "Great day for the market!"

        # Should fall back to overall sentiment
        sentiment = analyzer.analyze_with_context(text, "XYZ")
        overall = analyzer.analyze(text)

        assert sentiment.compound == overall.compound

    def test_custom_lexicon(self):
        """Test adding custom lexicon words."""
        custom = {"customword": 3.0}
        analyzer = WSBSentimentAnalyzer(custom_lexicon=custom)

        sentiment = analyzer.analyze("customword customword customword")
        assert sentiment.compound > 0.3

    def test_add_lexicon_word(self):
        """Test dynamically adding lexicon word."""
        analyzer = WSBSentimentAnalyzer()
        analyzer.add_lexicon_word("newword", 3.5)

        sentiment = analyzer.analyze("newword newword newword")
        assert sentiment.compound > 0.3

    def test_add_lexicon_word_bounds(self):
        """Test that lexicon scores are bounded."""
        analyzer = WSBSentimentAnalyzer()

        # Score should be clamped to max 4.0
        analyzer.add_lexicon_word("extreme_pos", 10.0)
        assert analyzer.analyzer.lexicon["extreme_pos"] == 4.0

        # Score should be clamped to min -4.0
        analyzer.add_lexicon_word("extreme_neg", -10.0)
        assert analyzer.analyzer.lexicon["extreme_neg"] == -4.0

    def test_empty_text(self):
        """Test handling of empty text."""
        analyzer = WSBSentimentAnalyzer()
        sentiment = analyzer.analyze("")

        assert sentiment.compound == 0.0

    def test_whitespace_only(self):
        """Test handling of whitespace-only text."""
        analyzer = WSBSentimentAnalyzer()
        sentiment = analyzer.analyze("   \n\t  ")

        assert sentiment.compound == 0.0

    def test_sentiment_scores_bounded(self):
        """Test that sentiment scores are properly bounded."""
        analyzer = WSBSentimentAnalyzer()

        # Even extreme text should have bounded scores
        extreme_text = "moon moon moon tendies rockets 🚀🚀🚀🚀🚀 diamond hands!!!"
        sentiment = analyzer.analyze(extreme_text)

        assert -1.0 <= sentiment.compound <= 1.0
        assert 0.0 <= sentiment.positive <= 1.0
        assert 0.0 <= sentiment.negative <= 1.0
        assert 0.0 <= sentiment.neutral <= 1.0


class TestModuleFunctions:
    """Test module-level convenience functions."""

    def test_get_analyzer_singleton(self):
        """Test that get_analyzer returns singleton."""
        analyzer1 = get_analyzer()
        analyzer2 = get_analyzer()

        assert analyzer1 is analyzer2

    def test_analyze_sentiment_function(self):
        """Test module-level analyze_sentiment function."""
        sentiment = analyze_sentiment("This is great! 🚀")

        assert sentiment.compound > 0
        assert hasattr(sentiment, "label")

    def test_analyze_sentiment_for_ticker_function(self):
        """Test module-level analyze_sentiment_for_ticker function."""
        text = "AAPL is meh. GME is mooning!"
        sentiment = analyze_sentiment_for_ticker(text, "GME")

        assert sentiment.compound > 0
