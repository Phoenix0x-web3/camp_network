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


import os
import datetime
import pandas as pd
from threading import Lock
 

write_lock = Lock()

def write_statistics(data, statistic_path, columns, mode='w'):
    directory = os.path.dirname(statistic_path)
    os.makedirs(directory, exist_ok=True)

    # If "append" requested but file doesn't exist yet, switch to write
    if mode == 'a' and not os.path.exists(statistic_path):
        mode = 'w'

    with write_lock:
        df = pd.DataFrame(data, columns=columns)
        df.to_csv(
            statistic_path,
            mode=mode,
            index=False,
            header=(mode != 'a'),    # no header when appending
            encoding='utf-8-sig'
        )
        logger.success(f"saved data to csv file length [{len(data)}]")
        
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
    
    async def iter_leaderboard(self, limit=1000):
        """
        Async generator that yields leaderboard items across all pages.
        Uses the last item's `id` as `startingAfter` for the next page.
        """
        headers = {
            'accept': '*/*',
            'cache-control': 'no-cache',
            'pragma': 'no-cache',
            'referer': 'https://loyalty.campnetwork.xyz/loyalty/leaderboard',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
        }

        base_params = {
            'limit': str(limit),
            'websiteId': '32afc5c9-f0fb-4938-9572-775dee0b4a2b',
            'organizationId': '26a1764f-5637-425e-89fa-2f3fb86e758c',
            'loyaltyCurrencyId': '7f74ae35-a6e2-496a-83ea-5b2e18769560',
            'sortDir': 'desc',
        }

        starting_after = None
        seen_cursors = set()  # safety to avoid loops
        count = 1
        while True:
            params = dict(base_params)
            if starting_after:
                params['startingAfter'] = starting_after

            ok, resp = await self.quest_client.request(
                url='https://loyalty.campnetwork.xyz/api/loyalty/leaderboard',
                method='GET',
                headers=headers,
                params=params
            )
            
 

            if not ok:
                # handle error
                return

            items = resp.get('data', []) or []
            if not items:
                break

            import asyncio
            await asyncio.sleep(0.5)  # small delay to avoid overwhelming the server
            # yield items to caller
            for item in items:
                yield item
       
            # prepare next page cursor
            
          
            
            starting_after = items[-1].get('id')
            if not resp.get('hasNextPage') or not starting_after:
                break

            amount = items[-1].get('amount', 0)
  
            logger.info(f"Fetched items from leaderboard page {count} amount {amount}")
            count += 1
            
          
            if int(amount) < 50:
                logger.info(f"Last item amount {amount} is less than 50, stopping iteration")
                break
            # loop guard
            if starting_after in seen_cursors:
                # server returned a repeated page/cursor; bail to avoid infinite loop
                break
            seen_cursors.add(starting_after)
    
    async def fetch_leaderboard_positions(self, limit=1000):
        results = []
        pos = 1

        async for item in self.iter_leaderboard(limit=limit):
            user = item.get("user") or {}
            address = user.get("walletAddress")

            try:
                points = int(item.get("amount") or 0)
            except (TypeError, ValueError):
                points = 0

            results.append({
                "position": pos,     # 1-based ranking
                "address": address,  # may be None if missing
                "points": points,
            })
            pos += 1

        return results

    async def show_statistics(self):
        logger.info(f"{self.user} showing statistics")
        if not self.auth_client.user_id:
            logger.info(f"{self.user} not authorized, performing authorization")
            auth_result = await self.login()
            

        leaderboard = await self.fetch_leaderboard_positions(limit=1000)
        leaderboard_sorted = sorted(leaderboard, key=lambda x: x["position"])

        # If you want by points (descending), use:
        # leaderboard_sorted = sorted(leaderboard, key=lambda x: x["points"], reverse=True)

        path = f"statistics/checker_statistics_{datetime.datetime.now():%Y-%m-%d-%H-%M-%S}.csv"
        columns = ["position", "address", "points"]

        write_statistics(leaderboard_sorted, path, columns, mode='w')
         
        return True
        # headers = {
        #     'accept': '*/*',
        #     'accept-language': 'en-US,en;q=0.9',
        #     'cache-control': 'no-cache',
        #     # 'cookie': 'cf_clearance=X3RUScmRvC5hE3kjdgZ6gZ5fVqhcLVktD6p4jz4FqjI-1755349355-1.2.1.1-xsRBPQUQprjSW1XxqNQU7hLM2CsBr5fk.PVm3mY9QsNwXYOvJmkB4Tn5lP6dxdUYQcFKHKN3k1YFFzKPXIwcvhn4upFiBATV7K4n67ip835BeVfY4wjuOzwXYXM55xKehYkHz.92h9y6v98eyOO3ckcijjvurHMJnOVp6kdtCL_PI3smWSm607KhT9sUEMzXBpOWkoyJPB4AuZxsoSlbLH_Hud0YQuvqAVFFcbaeSdw; __Secure-next-auth.callback-url=https%3A%2F%2Floyalty.campnetwork.xyz; __Host-next-auth.csrf-token=506d575d451868126b9c483f0613f19b03da42f72ee5ae795bf3b363a1fea562%7C03a21c6bd62df721831366fe5a92b4fc79e7364bde136bff1d85d0c6d0eb3cb4; _ga=GA1.1.1995493820.1755349362; AMP_ca1b91c797=JTdCJTIyZGV2aWNlSWQlMjIlM0ElMjIwYzRjOTk2YS02MDM5LTQ2MTItOTJiYS1hZDgxZTEyNWJiM2IlMjIlMkMlMjJzZXNzaW9uSWQlMjIlM0ExNzU1MzQ4NDQyODM1JTJDJTIyb3B0T3V0JTIyJTNBZmFsc2UlMkMlMjJsYXN0RXZlbnRUaW1lJTIyJTNBMTc1NTM0OTQyNjM2MSUyQyUyMmxhc3RFdmVudElkJTIyJTNBMTE5JTJDJTIycGFnZUNvdW50ZXIlMjIlM0E5JTdE; _ga_QKH2YTYNX7=GS2.1.s1755349361$o1$g1$t1755349426$j60$l0$h0',
        #     'pragma': 'no-cache',
        #     'priority': 'u=1, i',
        #     'referer': 'https://loyalty.campnetwork.xyz/loyalty/leaderboard',
        #     'sec-ch-ua': '"Not A(Brand";v="8", "Chromium";v="132", "Google Chrome";v="132"',
        #     'sec-ch-ua-arch': '"x86"',
        #     'sec-ch-ua-bitness': '"64"',
        #     'sec-ch-ua-full-version': '"132.0.6834.111"',
        #     'sec-ch-ua-full-version-list': '"Not A(Brand";v="8.0.0.0", "Chromium";v="132.0.6834.111", "Google Chrome";v="132.0.6834.111"',
        #     'sec-ch-ua-mobile': '?0',
        #     'sec-ch-ua-model': '""',
        #     'sec-ch-ua-platform': '"Windows"',
        #     'sec-ch-ua-platform-version': '"10.0.0"',
        #     'sec-fetch-dest': 'empty',
        #     'sec-fetch-mode': 'cors',
        #     'sec-fetch-site': 'same-origin',
        #     'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
        # }

        # params = {
        #     'limit': '1000',
        #     'websiteId': '32afc5c9-f0fb-4938-9572-775dee0b4a2b',
        #     'organizationId': '26a1764f-5637-425e-89fa-2f3fb86e758c',
        #     'loyaltyCurrencyId': '7f74ae35-a6e2-496a-83ea-5b2e18769560',
        #     'sortDir': 'desc',
        # }

    
    
        # headers = {k: v for k, v in headers.items() if v}  # Filter out empty values
        # response = await self.quest_client.request(url='https://loyalty.campnetwork.xyz/api/loyalty/leaderboard', method="GET", headers= headers, params=params)
        
    
        # response.json() 

        return True
        # if self.user.account_blocked:
        #     logger.warning(f"{self.user} account blocked")
        #     return False
        # if not self.auth_client.user_id:
        #     logger.info(f"{self.user} not authorized, performing authorization")
        #     auth_result = await self.login()

        #     if not auth_result[0]: 
        #         if isinstance(auth_result[1], str) and auth_result[1] == "RATE_LIMIT":
        #             logger.warning(
        #                 f"{self.user} account on hold due to rate limit"
        #             )
        #             return {"status": "RATE_LIMITED"}

        #         logger.error(
        #             f"{self.user} failed to authorize, quest execution impossible"
        #         )
        #         return False
        # return await self.quest_client.get_and_update_points()
    
    
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

