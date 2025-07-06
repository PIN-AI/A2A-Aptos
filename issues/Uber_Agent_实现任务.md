# Uber Agent 实现任务

## 任务概述
基于A2A协议和Aptos区块链实现专用打车Agent，专注于叫网约车功能。

## 上下文
- 参考架构：food_ordering_services 和 travel_services
- 目标：展示性demo，确保功能跑通
- 端口：10004（避免与food_agent冲突）

## 实现计划
1. ✅ 项目配置修正 (pyproject.toml)
2. ✅ 核心Agent实现 (agent.py)
3. ✅ 演示数据层（Bay Area司机、车型、路线数据）
4. ✅ 服务器入口点 (__main__.py)
5. ✅ 任务管理器 (task_manager.py)
6. ✅ 启动脚本 (run_uber_agent.sh)
7. ✅ README更新
8. ✅ 集成测试验证（基础功能测试通过）

## 核心功能
### 信息查询类（无区块链交互）
- search_nearby_drivers - 查询附近车辆
- estimate_fare - 估算费用时间
- get_available_car_types - 查询车型
- get_route_info - 路线信息

### 重要任务类（需区块链完成记录）
- request_ride - 叫车（支付确认）

### 表单处理类
- create_ride_request_form - 叫车表单
- return_ride_form - 表单返回

## 设计要点
- 全局实例模式：_current_agent_instance
- 区块链集成：Ed25519签名验证+任务完成记录
- 日志优化：减少噪音输出
- 演示数据：Bay Area区域模拟数据 