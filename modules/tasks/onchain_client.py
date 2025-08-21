import asyncio
import random
from loguru import logger

from data.settings import Settings
from utils.db_api.models import Wallet
from modules.tasks.camp_tasks.remix import Remix
from modules.tasks.camp_tasks.bleetz import Bleetz
from modules.tasks.camp_tasks.chainbills import ChainBillsCreate, ChainBillsWithdraw
from modules.tasks.camp_tasks.conft import CoNFT
from modules.tasks.camp_tasks.copass import CoPass
from modules.tasks.camp_tasks.merv import Merv
from modules.tasks.camp_tasks.mysphere import MySphere
from modules.tasks.camp_tasks.storychain import Storychain
from modules.tasks.camp_tasks.awana import Awana
from modules.tasks.camp_tasks.panenka import Panenka
from modules.tasks.camp_tasks.tokentails import TokenTails
from modules.tasks.camp_tasks.mint import MintFunctions
from modules.tasks.camp_tasks.scoreplay import Scoreplay
from libs.base import Base
from libs.eth_async.client import Client
from libs.eth_async.data.models import Networks
from data.models import Contracts


class CampOnchain(Base):
    def __init__(self, wallet: Wallet) -> None:
        self.wallet = wallet
        self.settings = Settings()
        self.client = Client(
            private_key=wallet.private_key, network=Networks.Camp, proxy=wallet.proxy
        )
        self.mint_funcs = MintFunctions(wallet=self.wallet)

    async def handle_actions(self) -> bool:
        start_delay = self.settings.random_pause_between_actions_min
        end_delay = self.settings.random_pause_between_actions_max
        actual_actions = random.sample(self.settings.onchain_actions, len(self.settings.onchain_actions))

        base_camp_contract = await self.client.contracts.get(contract_address=Contracts.BASE_CAMP)
        base_camp_max_mint = 50
        aura_contract = await self.client.contracts.get(contract_address=Contracts.AURA)
        aura_max_mint = 50
        sticky_pleb_contract = await self.client.contracts.get(contract_address=Contracts.STICKY_PLEB)
        sticky_pleb_max_mint = 1
        climb_contract = await self.client.contracts.get(contract_address=Contracts.CLIMB)
        climb_max_mint = 50
        pictographs_contract = await self.client.contracts.get(contract_address=Contracts.PICTOGRAPHS)
        pictographs_max_mint = 1
        omnihub_contract = await self.client.contracts.get(contract_address=Contracts.OMNI_HUB)
        omnihub_max_mint = 1
        tavern_quest_contract = await self.client.contracts.get(contract_address=Contracts.TAVERN_QUEST)
        tavern_quest_max_mint = 1
        mintpad_contract = await self.client.contracts.get(contract_address=Contracts.MINT_PAD)
        mintpad_contract_check = await self.client.contracts.get(contract_address=Contracts.MINT_PAD_CHECK)
        mintpad_max_mint = 50

        for action in actual_actions:
            try:
                logger.debug(f"{self.wallet} Processing action: {action}")

                if action == "remix":
                    remix = Remix(wallet=self.wallet)
                    success = await remix.run()
                    if not success:
                        continue
                elif action == "bleetz":
                    bleetz = Bleetz(wallet=self.wallet)
                    success = await bleetz.run()
                    if not success:
                        continue
                elif action == "chainbills":
                    chainbills = ChainBillsCreate(wallet=self.wallet)
                    success = await chainbills.run()
                    if not success:
                        continue
                    chainbills = ChainBillsWithdraw(wallet=self.wallet)
                    success = await chainbills.run()
                    if not success:
                        continue
                elif action == "conft":
                    conft = CoNFT(wallet=self.wallet)
                    success = await conft.run()
                    if not success:
                        continue
                elif action == "copass":
                    copass = CoPass(wallet=self.wallet)
                    success = await copass.run()
                    if not success:
                        continue
                elif action == "merv":
                    merv = Merv(wallet=self.wallet)
                    success = await merv.run()
                    if not success:
                        continue
                elif action == "mysphere":
                    mysphere = MySphere(wallet=self.wallet)
                    success = await mysphere.run()
                    if not success:
                        continue
                elif action == "storychain":
                    storychain = Storychain(wallet=self.wallet)
                    success = await storychain.run()
                    if not success:
                        continue
                elif action == "awana":
                    awana = Awana(wallet=self.wallet)
                    success = await awana.run()
                    if not success:
                        continue
                elif action == "panenka":
                    panenka = Panenka(wallet=self.wallet)
                    success = await panenka.run()
                    if not success:
                        continue
                elif action == "tokentails":
                    tokentails = TokenTails(wallet=self.wallet)
                    success = await tokentails.run()
                    if not success:
                        continue
                elif action == "scoreplay":
                    scoreplay = Scoreplay(wallet=self.wallet)
                    success = await scoreplay.run()
                    if not success:
                        continue
                elif action == "base_camp":
                    need_mint, quantity = await self.mint_funcs.need_mint_and_quantity(
                        contract=base_camp_contract, max_mint=base_camp_max_mint,action=action
                    )
                    if need_mint and quantity:
                        await self.mint_funcs.base_camp_mint(contract=base_camp_contract, quantity=quantity)
                    else:
                        continue
                elif action == "aura":
                    need_mint, quantity = await self.mint_funcs.need_mint_and_quantity(
                        contract=aura_contract, max_mint=aura_max_mint, action=action
                    )
                    if need_mint and quantity:
                        await self.mint_funcs.aura_mint(contract=aura_contract, quantity=quantity)
                    else:
                        continue
                elif action == "sticky_pleb":
                    need_mint, quantity = await self.mint_funcs.need_mint_and_quantity(
                        contract=sticky_pleb_contract, max_mint=sticky_pleb_max_mint, action=action
                    )
                    if need_mint and quantity:
                        await self.mint_funcs.sticky_pleb_mint(contract=sticky_pleb_contract, quantity=quantity)
                    else:
                        continue
                elif action == "climb":
                    need_mint, quantity = await self.mint_funcs.need_mint_and_quantity(
                        contract=climb_contract, max_mint=climb_max_mint, action=action
                    )
                    if need_mint and quantity:
                        await self.mint_funcs.climb_mint(contract=climb_contract, quantity=quantity)
                    else:
                        continue
                elif action == "pictographs":
                    need_mint, quantity = await self.mint_funcs.need_mint_and_quantity(
                        contract=pictographs_contract, max_mint=pictographs_max_mint, action=action
                    )
                    if need_mint and quantity:
                        await self.mint_funcs.pictographs_mint(contract=pictographs_contract)
                    else:
                        continue
                elif action == "omnihub_mint":
                    need_mint, quantity = await self.mint_funcs.need_mint_and_quantity(
                        contract=omnihub_contract, max_mint=omnihub_max_mint, action=action
                    )
                    if need_mint and quantity:
                        await self.mint_funcs.omnihub_mint(contract=omnihub_contract)
                    else:
                        continue
                elif action == "tavern_quest":
                    need_mint, quantity = await self.mint_funcs.need_mint_and_quantity(
                        contract=tavern_quest_contract, max_mint=tavern_quest_max_mint, action=action
                    )
                    if need_mint and quantity:
                        await self.mint_funcs.tavern_quest_mint(contract=tavern_quest_contract)
                    else:
                        continue
                elif action == "mintpad":
                    need_mint, quantity = await self.mint_funcs.need_mint_and_quantity(
                        contract=mintpad_contract_check, max_mint=mintpad_max_mint, action=action
                    )
                    if need_mint and quantity:
                        await self.mint_funcs.mintpad_mint(contract=mintpad_contract)
                    else:
                        continue
                else:
                    logger.warning(f"{self.wallet} Unknown action: {action}")
                    continue

                random_sleep = random.randint(start_delay, end_delay)
                logger.info(f"{self.wallet} sleep {random_sleep} seconds before next action")
                await asyncio.sleep(random_sleep)
            except Exception as e:
                continue

        logger.success(f"{self.wallet} Completed all actions processing")
        return True
