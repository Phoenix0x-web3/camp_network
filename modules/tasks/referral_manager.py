import os
import random
from loguru import logger
from data import config

from utils.db_api.wallet_api import get_available_ref_codes


def load_ref_codes():
    """Load referral codes from file"""
    ref_codes_file = config.REF_CODES_FILE
    if os.path.exists(ref_codes_file) and os.path.getsize(ref_codes_file) > 0:
        with open(ref_codes_file, 'r') as file:
            return [line.strip() for line in file if line.strip()]
    return []


async def get_referral_code_for_registration(use_random_from_db: bool = True):
    """
    Get a referral code for registration
    
    Args:
        use_random_from_db: Use a random code from the database
        
    Returns:
        Referral code or None
    """
    # First try to load codes from file
    file_codes = load_ref_codes()
    
    # If specified to use random code from database and file is empty
    if use_random_from_db:
        try:
            # Get codes from database
            db_codes = get_available_ref_codes()
            
            if db_codes:
                return random.choice(db_codes)
            else:
                return random.choice(file_codes)
        except Exception as e:
            logger.error(f"Error retrieving referral codes from database: {str(e)}")
    
    # If there are codes in file, use them
    if file_codes:
        return random.choice(file_codes)
        
    return None


async def add_ref_code_to_file(ref_code: str) -> bool:
    """
    Add a referral code to the file
    
    Args:
        ref_code: Referral code
        
    Returns:
        Success status
    """
    try:
        with open(config.REF_CODES_FILE, 'a') as f:
            f.write(f"{ref_code}\n")
        return True
    except Exception as e:
        logger.error(f"Error adding code to file: {str(e)}")
        return False


async def update_ref_codes_file_from_db() -> bool:
    """
    Update the referral codes file from the database
    
    Returns:
        Success status
    """
    try:
        db_codes = get_available_ref_codes()
        
        if db_codes:
            with open(config.REF_CODES_FILE, 'w') as f:
                for code in db_codes:
                    f.write(f"{code}\n")
            return True
        return False
    except Exception as e:
        logger.error(f"Error updating codes file: {str(e)}")
        return False
