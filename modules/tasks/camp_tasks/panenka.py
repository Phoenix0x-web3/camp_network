import asyncio
import json
from loguru import logger
from faker import Faker

from libs.eth_async.client import Client
from libs.eth_async.data.models import Networks
from data.settings import Settings
from utils.db_api.models import Wallet
from utils.browser import Browser
from utils.retry import async_retry
from utils.imap import Mail, MailTimedOut
from utils.encryption import format_password
from libs.base import Base
from modules.tasks.captcha_handler import CloudflareHandler


class Panenka(Base):
    def __init__(self, wallet: Wallet) -> None:
        """Initialize Panenka task client"""
        super().__init__(wallet=wallet, client=Client(private_key=wallet.private_key, network=Networks.Camp))
        self.__module_name__ = "Panenka" 
        self.browser = Browser(wallet=wallet)
        self.session_headers = {
            "Origin": "https://panenkafc.gg",
            "Referer": "https://panenkafc.gg/",
        }
        self.mail_waiter = Mail(mail_data=wallet.email_data) if wallet.email_data else None
        self.faker = Faker()
        self.captcha_token = None

    async def run(self):
        if not self.mail_waiter:
            logger.error(f"{self.wallet} Invalid or missing email data")
            return False

        password = format_password(self.mail_waiter.mail_pass)

        login_result = await self.panenka_login(login=self.mail_waiter.mail_login, password=password)
        if login_result:
            logger.info(f"{self.wallet} Successfully logged in to Panenka")
            await self.panenka_connect_wallet()
            logger.info(f"{self.wallet} Successfully connect wallet in to Panenka")
            return True

        already_registered = await self.panenka_register(login=self.mail_waiter.mail_login, password=password)
        if already_registered:
            logger.info(f"{self.wallet} User already registered, retrying login")
            login_result = await self.panenka_login(login=self.mail_waiter.mail_login, password=password)
            if login_result:
                logger.info(f"{self.wallet} Successfully logged in to Panenka after registration")
                await self.panenka_connect_wallet()
                logger.info(f"{self.wallet} Successfully connect wallet in to Panenka")
                return True
            logger.error(f"{self.wallet} Failed to login after registration")
            return False

        if self.mail_waiter.authed:
            if not await self.panenka_request_mail_code(self.mail_waiter.mail_login):
                logger.error(f"{self.wallet} Failed to request verification code")
                return False
            logger.debug(f"{self.wallet} Successfully requested verification code")

            verify_code = await self.get_verification_code()
            if not verify_code:
                logger.error(f"{self.wallet} Failed to get verification code")
                return False
            logger.debug(f"{self.wallet} Successfully got verification code: {verify_code}")

            if not await self.panenka_verify_mail(login=self.mail_waiter.mail_login, code=verify_code):
                logger.error(f"{self.wallet} Failed to verify email")
                return False
            logger.info(f"{self.wallet} Successfully verified and registered Panenka account")

        await self.panenka_connect_wallet()
        logger.info(f"{self.wallet} Successfully connect wallet in to Panenka")
        return True

    @async_retry()
    async def panenka_login(self, login: str, password: str):
        """Login to Panenka with email and password"""
        cloudflare = CloudflareHandler(wallet=self.wallet)
        token = await cloudflare.panenka_handle()
        if token:
            self.captcha_token = token 

        response = await self.browser.post(
            url='https://prod-api.panenkafc.gg/api/v1/auth/login',
            json={
                "email": login,
                "password": password,
                "turnstileToken": self.captcha_token	
            },
            headers=self.session_headers
        )
        data = response.json()
        logger.debug(f"{self.wallet} Login response: {data}")
        if data.get("success"):
            self.session_headers["Authorization"] = "Bearer " + data["accessToken"]
            return True
        elif data.get("error") == "Invalid email or password":
            return False
        raise Exception(f"Unexpected response: {data}")

    @async_retry()
    async def panenka_register(self, login: str, password: str):
        """Register a new Panenka account"""
        cloudflare = CloudflareHandler(wallet=self.wallet)
        token = await cloudflare.panenka_handle()
        if token:
            self.captcha_token = token 
        response = await self.browser.post(
            url='https://prod-api.panenkafc.gg/api/v1/auth',
            json={
                "firstName": self.faker.first_name(),
                "lastName": self.faker.last_name(),
                "email": login,
                "password": password,
                "referralCode": None,
                "turnstileToken": self.captcha_token	
            },
            headers=self.session_headers
        )
        data = response.json()
        logger.debug(f"{self.wallet} Register response: {data}")
        if data.get("success"):
            return False
        elif data.get("error") == "User already exists":
            return True
        raise Exception(f"Unexpected response: {data}")

    @async_retry()
    async def panenka_connect_wallet(self,):
        response = await self.browser.post(
            url='https://prod-api.panenkafc.gg/api/v1/wallets/para',
            json={
                'address': self.wallet.address
            },
            headers=self.session_headers
        )
        data = response.json()
        logger.debug(f"{self.wallet} Connect response: {data}")
        if data.get("success"):
            return True
        elif data.get("error") == "This para address already exists":
            return False
        raise Exception(f"Unexpected response: {data}")

    @async_retry()
    async def panenka_request_mail_code(self, login: str):
        """Request verification code for email"""
        response = await self.browser.post(
            url='https://prod-api.panenkafc.gg/api/v1/otp/generate',
            json={
                "purpose": "email_verification",
                "email": login,
            },
            headers=self.session_headers
        )
        data = response.json()
        logger.debug(f"{self.wallet} Request mail code response: {data}")
        if data.get("success"):
            return True
        raise Exception(f"Unexpected response: {data}")

    @async_retry()
    async def panenka_verify_mail(self, login: str, code: str):
        """Verify email with code"""
        response = await self.browser.post(
            url='https://prod-api.panenkafc.gg/api/v1/otp/validate',
            json={
                "otp": code,
                "purpose": "email_verification",
                "email": login
            },
            headers=self.session_headers
        )
        data = response.json()
        logger.debug(f"{self.wallet} Verify mail response: {data}")
        if data.get("success"):
            self.session_headers["Authorization"] = "Bearer " + data["accessToken"]
            return True
        raise Exception(f"Unexpected response: {data}")

    async def get_verification_code(self):
        """Get verification code from email"""
        if not self.mail_waiter:
            return
        for attempt in range(2):
            try:
                mail_body = await self.mail_waiter.find_mail(
                    msg_from=["welcome@panenkafc.gg"],
                    part_subject="Your Panenka FC Account Verification"
                )
                verify_code = mail_body.find("span").text
                return verify_code
            except MailTimedOut:
                logger.error(f"{self.wallet} Waiting mail timed out, attempt {attempt + 1}/2")
                if attempt == 0:
                    await self.panenka_request_mail_code(self.mail_waiter.mail_login)
                else:
                    return None
        return None
