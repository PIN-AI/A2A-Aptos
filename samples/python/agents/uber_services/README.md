# Uber Services Agent

专注于叫网约车功能的 A2A 协议和 Aptos 区块链集成的智能助手Agent。

## 功能概述

### 🚗 核心服务
- **司机搜索** - 查询附近可用司机和车辆信息
- **费用估算** - 准确估算不同车型的费用和到达时间
- **车型选择** - 提供多种车型选择（UberX、Comfort、XL、Black、Green）
- **叫车预订** - 完整的叫车流程，包含支付确认和区块链验证
- **路线规划** - 智能路线推荐和实时交通信息

### 🔐 区块链集成
- **Ed25519 签名验证** - 验证来自 Host Agent 的请求真实性
- **任务完成记录** - 重要叫车任务的区块链完成记录
- **支付确认** - 安全的支付流程和交易验证

## 快速开始

### 环境要求
- Python 3.12+
- Google API Key
- Aptos Devnet 配置

### 1. 环境配置
```bash
# Google API
export GOOGLE_API_KEY="your_google_api_key"

# Aptos 区块链配置
export APTOS_NODE_URL="https://api.devnet.aptoslabs.com/v1"
export APTOS_PRIVATE_KEY="ed25519-priv-0x..."
export APTOS_MODULE_ADDRESS="0x..."

# Host Agent 配置
export HOST_AGENT_APTOS_ADDRESS="0x..."
```

### 2. 快速启动
```bash
# 使用一键启动脚本
./scripts/run_uber_agent.sh

# 或手动启动
cd samples/python/agents/uber_services
python -m uber_services --port 10004
```

### 3. 验证服务
```bash
# 检查 Agent Card
curl http://localhost:10004/.well-known/agent.json

# 检查健康状态
curl http://localhost:10004/health
```

## 使用示例

### 信息查询类（无区块链交互）
```
用户: "查找我附近的司机"
Agent: 返回附近可用司机列表，包含距离、ETA、评分等信息

用户: "从SFO到市区要多少钱？"
Agent: 提供详细费用估算，包含不同车型价格对比

用户: "有哪些车型可以选择？"
Agent: 展示所有可用车型及其特点、定价、可用性
```

### 重要任务类（需区块链完成记录）
```
用户: "我要叫一辆车去机场"
Agent: 
1. 创建叫车表单
2. 确认订单详情
3. 分配司机
4. 区块链记录任务完成
5. 提供跟踪信息
```

### 表单交互
```
用户: "预订一辆UberXL去斯坦福大学"
Agent: 创建结构化预订表单，包含：
- 上车地点
- 目的地
- 车型选择
- 乘客人数
- 出发时间
- 特殊要求
```

## API 接口

### Agent Card
```
GET /.well-known/agent.json
```

### A2A 协议接口
```
POST /tasks/send          # 同步任务发送
POST /tasks/sendSubscribe # 流式任务发送
GET  /tasks/{id}         # 查询任务状态
POST /tasks/{id}/cancel  # 取消任务
```

## 技能定义

### 1. 司机搜索工具 (driver_search)
- **功能**: 查找附近可用司机
- **标签**: driver, search, availability, nearby
- **示例**: "查找我附近的司机", "旧金山有哪些司机可用？"

### 2. 费用估算工具 (fare_estimation)
- **功能**: 估算叫车费用
- **标签**: fare, estimate, pricing, cost
- **示例**: "从SFO到市区要多少钱？", "UberBlack比UberX贵多少？"

### 3. 叫车预订工具 (ride_booking)
- **功能**: 完整叫车流程
- **标签**: booking, ride, payment, confirmation
- **示例**: "我要叫一辆车去机场", "预订一辆UberXL去斯坦福大学"

### 4. 路线规划工具 (route_planning)
- **功能**: 路线和交通信息
- **标签**: route, traffic, navigation, time
- **示例**: "从旧金山到圣何塞最快的路线是什么？", "现在去机场会堵车吗？"

## 架构设计

### 文件结构
```
uber_services/
├── agent.py           # 核心Agent实现和工具函数
├── task_manager.py    # A2A协议和签名验证
├── __main__.py        # 服务器入口点
├── pyproject.toml     # 项目配置
└── README.md          # 文档说明
```

### 关键设计模式
- **全局实例模式**: `_current_agent_instance` 用于工具函数访问会话状态
- **异步上下文处理**: 区块链操作使用线程池处理异步调用
- **优雅降级机制**: 区块链故障时继续核心业务功能
- **智能任务路由**: 根据任务类型决定是否需要区块链确认

## 服务区域

当前支持 **Bay Area（湾区）** 地区：
- San Francisco (旧金山)
- Oakland (奥克兰)  
- Berkeley (伯克利)
- Palo Alto (帕罗奥图)

## 车型支持

- **UberX** - 经济实惠的日常出行
- **Comfort** - 更新车型，额外腿部空间
- **UberXL** - 大型车辆，最多6名乘客
- **Uber Black** - 豪华车型，高端体验
- **Uber Green** - 环保混合动力和电动车

## 开发与测试

### 本地开发
```bash
# 安装开发依赖
pip install -e .

# 运行单元测试
python -m pytest tests/

# 启动开发服务器
python -m uber_services --host localhost --port 10004
```

### 集成测试
```bash
# 测试 Agent Card
curl http://localhost:10004/.well-known/agent.json

# 测试信息查询
curl -X POST http://localhost:10004/tasks/send \
  -H "Content-Type: application/json" \
  -d '{"query": "查找我附近的司机"}'

# 测试叫车功能
curl -X POST http://localhost:10004/tasks/send \
  -H "Content-Type: application/json" \
  -d '{"query": "我要叫一辆车去机场"}'
```

## 故障排除

### 常见问题
1. **端口冲突** - 默认端口10004，可通过 `--port` 参数修改
2. **API Key错误** - 检查 `GOOGLE_API_KEY` 环境变量设置
3. **Aptos连接问题** - 验证 `APTOS_NODE_URL` 和网络连接
4. **签名验证失败** - 检查 `HOST_AGENT_APTOS_ADDRESS` 配置

### 调试模式
```bash
# 启用详细日志
export PYTHONPATH=.
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
" && python -m uber_services
```

## 贡献指南

欢迎提交 Issues 和 Pull Requests 来改进此 Agent。

## 许可证

遵循项目主许可证。 