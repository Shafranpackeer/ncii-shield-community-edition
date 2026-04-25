"""
SerpAPI adapter for Google search.
"""

import os
import logging
from typing import List, Dict, Any, Optional
import httpx

from .base import SearchEngineAdapter, SearchResult, RateLimitError
from app.utils.runtime_settings import get_runtime_setting


logger = logging.getLogger(__name__)


class SerpApiAdapter(SearchEngineAdapter):
    """
    Adapter for SerpAPI (Google search).

    Docs: https://serpapi.com/search-api
    """

    ENDPOINT = "https://serpapi.com/search"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize SerpAPI adapter.

        Args:
            api_key: SerpAPI key (loaded from SERPAPI_KEY env if not provided)
        """
        if api_key is None:
            api_key = get_runtime_setting("SERPAPI_KEY")
            if not api_key:
                raise ValueError("SERPAPI_KEY not found in environment")

        # SerpAPI rate limit depends on plan, conservative default
        super().__init__(api_key=api_key, rate_limit=1.0)  # 1 req/sec

    @property
    def engine_name(self) -> str:
        return "google"

    def _execute_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Execute search using SerpAPI."""
        params = {
            "api_key": self.api_key,
            "engine": "google",
            "q": query,
            "num": min(max_results, 100),  # Google max is 100
            "gl": "us",  # Country
            "hl": "en",  # Language
            "safe": "off"  # Required for NCII context
        }

        try:
            with httpx.Client() as client:
                response = client.get(
                    self.ENDPOINT,
                    params=params,
                    timeout=30.0
                )

                if response.status_code == 429:
                    raise RateLimitError("SerpAPI rate limit exceeded")

                response.raise_for_status()
                data = response.json()

                # Check for API errors
                if "error" in data:
                    if "rate limit" in data["error"].lower():
                        raise RateLimitError(data["error"])
                    else:
                        raise Exception(data["error"])

                # Extract organic results
                return data.get("organic_results", [])

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ValueError("Invalid SerpAPI key")
            elif e.response.status_code == 429:
                raise RateLimitError("SerpAPI rate limit exceeded")
            else:
                logger.error(f"SerpAPI error: {e}")
                raise

        except Exception as e:
            logger.error(f"SerpAPI search error: {str(e)}")
            raise

    def _parse_result(self, raw_result: Dict[str, Any], query: str, position: int) -> Optional[SearchResult]:
        """Parse SerpAPI result into SearchResult."""
        try:
            return SearchResult(
                url=raw_result["link"],
                title=raw_result.get("title", ""),
                snippet=raw_result.get("snippet", ""),
                engine=self.engine_name,
                position=position,
                query=query
            )
        except KeyError as e:
            logger.warning(f"Failed to parse SerpAPI result: missing field {e}")
            return None


class SerpApiYandexAdapter(SearchEngineAdapter):
    """
    Adapter for Yandex search via SerpAPI.

    Yandex is particularly effective for NCII discovery.
    """

    ENDPOINT = "https://serpapi.com/search"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Yandex adapter via SerpAPI."""
        if api_key is None:
            api_key = get_runtime_setting("SERPAPI_KEY")
            if not api_key:
                raise ValueError("SERPAPI_KEY not found in environment")

        super().__init__(api_key=api_key, rate_limit=1.0)

    @property
    def engine_name(self) -> str:
        return "yandex"

    def _execute_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Execute Yandex search using SerpAPI."""
        params = {
            "api_key": self.api_key,
            "engine": "yandex",
            "text": query,  # Yandex uses 'text' instead of 'q'
            "lang": "en",
            "lr": "1"  # Language region
        }

        try:
            with httpx.Client() as client:
                response = client.get(
                    self.ENDPOINT,
                    params=params,
                    timeout=30.0
                )

                if response.status_code == 429:
                    raise RateLimitError("SerpAPI rate limit exceeded")

                response.raise_for_status()
                data = response.json()

                # Check for API errors
                if "error" in data:
                    if "rate limit" in data["error"].lower():
                        raise RateLimitError(data["error"])
                    else:
                        raise Exception(data["error"])

                # Extract organic results
                results = data.get("organic_results", [])

                # Limit to max_results
                return results[:max_results]

        except Exception as e:
            logger.error(f"Yandex (SerpAPI) search error: {str(e)}")
            raise

    def _parse_result(self, raw_result: Dict[str, Any], query: str, position: int) -> Optional[SearchResult]:
        """Parse Yandex result into SearchResult."""
        try:
            return SearchResult(
                url=raw_result["link"],
                title=raw_result.get("title", ""),
                snippet=raw_result.get("snippet", ""),
                engine=self.engine_name,
                position=position,
                query=query
            )
        except KeyError as e:
            logger.warning(f"Failed to parse Yandex result: missing field {e}")
            return None
