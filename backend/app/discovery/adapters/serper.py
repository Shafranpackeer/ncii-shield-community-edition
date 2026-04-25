"""
Serper.dev adapter for Google search.

Serper.dev provides better results than Google Custom Search API
and is more suitable for NCII discovery with 2500 free queries/month.
"""

import os
import logging
from typing import List, Dict, Any, Optional
import httpx

from .base import SearchEngineAdapter, SearchResult, RateLimitError
from app.utils.runtime_settings import get_runtime_setting


logger = logging.getLogger(__name__)


class SerperAdapter(SearchEngineAdapter):
    """
    Adapter for Serper.dev (Google search).

    Docs: https://serper.dev/docs

    Advantages over Google Custom Search:
    - Real Google results (not limited index)
    - 2500 free queries/month
    - Better for NCII discovery
    - Supports Google Lens reverse image search (future feature)
    """

    ENDPOINT = "https://google.serper.dev/search"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Serper adapter.

        Args:
            api_key: Serper API key (loaded from SERPER_API_KEY env if not provided)
        """
        if api_key is None:
            api_key = get_runtime_setting("SERPER_API_KEY")
            if not api_key:
                raise ValueError("SERPER_API_KEY not found in environment")

        # Serper rate limit: 100 requests per minute
        super().__init__(api_key=api_key, rate_limit=1.67)  # ~100 req/min

    @property
    def engine_name(self) -> str:
        return "serper-google"

    def _execute_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Execute search using Serper.dev."""
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }

        payload = {
            "q": query,
            "num": min(max_results, 100),  # Max 100 per request
            "gl": "us",  # Country
            "hl": "en",  # Language
            "safe": "off"  # Required for NCII context
        }

        try:
            with httpx.Client() as client:
                response = client.post(
                    self.ENDPOINT,
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )

                if response.status_code == 429:
                    raise RateLimitError("Serper rate limit exceeded")

                response.raise_for_status()
                data = response.json()

                # Check for API errors
                if "error" in data:
                    if "rate limit" in data["error"].lower():
                        raise RateLimitError(data["error"])
                    else:
                        raise Exception(data["error"])

                # Extract organic results
                return data.get("organic", [])

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ValueError("Invalid Serper API key")
            elif e.response.status_code == 429:
                raise RateLimitError("Serper rate limit exceeded")
            else:
                logger.error(f"Serper error: {e}")
                raise

        except Exception as e:
            logger.error(f"Serper search error: {str(e)}")
            raise

    def _parse_result(self, raw_result: Dict[str, Any], query: str, position: int) -> Optional[SearchResult]:
        """Parse Serper result into SearchResult."""
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
            logger.warning(f"Failed to parse Serper result: missing field {e}")
            return None


class SerperImageAdapter(SearchEngineAdapter):
    """
    Adapter for Serper.dev Google Lens reverse image search.

    Reserved for Step 5 (Confirmation phase).
    """

    ENDPOINT = "https://google.serper.dev/images"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Serper image search adapter."""
        if api_key is None:
            api_key = get_runtime_setting("SERPER_API_KEY")
            if not api_key:
                raise ValueError("SERPER_API_KEY not found in environment")

        super().__init__(api_key=api_key, rate_limit=1.67)

    @property
    def engine_name(self) -> str:
        return "serper-images"

    def reverse_image_search(self, image_url: str, max_results: int = 10) -> List[SearchResult]:
        """
        Perform reverse image search using Google Lens via Serper.

        Args:
            image_url: URL of the image to search for
            max_results: Maximum number of results

        Returns:
            List of search results
        """
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }

        payload = {
            "url": image_url,
            "num": min(max_results, 100)
        }

        try:
            with httpx.Client() as client:
                response = client.post(
                    self.ENDPOINT,
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )

                if response.status_code == 429:
                    raise RateLimitError("Serper rate limit exceeded")

                response.raise_for_status()
                data = response.json()

                # Parse image results
                results = []
                for idx, result in enumerate(data.get("images", [])):
                    try:
                        search_result = SearchResult(
                            url=result.get("link", ""),
                            title=result.get("title", ""),
                            snippet=result.get("source", ""),
                            engine=self.engine_name,
                            position=idx,
                            query=f"reverse:{image_url}"
                        )
                        results.append(search_result)
                    except Exception as e:
                        logger.warning(f"Failed to parse image result: {e}")

                return results

        except Exception as e:
            logger.error(f"Serper image search error: {str(e)}")
            raise

    def _execute_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Not used for image search."""
        raise NotImplementedError("Use reverse_image_search method instead")

    def _parse_result(self, raw_result: Dict[str, Any], query: str, position: int) -> Optional[SearchResult]:
        """Not used for image search."""
        raise NotImplementedError("Use reverse_image_search method instead")
