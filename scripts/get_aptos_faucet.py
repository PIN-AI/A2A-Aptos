#!/usr/bin/env python3
"""Auto get Aptos devnet test coins"""

import asyncio
import os
import sys
import httpx
import json
import time
from typing import Optional

# Add project path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../samples/python'))

from common.aptos_config import AptosConfig

async def request_faucet_funds(address: str, amount: int = 100_000_000) -> bool:
    """Request Aptos devnet faucet funds
    
    Args:
        address: Aptos address
        amount: Request amount (unit: octas, default 1 APT = 100_000_000 octas)
        
    Returns:
        bool: Whether the request is successful
    """
    faucet_url = "https://faucet.devnet.aptoslabs.com"
    
    print(f"Requesting {amount / 100_000_000} APT for address {address}...")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{faucet_url}/mint",
                params={
                    "address": address,
                    "amount": amount
                }
            )
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    # Handle different response formats
                    if isinstance(result, list) and len(result) > 0:
                        # Response is an array
                        tx_hash = result[0] if result else "N/A"
                        print(f"✅ Successfully got test coins! Transaction hash: {tx_hash}")
                    elif isinstance(result, dict):
                        # Response is an object
                        tx_hash = result.get('hash', result.get('txHash', 'N/A'))
                        print(f"✅ Successfully got test coins! Transaction hash: {tx_hash}")
                    else:
                        # Other formats
                        print(f"✅ Successfully got test coins! Response: {result}")
                    return True
                except json.JSONDecodeError:
                    # If not JSON, but status code is 200, also consider it successful
                    print(f"✅ Successfully got test coins! Response: {response.text}")
                    return True
            else:
                print(f"❌ Request failed: {response.status_code} - {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Request exception: {e}")
        return False

async def check_balance_and_request_if_needed(private_key: str, min_balance: int = 10_000_000) -> bool:
    """Check balance, if insufficient, automatically request test coins
    
    Args:
        private_key: Aptos private key
        min_balance: Minimum balance requirement (unit: octas)
        
    Returns:
        bool: Whether there is enough balance
    """
    try:
        config = AptosConfig(private_key=private_key)
        
        if not config.address:
            print("❌ Unable to generate address from private key")
            return False
            
        address = str(config.address)
        print(f"Check balance of address {address}...")
        
        # Check network connection
        if not await config.is_connected():
            print("❌ Unable to connect to Aptos network")
            return False
        
        # Get current balance
        try:
            current_balance = await config.get_account_balance()
            print(f"Current balance: {current_balance / 100_000_000} APT ({current_balance} octas)")
            
            if current_balance >= min_balance:
                print(f"✅ Balance is sufficient (>= {min_balance / 100_000_000} APT)")
                return True
            else:
                print(f"⚠️ Balance is insufficient (< {min_balance / 100_000_000} APT), requesting test coins...")
                
                # Request test coins
                success = await request_faucet_funds(address)
                
                if success:
                    # Wait for a few seconds to confirm the transaction
                    print("Waiting for transaction confirmation...")
                    await asyncio.sleep(5)
                    
                    # Re-check balance
                    new_balance = await config.get_account_balance()
                    print(f"New balance: {new_balance / 100_000_000} APT ({new_balance} octas)")
                    
                    return new_balance >= min_balance
                else:
                    return False
                    
        except Exception as e:
            print(f"⚠️ Failed to get balance: {e}")
            print("Trying to request test coins directly...")
            return await request_faucet_funds(address)
            
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

async def main():
    """Main function"""
    print("Aptos Devnet test coins auto-request tool")
    print("=" * 50)
    
    # Get private key from environment variable or command line argument
    private_key = os.environ.get('APTOS_PRIVATE_KEY')
    
    if len(sys.argv) > 1:
        private_key = sys.argv[1]
    
    if not private_key:
        print("❌ Please provide Aptos private key")
        print("Usage:")
        print("  python get_aptos_faucet.py <private_key>")
        print("  or set environment variable APTOS_PRIVATE_KEY")
        return False
    
    # Remove 0x prefix (if exists)
    if private_key.startswith('0x'):
        private_key = private_key[2:]
    
    success = await check_balance_and_request_if_needed(private_key)
    
    if success:
        print("✅ Account balance is sufficient, can perform transactions")
        return True
    else:
        print("❌ Unable to get enough test coins")
        return False

if __name__ == '__main__':
    result = asyncio.run(main())
    sys.exit(0 if result else 1) 