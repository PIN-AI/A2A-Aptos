#!/usr/bin/env python3
"""
Aptos Bidding System - View Task Script
Query task details, bidding status and information
"""

import argparse
import asyncio
from common_bidding import (
    get_client_and_account, 
    get_platform_address,
    format_task_id,
    print_task_info,
    print_bid_info,
    DEFAULT_PROFILE
)


async def view_task(
    profile: str,
    platform_addr: str,
    task_id: str,
):
    """View task details"""
    
    client, account = await get_client_and_account(profile)
    
    print("=" * 50)
    print("View Task Information")
    print("=" * 50)
    print(f"Platform Address: {platform_addr}")
    print(f"Task ID: {task_id}")
    print("")
    
    try:
        # Convert task ID to hexadecimal format
        task_id_hex = "0x" + task_id.encode('utf-8').hex()
        
        # Call get_task view function
        result = await client.view(
            f"{platform_addr}::bidding_system::get_task",
            [],
            [platform_addr, task_id_hex]
        )
        
        if result:
            # Assume returned data is task struct data
            task_data = result  # Use result directly, not first element
            
            print("Task Details:")
            print("-" * 30)
            # Print raw data for now as structure may differ
            print(f"Raw task data: {task_data}")
            print("")
            
            # Get bidding information
            bid_result = await client.view(
                f"{platform_addr}::bidding_system::get_task_bids",
                [],
                [platform_addr, task_id_hex]
            )
            
            if bid_result:
                bids = bid_result
                print(f"Bidding information: {bids}")
                print("")
            else:
                print("No bidding information available")
        else:
            print("Task not found")
            return False
        
        return True
        
    except Exception as e:
        print(f"Task query failed: {e}")
        return False
    finally:
        await client.close()


async def check_task_exists(
    profile: str,
    platform_addr: str,
    task_id: str,
):
    """Check if task exists"""
    
    client, account = await get_client_and_account(profile)
    
    try:
        # Convert task ID to hexadecimal format
        task_id_hex = "0x" + task_id.encode('utf-8').hex()
        
        # Call task_exists view function
        result = await client.view(
            f"{platform_addr}::bidding_system::task_exists",
            [],
            [platform_addr, task_id_hex]
        )
        
        exists = result if result else False
        print(f"Task {task_id} exists: {exists}")
        return exists
        
    except Exception as e:
        print(f"Failed to check task existence: {e}")
        return False
    finally:
        await client.close()


async def main():
    parser = argparse.ArgumentParser(description="View task information")
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
    parser.add_argument(
        "--check-exists",
        action="store_true",
        help="Only check if task exists"
    )
    
    args = parser.parse_args()
    
    # Get platform address
    platform_addr = args.platform if args.platform else get_platform_address(DEFAULT_PROFILE)
    
    # Validate parameters
    if len(args.task_id.strip()) == 0:
        print("Error: Task ID cannot be empty")
        return
    
    # Execute query
    if args.check_exists:
        await check_task_exists(args.profile, platform_addr, args.task_id)
    else:
        success = await view_task(args.profile, platform_addr, args.task_id)
        
        if success:
            print("Task query complete!")
        else:
            print("Task query failed!")


if __name__ == "__main__":
    asyncio.run(main())