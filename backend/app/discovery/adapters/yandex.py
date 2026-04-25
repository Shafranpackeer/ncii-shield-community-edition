"""
Yandex search adapters.

Note: Using SerpAPI for regular Yandex search.
Direct Yandex reverse image search for image discovery.
"""

import os
import logging
from typing import List, Dict, Any, Optional
import httpx

from .base import SearchResult, RateLimitError, ReverseImageAdapter
from .serpapi import SerpApiYandexAdapter
from app.utils.runtime_settings import get_runtime_setting


logger = logging.getLogger(__name__)


# Re-export SerpAPI Yandex adapter as main Yandex adapter
YandexAdapter = SerpApiYandexAdapter


class YandexReverseImageAdapter(ReverseImageAdapter):
    """
    Yandex reverse image search adapter.

    Yandex has strong reverse image capabilities, particularly
    effective for NCII content discovery.
    """

    ENDPOINT = "https://yandex.com/images/search"

    def __init__(self):
        """Initialize Yandex reverse image adapter."""
        self.rate_limit = 1.0  # Conservative rate limit
        self.last_request_time = 0

    @property
    def engine_name(self) -> str:
        return "yandex_reverse"

    def search_by_image_url(self, image_url: str, max_results: int = 10) -> List[SearchResult]:
        """
        Search for pages containing the image using Yandex.

        Note: This is a simplified implementation. In production,
        you would need to handle Yandex's more complex API or
        use a proper reverse image search API.

        Args:
            image_url: URL of the image to search for
            max_results: Maximum results to return

        Returns:
            List of SearchResult objects
        """
        # Apply rate limiting
        import time
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.rate_limit:
            time.sleep(self.rate_limit - time_since_last)

        self.last_request_time = time.time()

        # Construct reverse image search URL
        params = {
            "rpt": "imageview",
            "url": image_url
        }

        try:
            # Note: In production, you would need proper Yandex API access
            # This is a placeholder implementation
            logger.warning(
                "YandexReverseImageAdapter: Direct Yandex reverse image search "
                "requires additional implementation. Using placeholder."
            )

            # Return empty results for now
            # In production, implement proper Yandex reverse image API
            return []

        except Exception as e:
            logger.error(f"Yandex reverse image search error: {str(e)}")
            return []


class YandexReverseImageViaSerpAPI(ReverseImageAdapter):
    """
    Alternative: Yandex reverse image search via SerpAPI.

    If SerpAPI supports Yandex image search in your plan.
    """

    ENDPOINT = "https://serpapi.com/search"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Yandex reverse image adapter via SerpAPI."""
        if api_key is None:
            api_key = get_runtime_setting("SERPAPI_KEY")
            if not api_key:
                raise ValueError("SERPAPI_KEY not found in environment")

        self.api_key = api_key
        self.rate_limit = 1.0

    @property
    def engine_name(self) -> str:
        return "yandex_reverse_serpapi"

    def search_by_image_url(self, image_url: str, max_results: int = 10) -> List[SearchResult]:
        """
        Search for similar images using Yandex via SerpAPI.

        Args:
            image_url: URL of the image to search for
            max_results: Maximum results to return

        Returns:
            List of SearchResult objects
        """
        params = {
            "api_key": self.api_key,
            "engine": "yandex_images",
            "url": image_url
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

                # Check if this engine is supported in the plan
                if "error" in data and "not supported" in data["error"].lower():
                    logger.warning("Yandex image search not supported in SerpAPI plan")
                    return []

                # Parse results
                results = []
                for i, item in enumerate(data.get("images_results", [])):
                    if i >= max_results:
                        break

                    # Extract source page info if available
                    if "source" in item:
                        result = SearchResult(
                            url=item["source"],
                            title=item.get("title", ""),
                            snippet=item.get("snippet", ""),
                            engine=self.engine_name,
                            position=i + 1,
                            query=f"reverse_image:{image_url}"
                        )
                        results.append(result)

                return results

        except Exception as e:
            logger.error(f"Yandex reverse image (SerpAPI) error: {str(e)}")
            return []
