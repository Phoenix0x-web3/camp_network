from base64 import b64encode
from json import dumps
from loguru import logger
from web3.types import TxParams
from eth_account.messages import encode_defunct

from libs.eth_async.client import Client
from libs.eth_async.data.models import Networks, TxArgs, TokenAmount
from data.settings import Settings
from data.models import Contracts
from utils.db_api.models import Wallet
from utils.browser import Browser
from utils.retry import async_retry
from libs.base import Base


class CoNFT(Base):

    def __init__(self, wallet: Wallet) -> None:
        """Initialize CoNFT task client"""
        super().__init__(wallet=wallet, client=Client(private_key=wallet.private_key, network=Networks.Camp))
        self.__module_name__ = "CoNFT"  # For async_retry logging
        self.browser = Browser(wallet=wallet)
        self.session_headers = {
            "Origin": "https://conft.app",
            "Referer": "https://conft.app/",
        }
        self.settings = Settings()
        self.session_cookie = {}

    async def run(self):
        balance = await self.check_nft_balance(contract=Contracts.CONFT)
        if balance > 0:
            logger.info(f"{self.wallet} Already owns CoNFT Trail Badge")
            return False

        if not await self.authorize():
            logger.error(f"{self.wallet} Failed to authorize for CoNFT task")
            return False

        return await self.mint()

    async def authorize(self):
        sign_nonce = await self.get_sign_nonce()
        if not sign_nonce:
            logger.error(f"{self.wallet} Failed to get sign nonce")
            return False
        logger.debug(f"{self.wallet} Got sign nonce: {sign_nonce}")

        sign_typed_data = {
            "types": {
                "EIP712Domain": [],
                "Message": [{"name": "text", "type": "string"}, {"name": "nonce", "type": "string"}]
            },
            "primaryType": "Message",
            "domain": {},
            "message": {
                "text": "Welcome to coNFT! Please sign the message. This request does not trigger a transaction or cost any gas fees.",
            }
        }
        sign_typed_data["message"]["nonce"] = sign_nonce
        sign_text = f"{sign_typed_data['message']['text']}\nNonce: {sign_nonce}"
        message_bytes = encode_defunct(text=sign_text)
        signature = self.client.account.sign_message(signable_message=message_bytes)
        if not signature:
            logger.error(f"{self.wallet} Failed to sign message for CoNFT task")
            return False
        logger.debug(f"{self.wallet} Got signature: {signature.signature.hex()}")

        address_cookie = await self.auth(signature=signature.signature.hex())
        if not address_cookie:
            logger.error(f"{self.wallet} Failed to authenticate")
            return False
        logger.debug(f"{self.wallet} Got address cookie: {address_cookie}")
        self.session_cookie = {"address": address_cookie}
        return True

    async def mint(self):
        contract = await self.client.contracts.get(contract_address=Contracts.CONFT)
        tx_label = "mint CoNFT Trail Badge"

        mint_data = await self.get_mint_data(nft_address=Contracts.CONFT.address)
        if not mint_data:
            logger.error(f"{self.wallet} Failed to get mint data")
            return False

        mint_value = await contract.functions.mintPrice().call()
        mint_amount = TokenAmount(amount=mint_value, wei=True)
        tx_label = f"mint CoNFT Trail Badge for {mint_amount} CAMP"

        token_data = b64encode(dumps(mint_data["badge"], separators=(",", ":")).encode()).decode()
        token_uri = f"data:application/json;base64,{token_data}"

        args = TxArgs(
            points=mint_data["points"],
            signature=mint_data["signature"],
            tokenUri=token_uri
        )
        data = contract.encode_abi("mint", args=(args.tuple()))
        tx_params = TxParams(
            to=Contracts.CONFT.address,
            data=data,
            value=mint_amount.Wei
        )
        result = await self.execute_transaction(
            tx_params=tx_params,
            activity_type=tx_label,
            retry_count=3
        )

        if result.success:
            logger.success(f"{self.wallet} Successfully minted CoNFT Trail Badge")
            return True
        else:
            logger.error(f"{self.wallet} Mint failed: {result.error_message}")
            return False

    @async_retry()
    async def get_sign_nonce(self):
        response = await self.browser.get(
            url=f'https://conft.app/connect?address={self.client.account.address.lower()}',
            headers=self.session_headers
        )
        data = response.json()
        logger.debug(f"{self.wallet} Sign nonce response: {data}")
        if not data.get("nonce", {}).get("nonce"):
            raise Exception(f"Unexpected response: {data}")
        return data["nonce"]["nonce"]

    @async_retry()
    async def auth(self, signature: str):
        response = await self.browser.post(
            url='https://conft.app/connect?_data=routes%2F_api.connect',
            data={
                "address": self.client.account.address.lower(),
                "signature": signature,
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            }
        )
        data = response.text
        logger.debug(f"{self.wallet} Auth response: {data}")
        if not data:
            raise Exception(f"Unexpected response: {data}")
        return data.split(';')[0]

    @async_retry()
    async def get_mint_data(self, nft_address: str):
        response = await self.browser.get(
            url=f'https://conft.app/get-badges/123420001114/{nft_address}/{self.client.account.address}',
            headers=self.session_headers,
            cookies=self.session_cookie
        )
        data = response.json()
        logger.debug(f"{self.wallet} Mint data response: {data}")
        if data.get("error"):
            raise Exception(f"Failed to get mint signature: {data}")
        return data
