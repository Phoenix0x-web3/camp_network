from base64 import b64encode
from datetime import datetime, timezone
from json import dumps
from random import choice

from loguru import logger
from web3.types import TxParams

from data.models import Contracts
from data.settings import Settings
from libs.base import Base
from libs.eth_async.client import Client
from libs.eth_async.data.models import Networks, TxArgs
from utils.browser import Browser
from utils.db_api.models import Wallet
from utils.retry import async_retry


class Merv(Base):
    def __init__(self, wallet: Wallet) -> None:
        super().__init__(wallet=wallet, client=Client(private_key=wallet.private_key, network=Networks.Camp))
        self.__module_name__ = "Merv"
        self.browser = Browser(wallet=wallet)
        self.session_headers = {
            "Origin": "https://camp.merv.wtf",
            "Referer": "https://camp.merv.wtf/",
            "X-External-Api-Key": "721f5430d43cb8821949a9802cea17ee",
            "X-Para-Version": "1.14.2",
        }
        self.settings = Settings()

    async def run(self):
        balance = await self.check_nft_balance(contract=Contracts.MERV)
        if balance > 0:
            logger.info(f"{self.wallet} Already owns Merv NFT")
            return False

        return await self.mint()

    async def mint(self):
        user_data = await self.merv_login()
        if not user_data:
            logger.error(f"{self.wallet} Failed to login to Merv")
            return False
        logger.debug(f"{self.wallet} Logged in, user ID: {user_data['userId']}")

        generated_images = await self.merv_generate(user_id=user_data["userId"])
        if not generated_images:
            logger.error(f"{self.wallet} Failed to generate images")
            return False
        random_generated_nft = choice(generated_images)
        logger.debug(f"{self.wallet} Selected generated NFT: {random_generated_nft}")

        nft_data_ = await self.merv_get_nft_data(user_id=user_data["userId"], generated_nft=random_generated_nft)
        if not nft_data_:
            logger.error(f"{self.wallet} Failed to get NFT data")
            return False
        logger.debug(f"{self.wallet} Got NFT data: {nft_data_}")

        nft_data = {
            "name": f"MERV IP #{nft_data_['id'].split('-')[0]}",
            "description": random_generated_nft["prompt"],
            "image": random_generated_nft["url"],
            "attributes": [
                {"trait_type": "Model", "value": random_generated_nft["model"]},
                {"trait_type": "Source System", "value": "Cloudflare"},
                {"trait_type": "Source Image ID", "value": random_generated_nft["id"]},
            ],
        }

        contract = await self.client.contracts.get(contract_address=Contracts.MERV)
        tx_label = "mint Merv NFT"

        encoded_nft_data = b64encode(dumps(nft_data, separators=(",", ":")).encode()).decode()
        encoded_token_uri = f"data:application/json;base64,{encoded_nft_data}"

        args = TxArgs(to=self.client.account.address, tokenURI=encoded_token_uri)
        data = contract.encode_abi("mint", args=(args.tuple()))
        tx_params = TxParams(to=Contracts.MERV.address, data=data)
        result = await self.execute_transaction(tx_params=tx_params, activity_type=tx_label, retry_count=3)

        if result.success:
            logger.success(f"{self.wallet} Successfully minted Merv NFT")
            return True
        else:
            logger.error(f"{self.wallet} Mint failed: {result.error_message}")
            return False

    @async_retry()
    async def merv_login(self):
        """Login to Merv to get user ID"""
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
        logger.debug(f"{self.wallet} Login response: {data}")
        if not data.get("userId"):
            raise Exception(f"Unexpected response: {data}")
        return data

    @async_retry()
    async def merv_generate(self, user_id: str):
        response = await self.browser.post(
            url="https://camp.merv.wtf/api/generate",
            json={},
            headers={
                "Accept-Language": "en-US",
                "Priority": "u=1, i",
                "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="133"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
                "Origin": "https://camp.merv.wtf",
                "Referer": "https://camp.merv.wtf/",
                "X-User-Id": user_id,
            },
        )
        data = response.json()
        logger.debug(f"{self.wallet} Generate images response: {data}")
        if data.get("success") is not True or not data.get("images"):
            raise Exception(f"Unexpected response: {data}")
        return data["images"]

    @async_retry()
    async def merv_get_nft_data(self, user_id: str, generated_nft: dict):
        auth_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl5a21lenlnY2ZwYnpqb25rZXhxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Mzk4NzYzNTIsImV4cCI6MjA1NTQ1MjM1Mn0.mjSC1QoBlweZjZQZcA9Csnv9_hYtpckKwWB9cN6ThC8"
        headers = {
            "Origin": "https://camp.merv.wtf",
            "Referer": "https://camp.merv.wtf/",
            "X-Client-Info": "supabase-js-web/2.48.1",
            "Apikey": auth_token,
            "Authorization": f"Bearer {auth_token}",
        }

        await self.browser.post(
            url="https://yykmezygcfpbzjonkexq.supabase.co/rest/v1/rpc/set_config",
            json={"setting": "app.current_user_id", "value": user_id},
            headers=headers,
        )

        current_date = datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds")[:-6] + "Z"
        await self.browser.post(
            url="https://yykmezygcfpbzjonkexq.supabase.co/rest/v1/users_camp",
            params={
                "columns": '"id","twitter_id","twitter_username","twitter_pfp_url","wallet_address","credits","last_login","created_at"',
                "select": "*",
            },
            json=[
                {
                    "id": user_id,
                    "twitter_id": None,
                    "twitter_username": None,
                    "twitter_pfp_url": None,
                    "wallet_address": self.client.account.address,
                    "credits": 1000,
                    "last_login": current_date,
                    "created_at": current_date,
                }
            ],
            headers={**headers, "Prefer": "return=representation"},
        )

        response = await self.browser.post(
            url="https://yykmezygcfpbzjonkexq.supabase.co/rest/v1/artworks_camp?select=*",
            json={
                "prompt": generated_nft["prompt"],
                "model_name": generated_nft["model"],
                "image_url": generated_nft["url"],
                "owner_id": user_id,
                "created_at": datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds")[:-6] + "Z",
                "no_background": False,
            },
            headers={**headers, "Prefer": "return=representation"},
        )
        data = response.json()
        logger.debug(f"{self.wallet} Register artwork response: {data}")
        if not isinstance(data, list) or not data[0].get("id"):
            raise Exception(f"Unexpected response: {data}")
        return data[0]
