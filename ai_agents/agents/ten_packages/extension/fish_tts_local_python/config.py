from typing import Any
import copy
from ten_ai_base import utils
from pydantic import BaseModel, Field


class FishTTSLocalConfig(BaseModel):
    """Configuration for local Fish TTS service"""
    # Base URL for the local Fish TTS service
    base_url: str = "http://host.docker.internal:8000"
    # Debug and logging
    dump: bool = False
    dump_path: str = "/tmp"
    sample_rate: int = 16000
    params: dict[str, Any] = Field(default_factory=dict)
    black_list_keys: list[str] = ["text"]

    def update_params(self) -> None:
        """Update configuration from params dictionary"""
        # Extract base_url if provided in params
        if "base_url" in self.params:
            self.base_url = self.params["base_url"]
            del self.params["base_url"]

        # Ensure format is PCM
        if "format" not in self.params:
            self.params["format"] = "pcm"

        # Set sample rate
        if "sample_rate" in self.params:
            self.sample_rate = int(self.params["sample_rate"])
        elif "samplingRate" in self.params:
            self.sample_rate = int(self.params["samplingRate"])

        # Ensure sample_rate is in params
        self.params["sample_rate"] = self.sample_rate

        # Remove sensitive keys from params
        for key in self.black_list_keys:
            if key in self.params:
                del self.params[key]

    def to_str(self, sensitive_handling: bool = True) -> str:
        """Convert config to string with optional sensitive data handling."""
        if not sensitive_handling:
            return f"{self}"

        config = copy.deepcopy(self)
        return f"{config}"
