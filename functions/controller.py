from libs.eth_async.client import Client
from libs.base import Base

from modules.camp_network.camp_client import CampNetworkClient
from utils.db_api.models import Wallet
from utils.logs_decorator import controller_log


class Controller:
    __controller__ = 'Controller'

    def __init__(self, client: Client, wallet: Wallet):
        #super().__init__(client)
        self.client = client
        self.wallet = wallet
        self.base = Base(client=client, wallet=wallet)
        self.camp_client = CampNetworkClient(user=wallet)

    @controller_log('Twitter and Regular Quests')
    async def complete_tw_and_regular_quests(self):
        return await self.camp_client.complete_twitter_and_regular_quests()
    @controller_log('Regular Quests')
    async def complete_regular_quests(self):
        return await self.camp_client.complete_all_quests()
    @controller_log('Twitter Quests')
    async def complete_twitter_quests(self):
        return await self.camp_client.complete_twitter_quests()
    @controller_log('Onchain Actions')
    async def complete_onchain(self):
        return await self.camp_client.complete_onchain()
    @controller_log('Faucet')
    async def complete_faucet(self):
        return await self.camp_client.complete_faucet()
