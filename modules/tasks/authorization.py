import asyncio
import json
import random
from datetime import datetime
from typing import Dict, Optional, Tuple

from eth_account.messages import encode_defunct
from loguru import logger

from data.settings import Settings
from libs.eth_async.client import Client
from utils.db_api.wallet_api import update_ref_code
from utils.imap import Mail

from .http_client import BaseHttpClient
from .resource_manager import ResourceManager


class AuthClient(BaseHttpClient):
    """Client for authentication on CampNetwork"""

    # URLs for authentication
    BASE_URL = "https://loyalty.campnetwork.xyz"
    AUTH_CSRF_URL = f"{BASE_URL}/api/auth/csrf"
    AUTH_CALLBACK_URL = f"{BASE_URL}/api/auth/callback/credentials"
    AUTH_SESSION_URL = f"{BASE_URL}/api/auth/session"
    AUTH_SIGNOUT_URL = f"{BASE_URL}/api/auth/signout"
    USER_INFO_URL = f"{BASE_URL}/api/users"
    DYNAMIC_CONNECT_URL = "https://app.dynamicauth.com/api/v0/sdk/09a766ae-a662-4d96-904a-28d1c9e4b587/connect"
    DYNAMIC_NONCE_URL = "https://app.dynamicauth.com/api/v0/sdk/09a766ae-a662-4d96-904a-28d1c9e4b587/nonce"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = Client(private_key=self.user.private_key, proxy=self.user.proxy, check_proxy=False)
        # Authentication data
        self.csrf_token = None
        self.nonce = None
        self.session_data = None
        self.user_id = None
        self.user_info = None

    async def initial_request(self) -> bool:
        """
        Perform initial request to check for Cloudflare protection

        Returns:
            Success status
        """
        try:
            logger.info(f"{self.user} performing initial request to check Cloudflare protection")

            success, response = await self.request(
                url=f"{self.BASE_URL}",
                method="GET",
                check_cloudflare=True,
            )
            if success:
                logger.success(f"{self.user} initial request successful")
                return True
            else:
                logger.error(f"{self.user} failed to perform initial request")
                return False

        except Exception as e:
            logger.error(f"{self.user} error during initial request: {str(e)}")
            return False

    async def connect_wallet(self) -> bool:
        """
        First stage of authentication - connect wallet via Dynamic Auth

        Returns:
            Success status
        """
        json_data = {
            "address": f"{self.user.address}",
            "chain": "EVM",
            "provider": "browserExtension",
            "walletName": "rabby",
            "authMode": "connect-only",
        }

        headers = await self.get_headers(
            {
                "Content-Type": "application/json",
                "x-dyn-version": "WalletKit/3.9.11",
                "x-dyn-api-version": "API/0.0.586",
                "Origin": "https://loyalty.campnetwork.xyz",
            }
        )

        success, response = await self.request(
            url=self.DYNAMIC_CONNECT_URL,
            method="POST",
            json_data=json_data,
            headers=headers,
        )

        if success:
            logger.info(f"{self.user} successfully connected wallet")
            return True
        else:
            logger.error(f"{self.user} failed to connect wallet: {response}")
            return False

    async def get_nonce(self) -> bool:
        """
        Retrieve nonce for authentication

        Returns:
            Success status
        """
        headers = await self.get_headers(
            {
                "x-dyn-version": "WalletKit/3.9.11",
                "x-dyn-api-version": "API/0.0.586",
            }
        )

        success, response = await self.request(url=self.DYNAMIC_NONCE_URL, method="GET", headers=headers)

        if success and isinstance(response, dict) and "nonce" in response:
            self.nonce = response["nonce"]
            logger.info(f"{self.user} retrieved nonce: {self.nonce[:10]}...")
            return True
        else:
            logger.error(f"{self.user} failed to retrieve nonce: {response}")
            return False

    async def get_csrf_token(self) -> bool | str:
        """
        Retrieve CSRF token with rate limit checking

        Returns:
            Success status or error code string
        """
        headers = await self.get_headers(
            {
                "Content-Type": "application/json",
                "Referer": "https://loyalty.campnetwork.xyz/home",
                "Origin": "https://loyalty.campnetwork.xyz",
                "Sec-Fetch-Site": "same-origin",
            }
        )

        success, response = await self.request(url=self.AUTH_CSRF_URL, method="GET", headers=headers)

        if success and isinstance(response, dict) and "csrfToken" in response:
            self.csrf_token = response["csrfToken"]
            logger.info(f"{self.user} retrieved CSRF token: {self.csrf_token[:10]}...")
            return True
        else:
            # Check for rate limit error
            if isinstance(response, dict) and response.get("message") == "Too many requests, please try again later.":
                logger.warning(f"{self.user} rate limit exceeded while retrieving CSRF token")
                return "RATE_LIMIT"
            else:
                logger.error(f"{self.user} failed to retrieve CSRF token: {response}")
                return False

    async def sign_message(self) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Sign message for authentication

        Returns:
            (message, signature): Message and signature
        """
        if not self.nonce:
            logger.error(f"{self.user} attempting to sign message without nonce")
            return None, None

        try:
            # Current date and time in ISO format
            current_time = datetime.utcnow().isoformat("T") + "Z"

            # Create message for signing
            message = {
                "domain": "loyalty.campnetwork.xyz",
                "address": self.user.address,
                "statement": "Sign in to the app. Powered by Snag Solutions.",
                "uri": "https://loyalty.campnetwork.xyz",
                "version": "1",
                "chainId": 1,
                "nonce": self.nonce,
                "issuedAt": current_time,
            }

            # Create string representation of message in EIP-191 format
            message_str = (
                f"loyalty.campnetwork.xyz wants you to sign in with your Ethereum account:\n"
                f"{message['address']}\n\n"
                f"{message['statement']}\n\n"
                f"URI: {message['uri']}\n"
                f"Version: {message['version']}\n"
                f"Chain ID: {message['chainId']}\n"
                f"Nonce: {message['nonce']}\n"
                f"Issued At: {message['issuedAt']}"
            )

            # Encode message for signing
            message_bytes = encode_defunct(text=message_str)

            # Sign message
            sign = self.client.account.sign_message(message_bytes)
            signature = sign.signature.hex()

            logger.info(f"{self.user} successfully signed message")

            return message, signature

        except Exception as e:
            logger.error(f"{self.user} error signing message: {str(e)}")
            return None, None

    async def authenticate(self):
        """
        Authenticate using signed message

        Returns:
            Success status and response
        """
        if not self.csrf_token or not self.nonce:
            logger.error(f"{self.user} attempting authentication without CSRF token or nonce")
            return False, False

        # Sign message
        message, signature = await self.sign_message()
        if not message or not signature:
            return False, False

        # Form data for request
        form_data = {
            "message": json.dumps(message),
            "accessToken": signature,
            "signature": signature,
            "walletConnectorName": "Rabby",
            "walletAddress": self.user.address,
            "redirect": "false",
            "callbackUrl": "/protected",
            "chainType": "evm",
            "csrfToken": self.csrf_token,
            "json": "true",
        }

        headers = await self.get_headers(
            {
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://loyalty.campnetwork.xyz/home",
                "Origin": "https://loyalty.campnetwork.xyz",
                "Sec-Fetch-Site": "same-origin",
            }
        )

        success, response = await self.request(url=self.AUTH_CALLBACK_URL, method="POST", data=form_data, headers=headers)

        if success:
            # Check for session token in cookies
            if "__Secure-next-auth.session-token" in self.cookies:
                logger.success(f"{self.user} successfully authenticated")
                return True, response

        logger.error(f"{self.user} failed to authenticate: {response}")
        return False, response

    async def get_session_info(self) -> bool:
        """
        Retrieve current session information

        Returns:
            Success status
        """
        if "__Secure-next-auth.session-token" not in self.cookies:
            logger.error(f"{self.user} attempting to get session info without token")
            return False

        headers = await self.get_headers(
            {
                "Content-Type": "application/json",
                "Referer": "https://loyalty.campnetwork.xyz/home",
                "Sec-Fetch-Site": "same-origin",
            }
        )

        success, response = await self.request(url=self.AUTH_SESSION_URL, method="GET", headers=headers)

        if success and isinstance(response, dict) and "user" in response and "id" in response["user"]:
            self.session_data = response
            self.user_id = response["user"]["id"]
            logger.info(f"{self.user} retrieved session info, user ID: {self.user_id}")
            return True
        else:
            logger.error(f"{self.user} failed to retrieve session info: {response}")
            return False

    async def get_user_info(self):
        headers = await self.get_headers(
            {
                "Content-Type": "application/json",
                "Referer": "https://loyalty.campnetwork.xyz/home",
                "Sec-Fetch-Site": "same-origin",
            }
        )
        params = {
            "includeDelegation": "false",
            "walletAddress": f"{self.client.account.address}",
            "websiteId": "32afc5c9-f0fb-4938-9572-775dee0b4a2b",
            "organizationId": "26a1764f-5637-425e-89fa-2f3fb86e758c",
        }

        success, response = await self.request(url=self.USER_INFO_URL, method="GET", headers=headers, params=params)

        if success and isinstance(response, dict) and "userMetadata" in response["data"][0]:
            self.user_info = response["data"][0]
            return True
        else:
            logger.error(f"{self.user} failed to retrieve user info: {response}")
            return False

    async def get_email_info(self):
        if self.user_info:
            email_connect = self.user_info["userMetadata"][0]["emailAddress"]
            email_verifed = self.user_info["userMetadata"][0]["emailVerifiedAt"]
            if email_connect and email_verifed:
                return True
        return False

    async def request_email_code(self, email: str) -> bool:
        """
        Request email verification code

        Args:
            email: Email address to verify

        Returns:
            Success status
        """
        if not self.user_id:
            logger.error(f"{self.user} attempting to request email code without user ID")
            return False

        try:
            url = f"{self.BASE_URL}/api/users/{self.user_id}"
            json_data = {"emailAddress": email}

            headers = await self.get_headers(
                {
                    "Content-Type": "application/json",
                    "Origin": "https://loyalty.campnetwork.xyz",
                }
            )

            success, response = await self.request(
                url=url,
                method="POST",
                json_data=json_data,
                headers=headers,
            )

            if success and isinstance(response, dict) and response.get("success") is True:
                logger.info(f"{self.user} successfully requested email verification code for {email}")
                return True
            else:
                logger.error(f"{self.user} failed to request email code: {response}")
                return False

        except Exception as e:
            logger.error(f"{self.user} error requesting email code: {str(e)}")
            return False

    async def connect_email(self) -> bool:
        """
        Connect and verify email if not already connected

        Returns:
            Success status
        """
        if not self.user_info:
            if not await self.get_user_info():
                return False
        if await self.get_email_info() or not self.user.email_data:
            return False

        try:
            mail_waiter = Mail(mail_data=self.user.email_data)
            if not mail_waiter.authed:
                return False
            email_login = mail_waiter.mail_login

            if not await self.request_email_code(email=email_login):
                return False

            mail_body = await mail_waiter.find_mail(
                msg_from=["Snag Solutions <accounts@snagsolutions.io>", "snagsolutions.io", "accounts@snagsolutions.io"],
                part_subject="Verify email - Climb to the Summit marketplace",
            )

            verify_link = mail_body.find("a")["href"].replace("http://", "https://")
            logger.info(f"{self.user} extracted verification link: {verify_link[:50]}...")

            headers = await self.get_headers(
                {
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Referer": "https://loyalty.campnetwork.xyz/",
                }
            )

            success, response = await self.request(
                url=verify_link,
                method="GET",
                headers=headers,
            )

            if success:
                logger.success(f"{self.user} email {email_login} successfully connected and verified")
                return True
            else:
                logger.error(f"{self.user} failed to verify email: {response}")
                return False

        except Exception as e:
            logger.error(f"{self.user} error connecting email: {str(e)}")
            return False

    async def login(self):
        """
        Complete authentication process with rate limit handling

        Returns:
            Success status and response
        """
        try:
            # Step 1: Initial request and Cloudflare handling
            if not await self.initial_request():
                return False, "None"

            # Step 2: Connect wallet
            if not await self.connect_wallet():
                return False, "None"

            # Step 3: Retrieve nonce
            if not await self.get_nonce():
                return False, "None"

            # Step 4: Retrieve CSRF token with rate limit handling
            csrf_result = await self.get_csrf_token()

            # Handle rate limit error
            if csrf_result == "RATE_LIMIT":
                # Put account in timeout for 5-10 minutes (300-600 seconds)
                timeout_duration = random.uniform(300, 600)
                logger.warning(f"{self.user} rate limit reached, waiting {int(timeout_duration)} seconds before retry")
                await asyncio.sleep(timeout_duration)

                # Retry CSRF token retrieval
                if not await self.get_csrf_token():
                    return False, "None"
            elif not csrf_result:
                return False, "None"

            # Step 5: Authenticate with signed message
            success, response = await self.authenticate()
            if not success:
                return False, response

            # Step 6: Retrieve session info
            if not await self.get_session_info():
                return False, "None"

            if Settings().use_imap:
                await self.connect_email()

            return True, "None"

        except Exception as e:
            logger.error(f"{self.user} error during authentication process: {str(e)}")
            return False, "None"

    async def get_referral_code(self) -> str | None:
        """
        Retrieve referral code for current user

        Returns:
            Referral code or None in case of error
        """
        if not self.user_id:
            logger.error(f"{self.user} attempting to get referral code without user ID")
            return None

        try:
            headers = await self.get_headers(
                {
                    "Accept": "application/json, text/plain, */*",
                    "Content-Type": "application/json",
                    "Origin": "https://loyalty.campnetwork.xyz",
                }
            )

            # Request to get referral code
            success, response = await self.request(
                url="https://loyalty.campnetwork.xyz/api/referral/codes",
                method="POST",
                json_data={"loyaltyRuleId": "d3dc0a56-ffd2-4c67-88a7-96d40f22fc47"},
                headers=headers,
            )

            if success and isinstance(response, dict) and "referralCode" in response:
                ref_code = response.get("referralCode")
                logger.success(f"{self.user} retrieved referral code: {ref_code}")

                # Save referral code to database
                try:
                    update_ref_code(self.user.private_key, ref_code)
                except Exception as e:
                    logger.error(f"{self.user} error saving referral code: {str(e)}")

                return ref_code
            else:
                logger.error(f"{self.user} failed to retrieve referral code: {response}")
                return None
        except Exception as e:
            logger.error(f"{self.user} error retrieving referral code: {str(e)}")
            return None

    async def login_with_referral(self, referral_code: str | None = None):
        """
        Authenticate using referral code

        Args:
            referral_code: Referral code (optional)

        Returns:
            Success status and response
        """
        # Add referral code to cookies if provided
        if referral_code:
            logger.info(f"{self.user} starting registration with referral code: {referral_code}")
            self.cookies["referral_code"] = referral_code

        # Perform standard authentication
        success, response = await self.login()

        if not success and "WALLET_ADDRESS_BLOCKED".lower() in str(response).lower():
            resource_manager = ResourceManager()
            logger.error(f"{self.user} account blocked")
            await resource_manager.mark_wallet_as_blocked(self.user.private_key)
            return False

        if success and not self.user.ref_code:
            # Retrieve and save own referral code
            await self.get_referral_code()

        return success, response

    async def check_connect(self):
        sucess, response = await self.request(url="https://api.github.com", method="get")
        if sucess:
            return True
        else:
            return False
