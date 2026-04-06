"""
Base HTTP client with async support.

Provides common functionality for all API clients:
- Retry logic with exponential backoff
- Rate limiting
- Error handling
- Logging
"""

import asyncio
import hashlib
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

# Try to import Redis for caching (optional)
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

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
        max_retries: int = 3,
        enable_cache: bool = False,
        cache_ttl: int = 3600
    ):
        """
        Initialize base API client.

        Args:
            base_url: Base URL for API endpoints
            max_concurrent: Maximum concurrent requests (from settings if None)
            timeout: Request timeout in seconds (from settings if None)
            max_retries: Maximum number of retry attempts
            enable_cache: Enable Redis caching for responses
            cache_ttl: Cache TTL in seconds (default 1 hour)
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

        # Caching setup
        self.enable_cache = enable_cache and REDIS_AVAILABLE
        self.cache_ttl = cache_ttl
        self.redis_client: Optional[redis.Redis] = None

        if enable_cache and not REDIS_AVAILABLE:
            logger.warning("redis_not_available", message="Redis not installed, caching disabled")

    async def __aenter__(self):
        """
        Context manager entry - create HTTP session and Redis client.
        """
        # Create aiohttp session with timeout
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        self.session = aiohttp.ClientSession(timeout=timeout)

        # Create Redis client if caching enabled
        if self.enable_cache:
            try:
                self.redis_client = redis.Redis(
                    host='localhost',
                    port=6379,
                    decode_responses=True
                )
                # Test connection
                await self.redis_client.ping()
                logger.info("redis_connected")
            except Exception as e:
                logger.warning("redis_connection_failed", error=str(e))
                self.enable_cache = False
                self.redis_client = None

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit - close HTTP session and Redis client.
        """
        if self.session:
            await self.session.close()

        if self.redis_client:
            await self.redis_client.close()

    def _generate_cache_key(self, url: str, params: Optional[dict] = None) -> str:
        """Generate cache key from URL and params."""
        key_parts = [url]
        if params:
            # Sort params for consistent key
            sorted_params = sorted(params.items())
            key_parts.append(str(sorted_params))

        key_string = "|".join(key_parts)
        # Use hash to keep key size manageable
        return f"api_cache:{hashlib.md5(key_string.encode()).hexdigest()}"

    async def _get_from_cache(self, cache_key: str) -> Optional[str]:
        """Get value from cache."""
        if not self.enable_cache or not self.redis_client:
            return None

        try:
            value = await self.redis_client.get(cache_key)
            if value:
                logger.debug("cache_hit", key=cache_key)
            return value
        except Exception as e:
            logger.warning("cache_get_failed", error=str(e))
            return None

    async def _set_in_cache(self, cache_key: str, value: str) -> None:
        """Set value in cache with TTL."""
        if not self.enable_cache or not self.redis_client:
            return

        try:
            await self.redis_client.setex(cache_key, self.cache_ttl, value)
            logger.debug("cache_set", key=cache_key, ttl=self.cache_ttl)
        except Exception as e:
            logger.warning("cache_set_failed", error=str(e))

    async def get(
        self,
        url: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        use_cache: bool = True
    ) -> str:
        """
        Make GET request with retry logic and optional caching.

        Args:
            url: URL to fetch (relative to base_url or absolute)
            params: Query parameters
            headers: HTTP headers
            use_cache: Whether to use cache for this request

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

        # Check cache if enabled
        if use_cache and self.enable_cache:
            cache_key = self._generate_cache_key(full_url, params)
            cached_value = await self._get_from_cache(cache_key)
            if cached_value:
                return cached_value

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

                            # Cache successful response
                            if use_cache and self.enable_cache:
                                await self._set_in_cache(cache_key, text)

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
