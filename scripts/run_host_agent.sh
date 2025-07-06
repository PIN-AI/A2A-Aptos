#!/bin/bash

cd "$(dirname "$0")/../demo/ui" || exit

source .venv/bin/activate

export APTOS_NODE_URL="https://api.devnet.aptoslabs.com/v1"
export APTOS_PRIVATE_KEY="ed25519-priv-0x527ff01b4f55ecd7c6c96eb711be968f8dd42125984b751ddd856c7b5bdcbeac"
export APTOS_MODULE_ADDRESS="0x42e86d92f3d8645d290844f96451038efc722940fff706823dd3c0f8f67b46bd"
export REMOTE_AGENT_APTOS_ADDRESS="0x69029bc61f9828ed712a9238f70b4fe629b35144cd638a50f60bd278916b33c5"
export DEFAULT_REMOTE_AGENTS="http://localhost:10003"

echo "Check and get Aptos Devnet test coins..."
python ../../scripts/get_aptos_faucet.py "$APTOS_PRIVATE_KEY"
if [ $? -ne 0 ]; then
    echo "⚠️ Get test coins failed, but continue to start Host Agent"
fi

echo "Running Host Agent UI..."
uv run main.py

# If you need to specify a port, you can use:
# uv run main.py --port 12000 