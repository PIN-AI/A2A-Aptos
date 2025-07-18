#!/usr/bin/env python3
"""
A2A-Aptos Bidding System - Deployment and Initialization Script
Deploy smart contracts and initialize platform
"""

import asyncio
import argparse
import os
import sys
from dotenv import load_dotenv
from aptos_sdk.bcs import Serializer
from aptos_sdk.account_address import AccountAddress
from aptos_sdk.transactions import (
    EntryFunction,
    TransactionPayload,
    TransactionArgument,
)
from common_bidding import (
    get_client_and_account,
    DEFAULT_PROFILE
)


class BiddingSystemDeployer:
    """Bidding system deployer"""
    
    def __init__(self, profile: str = DEFAULT_PROFILE):
        self.profile = profile
        load_dotenv()
        
    async def deploy_and_initialize(self):
        """Deploy contracts and initialize platform"""
        print("=" * 60)
        print("A2A-Aptos Bidding System Deployment and Initialization")
        print("=" * 60)
        
        try:
            client, deployer_account = await get_client_and_account(self.profile)
            deployer_addr = str(deployer_account.address())
            
            print(f"Deployer Address: {deployer_addr}")
            print(f"Profile: {self.profile}")
            print("")
            
            # Step 1: Check account balance
            print("Step 1: Check Account Balance")
            balance = await client.account_balance(deployer_addr)
            print(f"Account Balance: {balance / 100_000_000:.8f} APT")
            
            if balance < 1_000_000:  # Less than 0.01 APT
                print("Warning: Account balance is low, recommend requesting test tokens first")
                print("Run: aptos account fund-with-faucet --profile your_profile")
                print("")
            
            # Step 2: Compile contracts
            print("Step 2: Compile Smart Contracts")
            print("Please ensure you have run in project root: aptos move compile")
            print("")
            
            # Step 3: Deploy contracts
            print("Step 3: Deploy Smart Contracts")
            print("Please ensure you have run in project root: aptos move publish --profile your_profile")
            print("")
            
            # Step 4: Initialize platform
            print("Step 4: Initialize Bidding Platform")
            success = await self.initialize_platform(client, deployer_account, deployer_addr)
            
            if success:
                print("=" * 60)
                print("✅ Deployment and Initialization Complete!")
                print("=" * 60)
                print(f"Platform Address: {deployer_addr}")
                print("")
                print("Next Steps:")
                print("1. Add platform address to PLATFORM_ADDRESS in .env file")
                print("2. Create Personal Agent and Service Agent accounts")
                print("3. Request test tokens for accounts")
                print("4. Start monitoring service and CLI tools")
                print("")
                print("Example .env configuration:")
                print(f"PLATFORM_ADDRESS={deployer_addr}")
                print("PERSONAL_AGENT_PROFILE=personal_agent")
                print("SERVICE_AGENT_PROFILE=service_agent")
                
            else:
                print("❌ Initialization Failed")
                
        except Exception as e:
            print(f"Deployment failed: {e}")
            return False
        finally:
            await client.close()
            
        return True
    
    async def initialize_platform(self, client, deployer_account, deployer_addr: str) -> bool:
        """Initialize platform"""
        try:
            # Build transaction payload
            payload = EntryFunction.natural(
                f"{deployer_addr}::bidding_system",
                "initialize",
                [],
                [
                    TransactionArgument(AccountAddress.from_str(deployer_addr), Serializer.struct),
                ],
            )
            
            # Generate and sign transaction
            signed_transaction = await client.create_bcs_signed_transaction(
                deployer_account, TransactionPayload(payload)
            )
            
            # Submit transaction
            txn_hash = await client.submit_bcs_transaction(signed_transaction)
            print(f"Submitting initialization transaction... Hash: {txn_hash}")
            
            # Wait for transaction confirmation
            await client.wait_for_transaction(txn_hash)
            tx_info = await client.transaction_by_hash(txn_hash)
            
            print(f"✅ Platform initialization successful! Transaction version: {tx_info['version']}")
            return True
            
        except Exception as e:
            print(f"❌ Platform initialization failed: {e}")
            return False


async def setup_accounts():
    """Account setup helper function"""
    print("=" * 60)
    print("Account Setup Guide")
    print("=" * 60)
    
    print("1. Create deployer account (usually task_manager_dev):")
    print("   aptos init --profile task_manager_dev --network devnet")
    print("")
    
    print("2. Create Personal Agent account:")
    print("   aptos init --profile personal_agent --network devnet")
    print("")
    
    print("3. Create Service Agent account:")
    print("   aptos init --profile service_agent --network devnet")
    print("")
    
    print("4. Request test tokens for all accounts:")
    print("   aptos account fund-with-faucet --profile task_manager_dev")
    print("   aptos account fund-with-faucet --profile personal_agent")
    print("   aptos account fund-with-faucet --profile service_agent")
    print("")
    
    print("5. Compile and deploy contracts:")
    print("   aptos move compile")
    print("   aptos move publish --profile task_manager_dev")
    print("")


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="A2A-Aptos Bidding System Deployment Tool")
    parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE,
        help=f"Specify Aptos CLI profile (default: {DEFAULT_PROFILE})"
    )
    parser.add_argument(
        "--setup-accounts",
        action="store_true",
        help="Show account setup guide"
    )
    parser.add_argument(
        "--initialize-only",
        action="store_true",
        help="Initialize platform only (assuming contracts are already deployed)"
    )
    
    args = parser.parse_args()
    
    if args.setup_accounts:
        await setup_accounts()
        return
    
    deployer = BiddingSystemDeployer(args.profile)
    
    if args.initialize_only:
        # Initialize platform only
        try:
            client, deployer_account = await get_client_and_account(args.profile)
            deployer_addr = str(deployer_account.address())
            
            print(f"Initializing platform... Deployer: {deployer_addr}")
            success = await deployer.initialize_platform(client, deployer_account, deployer_addr)
            
            if success:
                print("✅ Platform initialization complete!")
            else:
                print("❌ Platform initialization failed!")
                
            await client.close()
            
        except Exception as e:
            print(f"Initialization failed: {e}")
            sys.exit(1)
    else:
        # Complete deployment process
        await deployer.deploy_and_initialize()


if __name__ == "__main__":
    asyncio.run(main())