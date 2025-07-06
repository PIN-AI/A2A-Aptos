#!/usr/bin/env python3
"""自动获取 Aptos devnet 测试币的脚本"""

import asyncio
import os
import sys
import httpx
import json
import time
from typing import Optional

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../samples/python'))

from common.aptos_config import AptosConfig

async def request_faucet_funds(address: str, amount: int = 100_000_000) -> bool:
    """请求 Aptos devnet faucet 资金
    
    Args:
        address: Aptos 地址
        amount: 请求的金额 (单位: octas，默认 1 APT = 100_000_000 octas)
        
    Returns:
        bool: 是否成功
    """
    faucet_url = "https://faucet.devnet.aptoslabs.com"
    
    print(f"正在为地址 {address} 请求 {amount / 100_000_000} APT...")
    
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
                    # 处理不同的响应格式
                    if isinstance(result, list) and len(result) > 0:
                        # 响应是数组格式
                        tx_hash = result[0] if result else "N/A"
                        print(f"✅ 成功获取测试币！交易哈希: {tx_hash}")
                    elif isinstance(result, dict):
                        # 响应是对象格式
                        tx_hash = result.get('hash', result.get('txHash', 'N/A'))
                        print(f"✅ 成功获取测试币！交易哈希: {tx_hash}")
                    else:
                        # 其他格式
                        print(f"✅ 成功获取测试币！响应: {result}")
                    return True
                except json.JSONDecodeError:
                    # 如果不是JSON，但状态码是200，也认为成功
                    print(f"✅ 成功获取测试币！响应: {response.text}")
                    return True
            else:
                print(f"❌ 请求失败: {response.status_code} - {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False

async def check_balance_and_request_if_needed(private_key: str, min_balance: int = 10_000_000) -> bool:
    """检查余额，如果不足则自动请求测试币
    
    Args:
        private_key: Aptos 私钥
        min_balance: 最小余额要求 (单位: octas)
        
    Returns:
        bool: 是否有足够余额
    """
    try:
        config = AptosConfig(private_key=private_key)
        
        if not config.address:
            print("❌ 无法从私钥生成地址")
            return False
            
        address = str(config.address)
        print(f"Check balance of address {address}...")
        
        # 检查网络连接
        if not await config.is_connected():
            print("❌ 无法连接到 Aptos 网络")
            return False
        
        # 获取当前余额
        try:
            current_balance = await config.get_account_balance()
            print(f"Current balance: {current_balance / 100_000_000} APT ({current_balance} octas)")
            
            if current_balance >= min_balance:
                print(f"✅ Balance is sufficient (>= {min_balance / 100_000_000} APT)")
                return True
            else:
                print(f"⚠️ Balance is insufficient (< {min_balance / 100_000_000} APT), requesting test coins...")
                
                # 请求测试币
                success = await request_faucet_funds(address)
                
                if success:
                    # 等待几秒让交易确认
                    print("等待交易确认...")
                    await asyncio.sleep(5)
                    
                    # 重新检查余额
                    new_balance = await config.get_account_balance()
                    print(f"新余额: {new_balance / 100_000_000} APT ({new_balance} octas)")
                    
                    return new_balance >= min_balance
                else:
                    return False
                    
        except Exception as e:
            print(f"⚠️ 获取余额失败: {e}")
            print("尝试直接请求测试币...")
            return await request_faucet_funds(address)
            
    except Exception as e:
        print(f"❌ 配置错误: {e}")
        return False

async def main():
    """主函数"""
    print("Aptos Devnet 测试币自动获取工具")
    print("=" * 50)
    
    # 从环境变量或命令行参数获取私钥
    private_key = os.environ.get('APTOS_PRIVATE_KEY')
    
    if len(sys.argv) > 1:
        private_key = sys.argv[1]
    
    if not private_key:
        print("❌ 请提供 Aptos 私钥")
        print("用法:")
        print("  python get_aptos_faucet.py <private_key>")
        print("  或设置环境变量 APTOS_PRIVATE_KEY")
        return False
    
    # 移除0x前缀（如果存在）
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