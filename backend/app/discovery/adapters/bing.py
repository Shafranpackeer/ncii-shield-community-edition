"""
Bing Web Search API adapter.
"""

import os
import logging
from typing import List, Dict, Any, Optional
import httpx

from .base import SearchEngineAdapter, SearchResult, RateLimitError
from app.utils.runtime_settings import get_runtime_setting


logger = logging.getLogger(__name__)


class BingAdapter(SearchEngineAdapter):
    """
    Adapter for Bing Web Search API v7.

    Docs: https://docs.microsoft.com/en-us/bing/search-apis/bing-web-search/
    """

    ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Bing adapter.

        Args:
            api_key: Bing API key (loaded from BING_API_KEY env if not provided)
        """
        if api_key is None:
            api_key = get_runtime_setting("BING_API_KEY")
            if not api_key:
                raise ValueError("BING_API_KEY not found in environment")

        # Bing allows 3 requests per second on free tier
        super().__init__(api_key=api_key, rate_limit=0.34)  # ~3 req/sec

    @property
    def engine_name(self) -> str:
        return "bing"

    def _execute_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Execute search using Bing Web Search API."""
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Accept": "application/json"
        }

        params = {
            "q": query,
            "count": min(max_results, 50),  # Bing max is 50 per request
            "mkt": "en-US",
            "safeSearch": "Off"  # NCII context requires this
        }

        try:
            with httpx.Client() as client:
                response = client.get(
                    self.ENDPOINT,
                    headers=headers,
                    params=params,
                    timeout=30.0
                )

                if response.status_code == 429:
                    raise RateLimitError("Bing API rate limit exceeded")

                response.raise_for_status()
                data = response.json()

                # Extract web results
                return data.get("webPages", {}).get("value", [])

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ValueError("Invalid Bing API key")
            elif e.response.status_code == 429:
                raise RateLimitError("Bing API rate limit exceeded")
            else:
                logger.error(f"Bing API error: {e}")
                raise

        except Exception as e:
            logger.error(f"Bing search error: {str(e)}")
            raise

    def _parse_result(self, raw_result: Dict[str, Any], query: str, position: int) -> Optional[SearchResult]:
        """Parse Bing API result into SearchResult."""
        try:
            return SearchResult(
                url=raw_result["url"],
                title=raw_result.get("name", ""),
                snippet=raw_result.get("snippet", ""),
                engine=self.engine_name,
                position=position,
                query=query
            )
        except KeyError as e:
            logger.warning(f"Failed to parse Bing result: missing field {e}")
            return None


class BingVisualSearchAdapter:
    """
    Adapter for Bing Visual Search API.

    Used for reverse image search.
    """

    ENDPOINT = "https://api.bing.microsoft.com/v7.0/images/visualsearch"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Bing Visual Search adapter."""
        if api_key is None:
            api_key = get_runtime_setting("BING_API_KEY")
            if not api_key:
                raise ValueError("BING_API_KEY not found in environment")

        self.api_key = api_key
        self.rate_limit = 0.34  # Same as web search

    @property
    def engine_name(self) -> str:
        return "bing_visual"

    def search_by_image_url(self, image_url: str, max_results: int = 10) -> List[SearchResult]:
        """
        Search for pages containing the image.

        Args:
            image_url: URL of the image to search for
            max_results: Maximum results to return

        Returns:
            List of SearchResult objects
        """
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Content-Type": "application/json"
        }

        # Bing Visual Search requires JSON body
        json_body = {
            "imageInfo": {
                "url": image_url
            }
        }

        try:
            with httpx.Client() as client:
                response = client.post(
                    self.ENDPOINT,
                    headers=headers,
                    json=json_body,
                    timeout=30.0
                )

                if response.status_code == 429:
                    raise RateLimitError("Bing Visual Search API rate limit exceeded")

                response.raise_for_status()
                data = response.json()

                # Extract pages including the image
                results = []
                tags = data.get("tags", [])

                for tag in tags:
                    for action in tag.get("actions", []):
                        if action.get("actionType") == "PagesIncluding":
                            for i, page in enumerate(action.get("data", {}).get("value", [])):
                                if i >= max_results:
                                    break

                                result = SearchResult(
                                    url=page.get("hostPageUrl", ""),
                                    title=page.get("name", ""),
                                    snippet=page.get("snippet", ""),
                                    engine=self.engine_name,
                                    position=i + 1,
                                    query=f"reverse_image:{image_url}"
                                )
                                results.append(result)

                return results

        except httpx.HTTPStatusError as e:
            logger.error(f"Bing Visual Search API error: {e}")
            return []

        except Exception as e:
            logger.error(f"Bing Visual Search error: {str(e)}")
            return []
