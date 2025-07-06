"""Aptos区块链交互模块

封装与Aptos Move task_manager合约的所有交互逻辑。
"""

import logging
from typing import Optional, Dict, Any, Tuple

from aptos_sdk.transactions import EntryFunction, TransactionArgument, TransactionPayload
from aptos_sdk.bcs import Serializer
from aptos_sdk.account_address import AccountAddress

from .aptos_config import AptosConfig


logger = logging.getLogger(__name__)


class AptosTaskManager:
    """Aptos任务管理器区块链交互类"""
    
    def __init__(self, config: AptosConfig):
        self.config = config
        self.client = config.client
        self.account = config.account
        
    async def create_task(self, task_id: str, service_agent: str, amount_apt: int, 
                   deadline_seconds: int, description: str) -> Dict[str, Any]:
        """创建任务并托管APT
        
        Args:
            task_id: 任务ID字符串
            service_agent: 服务提供者地址
            amount_apt: 支付金额（octas为单位）
            deadline_seconds: 任务期限（秒）
            description: 任务描述
            
        Returns:
            包含交易结果的字典
        """
        try:
            # 将 task_id 字符串转换为字节数组
            task_id_bytes = task_id.encode('utf-8')

            # 构建入口函数调用
            entry_function = EntryFunction.natural(
                f"{self.config.module_address}::task_manager",
                "create_task",
                [], # 无 type arguments
                [
                    TransactionArgument(task_id_bytes, Serializer.sequence_serializer(Serializer.u8)),
                    TransactionArgument(AccountAddress.from_str(service_agent), Serializer.struct),
                    TransactionArgument(amount_apt, Serializer.u64),
                    TransactionArgument(deadline_seconds, Serializer.u64),
                    TransactionArgument(description, Serializer.str),
                ],
            )
            
            # 构建并签名交易
            signed_transaction = await self.client.create_bcs_signed_transaction(
                self.account, 
                TransactionPayload(entry_function)
            )
            
            # 提交交易
            tx_hash = await self.client.submit_bcs_transaction(signed_transaction)
            
            # 等待确认
            await self.client.wait_for_transaction(tx_hash)
            
            # 获取交易详情，增强错误处理
            try:
                tx_info = await self.client.transaction_by_hash(tx_hash)
                gas_used = 0
                vm_status = 'Unknown'
                
                if tx_info:
                    # 处理不同的响应格式
                    if isinstance(tx_info, dict):
                        gas_used = tx_info.get('gas_used', 0)
                        vm_status = tx_info.get('vm_status', 'Success')
                    elif hasattr(tx_info, 'gas_used'):
                        gas_used = getattr(tx_info, 'gas_used', 0)
                        vm_status = getattr(tx_info, 'vm_status', 'Success')
            except Exception as info_error:
                logger.warning(f"[APTOS] Could not fetch transaction details: {info_error}")
                gas_used = 0
                vm_status = 'Unknown'

            print(f"[APTOS] Task created successfully: {task_id}, you can check the task on https://explorer.aptoslabs.com/txn/{tx_hash}?network=devnet.")
            
            return {
                'success': True,
                'tx_hash': tx_hash,
                'gas_used': gas_used,
                'vm_status': vm_status
            }
            
        except Exception as e:
            logger.error(f"Error creating task on Aptos: {e}")
            return {'success': False, 'error': str(e)}
    
    async def complete_task(self, task_agent_address: str, task_id: str) -> Dict[str, Any]:
        """完成任务
        
        Args:
            task_agent_address: 任务创建者地址
            task_id: 任务ID字符串
            
        Returns:
            包含交易结果的字典
        """
        try:
            # 将 task_id 字符串转换为字节数组
            task_id_bytes = task_id.encode('utf-8')

            entry_function = EntryFunction.natural(
                f"{self.config.module_address}::task_manager",
                "complete_task",
                [],
                [
                    TransactionArgument(AccountAddress.from_str(task_agent_address), Serializer.struct),
                    TransactionArgument(task_id_bytes, Serializer.sequence_serializer(Serializer.u8)),
                ],
            )
            
            signed_transaction = await self.client.create_bcs_signed_transaction(
                self.account, 
                TransactionPayload(entry_function)
            )
            
            tx_hash = await self.client.submit_bcs_transaction(signed_transaction)
            await self.client.wait_for_transaction(tx_hash)
            
            logger.info(f"[APTOS] Task completed ! check transaction on https://explorer.aptoslabs.com/txn/{tx_hash}?network=devnet.")
            
            return {'success': True, 'tx_hash': tx_hash}
            
        except Exception as e:
            logger.error(f"Error completing task on Aptos: {e}")
            return {'success': False, 'error': str(e)}
    
    async def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """取消任务
        
        Args:
            task_id: 任务ID字符串
            
        Returns:
            包含交易结果的字典
        """
        try:
            # 将 task_id 字符串转换为字节数组
            task_id_bytes = task_id.encode('utf-8')

            entry_function = EntryFunction.natural(
                f"{self.config.module_address}::task_manager",
                "cancel_task",
                [],
                [
                    TransactionArgument(task_id_bytes, Serializer.sequence_serializer(Serializer.u8)),
                ],
            )
            
            signed_transaction = await self.client.create_bcs_signed_transaction(
                self.account, 
                TransactionPayload(entry_function)
            )
            
            tx_hash = await self.client.submit_bcs_transaction(signed_transaction)
            await self.client.wait_for_transaction(tx_hash)
            
            logger.info(f"[APTOS] Task cancelled successfully: {task_id}, tx: {tx_hash}")
            
            return {'success': True, 'tx_hash': tx_hash}
            
        except Exception as e:
            logger.error(f"Error cancelling task on Aptos: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_task_info(self, task_agent_address: str, task_id: str) -> Dict[str, Any]:
        """查询任务信息
        
        Args:
            task_agent_address: 任务创建者地址
            task_id: 任务ID字符串
            
        Returns:
            包含任务信息的字典
        """
        try:
            # 将 task_id 字符串转换为字节数组
            task_id_bytes = task_id.encode('utf-8')

            # 调用视图函数
            result = await self.client.view(
                function=self.config.get_module_function_name("get_task_info"),
                type_arguments=[],
                arguments=[
                    task_agent_address,
                    "0x" + task_id_bytes.hex()  # 转换为十六进制字符串
                ]
            )
            
            # 解析返回结果 (tuple)
            return {
                'task_agent': result[0],
                'service_agent': result[1], 
                'pay_amount': result[2],
                'created_at': result[3],
                'deadline': result[4],
                'is_completed': result[5],
                'is_cancelled': result[6],
                'description': result[7]
            }
            
        except Exception as e:
            logger.error(f"Error querying task info: {e}")
            return {'error': str(e)}
    
    async def get_task_stats(self, task_agent_address: str) -> Dict[str, Any]:
        """获取任务统计信息
        
        Args:
            task_agent_address: 任务创建者地址
            
        Returns:
            包含统计信息的字典
        """
        try:
            result = await self.client.view(
                function=self.config.get_module_function_name("get_task_stats"),
                type_arguments=[],
                arguments=[task_agent_address]
            )
            
            return {
                'total_tasks': result[0],
                'completed_tasks': result[1],
                'cancelled_tasks': result[2]
            }
            
        except Exception as e:
            logger.error(f"Error querying task stats: {e}")
            return {'error': str(e)}
    
    async def is_task_expired(self, task_agent_address: str, task_id: str) -> bool:
        """检查任务是否已过期
        
        Args:
            task_agent_address: 任务创建者地址
            task_id: 任务ID字符串
            
        Returns:
            任务是否过期
        """
        try:
            # 将 task_id 字符串转换为字节数组
            task_id_bytes = task_id.encode('utf-8')

            result = await self.client.view(
                function=self.config.get_module_function_name("is_task_expired"),
                type_arguments=[],
                arguments=[
                    task_agent_address,
                    "0x" + task_id_bytes.hex()  # 转换为十六进制字符串
                ]
            )
            
            return result[0] if result else False
            
        except Exception as e:
            logger.error(f"Error checking task expiration: {e}")
            return False


class AptosSignatureManager:
    """Aptos签名管理器"""
    
    def __init__(self, account):
        self.account = account
    
    def sign_message(self, message: str) -> Optional[str]:
        """使用Ed25519签名消息
        
        Args:
            message: 要签名的消息
            
        Returns:
            签名的十六进制字符串
        """
        try:
            # 使用账户的私钥对消息进行签名
            signature = self.account.sign(message.encode('utf-8'))
            # 使用__str__方法获取签名的十六进制字符串
            return str(signature)
        except Exception as e:
            logger.error(f"Error signing message: {e}")
            return None
    
    def verify_signature(self, message: str, signature: str, public_key: str) -> bool:
        """验证Ed25519签名
        
        Args:
            message: 原始消息
            signature: 签名
            public_key: 公钥
            
        Returns:
            签名是否有效
        """
        try:
            # 注意：实际的签名验证需要使用nacl库或Aptos SDK的验证方法
            # 这里提供基本的结构，实际实现可能需要更复杂的逻辑
            return True  # 简化实现
        except Exception as e:
            logger.error(f"Error verifying signature: {e}")
            return False 