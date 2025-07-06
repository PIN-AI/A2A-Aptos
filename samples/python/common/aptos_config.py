"""Aptos区块链配置模块

提供Aptos网络连接、账户管理和合约配置功能。
"""
import logging
import os
from typing import Optional

from aptos_sdk.async_client import RestClient
from aptos_sdk.account import Account
from aptos_sdk.account_address import AccountAddress

# Configure logging to reduce verbosity
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class AptosConfig:
    """Aptos区块链配置类"""
    
    def __init__(self, private_key: Optional[str] = None, node_url: Optional[str] = None):
        # 连接到 Aptos 网络
        self.node_url = node_url or os.getenv('APTOS_NODE_URL', 'https://api.devnet.aptoslabs.com/v1')
        self.client = RestClient(self.node_url)
        
        # 账户配置
        private_key_hex = private_key or os.getenv('APTOS_PRIVATE_KEY')
        if private_key_hex:
            # 移除各种前缀（如果存在）
            if private_key_hex.startswith('ed25519-priv-0x'):
                private_key_hex = private_key_hex[15:]  # 移除 'ed25519-priv-0x'
            elif private_key_hex.startswith('0x'):
                private_key_hex = private_key_hex[2:]   # 移除 '0x'
            self.account = Account.load_key(private_key_hex)
            self.address = self.account.address()
        else:
            self.account = None
            self.address = None

        # 打印账户地址
        logger.info(f"Config account address: {self.address}")
        
        # 合约配置
        self.module_address = os.getenv('APTOS_MODULE_ADDRESS', '0x42e86d92f3d8645d290844f96451038efc722940fff706823dd3c0f8f67b46bd')
        self.module_name = 'task_manager'
        
        # 确保模块地址格式正确
        if not self.module_address.startswith('0x'):
            self.module_address = '0x' + self.module_address
    
    async def get_account_balance(self, account_address=None) -> int:
        """获取账户APT余额（以octas为单位）"""
        if account_address is None:
            account_address = self.address
        
        if account_address is None:
            raise ValueError("No account address available")
            
        return await self.client.account_balance(account_address)
    
    async def get_sequence_number(self, account_address=None) -> int:
        """获取账户序列号"""
        if account_address is None:
            account_address = self.address
            
        if account_address is None:
            raise ValueError("No account address available")
            
        return await self.client.account_sequence_number(account_address)
    
    def get_module_function_name(self, function_name: str) -> str:
        """获取完整的模块函数名"""
        return f"{self.module_address}::{self.module_name}::{function_name}"
    
    async def is_connected(self) -> bool:
        """检查是否连接到Aptos网络"""
        try:
            # 尝试获取链信息来验证连接
            ledger_info = await self.client.info()
            return ledger_info is not None
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Aptos network connection failed: {e}")
            return False
    
    def __str__(self) -> str:
        return f"AptosConfig(node_url={self.node_url}, address={self.address}, module={self.module_address}::{self.module_name})" 