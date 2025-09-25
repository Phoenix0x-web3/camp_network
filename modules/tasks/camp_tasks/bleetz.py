from datetime import datetime, timezone
from random import choices
from string import hexdigits

from eth_account.messages import encode_defunct
from loguru import logger
from web3.types import TxParams

from data.models import Contracts
from libs.base import Base
from libs.eth_async.client import Client
from libs.eth_async.data.models import Networks, TxArgs
from utils.browser import Browser
from utils.db_api.models import Wallet
from utils.retry import async_retry


class Bleetz(Base):
    def __init__(self, wallet: Wallet) -> None:
        super().__init__(wallet=wallet, client=Client(private_key=wallet.private_key, network=Networks.Camp))
        self.__module_name__ = "Bleetz"  # For async_retry logging
        self.browser = Browser(wallet=self.wallet)
        self.session_headers = {
            "Origin": "https://www.bleetz.io",
            "Referer": "https://www.bleetz.io/",
            "X-External-Api-Key": "f16a8d7df49dbb5b3e939b9067779068",
            "X-Para-Version": "1.11.0",
        }

    async def run(self):
        balance = await self.check_nft_balance(contract=Contracts.BLEETZ)
        if balance > 0:
            logger.info(f"{self.wallet} Already owns Bleetz GamerID")
            return False

        if not await self.authorize():
            logger.error(f"{self.wallet} Failed to authorize for Bleetz task")
            return False

        return await self.mint()

    async def authorize(self):
        sign_data = await self.bleetz_get_sign_data()
        if not sign_data:
            logger.error(f"{self.wallet} Failed to get sign data")
            return False
        logger.debug(f"{self.wallet} Got sign data: {sign_data}")

        # Prepare and sign message
        issued_at = datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds")[:-6] + "Z"
        nonce = "".join(choices(hexdigits.lower(), k=24))
        sign_text = (
            f"Click to sign in and accept the EntertainM Terms of Service "
            f"(https://www.entertainm.io/terms-and-conditions) and Privacy Policy "
            f"(https://www.entertainm.io/privacy-policy).\n"
            f"Nonce: {nonce}\n"
            f"Issued At: {issued_at}"
        )
        message_bytes = encode_defunct(text=sign_text)
        signature = self.client.account.sign_message(signable_message=message_bytes)
        if not signature:
            logger.error(f"{self.wallet} Failed to sign message for Bleetz task")
            return False
        logger.debug(f"{self.wallet} Got signature: {signature.signature.hex()}")

        account_info = await self.bleetz_login(sign_text=sign_text, signature=signature.signature.hex())
        if not account_info:
            logger.error(f"{self.wallet} Failed to login for Bleetz task")
            return False
        logger.debug(f"{self.wallet} Successfully logged in, token: {account_info['token']}")
        self.session_headers["Authorization"] = "Bearer " + account_info["token"]

        if not await self.bleetz_fetch_user(cognito_id=account_info["cognito"]):
            logger.error(f"{self.wallet} Failed to fetch user data")
            return False

        return True

    async def mint(self):
        contract = await self.client.contracts.get(contract_address=Contracts.BLEETZ)
        tx_label = "mint bleetz GamerID"

        args = TxArgs()
        data = contract.encode_abi("mintGamerID", args=(args.tuple()))
        tx_params = TxParams(to=Contracts.BLEETZ.address, data=data)
        result = await self.execute_transaction(tx_params=tx_params, activity_type=tx_label, retry_count=3)

        if result.success:
            logger.success(f"{self.wallet} Successfully minted Bleetz GamerID")
            return True
        else:
            logger.error(f"{self.wallet} Mint failed: {result.error_message}")
            return False

    @async_retry()
    async def bleetz_get_sign_data(self):
        response = await self.browser.post(
            url="https://api.getpara.com/users/external-wallets/login",
            json={
                "externalAddress": self.client.account.address,
                "type": "EVM",
                "externalWalletProvider": "MetaMask",
                "shouldTrackUser": True,
            },
            headers=self.session_headers,
        )
        data = response.json()
        logger.debug(f"{self.wallet} Sign data response: {data}")
        if not data.get("signatureVerificationMessage"):
            raise Exception(f"Unexpected response: {data}")
        return data

    @async_retry()
    async def bleetz_login(self, sign_text: str, signature: str):
        response = await self.browser.post(
            url="https://services.meta-night.club/api/v1/auth/login",
            json={"signature": signature, "message": sign_text},
            headers=self.session_headers,
        )
        data = response.json()
        logger.debug(f"{self.wallet} Login response: {data}")
        if not data.get("token"):
            raise Exception(f"Unexpected response: {data}")
        return data

    @async_retry()
    async def bleetz_fetch_user(self, cognito_id: str):
        response = await self.browser.post(
            url="https://services.meta-night.club/api/v1/fetch-user", json={"cognitoId": cognito_id}, headers=self.session_headers
        )
        data = response.json()
        logger.debug(f"{self.wallet} Fetch user response: {data}")
        if response.status_code != 200:
            raise Exception(f"Unexpected response: {data}")
        return True
