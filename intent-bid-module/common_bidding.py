"""
Aptos Bidding System - Common Module
Python SDK helper tools based on bidding_system.move
"""

import yaml
import os
from aptos_sdk.async_client import RestClient, ClientConfig
from aptos_sdk.account import Account

# --- Configuration ---

# Devnet node and Faucet URLs
NODE_URL = "https://api.devnet.aptoslabs.com/v1"
FAUCET_URL = "https://faucet.devnet.aptoslabs.com"

# API Key for rate limiting
API_KEY = "aptoslabs_ZYXEWFj9U8Y_KzPc9M8Z7N42zdvZKuRWwLMARnskLzTTh"

# Default profile path
DEFAULT_PROFILE = "task_manager_dev"

# bidding_system module name
BIDDING_MODULE = "bidding_system"

# Task status constants
STATUS_PUBLISHED = 1
STATUS_ASSIGNED = 2
STATUS_COMPLETED = 3
STATUS_CANCELLED = 4

# Status name mapping
STATUS_NAMES = {
    STATUS_PUBLISHED: "PUBLISHED",
    STATUS_ASSIGNED: "ASSIGNED", 
    STATUS_COMPLETED: "COMPLETED",
    STATUS_CANCELLED: "CANCELLED"
}

# --- Core Functions ---

def load_account_from_profile(profile: str) -> Account:
    """Load specified profile account from .aptos/config.yaml"""
    
    # Prioritize project local config file, then global config file
    # Look for .aptos config in project root directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.join(current_dir, "..", "..")  # Back to project root directory
    local_config_path = os.path.join(project_root, ".aptos", "config.yaml")
    
    # Also check .aptos config in current directory
    current_config_path = os.path.join(".aptos", "config.yaml")
    global_config_path = os.path.expanduser("~/.aptos/config.yaml")
    
    config_path = ""

    if os.path.exists(local_config_path):
        config_path = local_config_path
    elif os.path.exists(current_config_path):
        config_path = current_config_path
    elif os.path.exists(global_config_path):
        config_path = global_config_path
    else:
        raise FileNotFoundError(
            f"Aptos config file not found in:\n"
            f"  - Project root: {local_config_path}\n"
            f"  - Current dir: {current_config_path}\n" 
            f"  - Global: {global_config_path}\n"
            f"Please run 'aptos init' to create configuration."
        )

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    if "profiles" not in config or profile not in config["profiles"]:
        raise ValueError(f"Profile '{profile}' not found in aptos config file.")

    private_key = config["profiles"][profile].get("private_key")
    if not private_key:
        raise ValueError(f"Private key not found for profile '{profile}'.")
        
    return Account.load_key(private_key)


async def get_client_and_account(profile: str = DEFAULT_PROFILE) -> tuple[RestClient, Account]:
    """
    Create an Aptos REST client and load account from specified profile.
    
    Returns:
        A tuple (RestClient, Account)
    """
    # Create ClientConfig with API key
    client_config = ClientConfig(api_key=API_KEY)
    
    # Create RestClient instance
    client = RestClient(NODE_URL, client_config)
    
    account = load_account_from_profile(profile)
    return client, account


def get_platform_address(profile: str = DEFAULT_PROFILE) -> str:
    """Get platform address (get account address from config file)"""
    account = load_account_from_profile(profile)
    return str(account.address())


def get_function_id(platform_addr: str, function_name: str) -> str:
    """Construct function ID"""
    return f"{platform_addr}::{BIDDING_MODULE}::{function_name}"


def format_task_id(task_id: str) -> bytes:
    """Convert string task ID to byte array"""
    return task_id.encode('utf-8')


def format_status(status: int) -> str:
    """Format status display"""
    return STATUS_NAMES.get(status, f"UNKNOWN({status})")


def format_amount(amount_octas: int) -> str:
    """Format amount display (Octas to APT)"""
    apt_amount = amount_octas / 100_000_000
    return f"{apt_amount:.8f} APT ({amount_octas} Octas)"


def print_task_info(task_data: dict):
    """Print task information"""
    print(f"Task ID: {task_data.get('id', 'N/A')}")
    print(f"Creator: {task_data.get('creator', 'N/A')}")
    print(f"Description: {task_data.get('description', 'N/A')}")
    print(f"Max Budget: {format_amount(task_data.get('max_budget', 0))}")
    print(f"Deadline: {task_data.get('deadline', 'N/A')}")
    print(f"Status: {format_status(task_data.get('status', 0))}")
    print(f"Created At: {task_data.get('created_at', 'N/A')}")
    
    if task_data.get('winner') and task_data.get('winner') != "0x0":
        print(f"Winner: {task_data.get('winner')}")
        print(f"Winning Price: {format_amount(task_data.get('winning_price', 0))}")
    
    if task_data.get('completed_at', 0) > 0:
        print(f"Completed At: {task_data.get('completed_at')}")


def print_bid_info(bid_data: dict):
    """Print bid information"""
    print(f"Bidder: {bid_data.get('bidder', 'N/A')}")
    print(f"Price: {format_amount(bid_data.get('price', 0))}")
    print(f"Reputation Score: {bid_data.get('reputation_score', 0)}")
    print(f"Submitted At: {bid_data.get('timestamp', 'N/A')}")


def print_platform_stats(stats: tuple):
    """Print platform statistics"""
    total_tasks, completed_tasks, cancelled_tasks = stats
    print(f"Total Tasks: {total_tasks}")
    print(f"Completed Tasks: {completed_tasks}")
    print(f"Cancelled Tasks: {cancelled_tasks}")
    print(f"Success Rate: {(completed_tasks / total_tasks * 100) if total_tasks > 0 else 0:.2f}%")


if __name__ == '__main__':
    # Simple test to verify configuration loading
    try:
        account = load_account_from_profile(DEFAULT_PROFILE)
        print(f"Successfully loaded profile '{DEFAULT_PROFILE}'")
        print(f"Account Address: {account.address()}")
        print(f"Platform Address: {get_platform_address()}")
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")