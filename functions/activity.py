import asyncio
import random
from datetime import datetime, timedelta

from curl_cffi import AsyncSession
from loguru import logger

from functions.controller import Controller
from libs.eth_async.client import Client
from libs.eth_async.data.models import Networks
from utils.db_api.models import Wallet
from utils.db_api.wallet_api import db
from data.settings import Settings
from utils.encryption import check_encrypt_param


async def execute(wallets : Wallet, task_func, timeout_hours : int = 0):
    while True:
        semaphore = asyncio.Semaphore(min(len(wallets), Settings().threads))

        if Settings().shuffle_wallets:
            random.shuffle(wallets)
            
        async def sem_task(wallet : Wallet):
            async with semaphore:
                try:
                    if wallet.account_blocked:
                        logger.warning(f"{wallet} account blocked")
                        return False
                    await task_func(wallet)
                except Exception as e:
                    logger.error(f"[{wallet.id}] failed: {e}")

        tasks = [asyncio.create_task(sem_task(wallet)) for wallet in wallets]
        await asyncio.gather(*tasks, return_exceptions=True)

        if timeout_hours == 0:
            break
        
        logger.info(f"Sleeping for {timeout_hours} hours before the next iteration")
        await asyncio.sleep(timeout_hours * 60 * 60)
        
async def activity(action: int):
    check_encrypt_param()

    all_wallets = db.all(Wallet)

    # Filter wallets if EXACT_WALLETS_TO_USE is defined
    if Settings().exact_wallets_to_run:
        wallets = [wallet for i, wallet in enumerate(all_wallets, start=1) if i in Settings().exact_wallets_to_run]
    else:
        wallets = all_wallets

    if action == 1:
        await execute(wallets, complete_all_quests)
    elif action == 2:
        await execute(wallets, complete_regular_quests)
    elif action == 3:
        await execute(wallets, complete_twitter_quests)
    elif action == 4:
        await execute(wallets, complete_onchain)
    elif action == 5:
        await execute(wallets, complete_faucet)
    elif action == 6:
        await execute(wallets, update_points)

async def random_sleep_before_start(wallet):
    random_sleep = random.randint(Settings().random_pause_start_wallet_min, Settings().random_pause_start_wallet_max)
    logger.info(f"{wallet} sleep {random_sleep} seconds before start actions")
    await asyncio.sleep(random_sleep)

async def complete_all_quests(wallet):
    await random_sleep_before_start(wallet=wallet)
    client = Client(private_key=wallet.private_key, proxy=wallet.proxy, network=Networks.Camp)

    controller = Controller(client=client, wallet=wallet)

    await controller.complete_tw_and_regular_quests()

async def complete_regular_quests(wallet):
    await random_sleep_before_start(wallet=wallet)
    client = Client(private_key=wallet.private_key, proxy=wallet.proxy, network=Networks.Camp)

    controller = Controller(client=client, wallet=wallet)

    await controller.complete_regular_quests()

async def complete_twitter_quests(wallet):
    await random_sleep_before_start(wallet=wallet)
    client = Client(private_key=wallet.private_key, proxy=wallet.proxy, network=Networks.Camp)

    controller = Controller(client=client, wallet=wallet)

    await controller.complete_twitter_quests()

async def complete_onchain(wallet):
    await random_sleep_before_start(wallet=wallet)
    client = Client(private_key=wallet.private_key, proxy=wallet.proxy, network=Networks.Camp)

    controller = Controller(client=client, wallet=wallet)

    await controller.complete_onchain()

async def complete_faucet(wallet):
    await random_sleep_before_start(wallet=wallet)
    client = Client(private_key=wallet.private_key, proxy=wallet.proxy, network=Networks.Camp)

    controller = Controller(client=client, wallet=wallet)

    await controller.complete_onchain()

async def update_points(wallet):
    await random_sleep_before_start(wallet=wallet)
    client = Client(private_key=wallet.private_key, proxy=wallet.proxy, network=Networks.Camp)

    controller = Controller(client=client, wallet=wallet)

    await controller.update_points()

