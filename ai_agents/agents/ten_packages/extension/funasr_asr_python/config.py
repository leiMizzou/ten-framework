from typing import Any, Dict, List
from pydantic import BaseModel, Field
from ten_ai_base.utils import encrypt


class FunASRConfig(BaseModel):
    ws_url: str = "ws://host.docker.internal:10095"
    language: str = "zh-CN"
    model: str = "paraformer-zh"
    mode: str = "2pass"  # FunASR supports "offline", "online", "2pass"
    hotwords: str = ""  # hotwords for recognition
    sample_rate: int = 16000  # audio sample rate in Hz
    dump: bool = False
    dump_path: str = "/tmp"

    @property
    def url(self) -> str:
        """Map ws_url to url for compatibility."""
        return self.ws_url

    @property
    def chunk_size(self) -> List[int]:
        """Default chunk size for streaming."""
        return [5, 10, 5]

    @property
    def chunk_interval(self) -> int:
        """Default audio chunk interval in ms."""
        return 10

    @property
    def params(self) -> Dict[str, Any]:
        """Return params dict for compatibility."""
        return {
            "url": self.ws_url,
            "language": self.language,
            "model": self.model,
            "mode": self.mode,
            "hotwords": self.hotwords,
        }

    def update(self, params: Dict[str, Any]) -> None:
        """Update configuration with additional parameters."""
        # Skip read-only properties
        read_only_properties = {'url', 'chunk_size', 'chunk_interval', 'params', 'normalized_language'}
        for key, value in params.items():
            if key not in read_only_properties and hasattr(self, key):
                setattr(self, key, value)

    def to_json(self, sensitive_handling: bool = False) -> str:
        """Convert config to JSON string with optional sensitive data handling."""
        config_dict = self.model_dump()
        return str(config_dict)

    @property
    def normalized_language(self):
        if self.language == "zh-CN":
            return "zh-CN"
        elif self.language == "en-US":
            return "en-US"
        elif self.language == "ja-JP":
            return "ja-JP"
        elif self.language == "ko-KR":
            return "ko-KR"
        else:
            return self.language
