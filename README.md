# langchain-nory

**LangChain tools for x402 payments** - Let your agents pay for APIs autonomously.

[![PyPI version](https://badge.fury.io/py/langchain-nory.svg)](https://pypi.org/project/langchain-nory/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

`langchain-nory` provides LangChain tools that enable AI agents to:

- **Pay for x402-protected APIs** automatically when they encounter HTTP 402 responses
- **Access pre-built paid APIs** for crypto prices, weather, translation, and more
- **Make direct payments** to any Solana or EVM wallet

All payments use **USDC stablecoin** on **Solana** (~400ms settlement) or EVM chains.

## Installation

```bash
pip install langchain-nory
```

## Quick Start

```python
from langchain_nory import get_nory_tools
from langchain_openai import ChatOpenAI
from langchain.agents import create_react_agent, AgentExecutor

# Get all Nory tools (uses NORY_WALLET_KEY env var)
tools = get_nory_tools()

# Or configure with explicit wallet key
tools = get_nory_tools(wallet_key="your-solana-private-key")

# Create agent with tools
llm = ChatOpenAI(model="gpt-4")
agent = create_react_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools)

# Agent can now pay for APIs!
result = executor.invoke({"input": "What's the current price of Bitcoin?"})
```

## Available Tools

### Core Tools

| Tool | Description | Cost |
|------|-------------|------|
| `NoryFetchTool` | Fetch any URL with automatic x402 payment handling | Varies |
| `NoryPaymentTool` | Make direct USDC payments to any wallet | 0.1% fee |

### Pre-built Paid API Tools

| Tool | Description | Cost per request |
|------|-------------|------------------|
| `NoryCryptoPricesTool` | Real-time crypto prices (BTC, ETH, SOL, etc.) | $0.001 |
| `NoryWeatherTool` | Weather + 7-day forecast for any city | $0.002 |
| `NoryTranslateTool` | Translate between 20+ languages | $0.005 |
| `NoryQRCodeTool` | Generate QR codes | $0.001 |
| `NoryWebSummaryTool` | Extract text from any webpage | $0.01 |

## Individual Tool Usage

### Fetch Any Paid API

```python
from langchain_nory import NoryFetchTool

tool = NoryFetchTool(wallet_key="your-key")

# Automatically pays if the API requires it
result = tool.run("https://api.example.com/premium-data")
```

### Get Crypto Prices

```python
from langchain_nory import NoryCryptoPricesTool

tool = NoryCryptoPricesTool(wallet_key="your-key")
result = tool.run("BTC,ETH,SOL")
# {"BTC": {"price": 45000.50, ...}, "ETH": {...}, "SOL": {...}}
```

### Get Weather

```python
from langchain_nory import NoryWeatherTool

tool = NoryWeatherTool(wallet_key="your-key")
result = tool.run("London")
# {"current": {"temp": 15, "condition": "Cloudy"}, "forecast": [...]}
```

### Translate Text

```python
from langchain_nory import NoryTranslateTool

tool = NoryTranslateTool(wallet_key="your-key")
result = tool.run(text="Hello world", to_lang="es")
# {"translation": "Hola mundo", "from": "en", "to": "es"}
```

## Environment Variables

```bash
export NORY_WALLET_KEY="your-solana-private-key"
```

## With CrewAI

```python
from crewai import Agent, Task, Crew
from langchain_nory import get_nory_tools

tools = get_nory_tools()

researcher = Agent(
    role="Market Researcher",
    goal="Get real-time crypto market data",
    tools=tools,
    verbose=True
)

task = Task(
    description="Get the current prices of BTC, ETH, and SOL",
    agent=researcher
)

crew = Crew(agents=[researcher], tasks=[task])
result = crew.kickoff()
```

## How x402 Payment Works

1. Agent requests a paid API endpoint
2. Server returns `402 Payment Required` with payment requirements
3. `NoryFetchTool` creates and signs a USDC transfer transaction
4. Transaction is sent to Nory for settlement (~400ms)
5. Agent retries request with `X-PAYMENT` header containing proof
6. Server verifies payment and returns data

All of this happens automatically - your agent just calls `tool.run(url)`.

## Links

- **Website**: [noryx402.com](https://noryx402.com)
- **Documentation**: [noryx402.com/docs](https://noryx402.com/docs)
- **x402 Protocol**: [github.com/coinbase/x402](https://github.com/coinbase/x402)
- **npm packages**: [nory-x402-payer](https://npmjs.com/package/nory-x402-payer) | [nory-x402-middleware](https://npmjs.com/package/nory-x402-middleware)

## License

MIT
