# FunASR ASR Python Extension

This is a TEN extension that provides Automatic Speech Recognition (ASR) capabilities using the FunASR WebSocket service.

## Features

- Real-time speech recognition via WebSocket connection
- Support for multiple languages (Chinese, English, Japanese, Korean)
- 2-pass mode for both real-time and final results
- Voice Activity Detection (VAD)
- Inverse Text Normalization (ITN)
- Automatic punctuation
- Hotwords support
- Automatic reconnection with exponential backoff
- Audio dumping for debugging

## Configuration

The extension can be configured through the `property.json` file or via runtime parameters:

### Basic Parameters

- `url` (string): FunASR WebSocket server URL (default: `ws://host.docker.internal:10095`)
- `language` (string): Recognition language (default: `zh-CN`)
  - Supported: `zh-CN`, `en-US`, `ja-JP`, `ko-KR`
- `model` (string): ASR model name (default: `paraformer-zh`)
- `sample_rate` (integer): Audio sample rate in Hz (default: `16000`)

### Advanced Parameters

- `mode` (string): Recognition mode (default: `2pass`)
  - `offline`: Offline recognition (final results only)
  - `online`: Online streaming recognition
  - `2pass`: Both real-time and final results
- `chunk_size` (array): Chunk size configuration for streaming `[start, middle, end]` (default: `[5, 10, 5]`)
- `chunk_interval` (integer): Audio chunk interval in milliseconds (default: `10`)
- `vad_enable` (boolean): Enable Voice Activity Detection (default: `true`)
- `itn_enable` (boolean): Enable Inverse Text Normalization (default: `true`)
- `punctuation_enable` (boolean): Enable automatic punctuation (default: `true`)
- `hotwords` (string): Hotwords for better recognition accuracy

### Debug Parameters

- `dump` (boolean): Enable audio dumping for debugging (default: `false`)
- `dump_path` (string): Path to save dumped audio (default: `/tmp`)

## FunASR Server Setup

This extension requires a running FunASR WebSocket server. You can start one using the official FunASR Docker image:

```bash
docker run -p 10095:10095 \
  -v /path/to/models:/workspace/models \
  registry.cn-hangzhou.aliyuncs.com/funasr_repo/funasr:latest \
  funasr-wss-server-2pass \
  --model-dir /workspace/models/paraformer-zh \
  --online-model-dir /workspace/models/paraformer-zh-online \
  --vad-dir /workspace/models/fsmn-vad \
  --punc-dir /workspace/models/ct-punc \
  --port 10095
```

## Example Configuration

```json
{
    "params": {
        "url": "ws://host.docker.internal:10095",
        "language": "zh-CN",
        "model": "paraformer-zh",
        "mode": "2pass",
        "chunk_size": [5, 10, 5],
        "chunk_interval": 10,
        "vad_enable": true,
        "itn_enable": true,
        "punctuation_enable": true,
        "hotwords": ""
    }
}
```

## API

This extension implements the standard TEN ASR interface defined in `../../system/ten_ai_base/api/asr-interface.json`.

### Input

- Audio frames (PCM16, 16kHz, mono)

### Output

- ASR results with:
  - `text`: Recognized text
  - `final`: Whether this is a final result
  - `start_ms`: Start time in milliseconds
  - `duration_ms`: Duration in milliseconds
  - `language`: Detected/configured language

## Dependencies

- `websockets>=13.0`: WebSocket client library
- `pydantic>=2.0.0`: Configuration validation
- `ten_runtime_python>=0.11`: TEN runtime
- `ten_ai_base>=0.7`: TEN AI base classes

## Development

### File Structure

```
funasr_asr_python/
├── __init__.py           # Package initialization
├── addon.py              # Extension registration
├── config.py             # Configuration models
├── const.py              # Constants
├── extension.py          # Main extension implementation
├── funasr_client.py      # FunASR WebSocket client
├── manifest.json         # Extension manifest
├── property.json         # Default properties
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

### Key Components

1. **FunASRClient**: WebSocket client that handles communication with FunASR server
   - Automatic connection management
   - Binary audio data transmission
   - JSON result reception
   - Error handling and reconnection

2. **FunASRExtension**: Main extension class implementing AsyncASRBaseExtension
   - Audio frame processing
   - Result handling and forwarding
   - Connection lifecycle management
   - Automatic reconnection with exponential backoff

3. **FunASRConfig**: Configuration validation using Pydantic
   - Type-safe configuration
   - Default values
   - Parameter validation

## License

Same as TEN framework.
