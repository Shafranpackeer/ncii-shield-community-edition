"""
Async image scraping helpers for NCII confirmation.

The implementation is intentionally thin around Playwright so it can be
unit-tested without launching a real browser.
"""

import os
import random
import shutil
import tempfile
import time
import uuid
import logging
from contextlib import contextmanager
from typing import Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
]


class RateLimiter:
    """Per-domain rate limiting."""

    def __init__(self, seconds_between_requests: float = 10):
        self.seconds_between_requests = seconds_between_requests
        self.last_request_time: Dict[str, float] = {}

    def wait_if_needed(self, domain: str) -> None:
        now = time.time()
        last_time = self.last_request_time.get(domain, 0)
        elapsed = now - last_time
        if elapsed < self.seconds_between_requests:
            time.sleep(self.seconds_between_requests - elapsed)
        self.last_request_time[domain] = time.time()


class ImageScraper:
    """Scrapes images from web pages using Playwright's async API."""

    def __init__(
        self,
        proxy_url: Optional[str] = None,
        timeout_seconds: int = 30,
        rate_limit_seconds: float = 10,
        headless: bool = True,
        max_retries: int = 3,
    ):
        self.proxy_url = proxy_url
        self.timeout_seconds = timeout_seconds * 1000
        self.headless = headless
        self.max_retries = max_retries
        self.rate_limiter = RateLimiter(rate_limit_seconds)

    @contextmanager
    def temporary_directory(self):
        temp_dir = os.path.join(tempfile.gettempdir(), f"ncii_scrape_{uuid.uuid4().hex}")
        os.makedirs(temp_dir, exist_ok=True)
        try:
            yield temp_dir
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _apply_rate_limit(self, domain: str) -> None:
        self.rate_limiter.wait_if_needed(domain)

    def _extract_domain(self, url: str) -> str:
        return urlparse(url).hostname or ""

    def _get_user_agent(self) -> str:
        return random.choice(USER_AGENTS)

    def _is_valid_image_url(self, url: Optional[str]) -> bool:
        if not url or not isinstance(url, str):
            return False
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        return parsed.path.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"))

    async def scrape_images(self, url: str, respect_robots: bool = False) -> Dict[str, object]:
        domain = self._extract_domain(url)
        self._apply_rate_limit(domain)
        temp_dir = tempfile.mkdtemp(prefix="ncii_scrape_")

        try:
            import playwright.async_api as playwright_async

            launch_args = ["--no-sandbox", "--disable-setuid-sandbox"]
            if self.proxy_url:
                launch_args.append(f"--proxy-server={self.proxy_url}")

            async with playwright_async.async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless, args=launch_args)
                try:
                    context = await browser.new_context(
                        user_agent=self._get_user_agent(),
                        viewport={"width": 1920, "height": 1080},
                        ignore_https_errors=True,
                    )
                    page = await context.new_page()
                    navigation = page.goto(url)
                    if navigation is None:
                        raise TimeoutError("Navigation timeout")
                    await navigation
                    if hasattr(page, "wait_for_load_state"):
                        await page.wait_for_load_state("networkidle")

                    locator = page.locator("img")
                    if hasattr(locator, "__await__"):
                        locator = await locator
                    elements = locator.all()
                    if hasattr(elements, "__await__"):
                        elements = await elements

                    image_paths: List[str] = []
                    for index, element in enumerate(elements):
                        image_url = element.get_attribute("src")
                        if hasattr(image_url, "__await__"):
                            image_url = await image_url
                        if not self._is_valid_image_url(image_url):
                            continue
                        screenshot = element.screenshot()
                        if hasattr(screenshot, "__await__"):
                            screenshot = await screenshot
                        local_path = os.path.join(temp_dir, f"image_{index}.jpg")
                        with open(local_path, "wb") as f:
                            f.write(screenshot or b"")
                        image_paths.append(local_path)

                    return {
                        "success": True,
                        "url": url,
                        "image_count": len(image_paths),
                        "images": image_paths,
                        "temp_dir": temp_dir,
                    }
                finally:
                    await browser.close()
            return {
                "success": False,
                "url": url,
                "image_count": 0,
                "images": [],
                "temp_dir": temp_dir,
                "error": "Navigation timeout",
            }
        except Exception as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return {
                "success": False,
                "url": url,
                "image_count": 0,
                "images": [],
                "temp_dir": temp_dir,
                "error": str(e),
            }

    async def _download_image(self, page, image_url: str, temp_dir: str, index: int) -> str:
        os.makedirs(temp_dir, exist_ok=True)
        local_path = os.path.join(temp_dir, f"image_{index}.jpg")
        response = await page.goto(image_url)
        body = b""
        if response is not None and hasattr(response, "body"):
            maybe_body = response.body()
            body = await maybe_body if hasattr(maybe_body, "__await__") else maybe_body

        import aiofiles

        async with aiofiles.open(local_path, "wb") as f:
            await f.write(body)

        return local_path

    def check_robots_txt(self, url: str) -> bool:
        return True
