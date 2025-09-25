import asyncio
import time
from random import choice, randint

from eth_account.messages import encode_defunct
from faker import Faker
from loguru import logger

from data.settings import Settings
from libs.base import Base
from libs.eth_async.client import Client
from libs.eth_async.data.models import Networks
from utils.browser import Browser
from utils.db_api.models import Wallet
from utils.retry import async_retry


class Storychain(Base):
    def __init__(self, wallet: Wallet) -> None:
        super().__init__(wallet=wallet, client=Client(private_key=wallet.private_key, network=Networks.Camp))
        self.__module_name__ = "Storychain"
        self.browser = Browser(wallet=wallet)
        self.session_headers = {
            "Origin": "https://storychain.ai",
            "Referer": "https://storychain.ai/",
        }
        self.settings = Settings()
        self.faker = Faker()
        self.cookies = {}

    async def run(self):
        if not await self.authorize():
            logger.error(f"{self.wallet} Failed to authorize for Storychain")
            return False
        if not await self.storychain_get_nova_stories():
            await self.storychain_create_nova_story()
            await asyncio.sleep(60)
            await self.send_snag_request(loyalty_id="0f197e1e-fe39-4ea5-8d42-d00f0be4fb56", campaign_id="67d41e05222c2dd7b47982f1")

        if await self.storychain_get_stories():
            logger.info(f"{self.wallet} Already created a story for Remix Comic")
            return False
        else:
            characters = await self.storychain_get_characters()
            if not characters:
                unpublished_character = await self.storychain_get_unpublished_character()
                new_character = unpublished_character if unpublished_character else await self.storychain_create_character()
                if not new_character:
                    logger.error(f"{self.wallet} Failed to create or get unpublished character")
                    return False

                created_character = await self.storychain_wait_for_character_created(new_character["_id"])
                if not created_character:
                    logger.error(f"{self.wallet} Failed to wait for character creation")
                    return False

                if not created_character.get("regularPortrait"):
                    await self.storychain_choose_character(new_character["_id"], len(created_character["initialCharacterImages"]))

                characters = [
                    await self.storychain_publish_character(
                        char_id=new_character["_id"],
                        first_name=self.faker.first_name_male() if new_character["gender"] == "Male" else self.faker.first_name_female(),
                    )
                ]

            random_character = choice(characters)
            if not await self.storychain_create_character_story(char_id=random_character["_id"]):
                logger.error(f"{self.wallet} Failed to create Remix Comic story")
                return False
            logger.success(f"{self.wallet} Successfully created Remix Comic story")

        logger.success(f"{self.wallet} Successfully completed Storychain tasks")
        return True

    async def authorize(self):
        sign_data = await self.storychain_get_sign_data()
        if not sign_data:
            logger.error(f"{self.wallet} Failed to get sign data")
            return False

        sign_text = (
            f"{sign_data['domain']} wants you to sign in with your Ethereum account:\n"
            f"{self.client.account.address}\n\n"
            f"{sign_data['statement']}\n\n"
            f"URI: {sign_data['domain']}\n"
            f"Version: {sign_data['version']}\n"
            f"Chain ID: {sign_data['chain_id']}\n"
            f"Nonce: {sign_data['nonce']}\n"
            f"Issued At: {sign_data['issued_at']}\n"
            f"Expiration Time: {sign_data['expiration_time']}\n"
            f"Not Before: {sign_data['invalid_before']}"
        )
        message_bytes = encode_defunct(text=sign_text)
        signature = self.client.account.sign_message(signable_message=message_bytes)
        if not signature:
            logger.error(f"{self.wallet} Failed to sign message for Storychain")
            return False
        logger.debug(f"{self.wallet} Got signature: {signature.signature.hex()}")

        if not await self.storychain_login(sign_data=sign_data, signature=signature.signature.hex()):
            logger.error(f"{self.wallet} Failed to login to Storychain")
            return False
        logger.debug(f"{self.wallet} Successfully logged in")
        return True

    @async_retry()
    async def storychain_get_stories(self):
        response = await self.browser.get(url="https://api.storychain.ai/characters/me", cookies=self.cookies)
        data = response.json()
        logger.debug(f"{self.wallet} Get stories response: {data}")
        if "characters" not in data:
            raise Exception(f"Unexpected response: {data}")
        return data["characters"]

    @async_retry()
    async def storychain_get_characters(self):
        """Get available characters"""
        response = await self.browser.get(url="https://api.storychain.ai/characters/me/available", cookies=self.cookies)
        data = response.json()
        logger.debug(f"{self.wallet} Get characters response: {data}")
        if "characters" not in data:
            raise Exception(f"Unexpected response: {data}")
        return data["characters"]

    @async_retry()
    async def storychain_get_unpublished_character(self):
        response = await self.browser.get(url="https://api.storychain.ai/characters/me", cookies=self.cookies)
        data = response.json()
        logger.debug(f"{self.wallet} Get unpublished character response: {data}")
        if "characters" not in data:
            raise Exception(f"Unexpected response: {data}")
        return data["characters"][0] if data["characters"] else {}

    @async_retry()
    async def storychain_create_nova_story(self):
        response = await self.browser.post(
            url="https://api.storychain.ai/p/camp-stories/create",
            json={"prompt": self.faker.text(randint(15, 30))[:-1], "isfr5": "true", "jn19": "true"},
            cookies=self.cookies,
        )
        data = response.json()
        logger.debug(f"{self.wallet} Create nova story response: {data}")
        if not data.get("storyId"):
            raise Exception(f"Unexpected response: {data}")
        return data

    @async_retry()
    async def storychain_get_nova_stories(self):
        response = await self.browser.get(url="https://api.storychain.ai/p/camp-stories/my-stories", cookies=self.cookies)
        data = response.json()
        logger.debug(f"{self.wallet} Get stories response: {data}")
        if "stories" in data:
            logger.info(f"{self.wallet} already create a Nova story")
            return True
        return False

    @async_retry()
    async def send_snag_request(self, loyalty_id, campaign_id):
        json_data = {
            "input": self.wallet.address,
            "LOYALTY_RULE_ID": f"{loyalty_id}",
            "CAMPAIGN_ID": f"{campaign_id}",
        }
        response = await self.browser.post(url="https://snag-quest-external.vercel.app/api/submit-story", json=json_data)
        data = response.json()
        logger.debug(f"{self.wallet} snag requst response: {data}")
        if data["verified"]:
            logger.success(f"{self.wallet} success create Nova Story")
            return True
        return False

    @async_retry()
    async def storychain_create_character(self):
        response = await self.browser.post(
            url="https://api.storychain.ai/characters/create/byoptions",
            json={
                **self._generate_random_character_params(),
                "runpod": True,
            },
            cookies=self.cookies,
        )
        data = response.json()
        logger.debug(f"{self.wallet} Create character response: {data}")
        if not data.get("_id"):
            raise Exception(f"Unexpected response: {data}")
        return data

    def _generate_random_character_params(self):
        return {
            "gender": choice(["Male", "Female", "Other"]),
            "age": choice(["Teenager", "Young Adult", "Adult", "Elderly"]),
            "skinColor": choice(["Pale", "Fair", "Olive", "Tan", "Brown", "Dark Brown", "Ebony"]),
            "hairColor": choice(
                ["Blonde", "Brown", "Black", "Red", "Ginger", "Orange", "Gray", "White", "Blue", "Green", "Purple", "Pink"]
            ),
            "hairLength": choice(["Bald", "Short", "Medium", "Long"]),
            "hairType": choice(["Straight", "Wavy", "Curly", "Coiled", "Dreadlocks", "Braided", "Afro"]),
            "facialHair": choice(["", "Clean-shaven", "Stubble", "Short beard", "Long beard", "Mustache", "Goatee", "Sideburns"]),
            "eyeColor": choice(["Brown", "Blue", "Green", "Hazel", "Gray", "Amber", "Violet", "Gold", "Silver", "Red", "Turquoise"]),
        }

    @async_retry()
    async def storychain_wait_for_character_created(self, char_id: str):
        time_started = int(time.time())
        timeout = 120

        while True:
            response = await self.browser.get(url=f"https://api.storychain.ai/characters/{char_id}", cookies=self.cookies)
            data = response.json()
            logger.debug(f"{self.wallet} Wait for character status: {data}")

            if data.get("initialCharacterImages"):
                return data
            elif time.time() > time_started + timeout:
                logger.error(f"{self.wallet} Timeout waiting for character creation")
                return False
            await asyncio.sleep(5)

    @async_retry()
    async def storychain_choose_character(self, char_id: str, images_amount: int):
        response = await self.browser.post(
            url="https://api.storychain.ai/characters/choose",
            json={
                "id": char_id,
                "index": randint(0, images_amount - 1),
            },
            cookies=self.cookies,
        )
        data = response.json()
        logger.debug(f"{self.wallet} Choose character response: {data}")
        if data.get("message") != "Success":
            raise Exception(f"Unexpected response: {data}")
        return data["character"]

    @async_retry()
    async def storychain_publish_character(self, char_id: str, first_name: str):
        response = await self.browser.post(
            url="https://api.storychain.ai/characters/publish",
            json={
                "id": char_id,
                "name": first_name,
            },
            cookies=self.cookies,
        )
        data = response.json()
        logger.debug(f"{self.wallet} Publish character response: {data}")
        if data.get("message") != "Success":
            raise Exception(f"Unexpected response: {data}")
        return data["character"]

    @async_retry()
    async def storychain_create_character_story(self, char_id: str):
        response = await self.browser.post(
            url="https://api.storychain.ai/stories/me/create",
            json={
                "id": char_id,
                "prompt": self.faker.text(randint(15, 30))[:-1],
            },
            cookies=self.cookies,
        )
        data = response.json()
        logger.debug(f"{self.wallet} Create character story response: {data}")
        if not data.get("public"):
            raise Exception(f"Unexpected response: {data}")
        return True

    @async_retry()
    async def storychain_get_sign_data(self):
        response = await self.browser.get(
            url="https://api.storychain.ai/thirdweb/login",
            params={
                "address": self.client.account.address,
                "chainId": "123420001114",
            },
        )
        data = response.json()
        logger.debug(f"{self.wallet} Sign data response: {data}")
        if not data.get("nonce"):
            raise Exception(f"Unexpected response: {data}")
        return data

    @async_retry()
    async def storychain_login(self, sign_data: dict, signature: str):
        response = await self.browser.post(
            url="https://api.storychain.ai/thirdweb/login",
            json={
                "signature": signature,
                "payload": sign_data,
            },
        )
        data = response.json()
        logger.debug(f"{self.wallet} Login response: {data}")
        if not data.get("userId"):
            raise Exception(f"Unexpected response: {data}")
        self.cookies = response.cookies
        return True
