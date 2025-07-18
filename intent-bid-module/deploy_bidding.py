#!/usr/bin/env python3
"""
Aptos Bidding System - Deployment Script
Responsible for compiling, deploying and initializing bidding_system smart contracts
"""

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path
from aptos_sdk.bcs import Serializer
from aptos_sdk.transactions import (
    EntryFunction,
    TransactionPayload,
    TransactionArgument,
)
from common_bidding import get_client_and_account, get_platform_address, get_function_id, DEFAULT_PROFILE


class BiddingDeployer:
    def __init__(self, profile: str = DEFAULT_PROFILE):
        self.profile = profile
        self.project_root = Path(__file__).parent.parent.parent
        
    def run_command(self, cmd: list, cwd: Path = None) -> tuple[int, str, str]:
        """Execute command and return results"""
        if cwd is None:
            cwd = self.project_root
            
        print(f"Executing command: {' '.join(cmd)}")
        print(f"Working directory: {cwd}")
        
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True
        )
        
        return result.returncode, result.stdout, result.stderr
    
    def compile_contract(self) -> bool:
        """Compile smart contracts"""
        print("=" * 50)
        print("Step 1: Compile Smart Contracts")
        print("=" * 50)
        
        # Clean previous builds
        build_path = self.project_root / "build"
        if build_path.exists():
            import shutil
            shutil.rmtree(build_path)
            print("Cleaned old build files")
        
        # Compile contracts
        cmd = ["aptos", "move", "compile", "--save-metadata"]
        returncode, stdout, stderr = self.run_command(cmd)
        
        if returncode != 0:
            print(f"Compilation failed: {stderr}")
            return False
        
        print("Compilation successful!")
        print(f"Output: {stdout}")
        return True
    
    def run_tests(self) -> bool:
        """Run unit tests"""
        print("=" * 50)
        print("Step 2: Run Unit Tests")
        print("=" * 50)
        
        cmd = ["aptos", "move", "test"]
        returncode, stdout, stderr = self.run_command(cmd)
        
        if returncode != 0:
            print(f"Tests failed: {stderr}")
            return False
        
        print("Tests passed!")
        print(f"Output: {stdout}")
        return True
    
    def deploy_contract(self) -> bool:
        """Deploy smart contracts"""
        print("=" * 50)
        print("Step 3: Deploy Smart Contracts")
        print("=" * 50)
        
        platform_addr = get_platform_address(self.profile)
        print(f"Deploy Address: {platform_addr}")
        print(f"Using Profile: {self.profile}")
        
        # Deploy contracts
        cmd = [
            "aptos", "move", "publish",
            "--profile", self.profile,
            "--named-addresses", f"aptos_task_manager={platform_addr}",
            "--max-gas", "100000",
            "--gas-unit-price", "100",
            "--assume-yes"
        ]
        
        returncode, stdout, stderr = self.run_command(cmd)
        
        # Check for errors (distinguish warnings from errors)
        if returncode != 0:
            if "error" in stderr.lower() and "warning" not in stderr.lower():
                print(f"Deployment failed: {stderr}")
                return False
            else:
                print("Deployment contains warnings but may have succeeded:")
                print(f"Output: {stdout}")
                print(f"Warnings: {stderr}")
                # Continue to check if deployment actually succeeded
        else:
            print("Deployment successful!")
            print(f"Output: {stdout}")
        
        # Verify deployment actually succeeded - check if modules exist
        print("Verifying deployment status...")
        verify_cmd = ["aptos", "account", "list", "--profile", self.profile, "--query", "modules"]
        verify_returncode, verify_stdout, verify_stderr = self.run_command(verify_cmd)
        
        if verify_returncode == 0:
            import json
            try:
                result = json.loads(verify_stdout)
                modules = result.get("Result", [])
                
                # Check if bidding_system module is included
                has_bidding_system = any("bidding_system" in str(module) for module in modules)
                
                if has_bidding_system:
                    print("✓ bidding_system module deployed successfully")
                    return True
                else:
                    print("✗ bidding_system module not found")
                    print(f"Deployed modules: {modules}")
                    return False
                    
            except json.JSONDecodeError as e:
                print(f"Failed to parse module list: {e}")
                print(f"Raw output: {verify_stdout}")
                return False
        else:
            print(f"Failed to verify deployment status: {verify_stderr}")
            return False
    
    async def initialize_platform(self) -> bool:
        """Initialize bidding platform"""
        print("=" * 50)
        print("Step 4: Initialize Bidding Platform")
        print("=" * 50)
        
        try:
            client, account = await get_client_and_account(self.profile)
            platform_addr = str(account.address())
            
            print(f"Platform Address: {platform_addr}")
            print(f"Initializing BiddingPlatform resource...")
            
            # Build initialization transaction
            payload = EntryFunction.natural(
                f"{platform_addr}::bidding_system",
                "initialize",
                [],  # No type parameters
                []   # No function parameters
            )
            
            # Generate and sign transaction
            signed_transaction = await client.create_bcs_signed_transaction(
                account, TransactionPayload(payload)
            )
            
            # Submit transaction
            txn_hash = await client.submit_bcs_transaction(signed_transaction)
            print(f"Submitting transaction... Hash: {txn_hash}")
            
            # Wait for transaction confirmation
            await client.wait_for_transaction(txn_hash)
            tx_info = await client.transaction_by_hash(txn_hash)
            
            print(f"Initialization successful! Transaction version: {tx_info['version']}")
            return True
            
        except Exception as e:
            print(f"Initialization failed: {e}")
            return False
        finally:
            await client.close()
    
    async def verify_deployment(self) -> bool:
        """Verify deployment status"""
        print("=" * 50)
        print("Step 5: Verify Deployment Status")
        print("=" * 50)
        
        try:
            client, account = await get_client_and_account(self.profile)
            platform_addr = str(account.address())
            
            print(f"Checking platform address: {platform_addr}")
            
            # Check if platform resource exists
            resource_type = f"{platform_addr}::bidding_system::BiddingPlatform"
            try:
                resources = await client.account_resources(platform_addr)
                platform_resource = None
                
                for resource in resources:
                    if resource['type'] == resource_type:
                        platform_resource = resource
                        break
                
                if platform_resource:
                    print("✓ BiddingPlatform resource created")
                    print(f"  Platform stats: {platform_resource['data']}")
                    return True
                else:
                    print("✗ BiddingPlatform resource not found")
                    return False
                    
            except Exception as e:
                print(f"✗ Resource check failed: {e}")
                return False
                
        except Exception as e:
            print(f"Verification failed: {e}")
            return False
        finally:
            await client.close()
    
    async def full_deployment(self) -> bool:
        """Complete deployment process"""
        print("Aptos Bidding System Deployment Started")
        print(f"Profile: {self.profile}")
        print(f"Project Directory: {self.project_root}")
        
        # Step 1: Compile
        if not self.compile_contract():
            return False
        
        # Step 2: Test
        if not self.run_tests():
            return False
        
        # Step 3: Deploy
        if not self.deploy_contract():
            return False
        
        # Step 4: Initialize
        if not await self.initialize_platform():
            return False
        
        # Step 5: Verify
        if not await self.verify_deployment():
            return False
        
        print("=" * 50)
        print("Deployment Complete!")
        print("=" * 50)
        print(f"Platform Address: {get_platform_address(self.profile)}")
        print("You can now use the interaction scripts for operations.")
        
        return True


async def main():
    parser = argparse.ArgumentParser(description="Aptos Bidding System Deployment Tool")
    parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE,
        help=f"Specify Aptos CLI profile (default: {DEFAULT_PROFILE})"
    )
    parser.add_argument(
        "--step",
        choices=["compile", "test", "deploy", "init", "verify", "all"],
        default="all",
        help="Specify execution step (default: all)"
    )
    
    args = parser.parse_args()
    
    deployer = BiddingDeployer(args.profile)
    
    success = False
    
    if args.step == "compile":
        success = deployer.compile_contract()
    elif args.step == "test":
        success = deployer.run_tests()
    elif args.step == "deploy":
        success = deployer.deploy_contract()
    elif args.step == "init":
        success = await deployer.initialize_platform()
    elif args.step == "verify":
        success = await deployer.verify_deployment()
    elif args.step == "all":
        success = await deployer.full_deployment()
    
    if success:
        print("Operation completed successfully!")
        sys.exit(0)
    else:
        print("Operation failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())