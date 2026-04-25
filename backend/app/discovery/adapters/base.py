"""
Base classes for search engine adapters.
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime


logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Represents a single search result."""
    url: str
    title: str
    snippet: str
    engine: str
    position: int
    query: str
    discovered_at: datetime = None

    def __post_init__(self):
        if self.discovered_at is None:
            self.discovered_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet,
            "engine": self.engine,
            "position": self.position,
            "query": self.query,
            "discovered_at": self.discovered_at.isoformat()
        }


class RateLimitError(Exception):
    """Raised when a search engine rate limits the request."""
    pass


class SearchEngineAdapter(ABC):
    """
    Abstract base class for search engine adapters.

    All adapters must implement the search method and handle:
    - Rate limiting with exponential backoff
    - API key management from environment
    - Graceful failure
    """

    def __init__(self, api_key: Optional[str] = None, rate_limit: float = 1.0):
        """
        Initialize adapter.

        Args:
            api_key: API key for the search engine (loaded from env if not provided)
            rate_limit: Minimum seconds between requests
        """
        self.api_key = api_key
        self.rate_limit = rate_limit
        self.last_request_time = 0
        self.retry_count = 3
        self.backoff_factor = 2.0

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """Return the name of this search engine."""
        pass

    @abstractmethod
    def _execute_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """
        Execute the actual search request.

        This method should be implemented by each adapter to perform
        the API call to the search engine.

        Args:
            query: Search query
            max_results: Maximum number of results to return

        Returns:
            List of raw result dictionaries from the API

        Raises:
            RateLimitError: If rate limited by the search engine
            Exception: For other API errors
        """
        pass

    def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """
        Execute a search with rate limiting and retries.

        Args:
            query: Search query
            max_results: Maximum number of results to return

        Returns:
            List of SearchResult objects
        """
        # Apply rate limiting
        self._apply_rate_limit()

        # Try with exponential backoff
        last_error = None
        for attempt in range(self.retry_count):
            try:
                # Execute the search
                raw_results = self._execute_search(query, max_results)

                # Convert to SearchResult objects
                results = []
                for i, raw in enumerate(raw_results):
                    result = self._parse_result(raw, query, i + 1)
                    if result:
                        results.append(result)

                logger.info(f"{self.engine_name} search for '{query}' returned {len(results)} results")
                return results

            except RateLimitError as e:
                last_error = e
                if attempt < self.retry_count - 1:
                    # Exponential backoff
                    wait_time = self.backoff_factor ** attempt
                    logger.warning(f"{self.engine_name} rate limited, waiting {wait_time}s before retry")
                    time.sleep(wait_time)
                else:
                    logger.error(f"{self.engine_name} rate limit exceeded after {self.retry_count} attempts")

            except Exception as e:
                last_error = e
                logger.error(f"{self.engine_name} search error: {str(e)}")
                if attempt < self.retry_count - 1:
                    time.sleep(1)  # Brief pause before retry

        # All retries failed
        logger.error(f"{self.engine_name} search failed for query '{query}': {str(last_error)}")
        return []  # Fail gracefully

    def _apply_rate_limit(self):
        """Apply rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.rate_limit:
            sleep_time = self.rate_limit - time_since_last
            logger.debug(f"Rate limiting {self.engine_name}: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    @abstractmethod
    def _parse_result(self, raw_result: Dict[str, Any], query: str, position: int) -> Optional[SearchResult]:
        """
        Parse a raw result dictionary into a SearchResult object.

        Args:
            raw_result: Raw result from the API
            query: The search query
            position: Result position (1-based)

        Returns:
            SearchResult object or None if parsing fails
        """
        pass


class ReverseImageAdapter(ABC):
    """Abstract base class for reverse image search adapters."""

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """Return the name of this reverse image search engine."""
        pass

    @abstractmethod
    def search_by_image_url(self, image_url: str, max_results: int = 10) -> List[SearchResult]:
        """
        Search for pages containing a specific image.

        Args:
            image_url: URL of the image to search for
            max_results: Maximum number of results to return

        Returns:
            List of SearchResult objects
        """
        pass