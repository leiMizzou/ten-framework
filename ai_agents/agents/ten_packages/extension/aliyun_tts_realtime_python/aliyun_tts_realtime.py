#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
#
import asyncio
import json
import base64
from typing import Any, AsyncIterator
import websockets
from websockets.client import WebSocketClientProtocol

from ten_runtime import AsyncTenEnv
from .config import AliyunTTSRealtimeConfig

EVENT_TTS_RESPONSE = "response"
EVENT_TTS_END = "end"
EVENT_TTS_ERROR = "error"
EVENT_TTS_FLUSH = "flush"


class AliyunTTSRealtimeClient:
    def __init__(
        self,
        config: AliyunTTSRealtimeConfig,
        ten_env: AsyncTenEnv
    ):
        self.config = config
        self.ten_env = ten_env
        self.websocket: WebSocketClientProtocol | None = None
        self.session_initialized = False
        self.lock = asyncio.Lock()

    async def connect(self):
        """Connect to Aliyun TTS WebSocket"""
        # In websockets 15.0+, check connection state differently
        if self.websocket and self.session_initialized:
            return

        try:
            # Build URL with model parameter
            ws_url = f"{self.config.ws_url}?model={self.config.model}"

            self.ten_env.log_info(
                f"Connecting to Aliyun TTS: {ws_url}"
            )

            # Use Authorization Bearer header (new API format)
            self.websocket = await websockets.connect(
                ws_url,
                additional_headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                },
                ping_interval=20,
                ping_timeout=10
            )

            self.ten_env.log_info("WebSocket connected successfully")

            # Wait for session.created event
            await self._wait_for_session_created()

        except Exception as e:
            self.ten_env.log_error(f"WebSocket connection failed: {e}")
            self.websocket = None
            raise

    async def _wait_for_session_created(self):
        """Wait for session.created event from server"""
        if not self.websocket:
            raise RuntimeError("WebSocket not connected")

        try:
            # Wait for session.created event
            response = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=10.0
            )
            event = json.loads(response)
            event_type = event.get("type")

            self.ten_env.log_info(f"Received event: {event_type}")

            if event_type == "session.created":
                self.ten_env.log_info("Session created successfully")
                self.session_initialized = True
                # Log session details
                session_info = event.get("session", {})
                self.ten_env.log_debug(f"Session info: {json.dumps(session_info)}")
            else:
                raise RuntimeError(f"Unexpected event: {event_type}, expected session.created")

        except asyncio.TimeoutError:
            raise RuntimeError("Timeout waiting for session.created")
        except Exception as e:
            self.ten_env.log_error(f"Failed to wait for session.created: {e}")
            raise

    async def synthesize(
        self,
        text: str,
        request_id: str
    ) -> AsyncIterator[tuple[str, Any]]:
        """
        Synthesize text to speech

        Yields:
            (event_type, data) tuples where event_type can be:
            - EVENT_TTS_RESPONSE: audio data chunk
            - EVENT_TTS_END: synthesis completed
            - EVENT_TTS_ERROR: error occurred
        """
        async with self.lock:
            try:
                # Ensure connection (websockets 15.0+ compatible)
                if not self.websocket or not self.session_initialized:
                    await self.connect()

                # Send text
                append_event = {
                    "type": "input_text_buffer.append",
                    "text": text
                }

                self.ten_env.log_debug(
                    f"[{request_id}] Sending text: {text[:50]}..."
                )
                await self.websocket.send(json.dumps(append_event))

                # Send commit event to trigger synthesis
                # This works for both commit and server_commit modes
                commit_event = {"type": "input_text_buffer.commit"}
                self.ten_env.log_debug(f"[{request_id}] Sending commit event")
                await self.websocket.send(json.dumps(commit_event))

                # Receive audio stream
                audio_chunks = 0
                while True:
                    try:
                        response = await asyncio.wait_for(
                            self.websocket.recv(),
                            timeout=30.0
                        )
                        event = json.loads(response)
                        event_type = event.get("type")

                        if event_type == "response.audio.delta":
                            # Decode audio data
                            audio_b64 = event.get("delta", "")
                            if audio_b64:
                                audio_data = base64.b64decode(audio_b64)
                                audio_chunks += 1
                                self.ten_env.log_debug(
                                    f"[{request_id}] Decoded audio chunk #{audio_chunks}, size={len(audio_data)}"
                                )
                                yield (EVENT_TTS_RESPONSE, audio_data)

                        elif event_type == "response.done":
                            self.ten_env.log_info(
                                f"[{request_id}] TTS completed, "
                                f"received {audio_chunks} chunks"
                            )
                            yield (EVENT_TTS_END, None)
                            break

                        elif event_type == "error":
                            error_info = event.get("error", {})
                            error_msg = error_info.get("message", "Unknown error")
                            self.ten_env.log_error(
                                f"[{request_id}] TTS error: {error_msg}"
                            )
                            yield (EVENT_TTS_ERROR, error_info)
                            break

                        elif event_type in ["response.created", "response.output_item.added",
                                           "response.content_part.added", "response.audio.done",
                                           "response.content_part.done", "response.output_item.done"]:
                            # Info events, just log
                            self.ten_env.log_debug(f"[{request_id}] Event: {event_type}")

                    except asyncio.TimeoutError:
                        self.ten_env.log_error(
                            f"[{request_id}] Timeout waiting for audio response"
                        )
                        yield (EVENT_TTS_ERROR, {"message": "Response timeout"})
                        break

            except Exception as e:
                self.ten_env.log_error(
                    f"[{request_id}] Synthesis failed: {e}"
                )
                yield (EVENT_TTS_ERROR, {"message": str(e)})

    async def stop(self):
        """Close WebSocket connection"""
        if self.websocket:
            try:
                # Send session.finish if needed
                if self.session_initialized:
                    finish_event = {"type": "session.finish"}
                    await self.websocket.send(json.dumps(finish_event))
                    await asyncio.sleep(0.1)

                await self.websocket.close()
                self.ten_env.log_info("WebSocket closed")
            except Exception as e:
                self.ten_env.log_error(f"Error closing WebSocket: {e}")
            finally:
                self.websocket = None
                self.session_initialized = False
