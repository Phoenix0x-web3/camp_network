import asyncio
from base64 import b64encode
from json import dumps
from time import time
from loguru import logger
from web3.types import TxParams

from libs.eth_async.client import Client
from libs.eth_async.data.models import Networks, TxArgs, TokenAmount
from data.settings import Settings
from data.models import Contracts
from utils.db_api.models import Wallet
from utils.browser import Browser
from utils.retry import async_retry
from libs.base import Base


class CoPass(Base):
    def __init__(self, wallet: Wallet) -> None:
        super().__init__(wallet=wallet, client=Client(private_key=wallet.private_key, network=Networks.Camp))
        self.__module_name__ = "CoPass" 
        self.browser = Browser(wallet=wallet)
        self.session_headers = {
            "Origin": "https://copass.app",
            "Referer": "https://copass.app/",
        }
        self.settings = Settings()

    async def run(self):
        balance = await self.check_nft_balance(contract=Contracts.COPASS)
        if balance > 0:
            logger.info(f"{self.wallet} Already owns CoPass Bronze Activity Badge")
            return False

        return await self.mint()

    async def mint(self):
        contract = await self.client.contracts.get(contract_address=Contracts.COPASS)
        tx_label = "mint CoPass Bronze Activity Badge"

        wallet_stats = await self.get_wallet_stats()
        if not wallet_stats:
            logger.error(f"{self.wallet} Failed to get wallet stats")
            return False
        logger.debug(f"{self.wallet} Wallet stats: {wallet_stats}")

        mint_value = await contract.functions.mintPrice().call()
        logger.debug(mint_value)
        mint_amount = TokenAmount(amount=mint_value, wei=True)
        tx_label = f"mint CoPass Bronze Activity Badge for {mint_amount} CAMP"

        badge_data = {
            "name": "Copass Basecamp Testnet Bronze Badge",
            "description": "Awarded for a special achievement in copass.app",
            "image": f"https://copass.app/api/badge/?points={wallet_stats['totalPoints']}&address={self.client.account.address[:5].lower()}...{self.client.account.address[-4:].lower()}&chainId=123420001114&status=bronze&timestamp={int(time() * 1e3)}"
        }
        token_data = b64encode(dumps(badge_data, separators=(",", ":")).encode()).decode()
        token_uri = f"data:application/json;base64,{token_data}"

        # Prepare transaction
        args = TxArgs(
            points=wallet_stats["totalPoints"],
            signature=wallet_stats["signature"],
            tokenUri=token_uri
        )
        data = contract.encode_abi("mint", args=(args.tuple()))
        tx_params = TxParams(
            to=Contracts.COPASS.address,
            data=data,
            value=mint_amount.Wei
        )
        result = await self.execute_transaction(
            tx_params=tx_params,
            activity_type=tx_label,
            retry_count=3
        )

        if result.success:
            logger.success(f"{self.wallet} Successfully minted CoPass Bronze Activity Badge")
            return True
        else:
            logger.error(f"{self.wallet} Mint failed: {result.error_message}")
            return False

    @async_retry()
    async def get_wallet_stats(self):
        response = await self.browser.get(
            url=f'https://copass.app/api/wallet-statistics/common?address={self.client.account.address}&chainId=123420001114',
            headers=self.session_headers
        )
        data = response.json()
        logger.debug(f"{self.wallet} Wallet stats response: {data}")
        if not data.get("totalPoints") or not data.get("signature"):
            raise Exception(f"Unexpected response: {data}")
        return data
