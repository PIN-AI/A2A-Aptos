#!/usr/bin/env python3
"""
A2A-Aptos Bidding System - Personal Agent CLI
Command-line tool for Personal Agent to publish tasks and manage bidding
"""

import argparse
import asyncio
import uuid
import os
import sys
from typing import Optional
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
    get_platform_address,
    format_task_id,
    format_amount,
    format_status,
    print_task_info,
    STATUS_NAMES,
    DEFAULT_PROFILE
)


class PersonalAgentCLI:
    """Personal Agent command-line tool"""
    
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Get settings from environment variables or config file
        self.platform_address = os.getenv("PLATFORM_ADDRESS")
        self.personal_agent_profile = os.getenv("PERSONAL_AGENT_PROFILE", "personal_agent")
        self.service_agent_profile = os.getenv("SERVICE_AGENT_PROFILE", "service_agent")
        
        if not self.platform_address:
            print("Error: Please set PLATFORM_ADDRESS in .env file")
            sys.exit(1)
    
    async def initialize_platform(self):
        """Initialize bidding platform"""
        print("=" * 50)
        print("Initialize Bidding Platform")
        print("=" * 50)
        
        client, deployer_account = await get_client_and_account(self.personal_agent_profile)
        deployer_addr = str(deployer_account.address())
        
        print(f"Deployer: {deployer_addr}")
        print(f"Platform Address: {self.platform_address}")
        print("")
        
        try:
            # Build transaction payload
            payload = EntryFunction.natural(
                f"{self.platform_address}::bidding_system",
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
            print(f"Submitting transaction... Hash: {txn_hash}")
            
            # Wait for transaction confirmation
            await client.wait_for_transaction(txn_hash)
            tx_info = await client.transaction_by_hash(txn_hash)
            
            print(f"Platform initialization successful! Transaction version: {tx_info['version']}")
            print("Platform is ready, you can start publishing tasks.")
            
            return True
            
        except Exception as e:
            print(f"Platform initialization failed: {e}")
            return False
        finally:
            await client.close()
    
    async def publish_task(self, task_id: str, description: str, max_budget: int, deadline_seconds: int):
        """Publish task"""
        print("=" * 50)
        print("Publish Task to Bidding Platform")
        print("=" * 50)
        
        client, creator_account = await get_client_and_account(self.personal_agent_profile)
        creator_addr = str(creator_account.address())
        
        print(f"Creator: {creator_addr}")
        print(f"Platform Address: {self.platform_address}")
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
                f"{self.platform_address}::bidding_system",
                "publish_task",
                [],
                [
                    TransactionArgument(AccountAddress.from_str(self.platform_address), Serializer.struct),
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
            
            print(f"Task published successfully! Transaction version: {tx_info['version']}")
            print(f"Funds escrowed: {format_amount(max_budget)}")
            print("")
            print(f"==> Task '{task_id}' has been published. Please note this ID for future operations. <==")
            print("Service providers can now bid on this task.")
            
            return True
            
        except Exception as e:
            print(f"Task publication failed: {e}")
            return False
        finally:
            await client.close()
    
    async def select_winner(self, task_id: str):
        """Select winner"""
        print("=" * 50)
        print("Select Task Winner")
        print("=" * 50)
        
        client, creator_account = await get_client_and_account(self.personal_agent_profile)
        creator_addr = str(creator_account.address())
        
        print(f"Executor: {creator_addr}")
        print(f"Task ID: {task_id}")
        print("")
        
        try:
            # Build transaction payload
            task_id_bytes = format_task_id(task_id)
            payload = EntryFunction.natural(
                f"{self.platform_address}::bidding_system",
                "select_winner",
                [],
                [
                    TransactionArgument(AccountAddress.from_str(self.platform_address), Serializer.struct),
                    TransactionArgument(task_id_bytes, Serializer.sequence_serializer(Serializer.u8)),
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
            
            print(f"Winner selection successful! Transaction version: {tx_info['version']}")
            print("Task has been assigned to the winner.")
            
            return True
            
        except Exception as e:
            print(f"Winner selection failed: {e}")
            return False
        finally:
            await client.close()
    
    async def complete_task(self, task_id: str):
        """Complete task (executed by Service Agent)"""
        print("=" * 50)
        print("Complete Task")
        print("=" * 50)
        
        client, service_account = await get_client_and_account(self.service_agent_profile)
        service_addr = str(service_account.address())
        
        print(f"Service Agent: {service_addr}")
        print(f"Task ID: {task_id}")
        print("")
        
        try:
            # Build transaction payload
            task_id_bytes = format_task_id(task_id)
            payload = EntryFunction.natural(
                f"{self.platform_address}::bidding_system",
                "complete_task",
                [],
                [
                    TransactionArgument(AccountAddress.from_str(self.platform_address), Serializer.struct),
                    TransactionArgument(task_id_bytes, Serializer.sequence_serializer(Serializer.u8)),
                ],
            )
            
            # Generate and sign transaction
            signed_transaction = await client.create_bcs_signed_transaction(
                service_account, TransactionPayload(payload)
            )
            
            # Submit transaction
            txn_hash = await client.submit_bcs_transaction(signed_transaction)
            print(f"Submitting transaction... Hash: {txn_hash}")
            
            # Wait for transaction confirmation
            await client.wait_for_transaction(txn_hash)
            tx_info = await client.transaction_by_hash(txn_hash)
            
            print(f"Task completion successful! Transaction version: {tx_info['version']}")
            print("Funds have been settled to Service Agent.")
            
            return True
            
        except Exception as e:
            print(f"Task completion failed: {e}")
            return False
        finally:
            await client.close()
    
    async def get_task_status(self, task_id: str):
        """Query task status"""
        print("=" * 50)
        print("Query Task Status")
        print("=" * 50)
        
        client, _ = await get_client_and_account(self.personal_agent_profile)
        
        try:
            # Get BiddingPlatform resource
            resource_type = f"{self.platform_address}::bidding_system::BiddingPlatform"
            resource = await client.account_resource(
                AccountAddress.from_str(self.platform_address),
                resource_type
            )
            
            # Get tasks table handle
            tasks_handle = resource["data"]["tasks"]["inner"]["buckets"]["inner"]["buckets"][0]["inner"]["kvs"][0]["key"]
            
            # Query specific task
            key_type = "vector<u8>"
            value_type = f"{self.platform_address}::bidding_system::Task"
            task_id_hex = task_id.encode('utf-8').hex()
            
            task_data = await client.get_table_item(
                tasks_handle,
                key_type,
                value_type,
                task_id_hex
            )
            
            print(f"Task ID: {task_id}")
            print_task_info(task_data)
            
            # Display bidding information
            bids = task_data.get('bids', [])
            if bids:
                print(f"Number of bids: {len(bids)}")
                print("Bid list:")
                for i, bid in enumerate(bids, 1):
                    print(f"  [{i}] Bidder: {bid['bidder']}")
                    print(f"      Price: {format_amount(bid['price'])}")
                    print(f"      Reputation: {bid['reputation_score']}")
                    print(f"      Time: {bid['timestamp']}")
                    print()
            else:
                print("Bid list: No bids or cleared")
            
            return True
            
        except Exception as e:
            print(f"Task status query failed: {e}")
            return False
        finally:
            await client.close()


async def main():
    """Main entry function"""
    cli = PersonalAgentCLI()
    
    parser = argparse.ArgumentParser(
        description="A2A-Aptos Personal Agent CLI - Tool for interacting with bidding platform"
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available subcommands")
    
    # Initialize platform
    subparsers.add_parser("init", help="Initialize platform (only needs to be executed once after deployment)")
    
    # Publish task
    p_publish = subparsers.add_parser("publish", help="Publish a new task")
    p_publish.add_argument("description", type=str, help="Detailed description of the task")
    p_publish.add_argument("--budget", type=int, required=True, 
                           help="Maximum budget (unit: Octas, e.g., 100000000 represents 1 APT)")
    p_publish.add_argument("--deadline", type=int, default=3600,
                           help="Bidding deadline (seconds from now, default is 3600 seconds)")
    p_publish.add_argument("--task-id", type=str,
                           help="Task ID (auto-generated if not specified)")
    
    # Select winner
    p_select = subparsers.add_parser("select-winner", help="Select a winner for the task")
    p_select.add_argument("task_id", type=str, help="Task ID obtained from 'publish' command")
    
    # Complete task
    p_complete = subparsers.add_parser("complete", help="Mark task as completed (executed by winning Service Agent)")
    p_complete.add_argument("task_id", type=str, help="Task ID")
    
    # Query status
    p_status = subparsers.add_parser("status", help="Query detailed status of the task")
    p_status.add_argument("task_id", type=str, help="Task ID")
    
    args = parser.parse_args()
    
    try:
        if args.command == "init":
            await cli.initialize_platform()
        elif args.command == "publish":
            task_id = args.task_id if args.task_id else f"task-{uuid.uuid4().hex[:8]}"
            await cli.publish_task(task_id, args.description, args.budget, args.deadline)
        elif args.command == "select-winner":
            await cli.select_winner(args.task_id)
        elif args.command == "complete":
            await cli.complete_task(args.task_id)
        elif args.command == "status":
            await cli.get_task_status(args.task_id)
    except KeyboardInterrupt:
        print("\nOperation cancelled")
    except Exception as e:
        print(f"Execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())