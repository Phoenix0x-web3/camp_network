import asyncio
from web3.types import TxParams
from loguru import logger

from libs.eth_async.client import Client
from libs.eth_async.data.models import Networks
from data.models import Contracts
from utils.db_api.models import Wallet
from utils.browser import Browser
from utils.retry import async_retry
from utils.imap import Mail, MailTimedOut
from libs.base import Base


class Awana(Base):
    def __init__(self, wallet: Wallet) -> None:
        super().__init__(wallet=wallet, client=Client(private_key=wallet.private_key, network=Networks.Camp))
        self.__module_name__ = "Awana"  
        self.browser = Browser(wallet=wallet)
        self.session_headers = {
            "Origin": "https://tech.awana.world",
            "Referer": "https://tech.awana.world/",
        }
        self.mail_waiter = Mail(mail_data=wallet.email_data) if wallet.email_data else None
        self.quest_info = {}

    async def run(self):

        if not self.mail_waiter or not self.mail_waiter.authed:
            logger.error(f"{self.wallet} Invalid or missing email data")
            return False

        if not await self.awana_request_mail(self.mail_waiter.mail_login):
            logger.error(f"{self.wallet} Failed to request verification code")
            return False
        logger.debug(f"{self.wallet} Successfully requested verification code")

        verify_code = await self.get_verification_code()
        if not verify_code:
            logger.error(f"{self.wallet} Failed to get verification code")
            return False
        logger.debug(f"{self.wallet} Successfully got verification code: {verify_code}")

        login_resp = await self.awana_login_mail(login=self.mail_waiter.mail_login, code=verify_code)
        if not login_resp:
            logger.error(f"{self.wallet} Failed to login for Awana task")
            return False
        self.session_headers["Webtoken"] = login_resp["token"]
        logger.debug(f"{self.wallet} Successfully logged in with token: {login_resp['token'][:10]}...")

        self.quest_info = await self.awana_get_quest_info()
        if not self.quest_info:
            logger.error(f"{self.wallet} Failed to get quest info")
            return False
        logger.debug(f"{self.wallet} Successfully got quest info")

        if not self.quest_info.get("account"):
            if not await self.awana_connect_wallet():
                logger.error(f"{self.wallet} Failed to connect wallet")
                return False
            logger.debug(f"{self.wallet} Successfully connected wallet")

        return await self.awana_request_mint()

    @async_retry()
    async def awana_request_mail(self, login: str):
        response = await self.browser.post(
            url='https://tech.awana.world/apis/user/sendWeb',
            json={
                "email": login,
                "invitationCode": ""
            },
            headers=self.session_headers
        )
        data = response.json()

        logger.debug(data)
        if data.get("msg") == "Please send it later again":
            logger.warning(f"{self.wallet} email doesn't support")
            return False
        if data.get("msg") != "SUCCESS" or not data.get("data"):
            raise Exception(f"Unexpected response: {data}")
        return data["data"]

    @async_retry()
    async def awana_login_mail(self, login: str, code: str):
        response = await self.browser.post(
            url='https://tech.awana.world/apis/user/loginWeb',
            json={
                "email": login,
                "code": code,
                "invitationCode": ""
            },
            headers=self.session_headers
        )
        data = response.json()
        logger.debug(f"{self.wallet} Login response: {data}")
        if data.get("msg") != "SUCCESS" or not data.get("data"):
            raise Exception(f"Unexpected response: {data}")
        return data["data"]

    async def get_verification_code(self):
        for attempt in range(2):
            try:
                mail_body = await self.mail_waiter.find_mail(
                    msg_from=["no.reply@awana.world", "noreply.2@awana.world", "noreply@awana.world", 
                              "no_reply@awana.world"],
                    part_subject="Your verification code is"
                )
                verify_code = mail_body.find("div", class_="verification-code").text
                return verify_code
            except MailTimedOut:
                logger.error(f"{self.wallet} Waiting mail timed out, attempt {attempt + 1}/2")
                if attempt == 0:
                    await self.awana_request_mail(self.mail_waiter.mail_login)
                else:
                    return None
        return None

    @async_retry()
    async def awana_get_quest_info(self):
        response = await self.browser.get(
            url='https://tech.awana.world/apis/user/getQuestInfo',
            headers=self.session_headers
        )
        data = response.json()
        logger.debug(f"{self.wallet} Quest info response: {data}")
        if data.get("msg") != "SUCCESS" or not data.get("data"):
            raise Exception(f"Unexpected response: {data}")
        return data["data"]

    @async_retry()
    async def awana_connect_wallet(self):
        response = await self.browser.post(
            url='https://tech.awana.world/apis/user/connectAccount',
            json={
                "address": self.client.account.address,
                "amount": "0.5",
                "type": "1"
            },
            headers=self.session_headers
        )
        data = response.json()
        logger.debug(f"{self.wallet} Connect wallet response: {data}")
        if data.get("msg") != "SUCCESS":
            raise Exception(f"Unexpected response: {data}")
        return True

    @async_retry()
    async def awana_request_mint(self):
        response = await self.browser.post(
            url='https://tech.awana.world/apis/user/mint',
            headers=self.session_headers
        )
        data = response.json()
        logger.debug(f"{self.wallet} Mint response: {data}")
        if data.get("msg") != "SUCCESS":
            raise Exception(f"Unexpected response: {data}")

        logger.success(f"{self.wallet} Successfully minted Awana NFT")
        return True
