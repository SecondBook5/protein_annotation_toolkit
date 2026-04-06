"""
Base HTTP client with async support.

Provides common functionality for all API clients:
- Retry logic with exponential backoff
- Rate limiting
- Error handling
- Logging
"""

import asyncio
from typing import Optional

import aiohttp
import structlog
from tenacity import (
    AsyncRetrying,
    RetryError,
    stop_after_attempt,
    wait_exponential,
)

from protein_annotation_toolkit.config import get_settings
from protein_annotation_toolkit.exceptions import APIError

# Set up logger
logger = structlog.get_logger(__name__)


class BaseAPIClient:
    """
    Base class for async API clients.

    Provides:
    - HTTP session management
    - Retry logic with exponential backoff
    - Rate limiting via semaphore
    - Consistent error handling
    """

    def __init__(
        self,
        base_url: str,
        max_concurrent: Optional[int] = None,
        timeout: Optional[int] = None,
        max_retries: int = 3
    ):
        """
        Initialize base API client.

        Args:
            base_url: Base URL for API endpoints
            max_concurrent: Maximum concurrent requests (from settings if None)
            timeout: Request timeout in seconds (from settings if None)
            max_retries: Maximum number of retry attempts
        """
        # Get settings
        settings = get_settings()

        # Store configuration
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout or settings.request_timeout
        self.max_retries = max_retries

        # Create semaphore for rate limiting
        max_concurrent = max_concurrent or settings.max_concurrent_requests
        self.semaphore = asyncio.Semaphore(max_concurrent)

        # Session will be created when entering context
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """
        Context manager entry - create HTTP session.
        """
        # Create aiohttp session with timeout
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit - close HTTP session.
        """
        if self.session:
            await self.session.close()

    async def get(
        self,
        url: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None
    ) -> str:
        """
        Make GET request with retry logic.

        Args:
            url: URL to fetch (relative to base_url or absolute)
            params: Query parameters
            headers: HTTP headers

        Returns:
            Response text

        Raises:
            APIError: If request fails after retries
        """
        # Ensure session exists
        if not self.session:
            raise RuntimeError("Client must be used as async context manager")

        # Build full URL
        if url.startswith("http"):
            full_url = url
        else:
            full_url = f"{self.base_url}/{url.lstrip('/')}"

        # Use semaphore to limit concurrent requests
        async with self.semaphore:
            try:
                # Retry with exponential backoff
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(self.max_retries),
                    wait=wait_exponential(multiplier=1, min=2, max=60),
                    reraise=True
                ):
                    with attempt:
                        logger.debug(
                            "api_request",
                            method="GET",
                            url=full_url,
                            attempt=attempt.retry_state.attempt_number
                        )

                        # Make request
                        async with self.session.get(
                            full_url,
                            params=params,
                            headers=headers
                        ) as response:
                            # Handle rate limiting (HTTP 429)
                            if response.status == 429:
                                # Get retry-after header if present
                                retry_after = response.headers.get("Retry-After", "5")
                                try:
                                    wait_time = int(retry_after)
                                except ValueError:
                                    wait_time = 5

                                logger.warning(
                                    "rate_limited",
                                    url=full_url,
                                    retry_after=wait_time
                                )

                                # Wait before retrying
                                await asyncio.sleep(wait_time)
                                raise APIError(f"Rate limited: {full_url}")

                            # Raise for HTTP errors
                            response.raise_for_status()

                            # Read response text
                            text = await response.text()

                            logger.info(
                                "api_success",
                                method="GET",
                                url=full_url,
                                status=response.status,
                                size=len(text)
                            )

                            return text

            except RetryError as e:
                # All retries exhausted
                logger.error(
                    "api_failed_after_retries",
                    url=full_url,
                    error=str(e)
                )
                raise APIError(f"Failed to fetch {full_url} after {self.max_retries} retries: {e}")

            except aiohttp.ClientError as e:
                # HTTP client error
                logger.error(
                    "api_client_error",
                    url=full_url,
                    error=str(e)
                )
                raise APIError(f"HTTP client error for {full_url}: {e}")

            except asyncio.TimeoutError:
                # Request timeout
                logger.error(
                    "api_timeout",
                    url=full_url,
                    timeout=self.timeout
                )
                raise APIError(f"Request timeout for {full_url} after {self.timeout}s")

    async def post(
        self,
        url: str,
        data: Optional[dict] = None,
        json: Optional[dict] = None,
        headers: Optional[dict] = None
    ) -> str:
        """
        Make POST request with retry logic.

        Args:
            url: URL to post to (relative to base_url or absolute)
            data: Form data
            json: JSON data
            headers: HTTP headers

        Returns:
            Response text

        Raises:
            APIError: If request fails after retries
        """
        # Ensure session exists
        if not self.session:
            raise RuntimeError("Client must be used as async context manager")

        # Build full URL
        if url.startswith("http"):
            full_url = url
        else:
            full_url = f"{self.base_url}/{url.lstrip('/')}"

        # Use semaphore to limit concurrent requests
        async with self.semaphore:
            try:
                # Retry with exponential backoff
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(self.max_retries),
                    wait=wait_exponential(multiplier=1, min=2, max=60),
                    reraise=True
                ):
                    with attempt:
                        logger.debug(
                            "api_request",
                            method="POST",
                            url=full_url,
                            attempt=attempt.retry_state.attempt_number
                        )

                        # Make request
                        async with self.session.post(
                            full_url,
                            data=data,
                            json=json,
                            headers=headers
                        ) as response:
                            # Handle rate limiting
                            if response.status == 429:
                                retry_after = response.headers.get("Retry-After", "5")
                                try:
                                    wait_time = int(retry_after)
                                except ValueError:
                                    wait_time = 5

                                logger.warning("rate_limited", url=full_url, retry_after=wait_time)
                                await asyncio.sleep(wait_time)
                                raise APIError(f"Rate limited: {full_url}")

                            # Raise for HTTP errors
                            response.raise_for_status()

                            # Read response text
                            text = await response.text()

                            logger.info(
                                "api_success",
                                method="POST",
                                url=full_url,
                                status=response.status
                            )

                            return text

            except RetryError as e:
                logger.error("api_failed_after_retries", url=full_url, error=str(e))
                raise APIError(f"Failed to post to {full_url} after {self.max_retries} retries: {e}")

            except aiohttp.ClientError as e:
                logger.error("api_client_error", url=full_url, error=str(e))
                raise APIError(f"HTTP client error for {full_url}: {e}")

            except asyncio.TimeoutError:
                logger.error("api_timeout", url=full_url, timeout=self.timeout)
                raise APIError(f"Request timeout for {full_url} after {self.timeout}s")
