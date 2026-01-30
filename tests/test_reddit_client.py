"""Tests for Reddit client module."""

import pytest
import httpx
import respx
from unittest.mock import patch, MagicMock

from wsb_tracker.reddit_client import JSONClient, PRAWClient, get_reddit_client
from wsb_tracker.models import RedditPost


class TestJSONClient:
    """Tests for JSONClient class."""

    @respx.mock
    def test_fetch_posts_success(self):
        """Test successful post fetching from Reddit JSON API."""
        mock_response = {
            "data": {
                "children": [
                    {
                        "kind": "t3",
                        "data": {
                            "id": "abc123",
                            "title": "GME to the moon!",
                            "selftext": "Diamond hands forever",
                            "author": "test_user",
                            "created_utc": 1704067200,
                            "score": 100,
                            "upvote_ratio": 0.95,
                            "num_comments": 50,
                            "link_flair_text": "DD",
                            "permalink": "/r/wallstreetbets/comments/abc123/",
                            "url": "https://reddit.com/r/wallstreetbets/comments/abc123/",
                            "subreddit": "wallstreetbets",
                            "all_awardings": [],
                        }
                    }
                ],
                "after": None
            }
        }
        respx.get("https://www.reddit.com/r/wallstreetbets/hot.json").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        with patch("wsb_tracker.reddit_client.get_settings") as mock_settings:
            mock_settings.return_value.reddit_user_agent = "test-agent"
            mock_settings.return_value.request_delay = 0.0
            client = JSONClient()
            client._delay = 0  # Skip rate limiting for tests
            posts = list(client.get_posts("wallstreetbets", "hot", 10))

        assert len(posts) == 1
        assert posts[0].id == "abc123"
        assert posts[0].title == "GME to the moon!"
        assert posts[0].is_dd is True

    @respx.mock
    def test_fetch_posts_empty_response(self):
        """Test handling of empty response."""
        mock_response = {"data": {"children": [], "after": None}}
        respx.get("https://www.reddit.com/r/wallstreetbets/hot.json").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        with patch("wsb_tracker.reddit_client.get_settings") as mock_settings:
            mock_settings.return_value.reddit_user_agent = "test-agent"
            mock_settings.return_value.request_delay = 0.0
            client = JSONClient()
            client._delay = 0
            posts = list(client.get_posts("wallstreetbets", "hot", 10))

        assert len(posts) == 0

    @respx.mock
    def test_fetch_posts_rate_limit_retry(self):
        """Test handling of rate limit response with retry."""
        # First response is 429, second is success
        mock_success = {
            "data": {
                "children": [
                    {
                        "kind": "t3",
                        "data": {
                            "id": "xyz789",
                            "title": "Test post",
                            "selftext": "",
                            "author": "user",
                            "created_utc": 1704067200,
                            "score": 50,
                            "upvote_ratio": 0.9,
                            "num_comments": 10,
                            "link_flair_text": None,
                            "permalink": "/r/wallstreetbets/comments/xyz789/",
                            "url": "https://reddit.com/r/wallstreetbets/comments/xyz789/",
                            "subreddit": "wallstreetbets",
                            "all_awardings": [],
                        }
                    }
                ],
                "after": None
            }
        }

        route = respx.get("https://www.reddit.com/r/wallstreetbets/hot.json")
        route.side_effect = [
            httpx.Response(429),
            httpx.Response(200, json=mock_success),
        ]

        with patch("wsb_tracker.reddit_client.get_settings") as mock_settings:
            mock_settings.return_value.reddit_user_agent = "test-agent"
            mock_settings.return_value.request_delay = 0.0
            with patch("time.sleep"):  # Skip actual sleep
                client = JSONClient()
                client._delay = 0
                posts = list(client.get_posts("wallstreetbets", "hot", 10))

        assert len(posts) == 1
        assert posts[0].id == "xyz789"

    @respx.mock
    def test_get_post_by_id_success(self):
        """Test fetching single post by ID."""
        mock_response = [
            {
                "data": {
                    "children": [
                        {
                            "kind": "t3",
                            "data": {
                                "id": "abc123",
                                "title": "Single post",
                                "selftext": "Content here",
                                "author": "poster",
                                "created_utc": 1704067200,
                                "score": 200,
                                "upvote_ratio": 0.85,
                                "num_comments": 30,
                                "link_flair_text": None,
                                "permalink": "/r/wallstreetbets/comments/abc123/",
                                "url": "https://reddit.com/r/wallstreetbets/comments/abc123/",
                                "subreddit": "wallstreetbets",
                                "all_awardings": [],
                            }
                        }
                    ]
                }
            }
        ]
        respx.get("https://www.reddit.com/comments/abc123.json").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        with patch("wsb_tracker.reddit_client.get_settings") as mock_settings:
            mock_settings.return_value.reddit_user_agent = "test-agent"
            mock_settings.return_value.request_delay = 0.0
            client = JSONClient()
            client._delay = 0
            post = client.get_post_by_id("abc123")

        assert post is not None
        assert post.id == "abc123"
        assert post.title == "Single post"

    @respx.mock
    def test_get_post_by_id_strips_prefix(self):
        """Test that t3_ prefix is properly stripped from post ID."""
        mock_response = [
            {
                "data": {
                    "children": [
                        {
                            "kind": "t3",
                            "data": {
                                "id": "abc123",
                                "title": "Test",
                                "selftext": "",
                                "author": "user",
                                "created_utc": 1704067200,
                                "score": 10,
                                "upvote_ratio": 0.9,
                                "num_comments": 5,
                                "link_flair_text": None,
                                "permalink": "/r/test/comments/abc123/",
                                "url": "",
                                "subreddit": "wallstreetbets",
                                "all_awardings": [],
                            }
                        }
                    ]
                }
            }
        ]
        respx.get("https://www.reddit.com/comments/abc123.json").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        with patch("wsb_tracker.reddit_client.get_settings") as mock_settings:
            mock_settings.return_value.reddit_user_agent = "test-agent"
            mock_settings.return_value.request_delay = 0.0
            client = JSONClient()
            client._delay = 0
            post = client.get_post_by_id("t3_abc123")

        assert post is not None
        assert post.id == "abc123"

    @respx.mock
    def test_get_post_by_id_not_found(self):
        """Test handling of not found post."""
        respx.get("https://www.reddit.com/comments/nonexistent.json").mock(
            return_value=httpx.Response(404)
        )

        with patch("wsb_tracker.reddit_client.get_settings") as mock_settings:
            mock_settings.return_value.reddit_user_agent = "test-agent"
            mock_settings.return_value.request_delay = 0.0
            client = JSONClient()
            client._delay = 0
            post = client.get_post_by_id("nonexistent")

        assert post is None

    def test_user_agent_header(self):
        """Test that proper user agent is set."""
        with patch("wsb_tracker.reddit_client.get_settings") as mock_settings:
            mock_settings.return_value.reddit_user_agent = "custom-user-agent/1.0"
            mock_settings.return_value.request_delay = 2.0
            client = JSONClient()

        assert client.client.headers["User-Agent"] == "custom-user-agent/1.0"
        assert client.client.headers["Accept"] == "application/json"

    def test_source_name(self):
        """Test source name property."""
        with patch("wsb_tracker.reddit_client.get_settings") as mock_settings:
            mock_settings.return_value.reddit_user_agent = "test-agent"
            mock_settings.return_value.request_delay = 0.0
            client = JSONClient()

        assert client.source_name == "json_fallback"

    def test_context_manager(self):
        """Test context manager functionality."""
        with patch("wsb_tracker.reddit_client.get_settings") as mock_settings:
            mock_settings.return_value.reddit_user_agent = "test-agent"
            mock_settings.return_value.request_delay = 0.0
            with JSONClient() as client:
                assert client is not None
                assert isinstance(client, JSONClient)

    def test_convert_post_handles_deleted_author(self):
        """Test that deleted authors are handled correctly."""
        with patch("wsb_tracker.reddit_client.get_settings") as mock_settings:
            mock_settings.return_value.reddit_user_agent = "test-agent"
            mock_settings.return_value.request_delay = 0.0
            client = JSONClient()

            data = {
                "id": "test123",
                "title": "Test post",
                "selftext": "Content",
                "author": "[deleted]",
                "created_utc": 1704067200,
                "score": 10,
                "upvote_ratio": 0.9,
                "num_comments": 5,
                "link_flair_text": None,
                "permalink": "/r/test/comments/test123/",
                "url": "",
                "all_awardings": [],
            }

            post = client._convert_post(data, "wallstreetbets")
            assert post.author == "[deleted]"

    def test_convert_post_handles_removed_selftext(self):
        """Test that removed selftext is cleared."""
        with patch("wsb_tracker.reddit_client.get_settings") as mock_settings:
            mock_settings.return_value.reddit_user_agent = "test-agent"
            mock_settings.return_value.request_delay = 0.0
            client = JSONClient()

            data = {
                "id": "test123",
                "title": "Test post",
                "selftext": "[removed]",
                "author": "user",
                "created_utc": 1704067200,
                "score": 10,
                "upvote_ratio": 0.9,
                "num_comments": 5,
                "link_flair_text": None,
                "permalink": "/r/test/comments/test123/",
                "url": "",
                "all_awardings": [],
            }

            post = client._convert_post(data, "wallstreetbets")
            assert post.selftext == ""

    def test_convert_post_detects_dd_flair(self):
        """Test DD post detection from flair."""
        with patch("wsb_tracker.reddit_client.get_settings") as mock_settings:
            mock_settings.return_value.reddit_user_agent = "test-agent"
            mock_settings.return_value.request_delay = 0.0
            client = JSONClient()

            # Test various DD flair variations
            dd_flairs = ["DD", "Due Diligence", "Research", "Technical Analysis"]
            for flair in dd_flairs:
                data = {
                    "id": "test123",
                    "title": "Test post",
                    "selftext": "",
                    "author": "user",
                    "created_utc": 1704067200,
                    "score": 10,
                    "upvote_ratio": 0.9,
                    "num_comments": 5,
                    "link_flair_text": flair,
                    "permalink": "/r/test/comments/test123/",
                    "url": "",
                    "all_awardings": [],
                }
                post = client._convert_post(data, "wallstreetbets")
                assert post.is_dd is True, f"Failed for flair: {flair}"

    def test_convert_post_counts_awards(self):
        """Test award counting."""
        with patch("wsb_tracker.reddit_client.get_settings") as mock_settings:
            mock_settings.return_value.reddit_user_agent = "test-agent"
            mock_settings.return_value.request_delay = 0.0
            client = JSONClient()

            data = {
                "id": "test123",
                "title": "Test post",
                "selftext": "",
                "author": "user",
                "created_utc": 1704067200,
                "score": 10,
                "upvote_ratio": 0.9,
                "num_comments": 5,
                "link_flair_text": None,
                "permalink": "/r/test/comments/test123/",
                "url": "",
                "all_awardings": [
                    {"count": 3},
                    {"count": 2},
                    {"count": 1},
                ],
            }

            post = client._convert_post(data, "wallstreetbets")
            assert post.awards_count == 6


class TestPRAWClient:
    """Tests for PRAWClient class."""

    def test_init_without_praw_raises_import_error(self):
        """Test that missing PRAW raises ImportError."""
        with patch.dict("sys.modules", {"praw": None}):
            with patch("wsb_tracker.reddit_client.get_settings") as mock_settings:
                mock_settings.return_value.has_reddit_credentials = True
                with pytest.raises(ImportError):
                    # Force reimport to trigger the error
                    import importlib
                    import wsb_tracker.reddit_client as rc
                    importlib.reload(rc)
                    rc.PRAWClient()

    def test_init_without_credentials_raises_value_error(self):
        """Test that missing credentials raises ValueError."""
        with patch("wsb_tracker.reddit_client.get_settings") as mock_settings:
            mock_settings.return_value.has_reddit_credentials = False
            with pytest.raises(ValueError, match="credentials not configured"):
                PRAWClient()

    def test_source_name(self):
        """Test source name property."""
        with patch("wsb_tracker.reddit_client.get_settings") as mock_settings:
            mock_settings.return_value.has_reddit_credentials = True
            mock_settings.return_value.reddit_client_id = "test_id"
            mock_settings.return_value.reddit_client_secret = "test_secret"
            mock_settings.return_value.reddit_user_agent = "test-agent"
            mock_settings.return_value.request_delay = 0.0
            with patch("praw.Reddit"):
                client = PRAWClient()
                assert client.source_name == "reddit_api"


class TestGetRedditClient:
    """Tests for get_reddit_client factory function."""

    def test_returns_json_client_by_default(self):
        """Test that JSONClient is returned when no credentials."""
        with patch("wsb_tracker.reddit_client.get_settings") as mock_settings:
            mock_settings.return_value.has_reddit_credentials = False
            mock_settings.return_value.reddit_user_agent = "test-agent"
            mock_settings.return_value.request_delay = 0.0
            client = get_reddit_client()

        assert isinstance(client, JSONClient)

    def test_returns_praw_client_with_credentials(self):
        """Test that PRAWClient is returned when credentials are available."""
        with patch("wsb_tracker.reddit_client.get_settings") as mock_settings:
            mock_settings.return_value.has_reddit_credentials = True
            mock_settings.return_value.reddit_client_id = "test_id"
            mock_settings.return_value.reddit_client_secret = "test_secret"
            mock_settings.return_value.reddit_user_agent = "test-agent"
            mock_settings.return_value.request_delay = 0.0
            with patch("praw.Reddit"):
                client = get_reddit_client()

        assert isinstance(client, PRAWClient)

    def test_falls_back_to_json_on_praw_import_error(self):
        """Test fallback to JSONClient when PRAW import fails."""
        with patch("wsb_tracker.reddit_client.get_settings") as mock_settings:
            mock_settings.return_value.has_reddit_credentials = True
            mock_settings.return_value.reddit_user_agent = "test-agent"
            mock_settings.return_value.request_delay = 0.0
            with patch("wsb_tracker.reddit_client.PRAWClient", side_effect=ImportError):
                client = get_reddit_client()

        assert isinstance(client, JSONClient)

    def test_falls_back_to_json_on_praw_value_error(self):
        """Test fallback to JSONClient when PRAW credentials are invalid."""
        with patch("wsb_tracker.reddit_client.get_settings") as mock_settings:
            mock_settings.return_value.has_reddit_credentials = True
            mock_settings.return_value.reddit_user_agent = "test-agent"
            mock_settings.return_value.request_delay = 0.0
            with patch("wsb_tracker.reddit_client.PRAWClient", side_effect=ValueError("Bad creds")):
                client = get_reddit_client()

        assert isinstance(client, JSONClient)
