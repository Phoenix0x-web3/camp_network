import asyncio
import random
from web3.types import TxParams
from loguru import logger

from libs.eth_async.client import Client
from libs.eth_async.data.models import Networks
from data.settings import Settings
from libs.eth_async.data.models import RawContract
from data.models import Contracts
from utils.db_api.models import Wallet
from utils.browser import Browser
from utils.retry import async_retry
from utils.imap import Mail
from libs.base import Base


class TokenTails(Base):
    def __init__(self, wallet: Wallet) -> None:
        """Initialize TokenTails task client"""
        super().__init__(wallet=wallet, client=Client(private_key=wallet.private_key, network=Networks.Camp))
        self.__module_name__ = "TokenTails"  # For async_retry logging
        self.browser = Browser(wallet=wallet)
        self.session_headers = {
            "Origin": "https://tokentails.com",
            "Referer": "https://tokentails.com/",
            "X-Client-Version": "Chrome/JsCore/11.8.0/FirebaseCore-web",
            "X-Firebase-Client": "eyJ2ZXJzaW9uIjoyLCJoZWFydGJlYXRzIjpbeyJhZ2VudCI6ImZpcmUtY29yZS8wLjEzLjAgZmlyZS1jb3JlLWVzbTIwMTcvMC4xMy4wIGZpcmUtanMvIGZpcmUtanMtYWxsLWFwcC8xMS44LjAgZmlyZS1hdXRoLzEuMTAuNSBmaXJlLWF1dGgtZXNtMjAxNy8xLjEwLjUiLCJkYXRlcyI6WyIyMDI1LTA2LTExIl19XX0",
            "X-Firebase-Gmpid": "1:158850509760:web:446ea8a11bdddeb616f625",
        }
        self.mail_waiter = Mail(mail_data=wallet.email_data) if wallet.email_data else None
        self.settings = Settings()

    async def run(self):
        """Run the TokenTails task workflow"""
        if not self.mail_waiter:
            logger.error(f"{self.wallet} Invalid or missing email data")
            return False

        login_resp = await self.tokentails_login_mail(login=self.mail_waiter.mail_login, password=self.mail_waiter.mail_pass)
        if not login_resp:
            logger.error(f"{self.wallet} Failed to login or register")
            return False
        logger.debug(f"{self.wallet} Successfully logged in or registered")

        # Get access token
        token_resp = await self.tokentails_get_token(refresh_token=login_resp["refreshToken"])
        if not token_resp:
            logger.error(f"{self.wallet} Failed to get access token")
            return False
        self.session_headers["Accesstoken"] = "fb" + token_resp["access_token"]
        logger.debug(f"{self.wallet} Successfully got access token: {token_resp['access_token'][:10]}...")


        # Get profile
        profile_info = await self.tokentails_get_profile()
        if not profile_info:
            logger.error(f"{self.wallet} Failed to get profile")
            return False
        logger.debug(f"{self.wallet} Successfully got profile: {profile_info.get('catpoints')} catpoints")

        for i in Contracts.MYSTERY_BOXES_TOKEN_TAILS:
            success = await self.mint(i)
            if success:
                random_sleep = random.randint(
                    self.settings.random_pause_between_actions_min,
                    self.settings.random_pause_between_actions_max
                )
                logger.info(f"{self.wallet} Sleeping {random_sleep:.2f} seconds after mint {i.title}")
                await asyncio.sleep(random_sleep)

        logger.info(f"{self.wallet} Completed TokenTails task")
        return True

    @async_retry()
    async def tokentails_login_mail(self, login: str, password: str):
        """Login to TokenTails with email and password"""
        response = await self.browser.post(
            url='https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword',
            params={"key": "AIzaSyCfitm6sU-lOunY3JpGdn8D4Ng7Dz5m3yk"},
            json={
                "returnSecureToken": True,
                "email": login,
                "password": password,
                "clientType": "CLIENT_TYPE_WEB"
            },
            headers=self.session_headers
        )
        data = response.json()
        logger.debug(f"{self.wallet} Login response: {data}")
        if data.get("idToken"):
            return data
        elif data.get("error") and data["error"].get("message") == "EMAIL_NOT_FOUND":
            return await self.tokentails_register_mail(login=login, password=password)
        raise Exception(f"Unexpected response: {data}")

    @async_retry()
    async def tokentails_register_mail(self, login: str, password: str):
        """Register a new TokenTails account"""
        response = await self.browser.post(
            url='https://identitytoolkit.googleapis.com/v1/accounts:signUp',
            params={"key": "AIzaSyCfitm6sU-lOunY3JpGdn8D4Ng7Dz5m3yk"},
            json={
                "returnSecureToken": True,
                "email": login,
                "password": password,
                "clientType": "CLIENT_TYPE_WEB"
            },
            headers=self.session_headers
        )
        data = response.json()
        logger.debug(f"{self.wallet} Register response: {data}")
        if data.get("idToken"):
            return data
        raise Exception(f"Unexpected response: {data}")

    @async_retry()
    async def tokentails_get_token(self, refresh_token: str):
        """Get access token using refresh token"""
        response = await self.browser.post(
            url='https://securetoken.googleapis.com/v1/token',
            params={"key": "AIzaSyCfitm6sU-lOunY3JpGdn8D4Ng7Dz5m3yk"},
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token
            },
            headers={"Content-Type": "application/x-www-form-urlencoded", **self.session_headers}
        )
        data = response.json()
        logger.debug(f"{self.wallet} Get token response: {data}")
        if data.get("access_token"):
            return data
        raise Exception(f"Unexpected response: {data}")

    @async_retry()
    async def tokentails_get_profile(self):
        """Get user profile"""
        response = await self.browser.get(
            url='https://api.tokentails.com/user/profile',
            headers=self.session_headers
        )
        data = response.json()
        logger.debug(f"{self.wallet} Profile response: {data}")
        if data.get("catpoints") is not None:
            return data
        raise Exception(f"Unexpected response: {data}")

    @async_retry()
    async def tokentails_use_random_ref(self, ref_code: str):
        """Apply random referral code"""
        response = await self.browser.get(
            url=f'https://api.tokentails.com/user/catbassadors/referralw/{ref_code}',
            headers=self.session_headers
        )
        data = response.json()
        logger.debug(f"{self.wallet} Referral response: {data}")
        if data == {} or data.get("message") == "You can not add same referral twice":
            return True
        raise Exception(f"Unexpected response: {data}")

    async def mint(self, contract: RawContract):
        """Mint a mystery box NFT"""
        index=int(contract.title[-1])
        contract = await self.client.contracts.get(contract_address=contract)
        balance = await self.check_nft_balance(contract=contract)
        if balance > 0:
            logger.info(f"{self.wallet} Already owns mystery box {index} NFT")
            return False

        tx_label = f'mint mystery box {index} NFT'
        data = contract.encode_abi("safeMint", args=(self.client.account.address,))
        tx_params = TxParams(
            to=contract.address,
            data=data
        )
        result = await self.execute_transaction(
            tx_params=tx_params,
            activity_type=tx_label,
            retry_count=3
        )

        if result.success:
            logger.success(f"{self.wallet} Successfully minted mystery box {index} NFT")
            if not await self.tokentails_complete_quest(api_path=contract.title):
                logger.error(f"{self.wallet} Failed to complete quest for mystery box {index}")
            else:
                logger.debug(f"{self.wallet} Successfully completed quest for mystery box {index}")
                return True
            return True
        else:
            logger.error(f"{self.wallet} Mint failed for mystery box {index}: {result.error_message}")
            return False

    @async_retry()
    async def tokentails_complete_quest(self, api_path: str):
        """Complete quest for mystery box"""
        response = await self.browser.get(
            url=f'https://api.tokentails.com/quest/contest/{api_path}',
            headers=self.session_headers
        )
        data = response.json()
        logger.debug(f"{self.wallet} Quest completion response: {data}")
        if data.get("success") is True:
            return True
        raise Exception(f"Unexpected response: {data}")
