"""
LangChain tools for Nory x402 payments.

These tools enable LangChain agents to:
1. Pay for x402-protected APIs automatically
2. Access pre-built paid APIs (crypto, weather, translate, etc.)
3. Make custom payments to any x402-enabled endpoint
"""

import os
import json
import base64
from typing import Optional, Type, Any, Dict
from pydantic import BaseModel, Field
import requests

try:
    from langchain_core.tools import BaseTool
    from langchain_core.callbacks import CallbackManagerForToolRun
except ImportError:
    from langchain.tools import BaseTool
    from langchain.callbacks.manager import CallbackManagerForToolRun


NORY_BASE_URL = "https://noryx402.com"


class PaymentInput(BaseModel):
    """Input schema for payment tool."""
    url: str = Field(description="The URL to fetch (may require payment)")
    method: str = Field(default="GET", description="HTTP method (GET or POST)")
    body: Optional[str] = Field(default=None, description="Request body for POST requests")


class NoryFetchTool(BaseTool):
    """
    Fetch any URL with automatic x402 payment handling.

    This tool will:
    1. Make the request to the URL
    2. If 402 Payment Required is returned, parse requirements
    3. Create and sign a USDC payment transaction
    4. Retry the request with the payment header
    5. Return the response data

    Requires NORY_WALLET_KEY environment variable.
    """

    name: str = "nory_fetch"
    description: str = """Fetch any URL with automatic payment for x402-protected resources.
    Use this when you need to access a paid API or any URL that might require payment.
    The tool automatically handles HTTP 402 responses by paying with USDC."""
    args_schema: Type[BaseModel] = PaymentInput

    wallet_key: Optional[str] = None
    network: str = "solana-mainnet"

    def __init__(self, wallet_key: Optional[str] = None, network: str = "solana-mainnet", **kwargs):
        super().__init__(**kwargs)
        self.wallet_key = wallet_key or os.environ.get("NORY_WALLET_KEY")
        self.network = network

    def _run(
        self,
        url: str,
        method: str = "GET",
        body: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """Execute the fetch with payment handling."""
        try:
            # Initial request
            headers = {"Accept": "application/json"}
            response = requests.request(
                method=method.upper(),
                url=url,
                headers=headers,
                data=body if body else None
            )

            # If 402, handle payment
            if response.status_code == 402:
                if not self.wallet_key:
                    return json.dumps({
                        "error": "Payment required but no wallet key configured",
                        "requirements": response.json()
                    })

                requirements = response.json()

                # Call Nory API to create payment
                payment_response = requests.post(
                    f"{NORY_BASE_URL}/api/x402/pay",
                    json={
                        "requirements": requirements,
                        "walletKey": self.wallet_key,
                        "network": self.network
                    },
                    headers={"Content-Type": "application/json"}
                )

                if payment_response.status_code != 200:
                    return json.dumps({
                        "error": "Payment failed",
                        "details": payment_response.text
                    })

                payment_data = payment_response.json()

                # Retry with payment header
                headers["X-PAYMENT"] = payment_data.get("paymentHeader", "")
                final_response = requests.request(
                    method=method.upper(),
                    url=url,
                    headers=headers,
                    data=body if body else None
                )

                return json.dumps({
                    "success": True,
                    "data": final_response.json() if final_response.headers.get("content-type", "").startswith("application/json") else final_response.text,
                    "payment": {
                        "amount": payment_data.get("amount"),
                        "txId": payment_data.get("transactionId")
                    }
                })

            # Return response directly
            try:
                return json.dumps({
                    "success": True,
                    "data": response.json()
                })
            except:
                return json.dumps({
                    "success": True,
                    "data": response.text
                })

        except Exception as e:
            return json.dumps({"error": str(e)})


class NoryPaymentTool(BaseTool):
    """Make a direct payment to any Solana/EVM wallet."""

    name: str = "nory_pay"
    description: str = """Make a USDC payment to any wallet address.
    Use this when you need to send a payment directly to someone.
    Supports Solana (fast, ~400ms) and EVM chains."""

    wallet_key: Optional[str] = None
    network: str = "solana-mainnet"

    def __init__(self, wallet_key: Optional[str] = None, network: str = "solana-mainnet", **kwargs):
        super().__init__(**kwargs)
        self.wallet_key = wallet_key or os.environ.get("NORY_WALLET_KEY")
        self.network = network

    def _run(
        self,
        recipient: str,
        amount: str,
        memo: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """Execute the payment."""
        if not self.wallet_key:
            return json.dumps({"error": "No wallet key configured"})

        try:
            response = requests.post(
                f"{NORY_BASE_URL}/api/x402/transfer",
                json={
                    "recipient": recipient,
                    "amount": amount,
                    "memo": memo,
                    "walletKey": self.wallet_key,
                    "network": self.network
                },
                headers={"Content-Type": "application/json"}
            )

            return json.dumps(response.json())
        except Exception as e:
            return json.dumps({"error": str(e)})


# Pre-built tools for common Nory paid APIs

class CryptoPricesInput(BaseModel):
    """Input for crypto prices tool."""
    symbols: str = Field(
        default="BTC,ETH,SOL",
        description="Comma-separated crypto symbols (e.g., BTC,ETH,SOL)"
    )


class NoryCryptoPricesTool(BaseTool):
    """Get real-time cryptocurrency prices."""

    name: str = "nory_crypto_prices"
    description: str = """Get real-time cryptocurrency prices from CoinGecko.
    Costs $0.001 USDC per request. Supports BTC, ETH, SOL, and 15+ other coins.
    Use this when you need current crypto prices."""
    args_schema: Type[BaseModel] = CryptoPricesInput

    wallet_key: Optional[str] = None

    def __init__(self, wallet_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_key = wallet_key or os.environ.get("NORY_WALLET_KEY")

    def _run(
        self,
        symbols: str = "BTC,ETH,SOL",
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """Get crypto prices."""
        fetch_tool = NoryFetchTool(wallet_key=self.wallet_key)
        return fetch_tool._run(
            url=f"{NORY_BASE_URL}/api/paid/live-crypto?symbols={symbols}"
        )


class WeatherInput(BaseModel):
    """Input for weather tool."""
    city: str = Field(description="City name to get weather for")


class NoryWeatherTool(BaseTool):
    """Get current weather and forecast for any city."""

    name: str = "nory_weather"
    description: str = """Get current weather and 7-day forecast for any city.
    Costs $0.002 USDC per request. Returns temperature, conditions, and forecast.
    Use this when you need weather information."""
    args_schema: Type[BaseModel] = WeatherInput

    wallet_key: Optional[str] = None

    def __init__(self, wallet_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_key = wallet_key or os.environ.get("NORY_WALLET_KEY")

    def _run(
        self,
        city: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """Get weather."""
        fetch_tool = NoryFetchTool(wallet_key=self.wallet_key)
        return fetch_tool._run(
            url=f"{NORY_BASE_URL}/api/paid/weather?city={city}"
        )


class TranslateInput(BaseModel):
    """Input for translation tool."""
    text: str = Field(description="Text to translate")
    to_lang: str = Field(default="es", description="Target language code (e.g., es, fr, de, ja)")
    from_lang: Optional[str] = Field(default=None, description="Source language (auto-detect if not specified)")


class NoryTranslateTool(BaseTool):
    """Translate text between 20+ languages."""

    name: str = "nory_translate"
    description: str = """Translate text between 20+ languages.
    Costs $0.005 USDC per request. Supports auto-detection of source language.
    Use this when you need to translate text."""
    args_schema: Type[BaseModel] = TranslateInput

    wallet_key: Optional[str] = None

    def __init__(self, wallet_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_key = wallet_key or os.environ.get("NORY_WALLET_KEY")

    def _run(
        self,
        text: str,
        to_lang: str = "es",
        from_lang: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """Translate text."""
        fetch_tool = NoryFetchTool(wallet_key=self.wallet_key)
        url = f"{NORY_BASE_URL}/api/paid/translate?text={text}&to={to_lang}"
        if from_lang:
            url += f"&from={from_lang}"
        return fetch_tool._run(url=url)


class QRCodeInput(BaseModel):
    """Input for QR code tool."""
    data: str = Field(description="Data to encode in QR code (text or URL)")
    size: int = Field(default=200, description="Image size in pixels (100-1000)")


class NoryQRCodeTool(BaseTool):
    """Generate QR codes for any data."""

    name: str = "nory_qrcode"
    description: str = """Generate QR codes for any text or URL.
    Costs $0.001 USDC per request. Returns QR code as base64 image.
    Use this when you need to create a QR code."""
    args_schema: Type[BaseModel] = QRCodeInput

    wallet_key: Optional[str] = None

    def __init__(self, wallet_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_key = wallet_key or os.environ.get("NORY_WALLET_KEY")

    def _run(
        self,
        data: str,
        size: int = 200,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """Generate QR code."""
        fetch_tool = NoryFetchTool(wallet_key=self.wallet_key)
        return fetch_tool._run(
            url=f"{NORY_BASE_URL}/api/paid/qr-code?data={data}&size={size}&format=json"
        )


class WebSummaryInput(BaseModel):
    """Input for web summary tool."""
    url: str = Field(description="URL to extract content from")


class NoryWebSummaryTool(BaseTool):
    """Extract clean text content from any webpage."""

    name: str = "nory_web_summary"
    description: str = """Extract clean text content from any webpage URL.
    Costs $0.01 USDC per request. Removes ads, navigation, and returns main content.
    Use this when you need to read webpage content."""
    args_schema: Type[BaseModel] = WebSummaryInput

    wallet_key: Optional[str] = None

    def __init__(self, wallet_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_key = wallet_key or os.environ.get("NORY_WALLET_KEY")

    def _run(
        self,
        url: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """Extract web content."""
        fetch_tool = NoryFetchTool(wallet_key=self.wallet_key)
        return fetch_tool._run(
            url=f"{NORY_BASE_URL}/api/paid/web-summary?url={url}"
        )


def get_nory_tools(wallet_key: Optional[str] = None) -> list:
    """
    Get all Nory tools configured with a wallet key.

    Args:
        wallet_key: Solana private key for payments.
                   Defaults to NORY_WALLET_KEY env var.

    Returns:
        List of LangChain tools ready to use with an agent.

    Example:
        from langchain_nory import get_nory_tools
        from langchain.agents import create_react_agent

        tools = get_nory_tools()
        agent = create_react_agent(llm, tools, prompt)
    """
    key = wallet_key or os.environ.get("NORY_WALLET_KEY")
    return [
        NoryFetchTool(wallet_key=key),
        NoryPaymentTool(wallet_key=key),
        NoryCryptoPricesTool(wallet_key=key),
        NoryWeatherTool(wallet_key=key),
        NoryTranslateTool(wallet_key=key),
        NoryQRCodeTool(wallet_key=key),
        NoryWebSummaryTool(wallet_key=key),
    ]
