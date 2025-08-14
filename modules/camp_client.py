from typing import Dict
import random
from loguru import logger

from data.settings import Settings
from utils.db_api.models import Wallet
from libs.eth_async.client import Client
from libs.eth_async.data.models import Networks

from modules.tasks.authorization import AuthClient
from modules.tasks.quests import QuestClient
from modules.tasks.twitter_camp import TwitterService
from modules.tasks.referral_manager import load_ref_codes, get_referral_code_for_registration
from modules.tasks.faucet import Faucet
from modules.tasks.onchain_client import CampOnchain
# from modules.tasks.camp_tasks.specific_tasks_client import SpecificTaskCamp


class CampNetworkClient:
    """Main client for CampNetwork, combining authorization and quest operations"""

    def __init__(self, user: Wallet):
        """
        Initialize the CampNetwork client

        Args:
            user: User object
        """
        self.user = user

        # Create clients for authorization and quest operations
        self.auth_client = AuthClient(user=user)
        self.quest_client = QuestClient(user=user)
        self.twitter_client = TwitterService(user=user)
        self.faucet_client = Faucet(wallet=user)
        self.onchain_client = CampOnchain(wallet=user)
        # self.specific_task_client = SpecificTaskCamp(wallet=user)

        # Quest IDs for easy access
        self.QUEST_IDS = self.quest_client.QUEST_IDS



    async def login(self):
        """
        Perform authorization on the site with an optional referral code

        Args:
            use_referral: Whether to use a referral code during authorization

        Returns:
            Success status and response
        """
        referral_code = None

        # Get settings for referral codes
        settings = Settings()
        use_referral = settings.use_ref_code
        use_only_file_codes = settings.use_only_file_ref_code

        # If using a referral code is enabled and no quests are completed
        if use_referral and not self.user.completed_quests:
            # If specified to use only file codes
            if use_only_file_codes:
                file_codes = load_ref_codes()
                referral_code = random.choice(file_codes) if file_codes else None
            else:
                # Use standard logic for selecting a code
                referral_code = await get_referral_code_for_registration(
                )

        # Perform authorization with referral code
        success, response = await self.auth_client.login_with_referral(
            referral_code=referral_code
        )

        if success:
            # If authorization is successful, pass cookies and user ID to quest client
            self.quest_client.cookies = self.auth_client.cookies
            self.quest_client.set_user_id(self.auth_client.user_id)
            self.twitter_client.cookies = self.auth_client.cookies
            return True, response
        else:
            return False, response

    async def complete_all_quests(
        self, retry_failed: bool = True, max_retries: int = 3
    ) -> Dict[str, bool]:
        """
        Complete all incomplete quests with error handling

        Args:
            retry_failed: Whether to retry failed quests
            max_retries: Maximum number of retry attempts

        Returns:
            Results of quest completion
        """
        # Check if authorized
        if self.user.account_blocked:
            logger.warning(f"{self.user} account blocked")
            return {}

        incomplete_quests = await self.quest_client.get_incomplete_quests()

        if not incomplete_quests:
            logger.success(f"{self.user} all regular quests already completed")
            return {}

        if not self.auth_client.user_id:
            logger.info(f"{self.user} not authorized, performing authorization")
            auth_result = await self.login()

            if not auth_result[0]:  # Check success status
                if isinstance(auth_result[1], str) and auth_result[1] == "RATE_LIMIT":
                    logger.warning(
                        f"{self.user} account on hold due to rate limit"
                    )
                    return {"status": "RATE_LIMITED"}

                logger.error(
                    f"{self.user} failed to authorize, quest execution impossible"
                )
                return {}

        # Execute all quests
        quests = await self.quest_client.complete_all_quests(
            retry_failed=retry_failed, max_retries=max_retries
        )
        await self.update_points()
        return quests

    async def complete_twitter_quests(
        self):
        # Check if authorized
        if self.user.account_blocked:
            logger.warning(f"{self.user} account blocked")
            return {}

        incomplete_quests = await self.twitter_client.get_incomplete_quests()

        if not incomplete_quests:
            logger.success(f"{self.user} all twitter quests already completed")
            return {}
        if not self.auth_client.user_id:
            logger.info(f"{self.user} not authorized, performing authorization")
            auth_result = await self.login()

            if not auth_result[0]:  # Check success status
                # If rate limit error received
                if isinstance(auth_result[1], str) and auth_result[1] == "RATE_LIMIT":
                    logger.warning(
                        f"{self.user} account on hold due to rate limit"
                    )
                    return {"status": "RATE_LIMITED"}

                logger.error(
                    f"{self.user} failed to authorize, quest execution impossible"
                )
                return {}

        # Execute all quests
        quests = await self.twitter_client.complete_twitter_quests()
        await self.update_points()
        return quests

    async def complete_twitter_and_regular_quests(self):
        if self.user.account_blocked:
            logger.warning(f"{self.user} account blocked")
            return False
        await self.complete_all_quests()
        await self.complete_twitter_quests()
        return

    async def update_points(self):
        if self.user.account_blocked:
            logger.warning(f"{self.user} account blocked")
            return False
        if not self.auth_client.user_id:
            logger.info(f"{self.user} not authorized, performing authorization")
            auth_result = await self.login()

            if not auth_result[0]: 
                if isinstance(auth_result[1], str) and auth_result[1] == "RATE_LIMIT":
                    logger.warning(
                        f"{self.user} account on hold due to rate limit"
                    )
                    return {"status": "RATE_LIMITED"}

                logger.error(
                    f"{self.user} failed to authorize, quest execution impossible"
                )
                return False
        return await self.quest_client.get_and_update_points()
    
    async def complete_faucet(self):
        connect = await self.auth_client.check_connect()
        if not connect:
            return False
        ether_client = Client(private_key=self.user.private_key, network=Networks.Ethereum)
        ether_nonce = await ether_client.wallet.nonce()
        client = Client(private_key=self.user.private_key, network=Networks.Camp)
        balance = await client.wallet.balance()
        if balance.Ether > 0 and not Settings().use_faucet_if_balance:
            return True
        elif balance.Ether == 0 and int(ether_nonce) < 3:
            logger.warning(f"{self.user} don't have balance for onchain and don't have 3+ transactions in ETH Mainnet for faucet")
            return False
        else:
            faucet = await self.faucet_client.handle_faucet()
            if not faucet and balance.Ether == 0:
                logger.warning(f"{self.user} can't faucet and have zero balance")
                return False
            return True

    async def complete_onchain(self):
        if self.user.account_blocked:
            logger.warning(f"{self.user} account blocked")
            return {}

        faucet = await self.complete_faucet()
        if faucet:
            return await self.onchain_client.handle_actions()

