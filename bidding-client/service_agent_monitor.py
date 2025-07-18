#!/usr/bin/env python3
"""
A2A-Aptos Bidding System - Service Agent Monitor Service
Background service that automatically monitors new tasks and places bids
"""

import time
import requests
import json
import os
import asyncio
import sys
import signal
from typing import Dict, List, Optional
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
    format_task_id,
    format_amount,
    DEFAULT_PROFILE
)

# Global shutdown event
shutdown_event = asyncio.Event()

def signal_handler(signum, frame):
    """Signal handler"""
    print(f"\nReceived signal {signum}, gracefully stopping service...")
    shutdown_event.set()


class ServiceAgentMonitor:
    """Service Agent monitoring and bidding service"""
    
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Get configuration from environment variables
        self.platform_address = os.getenv("PLATFORM_ADDRESS")
        self.node_url = os.getenv("APTOS_NODE_URL", "https://fullnode.devnet.aptoslabs.com/v1")
        self.indexer_url = os.getenv("APTOS_INDEXER_URL", "https://api.devnet.aptoslabs.com/v1/graphql")
        self.service_agent_profile = os.getenv("SERVICE_AGENT_PROFILE", "service_agent")
        
        # Monitor configuration
        self.poll_interval = int(os.getenv("MONITOR_POLL_INTERVAL", 30))
        self.bid_price_ratio = float(os.getenv("BID_PRICE_RATIO", 0.8))
        self.reputation_score = int(os.getenv("SERVICE_AGENT_REPUTATION", 90))
        
        # State file
        self.state_file = "monitor_state.json"
        
        # Event type
        self.event_type = f"{self.platform_address}::bidding_system::TaskPublishedEvent"
        
        # Validate required configuration
        if not self.platform_address:
            print("Error: Please set PLATFORM_ADDRESS in .env file")
            sys.exit(1)
        
        print("--- Service Agent Monitor Service Initialization ---")
        print(f"Platform Address: {self.platform_address}")
        print(f"Node URL: {self.node_url}")
        print(f"Indexer URL: {self.indexer_url}")
        print(f"Poll Interval: {self.poll_interval} seconds")
        print(f"Bidding Strategy: {self.bid_price_ratio * 100}% of budget")
        print(f"Reputation Score: {self.reputation_score}")
        print("--------------------------------------------------")
    
    def save_state(self, last_sequence_number: int):
        """Save the last processed event sequence number"""
        state = {"last_processed_sequence_number": last_sequence_number}
        try:
            with open(self.state_file, "w") as f:
                json.dump(state, f)
            print(f"    [State] State saved, sequence number: {last_sequence_number}")
        except IOError as e:
            print(f"    [State] Error: Unable to write state file '{self.state_file}': {e}")
    
    def load_state(self) -> int:
        """Load the last processed event sequence number"""
        if not os.path.exists(self.state_file):
            return 0
        
        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)
                return int(state.get("last_processed_sequence_number", 0))
        except (IOError, json.JSONDecodeError) as e:
            print(f"    [State] Warning: Unable to read state file, starting from beginning. Error: {e}")
            return 0
    
    def query_indexer_for_new_tasks(self, last_processed_seq_num: int) -> List[Dict]:
        """Query new task publication events through Indexer API"""
        query = """
        query GetNewTaskEvents($platform_address: String!, $event_type: String!, $last_seq_num: bigint!) {
          events(
            where: {
              account_address: { _eq: $platform_address },
              type: { _eq: $event_type },
              sequence_number: { _gt: $last_seq_num }
            },
            order_by: { sequence_number: asc },
            limit: 25
          ) {
            sequence_number
            data
          }
        }
        """
        
        variables = {
            "platform_address": self.platform_address,
            "event_type": self.event_type,
            "last_seq_num": last_processed_seq_num
        }
        
        try:
            response = requests.post(
                self.indexer_url,
                json={"query": query, "variables": variables},
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            if "errors" in data:
                print(f"GraphQL query error: {data['errors']}")
                return []
            
            events = data.get("data", {}).get("events", [])
            return events
            
        except requests.RequestException as e:
            print(f"Indexer query error: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            return []
    
    async def place_bid(self, task_id: str, bid_price: int, reputation: int) -> bool:
        """Submit bid"""
        print(f"Bidding on task '{task_id}', price: {format_amount(bid_price)}, reputation: {reputation}")
        
        try:
            client, bidder_account = await get_client_and_account(self.service_agent_profile)
            bidder_addr = str(bidder_account.address())
            
            # Build transaction payload
            task_id_bytes = format_task_id(task_id)
            payload = EntryFunction.natural(
                f"{self.platform_address}::bidding_system",
                "place_bid",
                [],
                [
                    TransactionArgument(AccountAddress.from_str(self.platform_address), Serializer.struct),
                    TransactionArgument(task_id_bytes, Serializer.sequence_serializer(Serializer.u8)),
                    TransactionArgument(bid_price, Serializer.u64),
                    TransactionArgument(reputation, Serializer.u64),
                ],
            )
            
            # Generate and sign transaction
            signed_transaction = await client.create_bcs_signed_transaction(
                bidder_account, TransactionPayload(payload)
            )
            
            # Submit transaction
            txn_hash = await client.submit_bcs_transaction(signed_transaction)
            print(f"  > Submitting transaction... Hash: {txn_hash}")
            
            # Wait for transaction confirmation
            await client.wait_for_transaction(txn_hash)
            tx_info = await client.transaction_by_hash(txn_hash)
            
            print(f"  > ✅ Bid successful! Transaction version: {tx_info['version']}")
            await client.close()
            return True
            
        except Exception as e:
            print(f"  > ❌ Bid failed: {e}")
            return False
    
    async def process_task_event(self, event: Dict) -> bool:
        """Process single task event"""
        try:
            current_seq_num = int(event["sequence_number"])
            task_data = event["data"]
            task_id = task_data["task_id"]
            max_budget = int(task_data["max_budget"])
            
            print(f"\n[New Task Found] ID: {task_id}, Budget: {format_amount(max_budget)}, Sequence: {current_seq_num}")
            
            # Calculate bid price (specified ratio of budget)
            bid_price = int(max_budget * self.bid_price_ratio)
            
            # Submit bid
            success = await self.place_bid(task_id, bid_price, self.reputation_score)
            
            if success:
                # Save state after successful bid
                self.save_state(current_seq_num)
                return True
            else:
                print(f"Failed to process task {task_id}, skipping state update")
                return False
                
        except Exception as e:
            print(f"Event processing failed: {e}")
            return False
    
    async def monitor_tasks(self):
        """Main monitoring loop"""
        last_seq_num = self.load_state()
        print(f"\n🚀 Service Agent monitor started, monitoring from sequence number {last_seq_num}...")
        print("Monitoring for new tasks", end="")
        
        try:
            while not shutdown_event.is_set():
                try:
                    # Query new events
                    events = self.query_indexer_for_new_tasks(last_seq_num)
                    
                    if not events:
                        print(".", end="", flush=True)
                        # Use wait_for to respond to stop signal
                        try:
                            await asyncio.wait_for(asyncio.sleep(self.poll_interval), timeout=1.0)
                        except asyncio.TimeoutError:
                            continue
                        continue
                    
                    # Process each event
                    for event in events:
                        # Check if need to stop
                        if shutdown_event.is_set():
                            print(f"\nReceived stop signal, saving current state...")
                            self.save_state(last_seq_num)
                            return
                            
                        success = await self.process_task_event(event)
                        if success:
                            last_seq_num = int(event["sequence_number"])
                        else:
                            # If processing fails, don't update sequence number, retry next time
                            break
                    
                    # Brief rest before continuing monitoring
                    try:
                        await asyncio.wait_for(asyncio.sleep(2), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue
                        
                except Exception as e:
                    print(f"\nError in monitoring loop: {e}")
                    print("Waiting 10 seconds before retry...")
                    try:
                        await asyncio.wait_for(asyncio.sleep(10), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue
                        
        finally:
            # Ensure final state is saved
            print(f"\nSaving final state...")
            self.save_state(last_seq_num)
            print("Monitor service stopped gracefully")


async def main():
    """Main function"""
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    monitor = ServiceAgentMonitor()
    
    try:
        await monitor.monitor_tasks()
    except Exception as e:
        print(f"Service execution failed: {e}")
        sys.exit(1)
    finally:
        print("Service completely stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # This should not be reached as signals are already handled
        print("\nProgram interrupted")
    except Exception as e:
        print(f"Program exited abnormally: {e}")
        sys.exit(1)