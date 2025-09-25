import asyncio
from random import randint, uniform

from eth_account.messages import encode_defunct
from faker import Faker
from loguru import logger
from web3.types import TxParams

from data.models import Contracts
from data.settings import Settings
from libs.base import Base
from libs.eth_async.client import Client
from libs.eth_async.data.models import Networks, TokenAmount, TxArgs
from utils.browser import Browser
from utils.db_api.models import Wallet
from utils.retry import async_retry


class ChainBillsBase(Base):
    def __init__(self, wallet: Wallet) -> None:
        super().__init__(wallet=wallet, client=Client(private_key=wallet.private_key, network=Networks.Camp))
        self.__module_name__ = "ChainBills"  # For async_retry logging
        self.browser = Browser(wallet=wallet)
        self.settings = Settings()
        self.session_headers = {
            "Origin": "https://chainbills.xyz",
            "Referer": "https://chainbills.xyz/",
            "Chain-Name": "basecamptestnet",
        }

    async def authorize(self):
        sign_text = "Authentication"
        message_bytes = encode_defunct(text=sign_text)
        signature = self.client.account.sign_message(signable_message=message_bytes)
        if not signature:
            logger.error(f"{self.wallet} Failed to sign message for ChainBills")
            return False
        logger.debug(f"{self.wallet} Got signature: {signature.signature.hex()}")
        self.session_headers.update(
            {
                "Signature": signature.signature.hex(),
                "Wallet-Address": self.client.account.address.lower(),
            }
        )
        return True

    async def get_created_payable(self):
        try:
            contract = await self.client.contracts.get(contract_address=Contracts.CHAINBILLS)
            created_payable_id = await contract.functions.userPayableIds(self.client.account.address, 0).call()
            created_payable_id = created_payable_id.hex()
            created_payable_id = self.add_0x(created_payable_id)
            payable_raw_data = await contract.functions.getPayable(created_payable_id).call()
            payable_data = {
                k: v
                for k, v in zip(
                    [
                        "host",
                        "chain_count",
                        "host_count",
                        "created_at",
                        "payments_count",
                        "withdrawals_count",
                        "activities_count",
                        "allowed_tokens_and_amounts_count",
                        "balances_count",
                        "is_closed",
                        "is_auto_withdraw",
                    ],
                    payable_raw_data,
                )
            }

            tokens_amounts = await contract.functions.getAllowedTokensAndAmounts(created_payable_id).call()
            bill_value = next(
                (token_amount[1] for token_amount in tokens_amounts if token_amount[0].lower() == Contracts.CHAINBILLS.address.lower()), 0
            )
            bill_amount = TokenAmount(amount=bill_value, wei=True)

            token_balances = await contract.functions.getBalances(created_payable_id).call()
            withdraw_value = next(
                (token_balance[1] for token_balance in token_balances if token_balance[0].lower() == Contracts.CHAINBILLS.address.lower()),
                0,
            )
            withdraw_amount = TokenAmount(amount=withdraw_value, wei=True)

            return {
                "id": created_payable_id,
                "data": payable_data,
                "price": {"amount": bill_amount, "value": bill_value},
                "withdraw": {"amount": withdraw_amount, "value": withdraw_value},
            }
        except Exception as e:
            logger.debug(f"{self.wallet} No created payable found: {str(e)}")
            return None

    @staticmethod
    def add_0x(value: str) -> str:
        if value.startswith("0x"):
            return value
        return "0x" + value


class ChainBillsCreate(ChainBillsBase):
    def __init__(self, wallet: Wallet) -> None:
        super().__init__(wallet=wallet)
        self.__module_name__ = "ChainBillsCreate"

    async def run(self):
        if not await self.authorize():
            return False
        created_payable = await self.get_created_payable()
        if created_payable is not None:
            logger.info(f"{self.wallet} Already created payable: {created_payable['id']}")
            return False

        return await self.create_bill()

    async def create_bill(self):
        contract = await self.client.contracts.get(contract_address=Contracts.CHAINBILLS)
        tx_label = "create chainbills"

        random_price = round(uniform(0.00001, 0.001), randint(3, 6))
        random_price_amount = TokenAmount(amount=random_price)

        args = TxArgs(tokens_and_amounts=[[Contracts.CHAINBILLS.address, random_price_amount.Wei]], is_auto_withdraw=False)
        data = contract.encode_abi("createPayable", args=(args.tuple()))
        tx_params = TxParams(to=Contracts.CHAINBILLS.address, data=data, value=random_price_amount.Wei)
        result = await self.execute_transaction(tx_params=tx_params, activity_type=tx_label, retry_count=3)

        if not result.success:
            logger.error(f"{self.wallet} Failed to create payable: {result.error_message}")
            return False

        tx_info = await self.client.w3.eth.get_transaction_receipt(result.tx_hash)
        payable_id = self.add_0x(tx_info["logs"][-1]["topics"][1].hex())
        logger.debug(f"{self.wallet} Created payable ID: {payable_id}")

        await asyncio.sleep(4)  # Delay after transaction
        success = await self.create_payable(payable_id=payable_id)
        if success:
            logger.success(f"{self.wallet} Successfully created payable")
            return True
        return False

    @async_retry()
    async def create_payable(self, payable_id: str):
        response = await self.browser.post(
            url="https://server-l3fxxyj7jq-uc.a.run.app/payable",
            json={"payableId": payable_id, "description": Faker().text(randint(8, 30))[:-1]},
            headers=self.session_headers,
        )
        data = response.json()
        logger.debug(f"{self.wallet} Create payable response: {data}")
        if data.get("success") is not True:
            raise Exception(f"Unexpected response: {data}")
        return True


class ChainBillsWithdraw(ChainBillsBase):
    def __init__(self, wallet: Wallet) -> None:
        super().__init__(wallet=wallet)
        self.__module_name__ = "ChainBillsWithdraw"

    async def run(self):
        created_payable = await self.get_created_payable()
        if created_payable is None:
            logger.error(f"{self.wallet} No payable found for withdrawal")
            return False

        if created_payable["data"]["withdrawals_count"]:
            logger.info(f"{self.wallet} Already withdrawn from payable: {created_payable['id']}")
            return False

        if created_payable["data"]["payments_count"] == 0:
            if not await self.pay_for_bill(created_payable=created_payable):
                logger.error(f"{self.wallet} Failed to pay for payable")
                return False
            await asyncio.sleep(randint(self.settings.random_pause_between_actions_min, self.settings.random_pause_between_actions_max))
            created_payable = await self.get_created_payable()
            if not created_payable:
                logger.error(f"{self.wallet} Failed to retrieve updated payable")
                return False

        return await self.withdraw_from_bill(created_payable=created_payable)

    async def pay_for_bill(self, created_payable: dict):
        contract = await self.client.contracts.get(contract_address=Contracts.CHAINBILLS)
        tx_label = f"pay chainbills {created_payable['price']['amount']} CAMP"

        args = TxArgs(payableId=created_payable["id"], token=Contracts.CHAINBILLS.address, amount=created_payable["price"]["value"])
        data = contract.encode_abi("pay", args=(args.tuple()))
        tx_params = TxParams(to=Contracts.CHAINBILLS.address, data=data, value=created_payable["price"]["amount"].Wei)
        result = await self.execute_transaction(tx_params=tx_params, activity_type=tx_label, retry_count=3)

        if not result.success:
            logger.error(f"{self.wallet} Failed to pay for payable: {result.error_message}")
            return False

        tx_info = await self.client.w3.eth.get_transaction_receipt(result.tx_hash)
        user_payment_id = self.add_0x(tx_info["logs"][0]["topics"][-1].hex())
        payment_id = self.add_0x(tx_info["logs"][-1]["topics"][-1].hex())
        logger.debug(f"{self.wallet} Paid for payable, user_payment_id: {user_payment_id}, payment_id: {payment_id}")
        return True

    async def withdraw_from_bill(self, created_payable: dict):
        contract = await self.client.contracts.get(contract_address=Contracts.CHAINBILLS)
        tx_label = f"withdraw {created_payable['withdraw']['amount']} CAMP from chainbills"

        args = TxArgs(payableId=created_payable["id"], token=Contracts.CHAINBILLS.address, amount=created_payable["withdraw"]["value"])
        data = contract.encode_abi("withdraw", args=(args.tuple()))
        tx_params = TxParams(to=Contracts.CHAINBILLS.address, data=data)
        result = await self.execute_transaction(tx_params=tx_params, activity_type=tx_label, retry_count=3)

        if not result.success:
            logger.error(f"{self.wallet} Failed to withdraw from payable: {result.error_message}")
            return False

        tx_info = await self.client.w3.eth.get_transaction_receipt(result.tx_hash)
        withdrawal_id = self.add_0x(tx_info["logs"][0]["topics"][-1].hex())
        logger.debug(f"{self.wallet} Withdrawn from payable, withdrawal_id: {withdrawal_id}")
        logger.success(f"{self.wallet} Successfully withdrawn from payable")
        return True
