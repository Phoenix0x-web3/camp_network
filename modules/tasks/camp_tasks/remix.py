from datetime import datetime, timezone
from random import choice, randint
from time import time

from eth_account.messages import encode_defunct
from faker import Faker
from loguru import logger
from web3.types import TxParams

from data.models import Contracts
from libs.base import Base
from libs.eth_async.client import Client
from libs.eth_async.data.models import Networks, TxArgs
from utils.browser import Browser
from utils.db_api.models import Wallet
from utils.retry import async_retry


class Remix(Base):
    def __init__(self, wallet: Wallet) -> None:
        """Initialize Remix task client"""
        super().__init__(wallet=wallet, client=Client(private_key=wallet.private_key, network=Networks.Camp))
        self.__module_name__ = "Remix"  # For async_retry logging
        self.browser = Browser(wallet=wallet)
        self.session_headers = {
            "Origin": "https://remix.campnetwork.xyz",
            "Referer": "https://remix.campnetwork.xyz/",
            "X-Client-Id": "9123887d-94f0-4427-a2f7-cd04d16c1fc3",
        }

    async def run(self):
        balance = await self.check_nft_balance(contract=Contracts.REMIX)
        if balance > 0:
            logger.info(f"{self.wallet} Already owns Remix NFT")
            return False
        # Get nonce for signing
        nonce = await self.remix_get_sign_nonce()
        if not nonce:
            logger.error(f"{self.wallet} Failed to get nonce for Remix task")
            return False
        logger.debug(f"{self.wallet} success get nonce {nonce}")

        # Prepare and sign message
        issued_at = datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds")[:-6] + "Z"
        sign_text = (
            f"remix.campnetwork.xyz wants you to sign in with your Ethereum account:\n"
            f"{self.client.account.address}\n\n"
            f"Connect with Camp Network\n\n"
            f"URI: https://remix.campnetwork.xyz\n"
            f"Version: 1\n"
            f"Chain ID: 123420001114\n"
            f"Nonce: {nonce}\n"
            f"Issued At: {issued_at}"
        )

        message_bytes = encode_defunct(text=sign_text)
        signature = self.client.account.sign_message(signable_message=message_bytes)
        if not signature:
            logger.error(f"{self.wallet} Failed to sign message for Remix task")
            return False
        logger.debug(f"{self.wallet} success get signature {signature}")

        # Login with signature
        auth_token = await self.remix_login(signature=signature.signature.hex(), sign_text=sign_text)
        logger.debug(f"{self.wallet} success get auth token in Remix {auth_token}")
        if not auth_token:
            logger.error(f"{self.wallet} Failed to login for Remix task")
            return False
        self.session_headers["Authorization"] = "Bearer " + auth_token

        return await self.mint()

    @async_retry()
    async def create_nft(self):
        """Create NFT data for minting"""
        # Check generations left
        if not await self.remix_check_generations():
            logger.error(f"{self.wallet} No generations left to mint Remix NFT")
            return False

        # Generate image
        model_type = choice(["fox", "raccoon", "bear", "goat", "moose", "owl"])
        images = await self.remix_generate(model_type)
        if not images:
            logger.error(f"{self.wallet} Failed to generate images")
            return False
        random_image = choice(images)

        # Upload image
        uploaded_data = await self.remix_upload_url()
        if not uploaded_data:
            logger.error(f"{self.wallet} Failed to get upload URL")
            return False

        # Update status
        if not await self.remix_update_status(file_key=uploaded_data["key"]):
            logger.error(f"{self.wallet} Failed to update status")
            return False

        # Register NFT
        deadline = int(time() * 1e3)
        nft_data = await self.remix_register_nft(
            random_image=random_image, uploaded_data=uploaded_data, model_type=model_type, deadline=deadline
        )
        if not nft_data:
            logger.error(f"{self.wallet} Failed to register NFT")
            return False

        return nft_data, deadline

    async def mint(self):
        """Mint Remix NFT"""
        contract = await self.client.contracts.get(contract_address=Contracts.REMIX)
        nft_raw_data = await self.create_nft()
        if nft_raw_data is False:
            return False

        nft_data, deadline = nft_raw_data
        tx_label = "mint remix NFT"

        args = TxArgs(
            to=self.client.account.address,
            tokenId=int(nft_data["tokenId"]),
            parentId=5,
            creatorContentHash=nft_data["creatorContentHash"],
            uri=nft_data["uri"],
            licenseTerms=(
                int(nft_data["licenseTerms"]["price"]),
                nft_data["licenseTerms"]["duration"],
                nft_data["licenseTerms"]["royaltyBps"],
                nft_data["licenseTerms"]["paymentToken"],
            ),
            deadline=deadline,
            signature=nft_data["signature"],
        )

        data = contract.encode_abi("claim", args=(args.tuple()))
        tx_params = TxParams(to=Contracts.REMIX.address, data=data)
        result = await self.execute_transaction(tx_params=tx_params, activity_type=tx_label, retry_count=3)

        if result.success:
            logger.success(f"{self.wallet} Successfully minted Remix NFT")
            return True
        else:
            logger.error(f"{self.wallet} Mint failed: {result.error_message}")
            return False

    @async_retry()
    async def remix_get_sign_nonce(self):
        """Get nonce for signing"""
        response = await self.browser.post(
            url="https://wv2h4to5qa.execute-api.us-east-2.amazonaws.com/dev/auth/client-user/nonce",
            json={"walletAddress": self.client.account.address},
            headers=self.session_headers,
        )
        data = response.json()
        if not data.get("data") or data.get("isError"):
            raise Exception(f"Unexpected response: {data}")
        return data["data"]

    @async_retry()
    async def remix_login(self, signature: str, sign_text: str):
        """Login with signature"""
        response = await self.browser.post(
            url="https://wv2h4to5qa.execute-api.us-east-2.amazonaws.com/dev/auth/client-user/verify",
            json={"message": sign_text, "signature": signature, "walletAddress": self.client.account.address},
            headers=self.session_headers,
        )
        data = response.json()
        logger.debug(data)
        if not data.get("data") or data.get("isError"):
            raise Exception(f"Unexpected response: {data}")
        return data["data"]

    @async_retry()
    async def remix_check_generations(self):
        """Check if generations are available"""
        response = await self.browser.get(
            url="https://wv2h4to5qa.execute-api.us-east-2.amazonaws.com/dev/auth/merv/check-generations", headers=self.session_headers
        )
        logger.debug(response.text)
        data = response.json()
        logger.debug(data)
        if not data.get("data") or data.get("isError"):
            raise Exception(f"Unexpected response: {data}")
        return data["data"]["generations_left"] > 0

    @async_retry()
    async def remix_generate(self, model_type: str):
        """Generate images for NFT"""
        response = await self.browser.post(
            url="https://wv2h4to5qa.execute-api.us-east-2.amazonaws.com/dev/auth/merv/generate-image",
            json={"model_type": model_type},
            headers=self.session_headers,
        )
        data = response.json()
        logger.debug(data)
        if not data.get("data") or data.get("isError"):
            raise Exception(f"Unexpected response: {data}")
        return data["data"]["images"]

    @async_retry()
    async def remix_upload_url(self):
        """Get upload URL for image"""
        response = await self.browser.post(
            url="https://wv2h4to5qa.execute-api.us-east-2.amazonaws.com/dev/auth/origin/upload-url",
            json={"name": "remix.png", "type": "image/png"},
            headers=self.session_headers,
        )
        data = response.json()
        logger.debug(data)
        if not data.get("data") or data.get("isError"):
            raise Exception(f"Unexpected response: {data}")
        return data["data"]

    @async_retry()
    async def remix_update_status(self, file_key: str):
        """Update upload status"""
        response = await self.browser.put(
            url="https://wv2h4to5qa.execute-api.us-east-2.amazonaws.com/dev/auth/origin/update-status",
            json={"status": "success", "fileKey": file_key},
            headers=self.session_headers,
        )
        data = response.json()
        logger.debug(data)
        if data.get("data") != "success" or data.get("isError"):
            raise Exception(f"Unexpected response: {data}")
        return True

    @async_retry()
    async def remix_register_nft(self, random_image: dict, uploaded_data: dict, model_type: str, deadline: int):
        """Register NFT data"""
        response = await self.browser.post(
            url="https://wv2h4to5qa.execute-api.us-east-2.amazonaws.com/dev/auth/origin/register",
            json={
                "source": "file",
                "deadline": deadline,
                "licenseTerms": {
                    "price": "0",
                    "duration": 2629800,
                    "royaltyBps": 0,
                    "paymentToken": "0x0000000000000000000000000000000000000000",
                },
                "metadata": {
                    "name": Faker().text(randint(8, 20))[:-1],
                    "description": "A unique remix created by mAItrix",
                    "image": random_image["url"],
                    "attributes": [{"trait_type": "Base Character", "value": model_type}],
                },
                "parentId": 5,
                "fileKey": uploaded_data["key"],
            },
            headers=self.session_headers,
        )
        data = response.json()
        logger.debug(data)
        if not data.get("data") or data.get("isError"):
            raise Exception(f"Unexpected response: {data}")
        return data["data"]
