#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
from datetime import datetime
import os
import traceback

from ten_ai_base.helper import PCMWriter
from ten_ai_base.message import (
    ModuleError,
    ModuleErrorCode,
    ModuleType,
    ModuleErrorVendorInfo,
    TTSAudioEndReason,
)
from ten_ai_base.struct import TTSTextInput
from ten_ai_base.tts2 import AsyncTTS2BaseExtension
from ten_ai_base.const import LOG_CATEGORY_VENDOR, LOG_CATEGORY_KEY_POINT
from .config import FishTTSLocalConfig

from .fish_tts_local import (
    EVENT_TTS_END,
    EVENT_TTS_ERROR,
    EVENT_TTS_RESPONSE,
    EVENT_TTS_INVALID_KEY_ERROR,
    EVENT_TTS_FLUSH,
    FishTTSLocalClient,
)
from ten_runtime import AsyncTenEnv


class FishTTSLocalExtension(AsyncTTS2BaseExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.config: FishTTSLocalConfig | None = None
        self.client: FishTTSLocalClient | None = None
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
                raise ValueError(
                    "Configuration is empty."
                )

            self.config = FishTTSLocalConfig.model_validate_json(
                config_json_str
            )
            self.config.update_params()

            ten_env.log_info(
                f"LOG_CATEGORY_KEY_POINT: {self.config.to_str(sensitive_handling=True)}",
                category=LOG_CATEGORY_KEY_POINT,
            )

            self.client = FishTTSLocalClient(
                config=self.config, ten_env=ten_env
            )

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

        await super().on_stop(ten_env)
        ten_env.log_debug("on_stop")

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        ten_env.log_debug("on_deinit")

    async def cancel_tts(self) -> None:
        self.current_request_finished = True
        if self.current_request_id:
            self.ten_env.log_debug(
                f"Current request {self.current_request_id} is being cancelled."
            )
            if self.client:
                self.client.cancel()
                if self.request_ts:
                    request_event_interval = int(
                        (datetime.now() - self.request_ts).total_seconds()
                        * 1000
                    )
                    duration_ms = self._calculate_audio_duration_ms()
                    await self.send_tts_audio_end(
                        request_id=self.current_request_id,
                        request_event_interval_ms=request_event_interval,
                        request_total_audio_duration_ms=duration_ms,
                        reason=TTSAudioEndReason.INTERRUPTED,
                    )
        else:
            self.ten_env.log_warn(
                "No current request found, skipping TTS cancellation."
            )

    def vendor(self) -> str:
        return "fish_tts_local"

    def synthesize_audio_sample_rate(self) -> int:
        return self.config.sample_rate if self.config else 16000

    async def request_tts(self, t: TTSTextInput) -> None:
        """Handle TTS requests"""
        try:
            self.ten_env.log_info(
                f"Requesting TTS for text: {t.text}, text_input_end: {t.text_input_end} request ID: {t.request_id}",
            )
            if not self.client:
                self.client = FishTTSLocalClient(
                    config=self.config, ten_env=self.ten_env
                )
                self.ten_env.log_info("TTS client reconnected successfully.")

            self.ten_env.log_info(
                f"current_request_id: {self.current_request_id}, new request_id: {t.request_id}"
            )

            if t.request_id != self.current_request_id:
                self.ten_env.log_info(
                    f"New TTS request with ID: {t.request_id}"
                )
                self.first_chunk = True
                self.sent_ts = datetime.now()
                self.current_request_id = t.request_id
                self.current_request_finished = False
                self.total_audio_bytes = 0
                if t.metadata is not None:
                    self.session_id = t.metadata.get("session_id", "")
                    self.current_turn_id = t.metadata.get("turn_id", -1)

                # Create new PCMWriter for new request_id and clean up old ones
                if self.config and self.config.dump:
                    old_request_ids = [
                        rid
                        for rid in self.recorder_map.keys()
                        if rid != t.request_id
                    ]
                    for old_rid in old_request_ids:
                        try:
                            await self.recorder_map[old_rid].flush()
                            del self.recorder_map[old_rid]
                            self.ten_env.log_debug(
                                f"Cleaned up old PCMWriter for request_id: {old_rid}"
                            )
                        except Exception as e:
                            self.ten_env.log_error(
                                f"Error cleaning up PCMWriter for request_id {old_rid}: {e}"
                            )

                    if t.request_id not in self.recorder_map:
                        dump_file_path = os.path.join(
                            self.config.dump_path,
                            f"fish_tts_local_dump_{t.request_id}.pcm",
                        )
                        self.recorder_map[t.request_id] = PCMWriter(
                            dump_file_path
                        )
                        self.ten_env.log_debug(
                            f"Created PCMWriter for request_id: {t.request_id}, file: {dump_file_path}"
                        )
            elif self.current_request_finished:
                self.ten_env.log_error(
                    f"Received a message for a finished request_id '{t.request_id}'"
                )
                return

            if t.text_input_end:
                self.ten_env.log_debug(
                    f"finish session for request ID: {t.request_id}"
                )
                self.current_request_finished = True

            chunk_count = 0
            async for audio_chunk, event in self.client.get(t.text):
                if event == EVENT_TTS_RESPONSE:
                    if audio_chunk is not None and len(audio_chunk) > 0:
                        chunk_count += 1
                        self.total_audio_bytes += len(audio_chunk)
                        duration_ms = self._calculate_audio_duration_ms()
                        self.ten_env.log_debug(
                            f"receive_audio: duration: {duration_ms} of request id: {self.current_request_id}",
                            category=LOG_CATEGORY_VENDOR,
                        )

                        # Send TTS audio start on first chunk
                        if self.first_chunk:
                            self.request_ts = datetime.now()
                            if self.sent_ts:
                                await self.send_tts_audio_start(
                                    request_id=self.current_request_id,
                                )
                                ttfb = int(
                                    (
                                        datetime.now() - self.sent_ts
                                    ).total_seconds()
                                    * 1000
                                )
                                await self.send_tts_ttfb_metrics(
                                    request_id=self.current_request_id,
                                    ttfb_ms=ttfb,
                                )
                                self.ten_env.log_debug(
                                    f"Sent TTS audio start and TTFB metrics: {ttfb}ms"
                                )
                            self.first_chunk = False

                        # Write to dump file if enabled
                        if (
                            self.config
                            and self.config.dump
                            and self.current_request_id
                            and self.current_request_id in self.recorder_map
                        ):
                            asyncio.create_task(
                                self.recorder_map[
                                    self.current_request_id
                                ].write(audio_chunk)
                            )

                        # Send audio data
                        await self.send_tts_audio_data(audio_chunk)
                    else:
                        self.ten_env.log_debug(
                            "Received empty payload for TTS response"
                        )

                elif event == EVENT_TTS_END:
                    self.ten_env.log_debug(
                        "Received TTS_END event from Fish TTS Local"
                    )
                    if self.request_ts and t.text_input_end:
                        request_event_interval = int(
                            (datetime.now() - self.request_ts).total_seconds()
                            * 1000
                        )
                        duration_ms = self._calculate_audio_duration_ms()
                        await self.send_tts_audio_end(
                            request_id=self.current_request_id,
                            request_event_interval_ms=request_event_interval,
                            request_total_audio_duration_ms=duration_ms,
                        )
                        self.ten_env.log_debug(
                            f"Sent TTS audio end event, interval: {request_event_interval}ms, duration: {duration_ms}ms",
                        )
                    break

                elif event == EVENT_TTS_ERROR:
                    error_msg = (
                        audio_chunk.decode("utf-8")
                        if audio_chunk
                        else "Unknown client error"
                    )
                    raise RuntimeError(error_msg)

                elif event == EVENT_TTS_FLUSH:
                    self.ten_env.log_debug("Received TTS_FLUSH event")
                    break

            self.ten_env.log_debug(
                f"TTS processing completed, total chunks: {chunk_count}"
            )

        except Exception as e:
            self.ten_env.log_error(
                f"Error in request_tts: {traceback.format_exc()}"
            )
            await self.send_tts_error(
                request_id=self.current_request_id or t.request_id,
                error=ModuleError(
                    message=str(e),
                    module=ModuleType.TTS,
                    code=ModuleErrorCode.NON_FATAL_ERROR,
                    vendor_info=ModuleErrorVendorInfo(vendor=self.vendor()),
                ),
            )

    def _calculate_audio_duration_ms(self) -> int:
        if self.config is None:
            return 0
        bytes_per_sample = 2  # 16-bit PCM
        channels = 1  # Mono
        duration_sec = self.total_audio_bytes / (
            self.synthesize_audio_sample_rate() * bytes_per_sample * channels
        )
        return int(duration_sec * 1000)
