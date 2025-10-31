from datetime import datetime
import json
import os

from typing_extensions import override
from .const import (
    DUMP_FILE_NAME,
    MODULE_NAME_ASR,
)
from ten_ai_base.asr import (
    ASRBufferConfig,
    ASRBufferConfigModeKeep,
    ASRResult,
    AsyncASRBaseExtension,
)
from ten_ai_base.message import (
    ModuleError,
    ModuleErrorVendorInfo,
    ModuleErrorCode,
)
from ten_runtime import (
    AsyncTenEnv,
    AudioFrame,
)
from ten_ai_base.const import (
    LOG_CATEGORY_KEY_POINT,
    LOG_CATEGORY_VENDOR,
)

import asyncio
from .config import FunASRConfig
from .funasr_client import FunASRClient
from ten_ai_base.dumper import Dumper


class FunASRExtension(AsyncASRBaseExtension):
    def __init__(self, name: str):
        super().__init__(name)
        self.connected: bool = False
        self.client: FunASRClient | None = None
        self.config: FunASRConfig | None = None
        self.audio_dumper: Dumper | None = None
        self.sent_user_audio_duration_ms_before_last_reset: int = 0
        self.last_finalize_timestamp: int = 0
        self.reconnect_attempts: int = 0
        self.max_reconnect_attempts: int = 5

    @override
    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        if self.audio_dumper:
            await self.audio_dumper.stop()
            self.audio_dumper = None

    @override
    def vendor(self) -> str:
        """Get the name of the ASR vendor."""
        return "funasr"

    @override
    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)

        config_json, _ = await ten_env.get_property_to_json("")

        try:
            self.config = FunASRConfig.model_validate_json(config_json)
            self.config.update(self.config.params)
            ten_env.log_info(
                f"KEYPOINT vendor_config: {self.config.to_json(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )

            if self.config.dump:
                dump_file_path = os.path.join(
                    self.config.dump_path, DUMP_FILE_NAME
                )
                self.audio_dumper = Dumper(dump_file_path)
        except Exception as e:
            ten_env.log_error(f"invalid property: {e}")
            self.config = FunASRConfig.model_validate_json("{}")
            await self.send_asr_error(
                ModuleError(
                    module=MODULE_NAME_ASR,
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message=str(e),
                ),
            )

    @override
    async def start_connection(self) -> None:
        assert self.config is not None
        self.ten_env.log_info("start_connection")

        try:
            await self.stop_connection()

            self.client = FunASRClient(
                url=self.config.url,
                mode=self.config.mode,
                chunk_size=self.config.chunk_size,
                chunk_interval=self.config.chunk_interval,
                logger=self.ten_env,
            )

            # Register event handlers
            self.client.on_open = self._funasr_event_handler_on_open
            self.client.on_close = self._funasr_event_handler_on_close
            self.client.on_message = self._funasr_event_handler_on_message
            self.client.on_error = self._funasr_event_handler_on_error

            if self.audio_dumper:
                await self.audio_dumper.start()

            # Connect to FunASR server
            result = await self.client.connect()
            if not result:
                self.ten_env.log_error("failed to connect to FunASR")
                await self.send_asr_error(
                    ModuleError(
                        module=MODULE_NAME_ASR,
                        code=ModuleErrorCode.NON_FATAL_ERROR.value,
                        message="failed to connect to FunASR",
                    )
                )
                asyncio.create_task(self._handle_reconnect())
            else:
                self.ten_env.log_info("start_connection completed")

        except Exception as e:
            self.ten_env.log_error(
                f"KEYPOINT start_connection failed: invalid vendor config: {e}"
            )
            await self.send_asr_error(
                ModuleError(
                    module=MODULE_NAME_ASR,
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message=str(e),
                ),
            )

    @override
    async def finalize(self, session_id: str | None) -> None:
        assert self.config is not None

        self.last_finalize_timestamp = int(datetime.now().timestamp() * 1000)
        self.ten_env.log_info(
            f"vendor_cmd: finalize start at {self.last_finalize_timestamp}",
            category=LOG_CATEGORY_VENDOR,
        )
        await self._handle_finalize()

    async def _handle_asr_result(
        self,
        text: str,
        final: bool,
        start_ms: int = 0,
        duration_ms: int = 0,
        language: str = "",
    ):
        """Handle the ASR result from FunASR."""
        assert self.config is not None

        if final:
            await self._finalize_end()

        asr_result = ASRResult(
            text=text,
            final=final,
            start_ms=start_ms,
            duration_ms=duration_ms,
            language=language,
            words=[],
        )
        await self.send_asr_result(asr_result)

    async def _funasr_event_handler_on_open(self):
        """Handle the open event from FunASR."""
        self.ten_env.log_info(
            "vendor_status_changed: on_open event",
            category=LOG_CATEGORY_VENDOR,
        )
        self.sent_user_audio_duration_ms_before_last_reset += (
            self.audio_timeline.get_total_user_audio_duration()
        )
        self.audio_timeline.reset()
        self.connected = True
        self.reconnect_attempts = 0

    async def _funasr_event_handler_on_close(self):
        """Handle the close event from FunASR."""
        self.ten_env.log_info(
            "vendor_status_changed: on_close",
            category=LOG_CATEGORY_VENDOR,
        )
        self.connected = False

        if not self.stopped:
            self.ten_env.log_warn(
                "FunASR connection closed unexpectedly. Reconnecting..."
            )
            await self._handle_reconnect()

    async def _funasr_event_handler_on_message(self, message: dict):
        """
        Handle the message event from FunASR.

        FunASR message format:
        {
            "text": "recognition result",
            "is_final": true/false,
            "timestamp": [start_ms, end_ms],
            "mode": "2pass-online" or "2pass-offline"
        }
        """
        assert self.config is not None

        try:
            self.ten_env.log_debug(
                f"vendor_result: on_message: {json.dumps(message)}",
                category=LOG_CATEGORY_VENDOR,
            )

            # Extract text from FunASR response
            text = message.get("text", "")
            if not text:
                return

            # Determine if this is a final result
            is_final = message.get("is_final", False)
            mode = message.get("mode", "")

            # For 2pass mode, offline results are final
            if "offline" in mode:
                is_final = True

            # Extract timestamp if available
            timestamp = message.get("timestamp", [0, 0])
            if isinstance(timestamp, list) and len(timestamp) >= 2:
                start_ms = int(timestamp[0])
                duration_ms = int(timestamp[1] - timestamp[0])
            else:
                start_ms = 0
                duration_ms = 0

            # Calculate actual start time based on audio timeline
            actual_start_ms = int(
                self.audio_timeline.get_audio_duration_before_time(start_ms)
                + self.sent_user_audio_duration_ms_before_last_reset
            )

            language = self.config.language

            self.ten_env.log_debug(
                f"funasr event callback on_message: {text}, language: {language}, is_final: {is_final}"
            )

            await self._handle_asr_result(
                text,
                final=is_final,
                start_ms=actual_start_ms,
                duration_ms=duration_ms,
                language=language,
            )

        except Exception as e:
            self.ten_env.log_error(f"Error processing FunASR message: {e}")

    async def _funasr_event_handler_on_error(self, error: Exception):
        """Handle the error event from FunASR."""
        self.ten_env.log_error(
            f"vendor_error: {str(error)}",
            category=LOG_CATEGORY_VENDOR,
        )

        await self.send_asr_error(
            ModuleError(
                module=MODULE_NAME_ASR,
                code=ModuleErrorCode.NON_FATAL_ERROR.value,
                message=str(error),
            ),
            ModuleErrorVendorInfo(
                vendor=self.vendor(),
                code="unknown",
                message=str(error),
            ),
        )

    async def _handle_finalize(self):
        """Handle finalize request."""
        assert self.config is not None

        if self.client is None or not self.client.is_connected():
            self.ten_env.log_debug("finalize: client is not connected")
            return

        await self.client.finalize()
        self.ten_env.log_info(
            "vendor_cmd: finalize completed",
            category=LOG_CATEGORY_VENDOR,
        )

    async def _handle_reconnect(self):
        """Handle reconnection with exponential backoff."""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            self.ten_env.log_error(
                f"Max reconnection attempts ({self.max_reconnect_attempts}) reached"
            )
            await self.send_asr_error(
                ModuleError(
                    module=MODULE_NAME_ASR,
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message="Failed to reconnect to FunASR after maximum attempts",
                )
            )
            return

        self.reconnect_attempts += 1
        delay = 0.3 * (2 ** (self.reconnect_attempts - 1))  # Exponential backoff

        self.ten_env.log_warn(
            f"Attempting reconnection #{self.reconnect_attempts}/{self.max_reconnect_attempts} "
            f"after {delay} seconds delay..."
        )

        try:
            await asyncio.sleep(delay)
            await self.start_connection()
        except Exception as e:
            self.ten_env.log_error(f"Reconnection attempt failed: {e}")
            if self.reconnect_attempts >= self.max_reconnect_attempts:
                await self.send_asr_error(
                    ModuleError(
                        module=MODULE_NAME_ASR,
                        code=ModuleErrorCode.FATAL_ERROR.value,
                        message=f"All reconnection attempts failed. Last error: {str(e)}",
                    )
                )

    async def _finalize_end(self) -> None:
        """Handle finalize end logic."""
        if self.last_finalize_timestamp != 0:
            timestamp = int(datetime.now().timestamp() * 1000)
            latency = timestamp - self.last_finalize_timestamp
            self.ten_env.log_debug(
                f"KEYPOINT finalize end at {timestamp}, counter: {latency}"
            )
            self.last_finalize_timestamp = 0
            await self.send_asr_finalize_end()

    async def stop_connection(self) -> None:
        """Stop the FunASR connection."""
        try:
            if self.client:
                await self.client.close()
                self.client = None
                self.connected = False
                self.ten_env.log_info("FunASR connection stopped")
        except Exception as e:
            self.ten_env.log_error(f"Error stopping FunASR connection: {e}")

    @override
    def is_connected(self) -> bool:
        return self.connected and self.client is not None

    @override
    def buffer_strategy(self) -> ASRBufferConfig:
        return ASRBufferConfigModeKeep(byte_limit=1024 * 1024 * 10)

    @override
    def input_audio_sample_rate(self) -> int:
        assert self.config is not None
        return self.config.sample_rate

    @override
    async def send_audio(
        self, frame: AudioFrame, session_id: str | None
    ) -> bool:
        assert self.config is not None
        assert self.client is not None

        buf = frame.lock_buf()
        if self.audio_dumper:
            await self.audio_dumper.push_bytes(bytes(buf))
        self.audio_timeline.add_user_audio(
            int(len(buf) / (self.config.sample_rate / 1000 * 2))
        )
        await self.client.send_audio(bytes(buf))
        frame.unlock_buf(buf)

        return True
