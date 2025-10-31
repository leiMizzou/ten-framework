#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
#
import asyncio
import traceback
from datetime import datetime

from ten_ai_base.helper import PCMWriter
from ten_ai_base.message import (
    ModuleError,
    ModuleErrorCode,
    ModuleType,
    ModuleErrorVendorInfo,
)
from ten_ai_base.struct import TTSTextInput
from ten_ai_base.tts2 import AsyncTTS2BaseExtension
from ten_ai_base.const import LOG_CATEGORY_VENDOR, LOG_CATEGORY_KEY_POINT
from ten_runtime import AsyncTenEnv

from .config import AliyunTTSRealtimeConfig
from .aliyun_tts_realtime import (
    EVENT_TTS_END,
    EVENT_TTS_ERROR,
    EVENT_TTS_RESPONSE,
    EVENT_TTS_FLUSH,
    AliyunTTSRealtimeClient,
)


class AliyunTTSRealtimeExtension(AsyncTTS2BaseExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.config: AliyunTTSRealtimeConfig | None = None
        self.client: AliyunTTSRealtimeClient | None = None
        self.current_request_id: str | None = None
        self.current_turn_id: int = -1
        self.sent_ts: datetime | None = None
        self.request_ts: datetime | None = None
        self.current_request_finished: bool = False
        self.total_audio_bytes: int = 0
        self.first_chunk: bool = False
        self.recorder_map: dict[str, PCMWriter] = {}

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        try:
            await super().on_init(ten_env)
            config_json_str, _ = await self.ten_env.get_property_to_json("")

            if not config_json_str or config_json_str.strip() == "{}":
                raise ValueError("Configuration is empty")

            self.config = AliyunTTSRealtimeConfig.model_validate_json(
                config_json_str
            )

            ten_env.log_info(
                f"LOG_CATEGORY_KEY_POINT: {self.config.to_str(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )

            # Validate API key
            if not self.config.api_key:
                raise ValueError("API key is required")

            self.client = AliyunTTSRealtimeClient(
                config=self.config, ten_env=ten_env
            )

            ten_env.log_info("Aliyun TTS Realtime extension initialized")

        except Exception as e:
            ten_env.log_error(f"on_init failed: {traceback.format_exc()}")
            await self.send_tts_error(
                request_id="",
                error=ModuleError(
                    message=f"Initialization failed: {e}",
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.FATAL_ERROR,
                    vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                ),
            )

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        if self.client:
            await self.client.stop()
            self.client = None

        # Clean up all PCMWriters
        for request_id, recorder in self.recorder_map.items():
            try:
                await recorder.flush()
                ten_env.log_debug(
                    f"Flushed PCMWriter for request_id: {request_id}"
                )
            except Exception as e:
                ten_env.log_error(
                    f"Error flushing PCMWriter for request_id {request_id}: {e}"
                )

        self.recorder_map.clear()
        await super().on_stop(ten_env)

    async def request_tts(self, t: TTSTextInput) -> None:
        """Handle text input for TTS synthesis"""
        text = t.text
        request_id = t.request_id
        # Get turn_id from metadata if available, otherwise use -1
        turn_id = t.metadata.get("turn_id", -1)

        self.current_turn_id = turn_id
        self.current_request_id = request_id
        self.current_request_finished = False
        self.total_audio_bytes = 0
        self.first_chunk = True
        self.request_ts = datetime.now()

        self.ten_env.log_info(
            f"[{request_id}] Processing TTS request, text: '{text[:50]}...'"
        )

        if not text or len(text.strip()) == 0:
            self.ten_env.log_warn(f"[{request_id}] Empty text received")
            await self.send_tts_audio_end(
                request_id=request_id,
                request_event_interval_ms=0,
            )
            return

        # Initialize PCM recorder if dump is enabled
        recorder: PCMWriter | None = None
        if self.config and hasattr(self.config, 'dump') and self.config.dump:
            recorder = PCMWriter(
                channels=1,
                sample_width=2,
                framerate=self.config.sample_rate,
                dump_path=getattr(self.config, 'dump_path', './'),
                file_name_prefix=f"aliyun_tts_{request_id}",
            )
            self.recorder_map[request_id] = recorder

        try:
            # Start synthesis
            async for event_type, data in self.client.synthesize(text, request_id):
                if event_type == EVENT_TTS_RESPONSE:
                    # Audio data chunk
                    audio_data = data
                    if audio_data and len(audio_data) > 0:
                        self.total_audio_bytes += len(audio_data)

                        if self.first_chunk:
                            self.sent_ts = datetime.now()
                            ttft = int(
                                (self.sent_ts - self.request_ts).total_seconds() * 1000
                            )
                            self.ten_env.log_info(
                                f"[{request_id}] First audio chunk received, "
                                f"TTFT: {ttft}ms, size: {len(audio_data)} bytes"
                            )
                            self.first_chunk = False

                            # Send audio start event
                            await self.send_tts_audio_start(
                                request_id=request_id,
                                turn_id=self.current_turn_id,
                            )

                        # Record audio if enabled
                        if recorder:
                            await recorder.write(audio_data)

                        # Send audio to framework
                        await self.send_tts_audio_data(audio_data)

                elif event_type == EVENT_TTS_END:
                    # Synthesis completed
                    self.current_request_finished = True

                    if self.sent_ts:
                        total_time = int(
                            (datetime.now() - self.request_ts).total_seconds() * 1000
                        )
                        self.ten_env.log_info(
                            f"[{request_id}] TTS completed, "
                            f"total_time: {total_time}ms, "
                            f"total_bytes: {self.total_audio_bytes}"
                        )

                    # Flush recorder
                    if recorder:
                        await recorder.flush()
                        self.recorder_map.pop(request_id, None)

                    # Send audio end event
                    request_event_interval = int(
                        (datetime.now() - self.request_ts).total_seconds() * 1000
                    ) if self.request_ts else 0

                    await self.send_tts_audio_end(
                        request_id=request_id,
                        request_event_interval_ms=request_event_interval,
                    )
                    break

                elif event_type == EVENT_TTS_ERROR:
                    # Error occurred
                    error_info = data
                    error_msg = error_info.get("message", "Unknown error")

                    self.ten_env.log_error(
                        f"[{request_id}] TTS error: {error_msg}"
                    )

                    # Cleanup recorder
                    if recorder:
                        self.recorder_map.pop(request_id, None)

                    await self.send_tts_error(
                        request_id=request_id,
                        error=ModuleError(
                            message=error_msg,
                            module=ModuleType.TTS,
                            code=ModuleErrorCode.NON_FATAL_ERROR,
                            vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                        ),
                    )
                    break

        except Exception as e:
            self.ten_env.log_error(
                f"[{request_id}] TTS synthesis exception: {traceback.format_exc()}"
            )

            # Cleanup recorder
            if recorder:
                self.recorder_map.pop(request_id, None)

            await self.send_tts_error(
                request_id=request_id,
                error=ModuleError(
                    message=f"Synthesis failed: {e}",
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.NON_FATAL_ERROR,
                    vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                ),
            )

    @staticmethod
    def vendor() -> str:
        return "aliyun"

    def synthesize_audio_sample_rate(self) -> int:
        """Get the sample rate for the TTS audio"""
        return self.config.sample_rate if self.config else 16000
