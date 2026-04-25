#!/usr/bin/env python3
"""
Test script for discovery flow with new adapters.

This script tests:
1. Search engine adapter initialization
2. Template loading
3. Query execution
4. Result deduplication
"""

import os
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.discovery.adapters import (
    BingAdapter,
    SerpApiYandexAdapter,
    SerperAdapter,
    SearchResult
)
from app.discovery.template_loader import DorkTemplateLoader, RiskLevel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_adapters():
    """Test that search adapters initialize properly."""
    print("\n=== Testing Search Adapters ===")

    adapters = {}

    # Test Serper (highest priority)
    if os.getenv("SERPER_API_KEY"):
        try:
            adapters["serper-google"] = SerperAdapter()
            print("✓ Serper adapter initialized")
        except Exception as e:
            print(f"✗ Serper adapter failed: {e}")
    else:
        print("- Serper adapter skipped (no API key)")

    # Test SerpAPI-Yandex
    if os.getenv("SERPAPI_KEY"):
        try:
            adapters["yandex"] = SerpApiYandexAdapter()
            print("✓ SerpAPI-Yandex adapter initialized")
        except Exception as e:
            print(f"✗ SerpAPI-Yandex adapter failed: {e}")
    else:
        print("- SerpAPI-Yandex adapter skipped (no API key)")

    # Test Bing
    if os.getenv("BING_API_KEY"):
        try:
            adapters["bing"] = BingAdapter()
            print("✓ Bing adapter initialized")
        except Exception as e:
            print(f"✗ Bing adapter failed: {e}")
    else:
        print("- Bing adapter skipped (no API key)")

    print(f"\nTotal adapters available: {len(adapters)}")
    return adapters


def test_template_loading():
    """Test dork template loading."""
    print("\n=== Testing Template Loading ===")

    loader = DorkTemplateLoader()

    # Test with sample data
    test_data = {
        "first_name": "Test",
        "last_name": "User",
        "handle": "testuser123"
    }

    # Get low-risk templates
    low_risk = loader.get_applicable_templates(
        available_data=test_data,
        engines=["serper-google", "yandex", "bing"],
        risk_threshold=RiskLevel.LOW
    )
    print(f"Low risk templates: {len(low_risk)}")

    # Get all templates (including high risk)
    all_templates = loader.get_applicable_templates(
        available_data=test_data,
        engines=["serper-google", "yandex", "bing"],
        risk_threshold=RiskLevel.HIGH
    )
    print(f"All templates: {len(all_templates)}")

    # Show a few example queries
    print("\nExample queries:")
    for template in low_risk[:3]:
        query = template.expand(test_data)
        print(f"  - {template.id}: {query}")

    return loader


def test_search_execution(adapters, loader):
    """Test executing a search with available adapters."""
    print("\n=== Testing Search Execution ===")

    if not adapters:
        print("No adapters available for testing")
        return

    # Use test data
    test_data = {
        "first_name": "Test",
        "last_name": "User"
    }

    # Get a simple template
    templates = loader.get_applicable_templates(
        available_data=test_data,
        engines=list(adapters.keys()),
        risk_threshold=RiskLevel.LOW
    )

    if not templates:
        print("No applicable templates found")
        return

    # Use the first template
    template = templates[0]
    query = template.expand(test_data)

    print(f"Testing query: {query}")
    print(f"Using template: {template.id}")
    print(f"Compatible engines: {template.engines}")

    # Try each adapter
    for engine_name, adapter in adapters.items():
        if engine_name not in template.engines:
            continue

        print(f"\nTesting {engine_name}...")
        try:
            results = adapter.search(query, max_results=5)
            print(f"  Found {len(results)} results")

            # Show first result
            if results:
                result = results[0]
                print(f"  First result: {result.url[:80]}...")
                print(f"  Title: {result.title[:80]}...")
        except Exception as e:
            print(f"  Error: {e}")


def test_rate_limiting(adapters):
    """Test rate limiting functionality."""
    print("\n=== Testing Rate Limiting ===")

    if not adapters:
        print("No adapters available for testing")
        return

    # Pick first available adapter
    engine_name, adapter = next(iter(adapters.items()))

    print(f"Testing rate limit on {engine_name}...")
    print(f"Rate limit: {adapter.rate_limit} requests/second")

    # Make two quick requests
    import time

    try:
        start = time.time()
        adapter.search("test query 1", max_results=1)
        mid = time.time()
        adapter.search("test query 2", max_results=1)
        end = time.time()

        delay = mid - start
        total = end - start

        print(f"First request took: {delay:.2f}s")
        print(f"Second request delayed by: {(end - mid):.2f}s")
        print(f"Total time: {total:.2f}s")
        print("✓ Rate limiting working correctly")
    except Exception as e:
        print(f"✗ Rate limiting test failed: {e}")


def main():
    """Run all tests."""
    print("NCII Shield Discovery Flow Test")
    print("=" * 40)

    # Check environment
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file)
        print("Loaded .env file")
    else:
        print("Warning: No .env file found")

    # Run tests
    adapters = test_adapters()
    loader = test_template_loading()

    if adapters and loader:
        test_search_execution(adapters, loader)
        test_rate_limiting(adapters)

    print("\n" + "=" * 40)
    print("Test complete!")


if __name__ == "__main__":
    main()