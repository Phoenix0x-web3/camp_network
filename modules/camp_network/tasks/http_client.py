from curl_cffi import CurlError
import asyncio
import random
import json
from typing import Dict, Tuple, Union, Optional
from loguru import logger

from data.settings import Settings
from utils.db_api.wallet_api import get_wallet_by_private_key
from utils.db_api.models import Wallet
from utils.browser import Browser
from .captcha_handler import CloudflareHandler


class BaseHttpClient:
    """Base HTTP client for making requests"""

    def __init__(self, user: Wallet):
        """
        Initialize the base HTTP client

        Args:
            user: User with private key and proxy
        """
        self.user = user
        self.browser = Browser(user)
        self.cookies = {}
        # Proxy error counter
        self.proxy_errors = 0
        # Captcha error counter
        self.captcha_errors = 0
        # Settings for automatic resource error handling
        self.settings = Settings()
        self.max_proxy_errors = self.settings.resources_max_failures
        # Last captcha solve time
        self.last_captcha_time = None
        # Captcha lifetime (20 minutes)
        self.captcha_lifetime = 20 * 60

    def _is_captcha_expired(self) -> bool:
        """
        Check if captcha has expired

        Returns:
            True if captcha has expired or was not solved
        """
        import time

        if not self.last_captcha_time:
            return True

        return (time.time() - self.last_captcha_time) > self.captcha_lifetime

    def _update_captcha_time(self):
        """Update the last captcha solve time"""
        import time

        self.last_captcha_time = time.time()

    async def handle_captcha_if_needed(self, url: str, response_text: str) -> str | bool:
        """
        Check if captcha is required and solve it if needed

        Args:
            url: Request URL
            response_text: Response text

        Returns:
            True if captcha was successfully solved
        """
        logger.info(f"{self.user} detected Cloudflare captcha, starting to solve")

        # Solve captcha
        cloudflare_handler = CloudflareHandler(wallet=self.user)
        success = await cloudflare_handler.handle_cloudflare_protection(
            html=response_text
        )

        if success:
            # Update last captcha solve time
            self._update_captcha_time()
            return success
        else:
            return False

    async def get_headers(self, additional_headers: Optional[Dict] = None) -> Dict:
        """
        Create base headers for requests

        Args:
            additional_headers: Additional headers

        Returns:
            Formatted headers
        """
        base_headers = {
            "User-Agent": self.settings.actual_ua,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Referer": "https://loyalty.campnetwork.xyz/",
            "DNT": "1",
            "Sec-GPC": "1",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Priority": "u=4",
        }

        if additional_headers:
            base_headers.update(additional_headers)

        return base_headers

    async def request(
        self,
        url: str,
        method: str,
        data: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: int = 30,
        retries: int = 5,
        extra_cookies: bool = False,
        allow_redirects: bool = True,
        check_cloudflare: bool = True,
        quest_id: str | None = None,
    ) -> Tuple[bool, Union[Dict, str]]:
        """
        Perform HTTP request with automatic captcha and proxy error handling

        Args:
            url: Request URL
            method: Request method (GET, POST, etc.)
            data: Form data
            json_data: JSON data
            params: URL parameters
            headers: Additional headers
            timeout: Request timeout in seconds
            retries: Number of retry attempts
            extra_cookies: Use additional cookies
            allow_redirects: Follow redirects
            check_cloudflare: Check and handle Cloudflare protection
            quest_id: Quest identifier for cookies

        Returns:
            (bool, data): Success status and response data
        """
        base_headers = await self.get_headers(headers)

        # Set up request parameters
        request_kwargs = {
            "url": url,
            "headers": base_headers,
            "cookies": self.cookies,
            "timeout": timeout,
            "allow_redirects": allow_redirects,
        }
        if quest_id:
            cookie_str = "rule-" + quest_id
            self.cookies[cookie_str] = "true"
        if not extra_cookies:
            self.cookies["accountLinkData"] = ""
        if not extra_cookies and self.cookies.get("__cf_bm"):
            self.cookies.pop("__cf_bm")
        # Add optional parameters
        if json_data is not None:
            request_kwargs["json"] = json_data
        if data is not None:
            request_kwargs["data"] = data
        if params is not None:
            request_kwargs["params"] = params

        # Perform request with retries
        for attempt in range(retries):
            try:
                logger.debug(request_kwargs)
                method_func = getattr(self.browser, method.lower())
                resp = await method_func(**request_kwargs)

                # Save cookies from response
                if resp.cookies:
                    for name, cookie in resp.cookies.items():
                        self.cookies[name] = cookie

                if 300 <= resp.status_code < 400 and not allow_redirects:
                    headers_dict = dict(resp.headers)
                    return False, headers_dict

                # Successful response
                if resp.status_code == 200 or resp.status_code == 202:
                    # Reset proxy error counter on successful request
                    self.proxy_errors = 0
                    self.captcha_errors = 0
                    try:
                        json_resp = resp.json()
                        return True, json_resp
                    except Exception:
                        return True, resp.text

                # Get response text for analysis
                response_text = resp.text

                # Check for Cloudflare protection in response
                if check_cloudflare and ("Just a moment" in response_text):
                    logger.warning(
                        f"{self.user} detected Cloudflare protection, attempting to solve captcha..."
                    )

                    # Solve captcha
                    cf_clearance = await self.handle_captcha_if_needed(
                        url, response_text
                    )

                    if cf_clearance:
                        self.cookies["cf_clearance"] = cf_clearance
                        continue
                    else:
                        self.captcha_errors += 1
                        if self.captcha_errors >= 3:
                            logger.error(
                                f"{self.user} failed to solve captcha after {self.captcha_errors} attempts"
                            )
                            return False, "CAPTCHA_FAILED"

                        # Pause before next attempt
                        await asyncio.sleep(2**attempt)
                        continue

                # Handle errors
                if 400 <= resp.status_code < 500:
                    logger.warning(
                        f"{self.user} received status {resp.status_code} for request {url}"
                    )

                    # Check for authorization issues
                    if resp.status_code == 401 or resp.status_code == 403:
                        if "!DOCTYPE" not in response_text:
                            logger.error(
                                f"{self.user} authorization error: {response_text}"
                            )
                        return False, response_text

                    # Check for rate limiting
                    if resp.status_code == 429:
                        logger.warning(f"{self.user} rate limit exceeded (429)")

                        # If not last attempt, wait and retry
                        if attempt < retries - 1:
                            wait_time = random.uniform(10, 30)  # 10-30 seconds
                            logger.info(
                                f"{self.user} waiting {int(wait_time)} seconds before next attempt"
                            )
                            await asyncio.sleep(wait_time)
                            continue

                        # Parse response for possible error JSON
                        try:
                            error_json = json.loads(response_text)
                            return False, error_json
                        except Exception:
                            return False, "RATE_LIMIT"

                    # Parse response for possible error JSON
                    try:
                        error_json = json.loads(response_text)
                        return False, error_json
                    except Exception:
                        return False, response_text

                elif 500 <= resp.status_code < 600:
                    logger.warning(
                        f"{self.user} received status {resp.status_code}, retry attempt {attempt + 1}/{retries}"
                    )
                    await asyncio.sleep(2**attempt)  # Exponential backoff
                    continue

                return False, response_text

            except CurlError as e:
                logger.warning(
                    f"{self.user} connection error during request {url}: {str(e)}"
                )

                # Increment proxy error counter
                if (
                    "proxy" in str(e).lower()
                    or "connection" in str(e).lower()
                    or "connect" in str(e).lower()
                ):
                    self.proxy_errors += 1

                    # If proxy error limit exceeded, mark proxy as bad
                    if self.proxy_errors >= self.max_proxy_errors:
                        logger.warning(
                            f"{self.user} proxy error limit exceeded ({self.proxy_errors}/{self.max_proxy_errors}), marking as BAD"
                        )
                        from .resource_manager import ResourceManager

                        resource_manager = ResourceManager()
                        await resource_manager.mark_proxy_as_bad(self.user.private_key)

                        # If auto-replace is enabled, try to replace proxy
                        if self.settings.resources_auto_replace:
                            success, message = await resource_manager.replace_proxy(
                                self.user.private_key
                            )
                            if success:
                                logger.info(
                                    f"{self.user} proxy automatically replaced: {message}"
                                )
                                # Update proxy for current client
                                updated_user = get_wallet_by_private_key(private_key=self.user.private_key)
                                if updated_user:
                                    self.user.proxy = updated_user.proxy
                                    # Reset error counter
                                    self.proxy_errors = 0
                                    # Update browser with new proxy
                                    self.browser = Browser(self.user)
                            else:
                                logger.error(
                                    f"{self.user} failed to replace proxy: {message}"
                                )

                await asyncio.sleep(2**attempt)  # Exponential backoff
                continue

            except Exception as e:
                logger.error(
                    f"{self.user} unexpected error during request {url}: {str(e)}"
                )
                return False, str(e)
