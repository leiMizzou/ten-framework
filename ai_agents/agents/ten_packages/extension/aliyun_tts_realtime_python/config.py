#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
#
from pydantic import BaseModel, Field


class AliyunTTSRealtimeConfig(BaseModel):
    api_key: str = Field(default="", description="Aliyun API Key")
    model: str = Field(
        default="qwen-tts-realtime-latest",
        description="TTS model name"
    )
    ws_url: str = Field(
        default="wss://dashscope.aliyuncs.com/api-ws/v1/realtime",
        description="WebSocket URL"
    )
    voice: str = Field(
        default="longxiaochun",
        description="Voice name"
    )
    format: str = Field(
        default="pcm",
        description="Audio format"
    )
    sample_rate: int = Field(
        default=16000,
        description="Sample rate"
    )
    mode: str = Field(
        default="server_commit",
        description="Synthesis mode: server_commit or commit"
    )

    def to_str(self, sensitive_handling: bool = False) -> str:
        """Convert config to string with optional sensitive data masking"""
        config_dict = self.model_dump()
        if sensitive_handling and config_dict.get("api_key"):
            config_dict["api_key"] = "***"
        return str(config_dict)
