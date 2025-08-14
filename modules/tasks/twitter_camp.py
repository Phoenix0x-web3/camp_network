import asyncio
import random
from typing import List, Dict
from loguru import logger

from data.settings import Settings
from modules.tasks.http_client import BaseHttpClient
from modules.tasks.quests import QuestClient
from modules.tasks.resource_manager import ResourceManager
from utils.db_api.models import Wallet
from utils.db_api.wallet_api import update_twitter_token, get_wallet_by_private_key, get_completed_quests
from utils.twitter.twitter_client import TwitterClient

class TwitterService(BaseHttpClient):
    """Service layer for Twitter-related operations using TwitterClient"""

    BASE_URL = "https://loyalty.campnetwork.xyz"
    TWITTER_AUTH_URL = f"{BASE_URL}/api/twitter/auth"
    TWITTER_DISCONNECT_URL = f"{BASE_URL}/api/twitter/auth/disconnect"

    def __init__(self, user: Wallet):
        """Initialize TwitterService with a TwitterClient instance"""
        super().__init__(user=user)
        self.twitter_client = TwitterClient(
            user=user,
            twitter_auth_token=user.twitter_token,
        )
        self.action_min_delay = Settings().random_pause_between_twitter_actions_min
        self.action_max_delay = Settings().random_pause_between_twitter_actions_max
        self.quest_min_delay = Settings().random_pause_between_actions_min
        self.quest_max_delay = Settings().random_pause_between_actions_max
        self.max_failures = Settings().resources_max_failures
        self.twitter_username = ""

    async def check_twitter_connection_status(self) -> bool:
        """
        Checks if Twitter is connected to the site.

        Returns:
            True if Twitter is connected, False otherwise.
        """
        try:
            url = f"{self.BASE_URL}/api/users"
            params = {
                "walletAddress": self.user.address,
                "includeDelegation": "false",
                "websiteId": "32afc5c9-f0fb-4938-9572-775dee0b4a2b",
                "organizationId": "26a1764f-5637-425e-89fa-2f3fb86e758c",
            }

            headers = await self.get_headers({
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://loyalty.campnetwork.xyz/loyalty",
            })

            success, response = await self.request(
                url=url,
                method="GET",
                params=params,
                headers=headers,
                timeout=30
            )

            if success and isinstance(response, dict) and "data" in response:
                user_data = response.get("data", [])[0] if response.get("data") else None
                if user_data and "userMetadata" in user_data:
                    user_metadata = user_data["userMetadata"][0] if user_data["userMetadata"] else None
                    if user_metadata and user_metadata.get("twitterUser") and user_metadata.get("twitterVerifiedAt"):
                        logger.info(f"{self.user} Twitter is connected (@{user_metadata.get('twitterUser')})")
                        self.twitter_username = user_metadata.get('twitterUser')
                        self.twitter_client.is_connected = True
                        return True

            logger.info(f"{self.user} Twitter is not connected")
            self.twitter_client.is_connected = False
            return False

        except Exception as e:
            logger.error(f"{self.user} Error checking Twitter connection status: {str(e)}")
            self.twitter_client.is_connected = False
            return False

    async def reconnect_twitter(self) -> bool:
        try:
            if await self.disconnect_twitter():
                logger.info(f"{self.user} Successfully disconnected old Twitter account")
            else:
                logger.warning(f"{self.user} Failed to disconnect old Twitter account, proceeding with reconnect")

            if await self.connect_twitter():
                logger.success(f"{self.user} Successfully reconnected with new Twitter token")
                return True
            else:
                logger.error(f"{self.user} Failed to reconnect with new Twitter token")
                return False
        except Exception as e:
            logger.error(f"{self.user} Error replacing Twitter token: {str(e)}")
            return False

    async def replace_twitter_token(self) -> bool:
        """
        Replaces the Twitter token if Settings().change_twitter is True.

        Returns:
            True if token was replaced and Twitter reconnected, False otherwise.
        """
        if not Settings().auto_replace_twitter:
            logger.info(f"{self.user} Twitter token replacement disabled in settings")
            return False

        logger.info(f"{self.user} Attempting to replace Twitter token")
        resource_manager = ResourceManager()
        await resource_manager.mark_twitter_as_bad(self.user.private_key)
        success, message = await resource_manager.replace_twitter(self.user.private_key)
        if not success:
            logger.error(f"{self.user} Failed to replace Twitter token: {message}")
            return False

        logger.info(f"{self.user} Twitter token replaced: {message}")
        updated_user = get_wallet_by_private_key(self.user.private_key)
        if not updated_user or not updated_user.twitter_token:
            logger.error(f"{self.user} No new Twitter token available")
            return False

        # Update the Twitter client with the new token
        self.twitter_client.twitter_account.auth_token = updated_user.twitter_token
        update_twitter_token(self.user.private_key, updated_user.twitter_token)
        return await self.reconnect_twitter()


    async def ensure_twitter_connected(self) -> bool:
        """
        Ensures Twitter is connected to the site, reconnecting if necessary.

        Returns:
            True if Twitter is connected, False otherwise.
        """
        if await self.check_twitter_connection_status():
            return True
        logger.info(f"{self.user} Twitter not connected, attempting to connect")
        return await self.connect_twitter()


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
                for quest_name, quest_id in list(Settings().quests_twitter.get("Follow", {}).items())
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

        for quest_name, quest_id in list(Settings().quests_twitter.get("Follow", {}).items()):
            # Check if quest ID is not in completed quests
            if quest_id not in completed_quests_ids:
                incomplete_quests.append(quest_name)

        logger.info(
            f"{self.user} incomplete quests ({len(incomplete_quests)}): {', '.join(incomplete_quests) if incomplete_quests else 'none'}"
        )
        return incomplete_quests

    async def complete_twitter_quests(self, follow_accounts: List[str] | None = None) -> Dict[str, bool]:
        """
        Completes Twitter follow quests using accounts from Settings().quests_twitter or a provided list.

        Args:
            follow_accounts: Optional list of Twitter account names to follow (with or without @).
                             If None, uses all accounts from Settings().quests_twitter["Follow"].

        Returns:
            Dictionary mapping account names to success status.
        """
        follow_accounts = await self.get_incomplete_quests()
        if not follow_accounts:
            logger.info(f"{self.user} No Twitter accounts available for quests")
            return {}

        results = {}
        twitter_rate_limited = False
        rate_limit_message = ""

        try:
            # Step 1: Ensure Twitter is connected
            if not await self.ensure_twitter_connected():
                logger.error(f"{self.user} Failed to ensure Twitter connection, aborting quests")
                return {account: False for account in follow_accounts}

            # Step 2: Initialize Twitter client
            if not await self.twitter_client.initialize():
                logger.error(f"{self.user} Failed to initialize Twitter client")
                if self.twitter_client.last_error and any(
                    x in self.twitter_client.last_error.lower()
                    for x in ["unauthorized", "authentication", "token", "banned"]
                ):
                    if await self.replace_twitter_token():
                        # Reinitialize after token replacement
                        if not await self.twitter_client.initialize():
                            logger.error(f"{self.user} Failed to reinitialize Twitter client after token replacement")
                            return {account: False for account in follow_accounts}
                    else:
                        logger.error(f"{self.user} Token replacement failed or disabled, aborting quests")
                        return {account: False for account in follow_accounts}
                return {account: False for account in follow_accounts}

            if self.twitter_username and self.twitter_client.twitter_account.username != self.twitter_username:
                await self.reconnect_twitter()


            # Step 3: Initialize QuestClient
            quest_client = QuestClient(user=self.user)
            quest_client.cookies = self.cookies

            # Step 4: Process follow quests in random order
            random.shuffle(follow_accounts)
            for account in follow_accounts:
                if twitter_rate_limited:
                    logger.warning(f"{self.user} Skipping follow for {account} due to Twitter rate limits: {rate_limit_message}")
                    results[account] = False
                    continue

                quest_id = Settings().quests_twitter.get("Follow", {}).get(account)
                if not quest_id:
                    logger.warning(f"{self.user} No quest ID for following {account}")
                    results[account] = False
                    continue

                # Check if quest is already completed
                if await quest_client.check_is_quest_completed(quest_id):
                    logger.info(f"{self.user} Follow quest for {account} (ID: {quest_id}) already completed")
                    results[account] = True
                    continue

                # Follow the account with retry
                follow_success = False
                for _ in range(Settings().resources_max_failures):
                    try:
                        follow_success = await self.twitter_client.follow_account(account)
                        if follow_success:
                            break
                        else:
                            await asyncio.sleep(5)
                            continue
                    except Exception as e:
                        logger.error(f"{self.user} errror with follow {e} try again")
                        await asyncio.sleep(5)
                        continue

                if follow_success:
                    # Delegate quest completion to QuestClient
                    success = await quest_client.complete_quest(quest_name=account, quest_id=quest_id)
                    results[account] = success
                else:
                    logger.error(f"{self.user} Failed to follow {account}")
                    results[account] = False
                    if await self.replace_twitter_token():
                        # Reinitialize after token replacement
                        if not await self.twitter_client.initialize():
                            logger.error(f"{self.user} Failed to reinitialize Twitter client after token replacement")
                            return {account: False for account in follow_accounts}
                        # Continue with the next account
                        continue
                    results[account] = False

                # Delay between follows
                if account != follow_accounts[-1] and not twitter_rate_limited:
                    delay = random.uniform(self.action_min_delay, self.action_max_delay)
                    logger.info(f"{self.user} Delaying {int(delay)}s before next follow")
                    await asyncio.sleep(delay)

            # Clean up
            await self.twitter_client.close()

            # Log results
            completed = sum(1 for result in results.values() if result)
            logger.success(f"{self.user} Completed {completed}/{len(follow_accounts)} Twitter follow quests")
            if twitter_rate_limited:
                logger.warning(f"{self.user} Some quests skipped due to Twitter limits: {rate_limit_message}")

            return results

        except Exception as e:
            logger.error(f"{self.user} Error completing Twitter quests: {str(e)}")
            await self.twitter_client.close()
            self.twitter_client.error_count += 1
            if any(x in str(e).lower() for x in ["unauthorized", "authentication", "token", "banned"]):
                if not await self.replace_twitter_token():
                    logger.error(f"{self.user} Failed to replace Twitter token, aborting quests")
            if self.twitter_client.error_count >= self.max_failures:
                logger.error(f"{self.user} Max error count reached, marking proxy as bad")
                resource_manager = ResourceManager()
                await resource_manager.mark_proxy_as_bad(self.user.private_key)
            return {account: False for account in follow_accounts}

    async def connect_twitter(self) -> bool:
        """
        Connects Twitter to the site using OAuth2, adapted from legacy connect_twitter_to_camp

        Returns:
            Success status
        """
        try:
            # Initialize Twitter client
            if not await self.twitter_client.initialize():
                logger.error(f"{self.user} Failed to initialize Twitter client")
                return False

            # Step 1: Request Twitter authorization URL
            logger.info(f"{self.user} Requesting Twitter authorization parameters")
            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": "https://loyalty.campnetwork.xyz/home",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Priority": "u=0, i",
            }

            success, response = await self.request(
                method="GET",
                url=self.TWITTER_AUTH_URL,
                headers=headers,
                timeout=30,
                allow_redirects=False
            )

            if not isinstance(response, dict):
                logger.error(f"{self.user} Failed to get Twitter authorization redirect")
                await self.twitter_client.close()
                return False

            twitter_auth_url = response['location']
            logger.debug(f"{self.user} Got Twitter auth URL: {twitter_auth_url}")

            # Step 2: Use TwitterClient's OAuth2 method
            auth_data = await self.twitter_client.connect_twitter_to_site_oauth2(twitter_auth_url)
            if not auth_data.auth_token or not auth_data.state_verifier_token:
                logger.error(f"{self.user} Failed to obtain OAuth2 authorization code")
                await self.twitter_client.close()
                return False

            callback_url = auth_data.callback_url

            success, connect_response = await self.request(
                method="GET",
                url=callback_url,
                timeout=30,
                allow_redirects=False
            )
            # Step 3: Follow callback redirect
            callback_response = connect_response

            connect_url = callback_response['location']
            logger.debug(f"{self.user} Got connect URL: {connect_url}")

            # Step 4: Complete connection
            connect_headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Referer": "https://x.com/",
                "DNT": "1",
                "Sec-GPC": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "cross-site",
                "Sec-Fetch-User": "?1",
                "Priority": "u=0, i",
            }

            success, connect_response = await self.request(
                method="GET",
                url=connect_url,
                headers=connect_headers,
                timeout=30,
                allow_redirects=False
            )

            # Check if connection was successful
            logger.success(f"{self.user} Twitter connected")
            self.twitter_client.is_connected = True
            await self.twitter_client.close()
            return True

        except Exception as e:
            logger.error(f"{self.user} Error connecting Twitter: {str(e)}")
            await self.twitter_client.close()
            return False

    async def disconnect_twitter(self) -> bool:
        """
        Disconnects Twitter account from the site

        Returns:
            Success status
        """
        try:
            headers = {
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://loyalty.campnetwork.xyz",
                "Referer": "https://loyalty.campnetwork.xyz/loyalty?editProfile=1&modalTab=social",
                "Content-Length": "0",
            }

            # Send disconnect request
            success, response = await self.request(
                method="POST",
                url=self.TWITTER_DISCONNECT_URL,
                headers=headers,
                timeout=30
            )

            if success:
                logger.success(f"{self.user} Twitter successfully disconnected")
                self.twitter_client.is_connected = False
                return True
            else:
                logger.error(f"{self.user} Failed to disconnect Twitter: {response}")
                return False

        except Exception as e:
            logger.error(f"{self.user} Error disconnecting Twitter: {str(e)}")
            return False
