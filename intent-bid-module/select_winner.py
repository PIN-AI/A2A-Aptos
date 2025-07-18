#!/usr/bin/env python3
"""
Aptos Bidding System - Select Winner Script
Personal Agent selects the winner for a task
"""

import argparse
import asyncio
from aptos_sdk.bcs import Serializer
from aptos_sdk.account_address import AccountAddress
from aptos_sdk.transactions import (
    EntryFunction,
    TransactionPayload,
    TransactionArgument,
)
from common_bidding import (
    get_client_and_account, 
    get_platform_address,
    format_task_id,
    DEFAULT_PROFILE
)


async def select_winner(
    profile: str,
    platform_addr: str,
    task_id: str,
):
    """Select the winner for a task"""
    
    client, executor_account = await get_client_and_account(profile)
    executor_addr = str(executor_account.address())
    
    print("=" * 50)
    print("Select Winner")
    print("=" * 50)
    print(f"Executor: {executor_addr}")
    print(f"Platform Address: {platform_addr}")
    print(f"Task ID: {task_id}")
    print("")
    
    try:
        # Convert task ID to byte array
        task_id_bytes = format_task_id(task_id)
        
        # Build transaction payload
        payload = EntryFunction.natural(
            f"{platform_addr}::bidding_system",
            "select_winner",
            [], # No type parameters
            [
                TransactionArgument(AccountAddress.from_str(platform_addr), Serializer.struct),
                TransactionArgument(task_id_bytes, Serializer.sequence_serializer(Serializer.u8)),
            ],
        )
        
        # Generate and sign transaction
        signed_transaction = await client.create_bcs_signed_transaction(
            executor_account, TransactionPayload(payload)
        )
        
        # Submit transaction
        txn_hash = await client.submit_bcs_transaction(signed_transaction)
        print(f"Submitting transaction... Hash: {txn_hash}")
        
        # Wait for transaction confirmation
        await client.wait_for_transaction(txn_hash)
        tx_info = await client.transaction_by_hash(txn_hash)
        
        print(f"Winner selection successful! Transaction version: {tx_info['version']}")
        print("")
        print("Best bidder selected based on price and reputation score.")
        print("Winner can now start executing the task and call complete_task when finished.")
        
        return True
        
    except Exception as e:
        print(f"Winner selection failed: {e}")
        return False
    finally:
        await client.close()


async def main():
    parser = argparse.ArgumentParser(description="Select the winner for a task")
    parser.add_argument("task_id", type=str, help="Unique ID of the task")
    parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE,
        help=f"Specify Aptos CLI profile (default: {DEFAULT_PROFILE})"
    )
    parser.add_argument(
        "--platform",
        help="Platform address (default from profile)"
    )
    
    args = parser.parse_args()
    
    # Get platform address
    platform_addr = args.platform if args.platform else get_platform_address(args.profile)
    
    # Validate parameters
    if len(args.task_id.strip()) == 0:
        print("Error: Task ID cannot be empty")
        return
    
    # Select winner
    success = await select_winner(
        args.profile,
        platform_addr,
        args.task_id,
    )
    
    if success:
        print("Winner selection complete!")
    else:
        print("Winner selection failed!")


if __name__ == "__main__":
    asyncio.run(main())