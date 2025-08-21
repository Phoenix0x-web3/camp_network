import asyncio
from time import time
from loguru import logger
from bs4 import BeautifulSoup
import re
from json import loads
from eth_account.messages import encode_defunct

from libs.eth_async.client import Client
from libs.eth_async.data.models import Networks,TokenAmount
from data.settings import Settings
from data.models import Contracts
from utils.db_api.models import Wallet
from utils.browser import Browser
from utils.retry import async_retry
from modules.tasks.captcha_handler import CloudflareHandler
from libs.base import Base


class Scoreplay(Base):
    def __init__(self, wallet: Wallet) -> None:
        """Initialize Scoreplay task client"""
        super().__init__(wallet=wallet, client=Client(private_key=wallet.private_key, network=Networks.Camp))
        self.__module_name__ = "Scoreplay" 
        self.browser = Browser(wallet=wallet)
        self.session_headers = {
            "Origin": "https://app.scoreplay.xyz",
            "Referer": "https://app.scoreplay.xyz/",
        }
        self.session_cookies = {}
        self.settings = Settings()
        self.user_id = None
        self.actions = None

    async def run(self):
        """Run the Scoreplay task workflow"""
        if TokenAmount(amount=await self.client.wallet.balance(token=Contracts.TSCORE)).Ether >= 70:
            logger.info(f"{self.wallet} account already have 70 TSCORE")
            return False
        if not await self.authorize():
            logger.error(f"{self.wallet} Failed to authorize")
            return False
        logger.debug(f"{self.wallet} Successfully authorized with user_id: {self.user_id}")

        old_balance = await self.client.wallet.balance(token=Contracts.TSCORE)
        tokens_resp = await self.scoreplay_request_tokens()
        if tokens_resp:
            success = await self.wait_balance(
                token=Contracts.TSCORE,
                old_balance=old_balance,
                timeout=60
            )
            if not success:
                logger.error(f"{self.wallet} Balance did not update after reclaim")
                return False

    async def wait_balance(self, token, old_balance, timeout = 60):
        time_now = time()
        while time_now + timeout > time():
            balance = await self.client.wallet.balance(token=token)
            if old_balance.Wei < balance.Wei:
                logger.success(f"{self.wallet} success claim TScore")
                return True
            await asyncio.sleep(5)
        return False


    async def authorize(self):
        """Authorize with Ethereum signature"""
        sign_data = await self.scoreplay_get_sign_data()
        if not sign_data:
            return False

        sign_text = (
            f"{sign_data['domain']} wants you to sign in with your Ethereum account:\n"
            f"{self.client.account.address}\n\n"
            f"{sign_data['statement']}\n\n"
            f"URI: {sign_data['uri']}\n"
            f"Version: {sign_data['version']}\n"
            f"Nonce: {sign_data['nonce']}\n"
            f"Issued At: {sign_data['issued_at']}\n"
            f"Expiration Time: {sign_data['expiration_time']}\n"
            f"Not Before: {sign_data['invalid_before']}"
        )
        message_bytes = encode_defunct(text=sign_text)
        signature = self.client.account.sign_message(signable_message=message_bytes)
        if not signature:
            logger.error(f"{self.wallet} Failed to sign message")
            return False

        self.user_id = await self.scoreplay_login(sign_data=sign_data, signature=signature.signature.hex())
        return bool(self.user_id)

    @async_retry()
    async def scoreplay_get_sign_data(self):
        """Get data for signing"""
        if not self.actions:
            await self.get_actual_actions()

        response = await self.browser.post(
            url='https://app.scoreplay.xyz/rewards',
            json=[{"address": self.client.account.address}],
            headers={"Next-Action": self.actions["generatePayload"], **self.session_headers},
            cookies=self.session_cookies
        )
        if "<!DOCTYPE html>" in response.text:
            await self.get_actual_actions(response.text)
            return await self.scoreplay_get_sign_data()

        lines = response.text.splitlines()
        if len(lines) < 2:
            raise Exception(f"Unexpected response: {response.text}")

        data = loads(lines[1].removeprefix("1:"))
        if not isinstance(data, dict) or not data.get("expiration_time"):
            raise Exception(f"Unexpected response: {data}")
        return data

    @async_retry()
    async def scoreplay_login(self, sign_data: dict, signature: str):
        """Login with signature"""
        response = await self.browser.post(
            url='https://app.scoreplay.xyz/rewards',
            json=[{
                "signature": signature,
                "payload": {k: v for k, v in sign_data.items() if v != "$undefined"}
            }, ""],
            headers={"Next-Action": self.actions["doLogin"], **self.session_headers},
            cookies=self.session_cookies
        )
        if "<!DOCTYPE html>" in response.text:
            await self.get_actual_actions(response.text)
            return await self.scoreplay_login(sign_data, signature)

        raw_response = next((line for line in response.text.splitlines() if line.startswith("1:")), None)
        if not response.cookies.get("jwt") or not raw_response:
            raise Exception(f"Unexpected response: {response.text}")

        self.session_cookies["jwt"] = response.cookies.get("jwt")
        data = loads(raw_response.removeprefix("1:"))
        if not isinstance(data, dict) or not data.get("user") or not data["user"].get("id"):
            raise Exception(f"Unexpected response: {response.text}")
        return data["user"]["id"]

    @async_retry()
    async def get_actual_actions(self, index_response: str | None = None):
        """Fetch and update Next.js actions"""
        logger.debug(f"{self.wallet} Updating Scoreplay site build...")
        re_pattern = r'createServerReference\)\("([a-f0-9]+)".*?"([a-zA-Z_][a-zA-Z0-9_]*)"\)'
        actions = {
            action_name: None
            for action_name in ["generatePayload", "doLogin"]
        }

        if not index_response:
            logger.debug(self.session_headers)
            response = await self.browser.get(url="https://app.scoreplay.xyz/rewards", headers=self.session_headers, cookies=self.session_cookies)
            index_response = response.text
            if "Just a moment..." in response.text or "!DOCTYPE" in response.text:
                cloudflare_handler = CloudflareHandler(wallet=self.wallet)
                cf_clearance = await cloudflare_handler.handle_cloudflare_protection(
                    html=response.text,
                    websiteURL="https://app.scoreplay.xyz/rewards",
                    websiteKey="0x4AAAAAAAAjq6WYeRDKmebM",
                )
                if cf_clearance:
                    self.session_cookies["cf_clearance"] = cf_clearance
                    logger.debug(f"{self.wallet} Successfully solved Cloudflare")
                    response = await self.browser.get(url="https://app.scoreplay.xyz/rewards", headers=self.session_headers, cookies=self.session_cookies)
                    index_response = response.text
                else:
                    raise Exception("Can't resolve captcha")
            logger.debug(index_response)

        soup = BeautifulSoup(index_response, "lxml")
        script_paths = [
            script["src"]
            for script in soup.find_all('script')
            if (
                script.get("src") and
                script["src"].startswith("/_next/static/chunks/") and
                not script["src"].startswith("/_next/static/chunks/app")
            )
        ]

        for script_path in script_paths:
            response = await self.browser.get(url=f"https://app.scoreplay.xyz{script_path}", headers=self.session_headers, cookies=self.session_cookies)
            matches = re.findall(re_pattern, response.text)
            for match in matches:
                if match[1] in actions:
                    actions[match[1]] = match[0]

            if all(actions.values()):
                self.actions = actions
                return actions
        raise Exception("Failed to find all Scoreplay Next-Actions")


    @async_retry()
    async def scoreplay_request_tokens(self): 
        """Request tScore tokens"""
        cloudflare = CloudflareHandler(wallet=self.wallet)
        token = await cloudflare.handle_turnstile_captcha(websiteURL="https://app.scoreplay.xyz/api/reclaim", websiteKey="0x4AAAAAABgcc9z2p-IJlyu-")
        headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'cache-control': 'no-cache',
            'content-type': 'text/plain;charset=UTF-8',
            'origin': 'https://app.scoreplay.xyz',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'referer': 'https://app.scoreplay.xyz/rewards',
            'sec-ch-ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
            'sec-ch-ua-arch': '"x86"',
            'sec-ch-ua-bitness': '"64"',
            'sec-ch-ua-full-version': '"139.0.7258.128"',
            'sec-ch-ua-full-version-list': '"Not;A=Brand";v="99.0.0.0", "Google Chrome";v="139.0.7258.128", "Chromium";v="139.0.7258.128"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-model': '""',
            'sec-ch-ua-platform': '"Windows"',
            'sec-ch-ua-platform-version': '"10.0.0"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
        }

        json_data = {"token": f"{token}"}
        logger.debug(json_data)
        response = await self.browser.post(
            url='https://app.scoreplay.xyz/api/reclaim',
            json=json_data,
            headers=headers,
            cookies=self.session_cookies
        )

        data = response.json()
        if data.get("error") == "Internal Server Error":
            raise Exception("Failed to request tokens")
        elif data.get("success") is True:
            return True
        elif data.get("message") == "You have already claimed your daily reward. Please wait." and data.get("timeLeft"):
            return False
        elif data.get("message") == "Too many requests. Try again later.":
            return False
        elif data.get("success") is not True:
            raise Exception(f"Unexpected response: {data}")
        return True
