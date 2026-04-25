"""Unit tests for the scraper module."""

import os
import time
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
import asyncio
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.confirmation.scraper import ImageScraper


class TestImageScraper:
    """Test cases for the ImageScraper class."""

    @pytest.fixture
    def scraper(self):
        """Create an ImageScraper instance."""
        return ImageScraper(
            timeout_seconds=5,  # 5 seconds for tests
            rate_limit_seconds=0.1,  # Faster for tests
            proxy_url=None
        )

    @pytest.mark.asyncio
    async def test_temporary_directory(self, scraper):
        """Test temporary directory creation and cleanup."""
        temp_dir = None

        # Use the context manager
        with scraper.temporary_directory() as dir_path:
            temp_dir = dir_path
            assert os.path.exists(dir_path)
            assert os.path.isdir(dir_path)

            # Create a test file
            test_file = os.path.join(dir_path, 'test.txt')
            with open(test_file, 'w') as f:
                f.write('test')
            assert os.path.exists(test_file)

        # After context manager exits, directory should be cleaned up
        assert not os.path.exists(temp_dir)

    @pytest.mark.asyncio
    async def test_temporary_directory_cleanup_on_error(self, scraper):
        """Test temporary directory cleanup even when error occurs."""
        temp_dir = None

        try:
            with scraper.temporary_directory() as dir_path:
                temp_dir = dir_path
                assert os.path.exists(dir_path)
                raise RuntimeError("Test error")
        except RuntimeError:
            pass

        # Directory should still be cleaned up
        assert not os.path.exists(temp_dir)

    @pytest.mark.asyncio
    async def test_rate_limiting(self, scraper):
        """Test rate limiting functionality."""
        domain = "example.com"

        # First request should be immediate
        start = time.time()
        scraper._apply_rate_limit(domain)
        elapsed = time.time() - start
        assert elapsed < 0.1  # Should be instant

        # Second request should be rate limited
        start = time.time()
        scraper._apply_rate_limit(domain)
        elapsed = time.time() - start
        assert elapsed >= 0.09  # Should wait ~0.1 seconds (10 req/s)

    @pytest.mark.asyncio
    async def test_extract_domain(self, scraper):
        """Test domain extraction from URLs."""
        assert scraper._extract_domain("https://example.com/page") == "example.com"
        assert scraper._extract_domain("http://sub.example.com/") == "sub.example.com"
        assert scraper._extract_domain("https://example.com:8080/") == "example.com"

    @pytest.mark.asyncio
    async def test_scrape_images_success(self, scraper):
        """Test successful image scraping."""
        # Mock playwright components
        mock_page = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_playwright = AsyncMock()

        # Setup mock returns
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)

        # Mock page behavior
        mock_page.goto = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()

        # Mock finding images
        mock_img1 = MagicMock()
        mock_img1.get_attribute = AsyncMock(return_value="https://example.com/image1.jpg")
        mock_img1.screenshot = AsyncMock(return_value=b"fake_image_data_1")

        mock_img2 = MagicMock()
        mock_img2.get_attribute = AsyncMock(return_value="https://example.com/image2.jpg")
        mock_img2.screenshot = AsyncMock(return_value=b"fake_image_data_2")

        mock_page.locator = AsyncMock(return_value=AsyncMock())
        mock_page.locator.return_value.all = AsyncMock(return_value=[mock_img1, mock_img2])

        with patch('playwright.async_api.async_playwright') as mock_async_playwright:
            mock_async_playwright.return_value.__aenter__ = AsyncMock(return_value=mock_playwright)
            mock_async_playwright.return_value.__aexit__ = AsyncMock()

            result = await scraper.scrape_images("https://example.com/test")

        assert result['success'] is True
        assert result['url'] == "https://example.com/test"
        assert result['image_count'] == 2
        assert len(result['images']) == 2
        assert os.path.exists(result['images'][0])
        assert os.path.exists(result['images'][1])

        # Cleanup
        for img_path in result['images']:
            if os.path.exists(img_path):
                os.unlink(img_path)
        if os.path.exists(result['temp_dir']):
            os.rmdir(result['temp_dir'])

    @pytest.mark.asyncio
    async def test_scrape_images_timeout(self, scraper):
        """Test scraping timeout handling."""
        mock_page = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_playwright = AsyncMock()

        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)

        # Make goto timeout
        mock_page.goto = AsyncMock(side_effect=PlaywrightTimeoutError("Navigation timeout"))

        with patch('playwright.async_api.async_playwright') as mock_async_playwright:
            mock_async_playwright.return_value.__aenter__ = AsyncMock(return_value=mock_playwright)
            mock_async_playwright.return_value.__aexit__ = AsyncMock()

            result = await scraper.scrape_images("https://timeout.example.com")

        assert result['success'] is False
        assert "timeout" in result['error'].lower()

    @pytest.mark.asyncio
    async def test_scrape_images_with_proxy(self):
        """Test scraping with proxy configuration."""
        proxy_scraper = ImageScraper(
            timeout_seconds=5,
            rate_limit_seconds=0.1,
            proxy_url="http://proxy.example.com:8080"
        )

        mock_browser = AsyncMock()
        mock_playwright = AsyncMock()

        # Capture the launch arguments
        launch_args = None

        async def capture_launch(**kwargs):
            nonlocal launch_args
            launch_args = kwargs
            return mock_browser

        mock_playwright.chromium.launch = capture_launch

        with patch('playwright.async_api.async_playwright') as mock_async_playwright:
            mock_async_playwright.return_value.__aenter__ = AsyncMock(return_value=mock_playwright)
            mock_async_playwright.return_value.__aexit__ = AsyncMock()

            # Setup remaining mocks
            mock_context = AsyncMock()
            mock_page = AsyncMock()
            mock_browser.new_context = AsyncMock(return_value=mock_context)
            mock_context.new_page = AsyncMock(return_value=mock_page)
            mock_page.goto = AsyncMock()
            mock_page.wait_for_load_state = AsyncMock()
            mock_page.locator = AsyncMock(return_value=AsyncMock())
            mock_page.locator.return_value.all = AsyncMock(return_value=[])

            await proxy_scraper.scrape_images("https://example.com")

        # Check that proxy was configured
        assert launch_args is not None
        assert 'args' in launch_args
        assert any('--proxy-server=http://proxy.example.com:8080' in arg for arg in launch_args['args'])

    @pytest.mark.asyncio
    async def test_download_image(self, scraper):
        """Test image download functionality."""
        mock_page = AsyncMock()

        # Test successful download
        with patch('aiofiles.open', create=True) as mock_aiofiles:
            mock_file = AsyncMock()
            mock_file.write = AsyncMock()
            mock_aiofiles.return_value.__aenter__ = AsyncMock(return_value=mock_file)
            mock_aiofiles.return_value.__aexit__ = AsyncMock()

            result = await scraper._download_image(
                mock_page,
                "https://example.com/test.jpg",
                "/tmp/test",
                0
            )

            assert result == "/tmp/test/image_0.jpg"
            mock_page.goto.assert_called_once_with("https://example.com/test.jpg")
            mock_file.write.assert_called_once()

    def test_user_agent_rotation(self, scraper):
        """Test that user agents are rotated."""
        agents = set()
        for _ in range(10):
            agent = scraper._get_user_agent()
            agents.add(agent)

        # Should have multiple different user agents
        assert len(agents) > 1

    def test_is_valid_image_url(self, scraper):
        """Test URL validation for images."""
        # Valid image URLs
        assert scraper._is_valid_image_url("https://example.com/image.jpg") is True
        assert scraper._is_valid_image_url("http://example.com/photo.png") is True
        assert scraper._is_valid_image_url("https://cdn.example.com/img.webp") is True

        # Invalid URLs
        assert scraper._is_valid_image_url("javascript:void(0)") is False
        assert scraper._is_valid_image_url("data:image/png;base64,abc") is False
        assert scraper._is_valid_image_url("about:blank") is False
        assert scraper._is_valid_image_url("file:///etc/passwd") is False
        assert scraper._is_valid_image_url(None) is False
        assert scraper._is_valid_image_url("") is False

        # Non-image URLs
        assert scraper._is_valid_image_url("https://example.com/page.html") is False
        assert scraper._is_valid_image_url("https://example.com/script.js") is False