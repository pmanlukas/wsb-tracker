"""Reddit client for fetching posts from subreddits.

Provides two implementations:
1. JSONClient: Uses public Reddit JSON endpoints (no auth required)
2. PRAWClient: Uses Reddit API via PRAW (requires API credentials)

The JSONClient is the default and works without any Reddit API approval.
"""

import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Iterator, Optional

import httpx

from wsb_tracker.config import get_settings
from wsb_tracker.models import RedditPost


class BaseRedditClient(ABC):
    """Abstract base class for Reddit clients."""

    @abstractmethod
    def get_posts(
        self,
        subreddit: str,
        sort: str,
        limit: int,
    ) -> Iterator[RedditPost]:
        """Fetch posts from a subreddit.

        Args:
            subreddit: Subreddit name without r/ prefix
            sort: Sort method (hot, new, rising, top)
            limit: Maximum posts to fetch

        Yields:
            RedditPost objects
        """
        pass

    @abstractmethod
    def get_post_by_id(self, post_id: str) -> Optional[RedditPost]:
        """Fetch a single post by ID.

        Args:
            post_id: Reddit post ID

        Returns:
            RedditPost or None if not found
        """
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Name of the data source for tracking."""
        pass


class JSONClient(BaseRedditClient):
    """Reddit client using public JSON endpoints.

    No authentication required. Uses reddit.com/{subreddit}.json endpoints.
    Rate limited to be respectful (minimum 2s between requests).

    Usage:
        client = JSONClient()
        for post in client.get_posts("wallstreetbets", "hot", 100):
            print(post.title)
    """

    BASE_URL = "https://www.reddit.com"

    def __init__(self) -> None:
        """Initialize HTTP client with appropriate headers."""
        settings = get_settings()
        self.client = httpx.Client(
            headers={
                "User-Agent": settings.reddit_user_agent,
                "Accept": "application/json",
            },
            timeout=30.0,
            follow_redirects=True,
        )
        # Minimum 2s delay for public endpoints to be respectful
        self._delay = max(settings.request_delay, 2.0)
        self._last_request = 0.0

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request
        if elapsed < self._delay:
            time.sleep(self._delay - elapsed)
        self._last_request = time.time()

    def get_posts(
        self,
        subreddit: str = "wallstreetbets",
        sort: str = "hot",
        limit: int = 100,
    ) -> Iterator[RedditPost]:
        """Fetch posts using public JSON API.

        Args:
            subreddit: Subreddit name without r/ prefix
            sort: Sort method (hot, new, rising, top)
            limit: Maximum posts to fetch (may be less due to API limits)

        Yields:
            RedditPost objects
        """
        url = f"{self.BASE_URL}/r/{subreddit}/{sort}.json"
        params: dict[str, str | int] = {"limit": min(limit, 100), "raw_json": 1}

        after: Optional[str] = None
        fetched = 0

        while fetched < limit:
            if after:
                params["after"] = after

            self._rate_limit()

            try:
                response = self.client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    # Rate limited - wait and retry
                    time.sleep(10)
                    continue
                raise
            except Exception as e:
                print(f"Error fetching posts: {e}")
                break

            posts = data.get("data", {}).get("children", [])
            if not posts:
                break

            for post_data in posts:
                if post_data.get("kind") != "t3":
                    continue

                post = self._convert_post(post_data["data"], subreddit)
                if post:
                    yield post
                    fetched += 1
                    if fetched >= limit:
                        break

            # Get pagination token
            after = data.get("data", {}).get("after")
            if not after:
                break

    def get_post_by_id(self, post_id: str) -> Optional[RedditPost]:
        """Fetch a single post by ID.

        Args:
            post_id: Reddit post ID (without t3_ prefix)

        Returns:
            RedditPost or None if not found
        """
        # Remove t3_ prefix if present
        post_id = post_id.replace("t3_", "")
        url = f"{self.BASE_URL}/comments/{post_id}.json"

        self._rate_limit()

        try:
            response = self.client.get(url, params={"raw_json": 1})
            response.raise_for_status()
            data = response.json()

            if data and len(data) > 0:
                children = data[0].get("data", {}).get("children", [])
                if children:
                    post_data = children[0].get("data", {})
                    subreddit = post_data.get("subreddit", "wallstreetbets")
                    return self._convert_post(post_data, subreddit)
        except Exception:
            pass

        return None

    def _convert_post(self, data: dict, subreddit: str) -> Optional[RedditPost]:
        """Convert JSON response data to RedditPost model.

        Args:
            data: Post data from Reddit JSON API
            subreddit: Subreddit name

        Returns:
            RedditPost or None if conversion fails
        """
        try:
            # Extract flair
            flair = data.get("link_flair_text")

            # Detect DD posts
            is_dd = False
            if flair:
                flair_lower = flair.lower()
                is_dd = any(term in flair_lower for term in [
                    "dd", "due diligence", "research", "analysis"
                ])

            # Handle deleted/removed posts
            author = data.get("author", "[deleted]")
            if author in ("[deleted]", "[removed]", None):
                author = "[deleted]"

            selftext = data.get("selftext", "") or ""
            # Handle removed content
            if selftext in ("[removed]", "[deleted]"):
                selftext = ""

            # Calculate awards count
            awards = data.get("all_awardings", [])
            awards_count = sum(a.get("count", 0) for a in awards) if awards else 0

            return RedditPost(
                id=data["id"],
                title=data["title"],
                selftext=selftext,
                author=author,
                subreddit=subreddit,
                score=data.get("score", 0),
                upvote_ratio=data.get("upvote_ratio", 0.5),
                num_comments=data.get("num_comments", 0),
                created_utc=datetime.utcfromtimestamp(data["created_utc"]),
                flair=flair,
                url=data.get("url", ""),
                permalink=f"https://reddit.com{data['permalink']}",
                is_dd=is_dd,
                awards_count=awards_count,
            )
        except (KeyError, ValueError, TypeError) as e:
            # Log conversion errors but don't crash
            print(f"Error converting post {data.get('id', 'unknown')}: {e}")
            return None

    @property
    def source_name(self) -> str:
        """Return data source identifier."""
        return "json_fallback"

    def close(self) -> None:
        """Close HTTP client."""
        self.client.close()

    def __enter__(self) -> "JSONClient":
        """Context manager entry."""
        return self

    def __exit__(self, *args: object) -> None:
        """Context manager exit."""
        self.close()


class PRAWClient(BaseRedditClient):
    """Reddit client using PRAW library.

    Requires Reddit API credentials configured in environment.
    Provides higher rate limits than public JSON endpoints.

    Usage:
        client = PRAWClient()  # Uses credentials from config
        for post in client.get_posts("wallstreetbets", "hot", 100):
            print(post.title)
    """

    def __init__(self) -> None:
        """Initialize PRAW client with credentials from config."""
        try:
            import praw
        except ImportError:
            raise ImportError(
                "PRAW is not installed. Install with: pip install praw\n"
                "Or install wsb-tracker with Reddit API support: pip install wsb-tracker[reddit-api]"
            )

        settings = get_settings()

        if not settings.has_reddit_credentials:
            raise ValueError(
                "Reddit API credentials not configured. "
                "Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET environment variables."
            )

        self.reddit = praw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
        )
        self._delay = settings.request_delay

    def get_posts(
        self,
        subreddit: str = "wallstreetbets",
        sort: str = "hot",
        limit: int = 100,
    ) -> Iterator[RedditPost]:
        """Fetch posts using PRAW.

        Args:
            subreddit: Subreddit name without r/ prefix
            sort: Sort method (hot, new, rising, top)
            limit: Maximum posts to fetch

        Yields:
            RedditPost objects
        """
        sub = self.reddit.subreddit(subreddit)

        # Get appropriate listing
        if sort == "hot":
            posts = sub.hot(limit=limit)
        elif sort == "new":
            posts = sub.new(limit=limit)
        elif sort == "rising":
            posts = sub.rising(limit=limit)
        elif sort == "top":
            posts = sub.top(limit=limit, time_filter="day")
        else:
            posts = sub.hot(limit=limit)

        for submission in posts:
            post = self._convert_submission(submission, subreddit)
            if post:
                yield post
            time.sleep(self._delay)

    def get_post_by_id(self, post_id: str) -> Optional[RedditPost]:
        """Fetch a single post by ID.

        Args:
            post_id: Reddit post ID (without t3_ prefix)

        Returns:
            RedditPost or None if not found
        """
        try:
            # Remove t3_ prefix if present
            post_id = post_id.replace("t3_", "")
            submission = self.reddit.submission(id=post_id)
            # Access an attribute to trigger the fetch
            _ = submission.title
            return self._convert_submission(submission, str(submission.subreddit))
        except Exception:
            return None

    def _convert_submission(self, submission, subreddit: str) -> Optional[RedditPost]:
        """Convert PRAW submission to RedditPost model.

        Args:
            submission: PRAW Submission object
            subreddit: Subreddit name

        Returns:
            RedditPost or None if conversion fails
        """
        try:
            # Get flair
            flair = getattr(submission, "link_flair_text", None)

            # Detect DD posts
            is_dd = False
            if flair:
                flair_lower = flair.lower()
                is_dd = any(term in flair_lower for term in [
                    "dd", "due diligence", "research", "analysis"
                ])

            # Handle author
            author = str(submission.author) if submission.author else "[deleted]"

            # Handle selftext
            selftext = submission.selftext or ""
            if selftext in ("[removed]", "[deleted]"):
                selftext = ""

            # Count awards
            awards_count = 0
            if hasattr(submission, "all_awardings"):
                awards_count = sum(a.get("count", 0) for a in submission.all_awardings)

            return RedditPost(
                id=submission.id,
                title=submission.title,
                selftext=selftext,
                author=author,
                subreddit=subreddit,
                score=submission.score,
                upvote_ratio=submission.upvote_ratio,
                num_comments=submission.num_comments,
                created_utc=datetime.utcfromtimestamp(submission.created_utc),
                flair=flair,
                url=submission.url,
                permalink=f"https://reddit.com{submission.permalink}",
                is_dd=is_dd,
                awards_count=awards_count,
            )
        except Exception as e:
            print(f"Error converting submission: {e}")
            return None

    @property
    def source_name(self) -> str:
        """Return data source identifier."""
        return "reddit_api"


def get_reddit_client() -> BaseRedditClient:
    """Get appropriate Reddit client based on configuration.

    Returns JSONClient by default (no auth required).
    Returns PRAWClient if credentials are configured and PRAW is installed.

    Returns:
        Reddit client instance
    """
    settings = get_settings()

    if settings.has_reddit_credentials:
        try:
            return PRAWClient()
        except ImportError:
            print("PRAW not installed, using JSON client")
        except ValueError as e:
            print(f"Could not initialize PRAW client: {e}")
        except Exception as e:
            print(f"Failed to initialize PRAW client: {e}")

    return JSONClient()
