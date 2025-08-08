import asyncio
import random
from typing import Dict, List
from loguru import logger

from data.settings import Settings
from utils.db_api.wallet_api import get_completed_quests, mark_quest_completed, is_quest_completed
from .http_client import BaseHttpClient


class QuestClient(BaseHttpClient):
    """Client for interacting with CampNetwork quests"""

    # Quest IDs collected from curl requests
    QUEST_IDS = Settings().quests_name_and_ids 
    TWITTER_QUEST_ID = Settings().quests_twitter

    # URLs for requests
    BASE_URL = "https://loyalty.campnetwork.xyz"
    COMPLETE_URL_TEMPLATE = f"{BASE_URL}/api/loyalty/rules/{{quest_id}}/complete"
    STATUS_URL = f"{BASE_URL}/api/loyalty/rules/status"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.completed_quests = []  # List of completed quests in the current session
        self.user_id = kwargs.get("user_id")  # User ID

    def set_user_id(self, user_id: str) -> None:
        """
        Set the user ID

        Args:
            user_id: User ID
        """
        self.user_id = user_id

    async def get_status_params(self) -> Dict[str, str]:
        """
        Get parameters for quest status request

        Returns:
            Parameters for status request
        """
        if not self.user_id:
            logger.error(
                f"{self.user} attempting to get status parameters without user ID"
            )
            return {}

        return {
            "userId": self.user_id,
            "websiteId": "32afc5c9-f0fb-4938-9572-775dee0b4a2b",
            "organizationId": "26a1764f-5637-425e-89fa-2f3fb86e758c",
        }

    async def check_quests_status(self) -> Dict:
        """
        Check the status of all quests

        Returns:
            Quest status
        """
        params = await self.get_status_params()
        if not params:
            return {}

        success, response = await self.request(
            url=self.STATUS_URL, method="GET", params=params
        )

        if success and isinstance(response, dict):
            self.quest_status = response
            logger.info(
                f"{self.user} retrieved quest status (total {len(response.get('rules', []))})"
            )
            return response
        else:
            logger.error(f"{self.user} failed to retrieve quest status: {response}")
            return {}

    async def get_db_completed_quests(self) -> List[str]:
        """
        Get list of completed quests from the database

        Returns:
            List of completed quest IDs
        """
        try:
            completed_quests = get_completed_quests(self.user.private_key)

            self.completed_quests = [
                quest_name
                for quest_name, quest_id in self.QUEST_IDS.items()
                if quest_id in completed_quests
            ]

            return completed_quests

        except Exception as e:
            logger.error(
                f"{self.user} error retrieving completed quests from database: {e}"
            )
            return []

    async def get_incomplete_quests(self) -> List[str]:
        """
        Get list of incomplete quests using database data

        Returns:
            List of incomplete quest names
        """
        # Get completed quests from database
        completed_quests_ids = await self.get_db_completed_quests()

        # Form list of incomplete quests
        incomplete_quests = []

        for quest_name, quest_id in self.QUEST_IDS.items():
            # Check if quest ID is not in completed quests
            if quest_id not in completed_quests_ids:
                incomplete_quests.append(quest_name)

        logger.info(
            f"{self.user} incomplete quests ({len(incomplete_quests)}): {', '.join(incomplete_quests) if incomplete_quests else 'none'}"
        )
        return incomplete_quests

    async def mark_quest_completed(self, quest_name: str) -> bool:
        """
        Mark a quest as completed in the database

        Args:
            quest_name: Quest name

        Returns:
            Success status
        """
        try:
            result = mark_quest_completed(self.user.private_key, quest_name)

            if result:
                # Add to local list of completed quests
                if quest_name not in self.completed_quests:
                    self.completed_quests.append(quest_name)

                return True
            else:
                return False

        except Exception as e:
            logger.error(
                f"{self.user} error marking quest {quest_name} as completed: {e}"
            )
            return False

    async def check_is_quest_completed(self, quest_name: str) -> bool:
        """
        Check if a quest is completed

        Args:
            quest_name: Quest name

        Returns:
            Completion status
        """
        # First check in local list of completed quests
        if quest_name in self.completed_quests:
            return True

        # Then check in database
        try:
            return is_quest_completed(self.user.private_key, quest_name)

        except Exception as e:
            logger.error(
                f"{self.user} error checking status of quest {quest_name}: {e}"
            )
            return False

    async def complete_quest(self, quest_name: str | None = None, quest_id: str | None = None) -> bool:
        """
        Complete a quest by its name and save result to database

        Args:
            quest_name: Quest name

        Returns:
            Success status
        """
        # Get quest ID
        if not quest_id:
            quest_id = self.QUEST_IDS.get(quest_name)
            if not quest_id: 
                logger.error(f"Quest {quest_name} not found in list")
                return False

        # Check if quest is already completed
        try:
            if is_quest_completed(self.user.private_key, quest_id):
                logger.info(
                    f"{self.user} quest {quest_name} (ID: {quest_id}) already completed previously (from database)"
                )
                return True
        except Exception as e:
            logger.error(f"{self.user} error checking quest status in database: {e}")

        try:
            url = self.COMPLETE_URL_TEMPLATE.format(quest_id=quest_id)

            # Add random delay to mimic human behavior
            await asyncio.sleep(random.uniform(1.5, 4.0))

            logger.info(f"{self.user} completing quest {quest_name} (ID: {quest_id})")

            headers = await self.get_headers(
                {
                    "Content-Type": "application/json",
                    "Origin": "https://loyalty.campnetwork.xyz",
                    "Priority": "u=0",
                }
            )

            success, response = await self.request(
                url=url,
                method="POST",
                json_data={},  # Empty JSON as in curl requests
                headers=headers,
                quest_id=quest_id,
            )

            if success:
                logger.success(
                    f"{self.user} successfully completed quest {quest_name} (ID: {quest_id})"
                )
                # Mark quest as completed in database
                try:
                    mark_result = mark_quest_completed(
                        self.user.private_key, quest_id
                    )

                    if mark_result:
                        logger.debug(f"{self.user} quest {quest_name} (ID: {quest_id}) successfully marked in database")
                    else:
                        logger.warning(
                            f"{self.user} failed to mark quest {quest_name} (ID: {quest_id}) in database"
                        )
                except Exception as e:
                    logger.error(
                        f"{self.user} error saving quest status to database: {e}"
                    )

                return True
            else:
                # Check if quest was already completed
                if (
                    isinstance(response, dict)
                    and response.get("message") == "You have already been rewarded"
                    and response.get("rewarded") is True
                ):
                    logger.info(
                        f"{self.user} quest {quest_name} (ID: {quest_id}) already completed previously (server response)"
                    )
                    # Mark quest as completed in database
                    try:
                        mark_quest_completed(self.user.private_key, quest_id)
                    except Exception as e:
                        logger.error(
                            f"{self.user} error saving quest status to database: {e}"
                        )
                    return True  # Consider this a successful completion
                else:
                    logger.error(
                        f"{self.user} error completing quest {quest_name} (ID: {quest_id}): {response}"
                    )
                    return False

        except Exception as e:
            logger.error(
                f"{self.user} exception during quest {quest_name} (ID: {quest_id}) completion: {e}"
            )
            return False

    async def complete_all_quests(
        self, retry_failed: bool = True, max_retries: int = 3
    ) -> Dict[str, bool]:
        """
        Complete all incomplete quests in random order

        Args:
            retry_failed: Whether to retry failed quests
            max_retries: Maximum number of retry attempts

        Returns:
            Results of quest completion
        """
        results = {}

        # Get list of incomplete quests
        incomplete_quests = await self.get_incomplete_quests()

        if not incomplete_quests:
            logger.success(f"{self.user} all quests already completed")
            return results

        # Shuffle quest list for random execution order
        random.shuffle(incomplete_quests)

        # Dictionary to track retry attempts
        retry_counts = {quest: 0 for quest in incomplete_quests}

        # Execute quests
        for quest_name in incomplete_quests:
            success = await self.complete_quest(quest_name)
            results[quest_name] = success

            # Increased delay between quests (20-30 seconds)
            await asyncio.sleep(random.uniform(Settings().random_pause_between_actions_min, Settings().random_pause_between_actions_max))

        # Check results and retry failed quests if needed
        if retry_failed:
            # Get updated list of incomplete quests
            remaining = await self.get_incomplete_quests()

            # Retry failed quests
            for quest_name in remaining:
                # Only consider quests from the original list
                if quest_name in retry_counts:
                    retry_counts[quest_name] += 1

                    if retry_counts[quest_name] <= max_retries:
                        logger.warning(
                            f"{self.user} retry attempt {retry_counts[quest_name]}/{max_retries} for quest {quest_name}"
                        )

                        # Delay before retry (30-40 seconds)
                        await asyncio.sleep(random.uniform(Settings().random_pause_between_actions_min, Settings().random_pause_between_actions_max))

                        success = await self.complete_quest(quest_name)
                        results[quest_name] = success

        # Get final statistics
        completed = sum(1 for result in results.values() if result)
        logger.success(f"{self.user} completed {completed} out of {len(results)} quests")

        return results



