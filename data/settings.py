import yaml
import sys
from libs.eth_async.classes import Singleton
from data.config import SETTINGS_FILE
from data.config import LOG_FILE, SETTINGS_FILE
from loguru import logger

class Settings(Singleton):
    def __init__(self):
        with open(SETTINGS_FILE, 'r') as file:
            json_data = yaml.safe_load(file) or {}

        self.private_key_encryption = json_data.get("private_key_encryption", False)
        self.threads = json_data.get("threads", 4)
        self.retry = json_data.get("retry", {})
        self.exact_wallets_to_run = json_data.get("exact_wallets_to_run", [])
        self.shuffle_wallets = json_data.get("shuffle_wallets", True)
        self.hide_wallet_address_log = json_data.get("hide_wallet_address_log", True)
        self.log_level = json_data.get("log_level", "INFO")
        self.sleep_after_each_cycle_hours = json_data.get("sleep_after_each_cycle_hours", 0)
        self.random_pause_start_wallet_min = json_data.get("random_pause_start_wallet",{}).get("min")
        self.random_pause_start_wallet_max = json_data.get("random_pause_start_wallet", {}).get("max")
        self.random_pause_between_actions_min = json_data.get("random_pause_between_actions", {}).get("min")
        self.random_pause_between_actions_max = json_data.get("random_pause_between_actions", {}).get("max")
        self.random_pause_between_twitter_actions_min = json_data.get("random_pause_between_twitter_actions", {}).get("min")
        self.random_pause_between_twitter_actions_max = json_data.get("random_pause_between_twitter_actions", {}).get("max")
        self.tg_bot_id = json_data.get("tg_bot_id", "")
        self.tg_user_id = json_data.get("tg_user_id", "")
        self.actual_ua = json_data.get("actual_ua", "")
        self.capmonster_api_key = json_data.get("capmonster_api_key", "")
        self.solvecaptcha_api_key = json_data.get("solvecaptcha_api_key", "")
        self.use_ref_code = json_data.get("use_ref_code", True)
        self.use_only_file_ref_code = json_data.get("use_only_file_ref_code", False)
        self.auto_replace_proxy = json_data.get("auto_replace_proxy ", True)
        self.auto_replace_twitter = json_data.get("auto_replace_twitter ", True)
        self.resources_max_failures = json_data.get("resources_max_failures", 3)
        self.onchain_actions = json_data.get("onchain_actions", [])
        self.multiple_actions = json_data.get("multiple_actions", True)
        self.use_faucet_if_balance = json_data.get("use_faucet_if_balance", False)
        self.quests_name_and_ids = json_data.get("quests_name_and_ids", {})
        self.quests_twitter = json_data.get("quests_twitter", {})
        self.use_imap = json_data.get("use_imap", False)
        self.imap_server = json_data.get("imap_server", "")
        self.imap_port = json_data.get("imap_port", "")

# Configure the logger based on the settings
settings = Settings()

if settings.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR"]:
    raise ValueError(f"Invalid log level: {settings.log_level}. Must be one of: DEBUG, INFO, WARNING, ERROR")
logger.remove()  # Remove the default logger
logger.add(sys.stderr, level=settings.log_level)

logger.add(LOG_FILE, level="DEBUG")