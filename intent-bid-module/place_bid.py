#!/usr/bin/env python3
"""
Aptos Bidding System - Bidding Script
Service Agent bids on published tasks
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


async def place_bid(
    profile: str,
    platform_addr: str,
    task_id: str,
    bid_price: int,
    reputation_score: int,
):
    """Bid on task"""
    
    client, bidder_account = await get_client_and_account(profile)
    bidder_addr = str(bidder_account.address())
    
    print("=" * 50)
    print("Submit Bid")
    print("=" * 50)
    print(f"Bidder: {bidder_addr}")
    print(f"Platform Address: {platform_addr}")
    print(f"Task ID: {task_id}")
    print(f"Bid Price: {format_amount(bid_price)}")
    print(f"Reputation Score: {reputation_score}")
    print("")
    
    try:
        # Convert task ID to byte array
        task_id_bytes = format_task_id(task_id)
        
        # Build transaction payload
        payload = EntryFunction.natural(
            f"{platform_addr}::bidding_system",
            "place_bid",
            [], # No type parameters
            [
                TransactionArgument(AccountAddress.from_str(platform_addr), Serializer.struct),
                TransactionArgument(task_id_bytes, Serializer.sequence_serializer(Serializer.u8)),
                TransactionArgument(bid_price, Serializer.u64),
                TransactionArgument(reputation_score, Serializer.u64),
            ],
        )
        
        # Generate and sign transaction
        signed_transaction = await client.create_bcs_signed_transaction(
            bidder_account, TransactionPayload(payload)
        )
        
        # Submit transaction
        txn_hash = await client.submit_bcs_transaction(signed_transaction)
        print(f"Submitting transaction... Hash: {txn_hash}")
        
        # Wait for transaction confirmation
        await client.wait_for_transaction(txn_hash)
        tx_info = await client.transaction_by_hash(txn_hash)
        
        print(f"Bid submission successful! Transaction version: {tx_info['version']}")
        print(f"Bid Price: {format_amount(bid_price)}")
        print("")
        print("Waiting for task creator to select winner...")
        
        return True
        
    except Exception as e:
        print(f"Bid failed: {e}")
        return False
    finally:
        await client.close()


async def main():
    parser = argparse.ArgumentParser(description="Bid on task")
    parser.add_argument("task_id", type=str, help="Unique ID of the task")
    parser.add_argument("bid_price", type=int, help="Bid price (Octas)")
    parser.add_argument("reputation_score", type=int, help="Reputation score (0-100)")
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
    platform_addr = args.platform if args.platform else get_platform_address(DEFAULT_PROFILE)
    
    # Validate parameters
    if args.bid_price <= 0:
        print("Error: Bid price must be greater than 0")
        return
    
    if args.reputation_score < 0 or args.reputation_score > 100:
        print("Error: Reputation score must be between 0-100")
        return
    
    if len(args.task_id.strip()) == 0:
        print("Error: Task ID cannot be empty")
        return
    
    print(f"args.profile: {args.profile}")
    print(f"platform_addr: {platform_addr}")
    
    # Submit bid
    success = await place_bid(
        args.profile,
        platform_addr,
        args.task_id,
        args.bid_price,
        args.reputation_score,
    )
    
    if success:
        print("Bid submission complete!")
    else:
        print("Bid submission failed!")


if __name__ == "__main__":
    asyncio.run(main())