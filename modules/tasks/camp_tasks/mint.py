# mint.py
from typing import Optional

from loguru import logger
from web3.constants import MAX_INT
from web3.contract.async_contract import AsyncContract
from web3.contract.contract import Contract
from web3.types import TxParams

from data.settings import Settings
from libs.base import Base
from libs.eth_async.client import Client
from libs.eth_async.data.models import Networks, TokenAmount, TxArgs
from utils.db_api.models import Wallet

ETH_ADDRESS = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
F_ADDRESS = "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"


class MintFunctions(Base):
    def __init__(self, wallet: Wallet):
        super().__init__(wallet=wallet, client=Client(private_key=wallet.private_key, network=Networks.Camp))
        self.settings = Settings()

    async def need_mint_and_quantity(self, contract: AsyncContract | Contract, max_mint: int, action: str) -> tuple[bool, int]:
        """Check if mint is needed and calculate quantity

        Args:
            contract: Contract instance
            max_mint: Maximum mint quantity

        Returns:
            (need_mint, quantity): Whether mint is needed and quantity
        """
        try:
            balance = await self.check_nft_balance(contract=contract)
            if balance >= max_mint:
                logger.info(f"{self.wallet} already minted maximum NFT {balance} for {action}")
                return False, 0
            if self.settings.multiple_actions or not balance:
                quantity = 1
                return True, quantity
            else:
                logger.info(f"{self.wallet} already minted NFT for {action}")
                return False, 0

        except Exception as e:
            logger.error(f"{self.wallet} Error checking mint need: {str(e)}")
            return False, 0

    async def base_camp_mint(self, contract: AsyncContract | Contract, quantity: int = 1) -> Optional[str]:
        """Mint Base Camp NFT

        Args:
            contract: Contract instance
            quantity: Quantity to mint

        Returns:
            Transaction hash or None
        """
        swap_params = TxArgs(
            receiver=self.client.account.address,
            quantity=quantity,
            currency=ETH_ADDRESS,
            pricePerToken=0,
            allowlistProof=TxArgs(
                proof=[],
                quantityLimitPerWallet=0,
                pricePerToken=0,
                currency=ZERO_ADDRESS,
            ).tuple(),
            data="0x",
        )

        data = contract.encode_abi("claim", args=(swap_params.tuple()))

        tx_params = TxParams(to=contract.address, data=data)

        result = await self.execute_transaction(tx_params=tx_params, activity_type="Base_camp_mint", retry_count=3)

        if result.success:
            return result.tx_hash
        else:
            raise Exception(f"Mint failed: {result.error_message}")

    async def aura_mint(self, contract: AsyncContract | Contract, quantity: int = 1) -> Optional[str]:
        """Mint Aura NFT

        Args:
            contract: Contract instance
            quantity: Quantity to mint

        Returns:
            Transaction hash or None
        """
        swap_params = TxArgs(
            receiver=self.client.account.address,
            quantity=quantity,
            currency=ETH_ADDRESS,
            pricePerToken=0,
            allowlistProof=TxArgs(
                proof=[],
                quantityLimitPerWallet=0,
                pricePerToken=0,
                currency=ZERO_ADDRESS,
            ).tuple(),
            data="0x",
        )

        data = contract.encode_abi("claim", args=(swap_params.tuple()))

        tx_params = TxParams(to=contract.address, data=data)

        result = await self.execute_transaction(tx_params=tx_params, activity_type="Aura_mint", retry_count=3)

        if result.success:
            return result.tx_hash
        else:
            raise Exception(f"Mint failed: {result.error_message}")

    async def sticky_pleb_mint(self, contract: AsyncContract | Contract, quantity: int = 1) -> Optional[str]:
        """Mint Sticky Pleb NFT

        Args:
            contract: Contract instance
            quantity: Quantity to mint

        Returns:
            Transaction hash or None
        """
        price_per_token = int(MAX_INT, 16)
        allowlist_proof_params = TxArgs(
            proof=[],
            quantityLimitPerWallet=0,
            pricePerToken=price_per_token,
            currency=F_ADDRESS,
        )
        swap_params = TxArgs(
            _receiver=self.client.account.address,
            _quantity=quantity,
            _currency=ETH_ADDRESS,
            _pricePerToken=0,
            _allowlistProof=allowlist_proof_params.tuple(),
            _data="0x",
        )

        data = contract.encode_abi("claim", args=(swap_params.tuple()))

        tx_params = TxParams(to=contract.address, data=data)

        result = await self.execute_transaction(tx_params=tx_params, activity_type="Sticky_pleb_mint", retry_count=3)

        if result.success:
            return result.tx_hash
        else:
            raise Exception(f"Mint failed: {result.error_message}")

    async def climb_mint(self, contract: AsyncContract | Contract, quantity: int = 1) -> Optional[str]:
        """Mint Climb NFT

        Args:
            contract: Contract instance
            quantity: Quantity to mint

        Returns:
            Transaction hash or None
        """
        price_per_token = int(MAX_INT, 16)
        allowlist_proof_params = TxArgs(
            proof=[],
            quantityLimitPerWallet=0,
            pricePerToken=price_per_token,
            currency=ZERO_ADDRESS,
        )
        real_price_per_token = 1000000000000000
        swap_params = TxArgs(
            _receiver=self.client.account.address,
            _quantity=quantity,
            _currency=ETH_ADDRESS,
            _pricePerToken=real_price_per_token,
            _allowlistProof=allowlist_proof_params.tuple(),
            _data="0x",
        )

        value = real_price_per_token * quantity
        value = TokenAmount(value, wei=True)

        data = contract.encode_abi("claim", args=(swap_params.tuple()))

        tx_params = TxParams(to=contract.address, data=data, value=value.Wei)

        result = await self.execute_transaction(tx_params=tx_params, activity_type="climb_mint", retry_count=3)

        if result.success:
            return result.tx_hash
        else:
            raise Exception(f"Mint failed: {result.error_message}")

    async def pictographs_mint(self, contract: AsyncContract | Contract) -> Optional[str]:
        """Mint Pictographs NFT

        Args:
            contract: Contract instance

        Returns:
            Transaction hash or None
        """
        data = "0x14f710fe"

        tx_params = TxParams(to=contract.address, data=data)

        result = await self.execute_transaction(tx_params=tx_params, activity_type="pictographs_mint", retry_count=3)

        if result.success:
            return result.tx_hash
        else:
            raise Exception(f"Mint failed: {result.error_message}")

    async def token_tails_mint(self, contract: AsyncContract | Contract) -> Optional[str]:
        """Mint Token Tails NFT

        Args:
            contract: Contract instance

        Returns:
            Transaction hash or None
        """
        swap_params = TxArgs(
            to=self.client.account.address,
        )

        data = contract.encode_abi("safeMint", args=(swap_params.tuple()))

        tx_params = TxParams(to=contract.address, data=data)

        result = await self.execute_transaction(tx_params=tx_params, activity_type="token_tails_mint", retry_count=3)

        if result.success:
            return result.tx_hash
        else:
            raise Exception(f"Mint failed: {result.error_message}")

    async def omnihub_mint(self, contract: AsyncContract | Contract) -> Optional[str]:
        """Mint Omnihub NFT

        Args:
            contract: Contract instance

        Returns:
            Transaction hash or None
        """
        data = "0xa25ffea800000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000800000000000000000000000000000000000000000000000000000000000000000"

        tx_params = TxParams(to=contract.address, data=data, value=TokenAmount(amount=100000000000000, wei=True).Wei)

        result = await self.execute_transaction(tx_params=tx_params, activity_type="omnihub_mint", retry_count=3)

        if result.success:
            return result.tx_hash
        else:
            raise Exception(f"Mint failed: {result.error_message}")

    async def tavern_quest_mint(self, contract: AsyncContract | Contract) -> Optional[str]:
        """Mint Tavern Quest NFT

        Args:
            contract: Contract instance

        Returns:
            Transaction hash or None
        """
        data = "0xba41b0c6000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000000400000000000000000000000000000000000000000000000000000000000000000"

        tx_params = TxParams(to=contract.address, data=data)

        result = await self.execute_transaction(tx_params=tx_params, activity_type="tavern_quest_mint", retry_count=3)

        if result.success:
            return result.tx_hash
        else:
            raise Exception(f"Mint failed: {result.error_message}")

    async def mintpad_mint(self, contract: AsyncContract | Contract) -> Optional[str]:
        """Mint Mintpad NFT

        Args:
            contract: Contract instance

        Returns:
            Transaction hash or None
        """
        data = f"0xb510391f000000000000000000000000ac6f313c90c5a4c38811766ff09b4394921f853800000000000000000000000000000000000000000000000000000000000000400000000000000000000000000000000000000000000000000000000000000044449a52f8000000000000000000000000{self.client.account.address[2:]}000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000"

        tx_params = TxParams(to=contract.address, data=data, value=TokenAmount(amount=6660000000, wei=True).Wei)

        result = await self.execute_transaction(tx_params=tx_params, activity_type="mintpad_mint", retry_count=3)

        if result.success:
            return result.tx_hash
        else:
            raise Exception(f"Mint failed: {result.error_message}")
