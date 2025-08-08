import asyncio
from curl_cffi import CurlError
from loguru import logger
from datetime import datetime, timedelta

from data.settings import Settings
from utils.browser import Browser
from utils.db_api.models import Wallet
from utils.db_api.wallet_api import update_faucet_time


class FaucetError(Exception):
    pass


class CaptchaUnsolvableError(FaucetError):
    pass


class RateLimitError(FaucetError):
    pass


class Faucet:
    def __init__(self, wallet: Wallet):
        self.browser = Browser(wallet=wallet)
        self.user = wallet
        self.api_key = Settings().solvecaptcha_api_key
        self.site_key = "5b86452e-488a-4f62-bd32-a332445e2f51"
        self.base_url = "https://faucet-go-production.up.railway.app/api/claim"
        self.captcha_url = "https://api.solvecaptcha.com"
        self.page_url = "https://faucet.campnetwork.xyz/"
        self.headers = {
            "User-Agent": f"{Settings().actual_ua}",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": self.page_url,
            "Content-Type": "application/json",
            "Origin": "https://faucet.campnetwork.xyz",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
            "Priority": "u=4",
        }

    async def solve_captcha(self) -> str:
        """Solve hCaptcha using solvecaptcha service."""
        params = {
            "key": self.api_key,
            "method": "hcaptcha",
            "sitekey": self.site_key,
            "pageurl": self.page_url,
            "json": 1,
        }
        if self.user.proxy:
            params["proxy"] = self.user.proxy.split("//")[-1]
            params["proxytype"] = "HTTP"

        try:
            # Submit captcha solving request
            response = await self.browser.get(url=f"{self.captcha_url}/in.php", params=params)
            logger.debug("Send submit captcha")
            if response.status_code != 200:
                logger.debug("status code not 200")
                raise FaucetError(
                    f"Captcha submission failed: HTTP {response.status_code}"
                )
            data = response.json()
            if data.get("status") != 1:
                raise FaucetError(
                    f"Captcha submission error: {data.get('request')}"
                )
            captcha_id = data.get("request")
            logger.debug(
                f"{self.user} success submit capthca solving request {captcha_id}"
            )

            # Poll for captcha solution
            for _ in range(45):  # Max 3 minutes wait (30 * 6 seconds)
                await asyncio.sleep(6)
                params={
                    "key": self.api_key,
                    "action": "get",
                    "id": captcha_id,
                    "json": 1,
                }
                logger.debug(params)
                response = await self.browser.get(url=f"{self.captcha_url}/res.php",params=params)
                logger.debug("success sumbit solution")
                if response.status_code != 200:
                    logger.debug("status code not 200")
                    raise FaucetError(
                        f"Captcha polling failed: HTTP {response.status_code}"
                    )
                result = response.json()
                logger.debug(result)
                if result.get("status") == 1:
                    return result.get("request")

                if result.get("request") != "CAPCHA_NOT_READY":
                    if result.get("request") == "ERROR_CAPTCHA_UNSOLVABLE":
                        raise CaptchaUnsolvableError(
                            f"{self.user} Captcha unsolvable error"
                        )
                    raise FaucetError(
                        f"Captcha solving failed: {result.get('request')}"
                    )
            raise FaucetError("Captcha solving timeout")
        except CurlError as e:
            raise FaucetError(f"Network error during captcha solving: {str(e)}")

    async def check_faucet_time(self) -> bool:
        if not self.user.last_faucet_claim:
            return True
        elif datetime.now() >= self.user.last_faucet_claim + timedelta(hours=24):
            return True
        else:
            logger.warning(f"{self.user} already claim faucet last 24 hours")
            return False

    async def claim_tokens(self) -> dict:
        """Claim tokens from faucet using solved captcha."""
        try:
            logger.info(f"{self.user} start faucet claim")
            captcha_response = await self.solve_captcha()
            logger.debug(f"{self.user} success get captcha token {captcha_response}")
            self.headers["h-captcha-response"] = captcha_response
            json_data = {"address": self.user.address}

            response = await self.browser.post(url=self.base_url, headers=self.headers, json=json_data)
            if response.status_code != 200:
                logger.debug(
                    f"{self.user} request failed {response.status_code} {response.text}"
                )
                if response.status_code == 429:
                    update_faucet_time(private_key=self.user.private_key, new_time=datetime.now())
                    raise RateLimitError(
                        f"{self.user} Rate limit exceeded: Tokens already claimed from this IP in last 24 hours"
                    )
                raise FaucetError(
                    f"{self.user} Claim request failed: HTTP {response.status_code} {response.text}"
                )
            result = response.json()
            if "error" in result:
                raise FaucetError(
                    f"{self.user} Faucet error: {result['error']}"
                )
            logger.success(f"{self.user} success faucet claim")
            return result

        except CurlError as e:
            raise FaucetError(f"Network error during claim: {str(e)}")

    async def handle_faucet(self):
        if not await self.check_faucet_time():
            return False

        max_retry = Settings().resources_max_failures
        for _ in range(max_retry):
            try:
                await self.claim_tokens()
                return True
            except FaucetError:
                continue
        return False

        
