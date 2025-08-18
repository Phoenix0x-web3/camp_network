from libs.eth_async.classes import Singleton
from libs.eth_async.data.models import RawContract, DefaultABIs
from libs.eth_async.utils.files import read_json
from data.config import ABIS_DIR


class Settings:
    pass

class Contracts(Singleton):

    ETH = RawContract(
        title='ETH',
        address='0x0000000000000000000000000000000000000000',
        abi=DefaultABIs.Token
    )

    BASE_CAMP = RawContract(
        title="BASE_CAMP",
        address="0x72E2160e41C467D7437cAe4d76Ac4FdC2D475e68",
        abi=read_json(path=(ABIS_DIR, "rarible.json")),
    )

    AURA = RawContract(
        title="AURA",
        address="0x42b978985F1b0676f7224ddBCa76D67A5D4a4dc3",
        abi=read_json(path=(ABIS_DIR, "rarible.json")),
    )

    STICKY_PLEB = RawContract(
        title="STICKY_PLEB",
        address="0x0d7516f4A6823F6F11a8F1C292E5DF1A6fF5775b",
        abi=read_json(path=(ABIS_DIR, "rarible.json")),
    )

    CLIMB = RawContract(
        title="CLIMB",
        address="0x3785F882e823F3436Df2e669Fc9f7490525f47d4",
        abi=read_json(path=(ABIS_DIR, "rarible.json")),
    )

    PICTOGRAPHS = RawContract(
        title="PICTOGRAPHS",
        address="0x37Cbfa07386dD09297575e6C699fe45611AC12FE",
        abi=read_json(path=(ABIS_DIR, "rarible.json")),
    )
    TOKEN_TAILS = RawContract(
        title="TOKEN_TAILS",
        address="0xa0D4687483F049c53e6EC8cBCbc0332C74180168",
        abi=read_json(path=(ABIS_DIR, "tokenTails.json")),
    )

    OMNI_HUB = RawContract(
        title="OMNI_HUB",
        address="0x29248D49a64Df624fecC543624beaB16904d0F3f",
        abi=read_json(path=(ABIS_DIR, "rarible.json")),
    )

    TAVERN_QUEST = RawContract(
        title="TAVERN_QUEST",
        address="0x294246b7353081763BF57e05D827816Cec4B9093",
        abi=read_json(path=(ABIS_DIR, "rarible.json")),
    )

    MINT_PAD = RawContract(
        title="MINT_PAD",
        address="0x00000000009a1E02f00E280dcfA4C81c55724212",
        abi=read_json(path=(ABIS_DIR, "rarible.json")),
    )

    MINT_PAD_CHECK = RawContract(
        title="MINT_PAD_CHECK",
        address="0xac6f313c90C5A4C38811766Ff09b4394921F8538",
        abi=read_json(path=(ABIS_DIR, "rarible.json")),
    )

    REMIX = RawContract(
        title="REMIX",
        address="0xF90733b9eCDa3b49C250B2C3E3E42c96fC93324E",
        abi=read_json(path=(ABIS_DIR, "remix.json"))
    )
    BLEETZ = RawContract(
        title="BLEETZ",
        address="0x0b0A5B8e848b27a05D5cf45CAab72BC82dF48546",
        abi='[{"inputs":[],"name":"mintGamerID","outputs":[],"stateMutability":"nonpayable","type":"function"}]'
    )
    CHAINBILLS = RawContract(
        title="CHAINBILLS",
        address="0x92e67Bfe49466b18ccDF2A3A28B234AB68374c60",
        abi=read_json(path=(ABIS_DIR, "chainbills.json"))
    )
    CONFT = RawContract(
        title="CONFT",
        address="0x7A72942d0F7C4d8909dC1f078319E97F06701092",
        abi=read_json(path=(ABIS_DIR, "conft.json"))
    )
    COPASS = RawContract(
        title="COPASS",
        address="0x2907aD6D787Df0eAA53b6C1C8dd6948475234C3f",
        abi=read_json(path=(ABIS_DIR, "copass.json"))
    )
    MERV = RawContract(
        title="MERV",
        address="0xe5e5bE029793A4481287Be2BFc37e2D38316c422",
        abi=read_json(path=(ABIS_DIR, "merv.json"))
    )
    MYSPHERE_POST = RawContract(
        title="MYSPHERE_POST",
        address="0x177Af844a3c7A1749dE97656a5d84b6373Fc350E",
        abi=read_json(path=(ABIS_DIR, "mysphere.json"))
    )
    MYSPHERE_NFT = RawContract(
        title="MYSPHERE_NFT",
        address="0x1eD74B27f846C699A90926daD057A7f6FD22C126",
        abi=read_json(path=(ABIS_DIR, "mysphere.json"))
    )
    MYSTERY_BOXES_TOKEN_TAILS = [
        RawContract(
            title="CAMP_1",
            address="0xa0D4687483F049c53e6EC8cBCbc0332C74180168",
            abi=read_json(path=(ABIS_DIR, "tokenTails.json"))
        ),
        RawContract(
            title="CAMP_2",
            address="0x0A65888A4F76D821A3148620866BC65A5db599BB",
            abi=read_json(path=(ABIS_DIR, "tokenTails.json"))
        ),
        RawContract(
            title="CAMP_3",
            address="0xec735A2Ba32703215b3e40d669C61FBd849b422a",
            abi=read_json(path=(ABIS_DIR, "tokenTails.json"))
        ),
    ]
