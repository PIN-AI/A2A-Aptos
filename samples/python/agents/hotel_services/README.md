# Travel Services Agent

A comprehensive travel assistant powered by A2A protocol and Aptos blockchain.

## Features

- **Trip Planning**: Comprehensive itinerary creation
- **Hotel Services**: Search and booking with global coverage
- **Flight Services**: Search and booking across major airlines
- **Destination Discovery**: Personalized recommendations
- **Weather Information**: Real-time weather data
- **Attractions**: Local points of interest and activities
- **Blockchain Integration**: Aptos-powered task completion verification

## Quick Start

1. Set environment variables:
```bash
export GOOGLE_API_KEY="your_google_api_key"
export APTOS_PRIVATE_KEY="ed25519-priv-0x..."
export APTOS_NODE_URL="https://api.devnet.aptoslabs.com/v1"
export PORT=10004
```

2. Install and run:
```bash
pip install -e .
python -m travel_services
```

## Architecture

- **Framework**: Google ADK + A2A Protocol
- **Blockchain**: Aptos + Ed25519 Signatures
- **LLM**: Gemini 2.0 Flash
- **Port**: 10004 (configurable)

## Agent Capabilities

### Information Queries (No blockchain)
- Destination search and recommendations
- Hotel search and comparison
- Flight search and pricing
- Weather information
- Local attractions

### Important Tasks (Blockchain verified)
- Hotel booking with payment
- Flight booking with payment
- Comprehensive itinerary planning

### Form Processing
- Interactive booking forms
- Itinerary planning forms
- Payment processing forms 