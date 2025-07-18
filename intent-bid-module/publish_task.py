#!/usr/bin/env python3
"""
Aptos Bidding System - Publish Task Script
Personal Agent publishes tasks and escrows funds
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
    format_amount,
    DEFAULT_PROFILE
)


async def publish_task(
    profile: str,
    platform_addr: str,
    task_id: str,
    description: str,
    max_budget: int,
    deadline_seconds: int,
):
    """Publish task to bidding platform"""
    
    client, creator_account = await get_client_and_account(profile)
    creator_addr = str(creator_account.address())
    
    print("=" * 50)
    print("Publish Task to Bidding Platform")
    print("=" * 50)
    print(f"Creator: {creator_addr}")
    print(f"Platform Address: {platform_addr}")
    print(f"Task ID: {task_id}")
    print(f"Description: {description}")
    print(f"Max Budget: {format_amount(max_budget)}")
    print(f"Deadline: {deadline_seconds} seconds")
    print("")
    
    try:
        # Convert task ID to byte array
        task_id_bytes = format_task_id(task_id)
        
        # Build transaction payload
        payload = EntryFunction.natural(
            f"{platform_addr}::bidding_system",
            "publish_task",
            [], # No type parameters
            [
                TransactionArgument(AccountAddress.from_str(platform_addr), Serializer.struct),
                TransactionArgument(task_id_bytes, Serializer.sequence_serializer(Serializer.u8)),
                TransactionArgument(description, Serializer.str),
                TransactionArgument(max_budget, Serializer.u64),
                TransactionArgument(deadline_seconds, Serializer.u64),
            ],
        )
        
        # Generate and sign transaction
        signed_transaction = await client.create_bcs_signed_transaction(
            creator_account, TransactionPayload(payload)
        )
        
        # Submit transaction
        txn_hash = await client.submit_bcs_transaction(signed_transaction)
        print(f"Submitting transaction... Hash: {txn_hash}")
        
        # Wait for transaction confirmation
        await client.wait_for_transaction(txn_hash)
        tx_info = await client.transaction_by_hash(txn_hash)
        
        print(f"Task publication successful! Transaction version: {tx_info['version']}")
        print(f"Funds escrowed: {format_amount(max_budget)}")
        print("")
        print("Service providers can now bid on this task.")
        
        return True
        
    except Exception as e:
        print(f"Task publication failed: {e}")
        return False
    finally:
        await client.close()


async def main():
    parser = argparse.ArgumentParser(description="Publish task to bidding platform")
    parser.add_argument("task_id", type=str, help="Unique ID of the task")
    parser.add_argument("description", type=str, help="Task description")
    parser.add_argument("max_budget", type=int, help="Maximum budget (Octas)")
    parser.add_argument("deadline_seconds", type=int, help="Deadline (seconds)")
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
    if args.max_budget <= 0:
        print("Error: Maximum budget must be greater than 0")
        return
    
    if args.deadline_seconds <= 0:
        print("Error: Deadline must be greater than 0")
        return
    
    if len(args.task_id.strip()) == 0:
        print("Error: Task ID cannot be empty")
        return
    
    # Publish task
    success = await publish_task(
        args.profile,
        platform_addr,
        args.task_id,
        args.description,
        args.max_budget,
        args.deadline_seconds,
    )
    
    if success:
        print("Task publication complete!")
    else:
        print("Task publication failed!")


if __name__ == "__main__":
    asyncio.run(main())