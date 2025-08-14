from datetime import datetime, timezone
from random import randint
from loguru import logger
from faker import Faker
from web3.types import TxParams
from eth_account.messages import encode_defunct

from libs.eth_async.client import Client
from libs.eth_async.data.models import Networks, TxArgs
from data.settings import Settings
from data.models import Contracts
from utils.db_api.models import Wallet
from utils.browser import Browser
from libs.base import Base


class MySphere(Base):
    def __init__(self, wallet: Wallet) -> None:
        super().__init__(wallet=wallet, client=Client(private_key=wallet.private_key, network=Networks.Camp))
        self.__module_name__ = "MySphere"
        self.browser = Browser(wallet=wallet)
        self.session_headers = {
            "Origin": "https://mysphere.fun",
            "Referer": "https://mysphere.fun/",
        }
        self.settings = Settings()

    async def run(self):
        contract_post = await self.client.contracts.get(contract_address=Contracts.MYSPHERE_POST)
        post_count = await contract_post.functions.getPostCount(self.client.account.address).call()
        if post_count > 0:
            logger.info(f"{self.wallet} Already created a post on MySphere")
        else:
            if not await self.create_post():
                logger.error(f"{self.wallet} Failed to create post")
                return False

        balance = await self.check_nft_balance(contract=Contracts.MYSPHERE_NFT, id=1)
        if balance > 0:
            logger.info(f"{self.wallet} Already owns MySphere Portal NFT")
            return False
        else:
            if not await self.claim_nft():
                logger.error(f"{self.wallet} Failed to claim Portal NFT")
                return False

        logger.success(f"{self.wallet} Successfully completed MySphere tasks")
        return True


    async def create_post(self):
        contract = await self.client.contracts.get(contract_address=Contracts.MYSPHERE_POST)
        tx_label = "create MySphere post"

        post_content = Faker().text(randint(15, 30))[:-1]
        args = TxArgs(contentHash=post_content)
        data = contract.encode_abi("createPost", args=(args.tuple()))
        tx_params = TxParams(
            to=Contracts.MYSPHERE_POST.address,
            data=data
        )
        result = await self.execute_transaction(
            tx_params=tx_params,
            activity_type=tx_label,
            retry_count=3
        )

        if result.success:
            logger.success(f"{self.wallet} Successfully created MySphere post")
            return True
        else:
            logger.error(f"{self.wallet} Failed to create post: {result.error_message}")
            return False

    async def claim_nft(self):
        contract = await self.client.contracts.get(contract_address=Contracts.MYSPHERE_NFT)
        tx_label = "mint MySphere Portal NFT"

        args = TxArgs()
        data = contract.encode_abi("claim", args=(args.tuple()))
        tx_params = TxParams(
            to=Contracts.MYSPHERE_NFT.address,
            data=data
        )
        result = await self.execute_transaction(
            tx_params=tx_params,
            activity_type=tx_label,
            retry_count=3
        )

        if result.success:
            logger.success(f"{self.wallet} Successfully claimed MySphere Portal NFT")
            return True
        else:
            logger.error(f"{self.wallet} Failed to claim NFT: {result.error_message}")
            return False
