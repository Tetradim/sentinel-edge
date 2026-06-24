"""WebSocket Manager — real-time price streaming via Alpaca."""

import asyncio
import logging
import os
import time
from typing import Callable, Optional, Set

import aiohttp

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections for live price streaming."""

    # Connection retry settings
    MAX_RETRY_ATTEMPTS = 5
    INITIAL_BACKOFF = 1.0  # seconds
    MAX_BACKOFF = 60.0  # seconds

    def __init__(
        self,
        price_fetcher,
        on_price_update: Callable[[str, float, float], None],  # symbol, price, volume
        get_active_symbols: Optional[Callable[[], Set[str]]] = None,
    ):
        self.price_fetcher = price_fetcher
        self.on_price_update = on_price_update
        self.get_active_symbols = get_active_symbols  # Callback to get tickers
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Track which symbols have active WS subscriptions
        self.subscribed_symbols: Set[str] = set()

        # Reconnection state
        self._retry_count = 0
        self._reconnect_backoff = self.INITIAL_BACKOFF

        # Alpaca market-data credentials. Do not use broker/trading account
        # credential env names in Edge; Pulse owns broker connectivity.
        self._api_key = os.getenv("ALPACA_MARKET_DATA_API_KEY", "")
        self._secret_key = os.getenv("ALPACA_MARKET_DATA_SECRET_KEY", "")
        self._ws_url = os.getenv(
            "ALPACA_MARKET_DATA_WS_URL",
            "wss://stream.data.alpaca.markets/v2/stream"
        )

        logger.info("WebSocketManager initialized")

    async def start(self):
        """Start the WebSocket connection."""
        if self._running:
            logger.warning("WebSocket already running")
            return

        if not self._api_key or not self._secret_key:
            logger.info("Alpaca market-data credentials not configured - WebSocket disabled")
            return

        self._running = True
        self._session = aiohttp.ClientSession()
        self._task = asyncio.create_task(self._connect_with_retry())
        logger.info("Alpaca WebSocket started")

    async def _connect_with_retry(self):
        """Connect with exponential backoff reconnection."""
        while self._running and self._retry_count < self.MAX_RETRY_ATTEMPTS:
            try:
                await self._connect()
                # If we get here, connection was successful - reset retry count
                self._retry_count = 0
                self._reconnect_backoff = self.INITIAL_BACKOFF
            except Exception as e:
                if not self._running:
                    break
                self._retry_count += 1
                logger.warning(
                    f"WebSocket disconnected (attempt {self._retry_count}/{self.MAX_RETRY_ATTEMPTS}): {e}"
                )
                await asyncio.sleep(self._reconnect_backoff)
                # Exponential backoff
                self._reconnect_backoff = min(
                    self._reconnect_backoff * 2,
                    self.MAX_BACKOFF
                )

    async def _connect(self):
        """Connect to Alpaca WebSocket and subscribe to symbols."""
        try:
            async with self._session.ws_connect(
                self._ws_url,
                headers={
                    "APCA-API-KEY-ID": self._api_key,
                    "APCA-API-SECRET-KEY": self._secret_key,
                },
            ) as ws:
                self._ws = ws
                await self._subscribe()
                await self._listen()
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            raise
        finally:
            self._running = False

    async def add_symbols(self, symbols: Set[str]):
        """Add new symbols to subscribe to. Resubscribes if already connected."""
        new_symbols = symbols - self.subscribed_symbols
        if not new_symbols:
            return

        self.subscribed_symbols.update(new_symbols)

        # If connected, resubscribe immediately
        if self._ws and not self._ws.closed:
            await self._resubscribe(new_symbols)
        else:
            logger.debug(f"Added symbols to queue: {new_symbols}")

    async def _subscribe(self):
        """Subscribe to trade updates for all active tickers."""
        if not self._ws:
            return

        # Use callback to get symbols if available, otherwise use cached from fetcher
        if self.get_active_symbols:
            symbols = self.get_active_symbols()
        else:
            # Fallback: get symbols from price fetcher cache
            symbols = getattr(self.price_fetcher, '_cache', {}) or {}
            if not symbols:
                symbols = {"SPY", "QQQ"}  # Default tickers

        symbols = set(symbols) if symbols else {"SPY", "QQQ"}
        self.subscribed_symbols.update(symbols)

        msg = {
            "action": "subscribe",
            "trades": list(symbols),
        }
        await self._ws.send_json(msg)
        logger.info(f"Subscribed {', '.join(symbols)} via WebSocket")

    async def _resubscribe(self, new_symbols: Set[str]):
        """Subscribe to additional symbols (called when new tickers added)."""
        if not self._ws or self._ws.closed:
            return

        msg = {
            "action": "subscribe",
            "trades": list(new_symbols),
        }
        await self._ws.send_json(msg)
        logger.info(f"Resubscribed new symbols: {', '.join(new_symbols)}")

    async def resubscribe(self):
        """Manually trigger a full resubscription to current symbols."""
        if self._ws and not self._ws.closed:
            await self._subscribe()
        else:
            logger.warning("Cannot resubscribe - WebSocket not connected")

    async def _listen(self):
        """Listen for incoming messages."""
        async for msg in self._ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                await self._handle_message(msg.json())
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error(f"WebSocket error: {msg}")
                break

    async def _handle_message(self, data: dict):
        """Process incoming WebSocket message."""
        try:
            # Handle Alpaca streaming format
            # Expected: {"T": "t", "S": "SPY", "p": 500.00, "v": 1000}
            if data.get("T") == "t":
                symbol = data.get("S")
                price = data.get("p")
                volume = data.get("v", 0)

                if symbol and price:
                    # Update price in fetcher cache
                    self.price_fetcher.update_live_price(symbol, price, volume)

                    # Trigger callback
                    if self.on_price_update:
                        await self.on_price_update(symbol, price, volume)

                    logger.debug(f"📡 WS Live Update → {symbol} @ ${price:.2f}")
        except Exception as e:
            logger.debug(f"WS message parse error: {e}")

    async def stop(self):
        """Stop the WebSocket connection."""
        self._running = False
        if self._ws:
            await self._ws.close()
        if self._session:
            await self._session.close()
        if self._task:
            self._task.cancel()
        logger.info("WebSocket stopped")
