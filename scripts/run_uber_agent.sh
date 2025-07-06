#!/bin/bash

echo "=== Starting Uber Services Agent ==="

export APTOS_NODE_URL="https://api.devnet.aptoslabs.com/v1"
export APTOS_PRIVATE_KEY="ed25519-priv-0x280170ba1051145feaadec53769c92005c4b094cd260d339529be424a30b97b4"
export HOST_AGENT_APTOS_ADDRESS="0x42e86d92f3d8645d290844f96451038efc722940fff706823dd3c0f8f67b46bd"
export APTOS_MODULE_ADDRESS="0x42e86d92f3d8645d290844f96451038efc722940fff706823dd3c0f8f67b46bd"

if [ -z "$APTOS_NODE_URL" ]; then
    echo "Setting default Aptos devnet URL..."
    export APTOS_NODE_URL="https://api.devnet.aptoslabs.com/v1"
fi

if [ -z "$APTOS_MODULE_ADDRESS" ]; then
    echo "⚠️ Warning: APTOS_MODULE_ADDRESS environment variable is not set"
    echo "Please set the smart contract address or use the default value"
    export APTOS_MODULE_ADDRESS="0x..."  # Please replace with the actual contract address
fi

if [ -z "$HOST_AGENT_APTOS_ADDRESS" ]; then
    echo "⚠️ Warning: HOST_AGENT_APTOS_ADDRESS environment variable is not set"
    echo "Blockchain task completion function will be skipped, but core ride-hailing functionality will still work"
    echo "To enable blockchain functionality, please set a valid 64-bit hexadecimal Aptos address"
    echo "Example: export HOST_AGENT_APTOS_ADDRESS=\"0x42e86d92f3d8645d290844f96451038efc722940fff706823dd3c0f8f67b46bd\""
fi

export PORT=10004

echo "✅ Environment variables configured:"
echo "   - Google API Key: ${GOOGLE_API_KEY:0:10}..."
echo "   - Aptos Node URL: $APTOS_NODE_URL"
echo "   - Aptos Module: ${APTOS_MODULE_ADDRESS:0:10}..."
if [ -n "$HOST_AGENT_APTOS_ADDRESS" ]; then
    echo "   - Host Agent: ${HOST_AGENT_APTOS_ADDRESS:0:10}...${HOST_AGENT_APTOS_ADDRESS: -10}"
else
    echo "   - Host Agent: Not set (blockchain functionality disabled)"
fi
echo "   - Port: $PORT"

cd "$(dirname "$0")/../samples/python/agents/uber_services" || exit 1

echo "📂 Working directory: $(pwd)"

if [ ! -d ".venv" ]; then
    echo "🔧 Creating virtual environment..."
    python -m venv .venv
fi

echo "🚀 Activating virtual environment..."
source .venv/bin/activate

echo "📦 Installing dependencies..."
if [ -f "pyproject.toml" ]; then
    # First install the root project (includes common dependencies)
    pip install -e ../../
    # Then install the current project
    pip install -e .
else
    echo "❌ pyproject.toml file not found"
    exit 1
fi

# 启动 Uber Agent
echo ""
echo "🚗 Uber Services Agent (port $PORT) is running..."
echo "   Access Agent Card: http://localhost:$PORT/.well-known/agent.json"
if [ -n "$HOST_AGENT_APTOS_ADDRESS" ]; then
    echo "   Aptos Function: Enabled"
else
    echo "   Aptos Function: Disabled (core functionality works)"
fi
echo "   Use Ctrl+C to stop the service"
echo ""

python __main__.py --host localhost --port $PORT

echo "👋 Uber Services Agent stopped" 