import asyncio
import json
import websockets
from typing import Callable, Awaitable, Optional
from websockets.asyncio.client import ClientConnection


class FunASRClient:
    """
    WebSocket client for FunASR server.

    FunASR WebSocket Protocol:
    - Connect to WebSocket URL
    - Send audio chunks as binary data
    - Receive JSON results with recognition text
    - Supports 2pass mode for both real-time and final results
    """

    def __init__(
        self,
        url: str,
        mode: str = "2pass",
        chunk_size: list = None,
        chunk_interval: int = 10,
        logger=None,
    ):
        self.url = url
        self.mode = mode
        self.chunk_size = chunk_size or [5, 10, 5]
        self.chunk_interval = chunk_interval
        self.logger = logger
        self.ws: Optional[ClientConnection] = None
        self.connected = False
        self.receive_task: Optional[asyncio.Task] = None

        # Callbacks
        self.on_open: Optional[Callable[[], Awaitable[None]]] = None
        self.on_close: Optional[Callable[[], Awaitable[None]]] = None
        self.on_message: Optional[Callable[[dict], Awaitable[None]]] = None
        self.on_error: Optional[Callable[[Exception], Awaitable[None]]] = None

    async def connect(self) -> bool:
        """Connect to FunASR WebSocket server."""
        try:
            if self.logger:
                self.logger.log_info(f"Connecting to FunASR server at {self.url}")

            self.ws = await websockets.connect(
                self.url,
                ping_interval=20,
                ping_timeout=10,
                max_size=10 * 1024 * 1024,  # 10MB max message size
            )

            self.connected = True

            if self.logger:
                self.logger.log_info("Connected to FunASR server")

            # Send initial configuration
            await self._send_config()

            # Start receiving messages
            self.receive_task = asyncio.create_task(self._receive_loop())

            if self.on_open:
                await self.on_open()

            return True

        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Failed to connect to FunASR server: {e}")
            if self.on_error:
                await self.on_error(e)
            return False

    async def _send_config(self):
        """Send initial configuration to FunASR server."""
        config = {
            "mode": self.mode,
            "chunk_size": self.chunk_size,
            "chunk_interval": self.chunk_interval,
        }

        try:
            await self.ws.send(json.dumps(config))
            if self.logger:
                self.logger.log_debug(f"Sent config to FunASR: {config}")
        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Failed to send config: {e}")
            raise

    async def _receive_loop(self):
        """Continuously receive messages from FunASR server."""
        try:
            while self.connected and self.ws:
                try:
                    message = await self.ws.recv()

                    # FunASR sends JSON responses
                    if isinstance(message, str):
                        data = json.loads(message)
                        if self.on_message:
                            await self.on_message(data)
                    elif self.logger:
                        self.logger.log_warn(f"Received non-text message: {type(message)}")

                except websockets.exceptions.ConnectionClosed:
                    if self.logger:
                        self.logger.log_warn("FunASR connection closed")
                    break
                except json.JSONDecodeError as e:
                    if self.logger:
                        self.logger.log_error(f"Failed to decode JSON message: {e}")
                except Exception as e:
                    if self.logger:
                        self.logger.log_error(f"Error in receive loop: {e}")
                    if self.on_error:
                        await self.on_error(e)
                    break

        finally:
            await self._handle_disconnect()

    async def _handle_disconnect(self):
        """Handle disconnection cleanup."""
        self.connected = False
        if self.on_close:
            await self.on_close()

    async def send_audio(self, audio_data: bytes) -> bool:
        """
        Send audio data to FunASR server.

        Args:
            audio_data: Raw PCM audio bytes

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.connected or not self.ws:
            if self.logger:
                self.logger.log_warn("Cannot send audio: not connected")
            return False

        try:
            await self.ws.send(audio_data)
            return True
        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Failed to send audio: {e}")
            if self.on_error:
                await self.on_error(e)
            return False

    async def finalize(self):
        """
        Send finalize signal to FunASR to get final results.
        FunASR uses a special message to indicate end of audio stream.
        """
        if not self.connected or not self.ws:
            if self.logger:
                self.logger.log_warn("Cannot finalize: not connected")
            return

        try:
            # Send end-of-stream marker (empty JSON object)
            finalize_msg = json.dumps({"is_speaking": False})
            await self.ws.send(finalize_msg)

            if self.logger:
                self.logger.log_debug("Sent finalize signal to FunASR")

        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Failed to send finalize: {e}")
            if self.on_error:
                await self.on_error(e)

    async def close(self):
        """Close the WebSocket connection."""
        self.connected = False

        if self.receive_task:
            self.receive_task.cancel()
            try:
                await self.receive_task
            except asyncio.CancelledError:
                pass
            self.receive_task = None

        if self.ws:
            try:
                await self.ws.close()
                if self.logger:
                    self.logger.log_info("Closed FunASR connection")
            except Exception as e:
                if self.logger:
                    self.logger.log_error(f"Error closing connection: {e}")
            finally:
                self.ws = None

    def is_connected(self) -> bool:
        """Check if connected to FunASR server."""
        return self.connected and self.ws is not None
