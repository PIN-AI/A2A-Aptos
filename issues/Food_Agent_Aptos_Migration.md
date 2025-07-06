# Food Agent Aptos区块链迁移任务

## 任务背景
将Food Ordering Agent的`_complete_task_on_blockchain()`函数从以太坊迁移到Aptos区块链。

## 执行计划
1. **更新导入依赖** - 移除web3，添加Aptos模块
2. **重写核心函数** - 替换`_complete_task_on_blockchain()`实现 
3. **更新环境配置** - 确保Aptos环境变量配置
4. **更新依赖配置** - 修改pyproject.toml依赖
5. **测试验证** - 验证迁移结果

## 预期结果
Food Agent完成任务时调用Aptos `complete_task()`函数，实现链上任务完成记录。

## 执行时间
2025-01-14 