from typing import AsyncIterator
from httpx import AsyncClient, Timeout, Limits
import json

from .config import FishTTSLocalConfig
from ten_runtime import AsyncTenEnv
from ten_ai_base.const import LOG_CATEGORY_VENDOR

# Custom event types to communicate status back to the extension
EVENT_TTS_RESPONSE = 1
EVENT_TTS_END = 2
EVENT_TTS_ERROR = 3
EVENT_TTS_INVALID_KEY_ERROR = 4
EVENT_TTS_FLUSH = 5

BYTES_PER_SAMPLE = 2
NUMBER_OF_CHANNELS = 1


class FishTTSLocalClient:
    """Client for local Fish TTS HTTP service"""

    def __init__(
        self,
        config: FishTTSLocalConfig,
        ten_env: AsyncTenEnv,
    ):
        self.config = config
        self.base_url = config.base_url.rstrip('/')
        self.ten_env: AsyncTenEnv = ten_env
        self._is_cancelled = False

        # Try multiple possible endpoints for Fish Speech
        self.possible_endpoints = [
            f"{self.base_url}/v1/tts",
            f"{self.base_url}/v1/audio/speech",
            f"{self.base_url}/tts",
            f"{self.base_url}/api/tts",
            f"{self.base_url}/infer",
        ]

        self.headers = {
            "Content-Type": "application/json",
            "Accept": "audio/pcm, application/octet-stream, */*",
        }

        self.client = AsyncClient(
            timeout=Timeout(timeout=120.0),
            limits=Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=600.0,
            ),
            http2=True,
            follow_redirects=True,
        )

    async def stop(self):
        """Stop the client if it exists"""
        if self.client:
            self.ten_env.log_debug("Stopping Fish TTS local client")
            await self.client.aclose()
            self.client = None

    def cancel(self):
        self.ten_env.log_debug("FishTTSLocal: cancel() called.")
        self._is_cancelled = True

    async def get(
        self, text: str
    ) -> AsyncIterator[tuple[bytes | None, int | None]]:
        """Process a single TTS request"""
        self._is_cancelled = False
        if not self.client:
            return

        # Prepare request payloads for different API formats
        payloads = [
            # Fish Speech v1 API format
            {
                "text": text,
                # "format": "pcm",  # Removed hardcode, use config
                **self.config.params,
            },
            # OpenAI-compatible format
            {
                "input": text,
                "voice": self.config.params.get("reference_id", "default"),
                "response_format": "pcm",
            },
            # Simple format
            {
                "text": text,
            }
        ]

        success = False
        last_error = None

        # Try each endpoint with each payload format
        for endpoint in self.possible_endpoints:
            for payload_idx, payload in enumerate(payloads):
                if success:
                    break

                try:
                    self.ten_env.log_info(
                        f"Trying Fish TTS endpoint: {endpoint} with payload format {payload_idx + 1}"
                    )

                    async with self.client.stream(
                        "POST",
                        endpoint,
                        headers=self.headers,
                        json=payload,
                    ) as response:
                        if response.status_code != 200:
                            self.ten_env.log_warn(
                                f"Endpoint {endpoint} returned status {response.status_code}"
                            )
                            continue

                        # If we got a successful response, mark success
                        success = True
                        self.ten_env.log_info(
                            f"Successfully connected to Fish TTS at {endpoint}"
                        )

                        async for chunk in response.aiter_bytes(chunk_size=4096):
                            if self._is_cancelled:
                                self.ten_env.log_debug(
                                    "Cancellation flag detected, sending flush event"
                                )
                                yield None, EVENT_TTS_FLUSH
                                return

                            if len(chunk) > 0:
                                self.ten_env.log_debug(
                                    f"FishTTSLocal: received {len(chunk)} bytes"
                                )
                                yield chunk, EVENT_TTS_RESPONSE

                        # Send end event
                        if not self._is_cancelled:
                            self.ten_env.log_debug("FishTTSLocal: sending EVENT_TTS_END")
                            yield None, EVENT_TTS_END
                        return

                except Exception as e:
                    last_error = str(e)
                    self.ten_env.log_debug(
                        f"Failed to connect to {endpoint}: {e}"
                    )
                    continue

        # If we tried all endpoints and none worked, raise error
        if not success:
            error_msg = f"Could not connect to Fish TTS service at any endpoint. Last error: {last_error}"
            self.ten_env.log_error(
                f"vendor_error: {error_msg}",
                category=LOG_CATEGORY_VENDOR,
            )
            yield error_msg.encode("utf-8"), EVENT_TTS_ERROR

    def clean(self):
        """Clean up resources"""
        self.ten_env.log_debug("FishTTSLocal: clean() called.")
