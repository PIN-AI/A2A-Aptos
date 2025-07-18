#!/usr/bin/env python3
"""
Aptos Bidding System - Platform Statistics Script
View overall platform statistics
"""

import argparse
import asyncio
from common_bidding import (
    get_client_and_account, 
    get_platform_address,
    print_platform_stats,
    DEFAULT_PROFILE
)


async def view_platform_stats(
    profile: str,
    platform_addr: str,
):
    """View platform statistics"""
    
    client, account = await get_client_and_account(profile)
    
    print("=" * 50)
    print("Platform Statistics")
    print("=" * 50)
    print(f"Platform Address: {platform_addr}")
    print("")
    
    try:
        # Call get_platform_stats view function
        result = await client.view(
            f"{platform_addr}::bidding_system::get_platform_stats",
            [],
            [platform_addr]
        )
        
        if result:
            # Returns (total_tasks, completed_tasks, cancelled_tasks) tuple
            stats = result  # Use result directly
            
            print("Platform Statistics:")
            print("-" * 30)
            # Print raw data for now
            print(f"Raw statistics data: {stats}")
            print("")
            
            # Get platform resource status
            try:
                resource_type = f"{platform_addr}::bidding_system::BiddingPlatform"
                resources = await client.account_resources(platform_addr)
                
                platform_resource = None
                for resource in resources:
                    if resource['type'] == resource_type:
                        platform_resource = resource
                        break
                
                if platform_resource:
                    print("Platform Resource Status:")
                    print("-" * 30)
                    print("✓ BiddingPlatform resource initialized")
                    print(f"Resource data: {platform_resource['data']}")
                else:
                    print("⚠️ BiddingPlatform resource not found")
                    
            except Exception as e:
                print(f"Failed to get platform resource status: {e}")
        else:
            print("Unable to get platform statistics")
            return False
        
        return True
        
    except Exception as e:
        print(f"Platform statistics query failed: {e}")
        return False
    finally:
        await client.close()


async def main():
    parser = argparse.ArgumentParser(description="View platform statistics")
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
    
    # View platform statistics
    success = await view_platform_stats(args.profile, platform_addr)
    
    if success:
        print("Platform statistics query complete!")
    else:
        print("Platform statistics query failed!")


if __name__ == "__main__":
    asyncio.run(main())