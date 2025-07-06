#!/bin/bash

cd "$(dirname "$0")/../samples/python" || exit

source .venv/bin/activate

export APTOS_NODE_URL="https://api.devnet.aptoslabs.com/v1"
export APTOS_PRIVATE_KEY="ed25519-priv-0x280170ba1051145feaadec53769c92005c4b094cd260d339529be424a30b97b4"
export HOST_AGENT_APTOS_ADDRESS="0x42e86d92f3d8645d290844f96451038efc722940fff706823dd3c0f8f67b46bd"
export APTOS_MODULE_ADDRESS="0x42e86d92f3d8645d290844f96451038efc722940fff706823dd3c0f8f67b46bd"

echo "Checking and getting Aptos Devnet test coins..."
python ../../scripts/get_aptos_faucet.py "$APTOS_PRIVATE_KEY"
if [ $? -ne 0 ]; then
    echo "⚠️ Getting test coins failed, but continuing to start Food Agent"
fi

echo "Running Food Ordering Service Agent..."
uv run agents/food_ordering_services --host 0.0.0.0 --port 10003

# If you need to specify a port, you can use:
# uv run agents/food_ordering_services --port 10002 