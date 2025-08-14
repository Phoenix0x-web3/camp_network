from utils.db_api.models import Base, Wallet
from utils.db_api.db import DB

from data.config import WALLETS_DB

def get_wallets(sqlite_query: bool = False) -> list[Wallet]:
    if sqlite_query:
        return db.execute('SELECT * FROM wallets')

    return db.all(entities=Wallet)


def get_wallet_by_private_key(private_key: str, sqlite_query: bool = False) -> Wallet | None:
    if sqlite_query:
        return db.execute('SELECT * FROM wallets WHERE private_key = ?', (private_key,), True)

    return db.one(Wallet, Wallet.private_key == private_key)
  
def get_wallet_by_address(address: str, sqlite_query: bool = False) -> Wallet | None:
    if sqlite_query:
        return db.execute('SELECT * FROM wallets WHERE private_key = ?', (private_key,), True)

    return db.one(Wallet, Wallet.address == address)
  
def update_points(private_key: str, points: int | None) -> bool:
    """
    Updates the Points for a wallet with the given private_key.
    
    Args:
        private_key: The private key of the wallet to update
        points: The update points number
    Returns:
        bool: True if update was successful, False if wallet not found
    """
    if not points:
        return False

    wallet = db.one(Wallet, Wallet.private_key == private_key)
    if not wallet:
        return False
    
    wallet.points = points
    db.commit()
    return True

def update_twitter_token(private_key: str, updated_token: str | None) -> bool:
    """
    Updates the Twitter token for a wallet with the given private_key.
    
    Args:
        private_key: The private key of the wallet to update
        new_token: The new Twitter token to set
    
    Returns:
        bool: True if update was successful, False if wallet not found
    """
    if not updated_token:
        return False

    wallet = db.one(Wallet, Wallet.private_key == private_key)
    if not wallet:
        return False
    
    wallet.twitter_token = updated_token
    db.commit()
    return True

def update_faucet_time(private_key:str, new_time) -> bool:
    wallet = db.one(Wallet, Wallet.private_key == private_key)
    if not wallet:
        return False
    wallet.last_faucet_claim = new_time
    return True

def update_ref_code(private_key: str, ref_code: str | None) -> bool:
    """
    Updates the Ref Code token for Camp for a wallet with the given private_key.
    
    Args:
        private_key: The private key of the wallet to update
        new_token: The new Twitter token to set
    
    Returns:
        bool: True if update was successful, False if wallet not found
    """
    if not ref_code:
        return False

    wallet = db.one(Wallet, Wallet.private_key == private_key)
    if not wallet:
        return False
    
    wallet.ref_code = ref_code
    db.commit()
    return True

def replace_bad_proxy(private_key: str, new_proxy: str) -> bool:
    wallet = db.one(Wallet, Wallet.private_key == private_key)
    if not wallet:
        return False
    wallet.proxy = new_proxy
    wallet.proxy_status = "OK"
    db.commit()
    return True

def replace_bad_twitter(private_key: str, new_token: str) -> bool:
    wallet = db.one(Wallet, Wallet.private_key == private_key)
    if not wallet:
        return False
    wallet.twitter_token = new_token
    wallet.twitter_status = "OK"
    db.commit()
    return True

def mark_proxy_as_bad(private_key:str) -> bool:
    wallet = db.one(Wallet, Wallet.private_key == private_key)
    if not wallet:
        return False
    wallet.proxy_status = "BAD"
    db.commit()
    return True

def mark_twitter_as_bad(private_key:str) -> bool:
    wallet = db.one(Wallet, Wallet.private_key == private_key)
    if not wallet:
        return False
    wallet.twitter_status = "BAD"
    db.commit()
    return True

def mark_account_as_blocked(private_key:str) -> bool:
    wallet = db.one(Wallet, Wallet.private_key == private_key)
    if not wallet:
        return False
    wallet.account_blocked = True
    db.commit()
    return True

def get_wallets_with_bad_proxy() -> list:
    return db.all(Wallet, Wallet.proxy_status == "BAD")

def get_wallets_with_bad_twitter() -> list:
    return db.all(Wallet, Wallet.twitter_status == "BAD")

def get_completed_quests(private_key: str):
    wallet = db.one(Wallet, Wallet.private_key == private_key)
    if not wallet or not wallet.completed_quests:
        return []
    return wallet.completed_quests.split(",")

def mark_quest_completed(private_key: str, quest_id: str):
    wallet = db.one(Wallet, Wallet.private_key == private_key)
    if not wallet:
        return False
    completed_quests = (
        wallet.completed_quests.split(",") if wallet.completed_quests else []
    )

    # Добавляем задание, если его там нет
    if quest_id not in completed_quests:
        completed_quests.append(quest_id)

    # Обновляем поле в БД
    wallet.completed_quests = ",".join(completed_quests)
    db.commit()
    return True

def is_quest_completed(private_key: str, quest_id: str):
    wallet = db.one(Wallet, Wallet.private_key == private_key)
    if not wallet or not wallet.completed_quests:
        return False

    completed_quests = wallet.completed_quests.split(",")
    return quest_id in completed_quests

def get_available_ref_codes() -> list:
    result = db.all(Wallet, Wallet.ref_code != None)
    code = [code.ref_code for code in result]
    return code




db = DB(f'sqlite:///{WALLETS_DB}', echo=False, pool_recycle=3600, connect_args={'check_same_thread': False})
db.create_tables(Base)
