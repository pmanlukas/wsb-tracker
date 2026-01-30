"""Tests for ticker extraction functionality."""

import pytest

from wsb_tracker.ticker_extractor import TickerExtractor, extract_tickers


class TestTickerExtractor:
    """Test suite for TickerExtractor class."""

    def test_extract_dollar_ticker(self):
        """Test extraction of $TICKER format."""
        extractor = TickerExtractor()
        text = "I'm buying $GME tomorrow!"

        matches = extractor.extract(text)

        assert len(matches) == 1
        assert matches[0].ticker == "GME"
        assert matches[0].has_dollar_sign is True
        assert matches[0].confidence == 0.95

    def test_extract_multiple_tickers(self):
        """Test extraction of multiple tickers."""
        extractor = TickerExtractor()
        text = "$GME and $AMC are going to moon! Also watching $AAPL."

        matches = extractor.extract(text)
        tickers = {m.ticker for m in matches}

        assert len(matches) == 3
        assert tickers == {"GME", "AMC", "AAPL"}

    def test_extract_standalone_ticker(self):
        """Test extraction of standalone ALL CAPS tickers."""
        extractor = TickerExtractor()
        text = "GME is going up! AAPL looking good too."

        matches = extractor.extract(text)
        tickers = {m.ticker for m in matches}

        # GME and AAPL are known tickers, should be extracted
        assert "GME" in tickers
        assert "AAPL" in tickers

    def test_filter_wsb_slang(self):
        """Test filtering of WSB slang terms."""
        extractor = TickerExtractor()
        text = "YOLO into GME! HODL! FOMO is real. DD looks good."

        matches = extractor.extract(text)
        tickers = {m.ticker for m in matches}

        # YOLO, HODL, FOMO, DD should be filtered
        assert "YOLO" not in tickers
        assert "HODL" not in tickers
        assert "FOMO" not in tickers
        assert "DD" not in tickers
        # GME should be extracted
        assert "GME" in tickers

    def test_filter_common_words(self):
        """Test filtering of common words that look like tickers."""
        extractor = TickerExtractor()
        text = "THE stock FOR today ARE great. CEO said BIG news."

        matches = extractor.extract(text)
        tickers = {m.ticker for m in matches}

        # Common words should be filtered
        assert "THE" not in tickers
        assert "FOR" not in tickers
        assert "ARE" not in tickers
        assert "CEO" not in tickers
        assert "BIG" not in tickers

    def test_filter_financial_acronyms(self):
        """Test filtering of financial acronyms."""
        extractor = TickerExtractor()
        text = "IPO announced. SEC filing shows EPS beat. PE ratio is 20."

        matches = extractor.extract(text)
        tickers = {m.ticker for m in matches}

        assert "IPO" not in tickers
        assert "SEC" not in tickers
        assert "EPS" not in tickers

    def test_single_letter_requires_dollar(self):
        """Test that single-letter tickers require $ prefix."""
        extractor = TickerExtractor()

        # With dollar sign - should extract
        text1 = "Buying $F today"
        matches1 = extractor.extract(text1)
        assert any(m.ticker == "F" for m in matches1)

        # Without dollar sign - should NOT extract single letter
        text2 = "I like F stock"
        matches2 = extractor.extract(text2)
        assert not any(m.ticker == "F" for m in matches2)

    def test_context_extraction(self):
        """Test that context is extracted around ticker mention."""
        extractor = TickerExtractor()
        text = "I think $GME is going to squeeze hard tomorrow!"

        matches = extractor.extract(text)

        assert len(matches) == 1
        assert "GME" in matches[0].context
        assert "squeeze" in matches[0].context

    def test_contextual_patterns(self):
        """Test contextual pattern extraction like 'buying X'."""
        extractor = TickerExtractor()
        text = "I'm buying NVDA calls for next week."

        matches = extractor.extract(text)
        tickers = {m.ticker for m in matches}

        assert "NVDA" in tickers

    def test_extract_unique(self):
        """Test extract_unique returns set of symbols only."""
        extractor = TickerExtractor()
        text = "$GME $GME $GME to the moon! Also $AMC"

        tickers = extractor.extract_unique(text)

        assert isinstance(tickers, set)
        assert tickers == {"GME", "AMC"}

    def test_deduplication(self):
        """Test that duplicate tickers are deduplicated."""
        extractor = TickerExtractor()
        text = "$GME is great! GME will moon! Buying more $GME!"

        matches = extractor.extract(text)

        # Should only have one GME entry
        assert len([m for m in matches if m.ticker == "GME"]) == 1

    def test_case_insensitivity(self):
        """Test that extraction handles various cases."""
        extractor = TickerExtractor()
        text = "$gme $Gme $GME"  # Dollar sign patterns get uppercased

        matches = extractor.extract(text)

        # Should be deduplicated to single GME
        assert len(matches) == 1
        assert matches[0].ticker == "GME"

    def test_add_exclusion(self):
        """Test adding custom exclusion."""
        extractor = TickerExtractor()
        extractor.add_exclusion("TEST")

        text = "TEST ticker should be excluded. $GME is fine."
        matches = extractor.extract(text)
        tickers = {m.ticker for m in matches}

        assert "TEST" not in tickers
        assert "GME" in tickers

    def test_add_known_ticker(self):
        """Test adding custom known ticker."""
        extractor = TickerExtractor()
        extractor.add_known_ticker("XYZ")

        text = "XYZ is a great stock!"
        matches = extractor.extract(text)
        tickers = {m.ticker for m in matches}

        assert "XYZ" in tickers

    def test_module_function(self):
        """Test module-level convenience function."""
        text = "$GME to the moon!"
        matches = extract_tickers(text)

        assert len(matches) == 1
        assert matches[0].ticker == "GME"

    def test_empty_text(self):
        """Test handling of empty text."""
        extractor = TickerExtractor()

        matches = extractor.extract("")
        assert len(matches) == 0

        matches = extractor.extract("   ")
        assert len(matches) == 0

    def test_no_tickers(self):
        """Test text with no valid tickers."""
        extractor = TickerExtractor()
        text = "The market is looking good today!"

        matches = extractor.extract(text)
        assert len(matches) == 0
