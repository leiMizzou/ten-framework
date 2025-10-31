# TEN Agent 部署和运维指南

> **版本**: 1.1
> **适用于**: TEN Agent v0.7.9+
> **最后更新**: 2025-10-31
> **文档版本**: 基于实际代码分析和验证

## ⚠️ 重要说明

**本文档描述的是自定义本地部署配置**，使用本地 TTS/ASR 服务以减少云服务依赖和成本：
- **STT**: FunASR (本地 WebSocket 服务)
- **TTS**: CosyVoice (本地 HTTP 服务)
- **LLM**: DeepSeek API (OpenAI 兼容接口)

**标准 voice-assistant 配置**使用云服务：
- **STT**: Deepgram API
- **TTS**: ElevenLabs API
- **LLM**: OpenAI API

如需标准配置，请参考 `/ai_agents/agents/examples/voice-assistant/README.md`

## 快速导航

**新用户推荐路径**:
1. 标准配置快速开始 → [voice-assistant/README.md](ai_agents/agents/examples/voice-assistant/README.md)
2. Docker 一键部署 → [Docker 部署](#release-as-docker-image)

**本文档适合**:
- 需要使用本地 TTS/ASR 服务的场景
- 希望减少云服务 API 调用成本
- 离线或内网部署需求
- 对延迟和数据隐私有特殊要求

## 目录
- [系统架构](#系统架构)
- [组件清单](#组件清单)
- [启动顺序](#启动顺序)
- [配置文件](#配置文件)
- [端口映射](#端口映射)
- [组件交互流程](#组件交互流程)
- [健康检查](#健康检查)
- [问题排查](#问题排查)
- [常用命令](#常用命令)
- [工具和构建系统](#工具和构建系统)
- [扩展包系统](#扩展包系统)
- [环境变量完整清单](#环境变量完整清单)
- [Voice Assistant 变体](#voice-assistant-变体)
- [CI/CD 和自动化](#cicd-和自动化)
- [生产环境部署](#生产环境部署)
- [术语表](#术语表)

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                         浏览器客户端                          │
│                   http://localhost:3000                      │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/WebSocket
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              TEN Agent Docker Container                      │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐ │
│  │   Frontend     │  │  Backend API   │  │ Graph Designer│ │
│  │   (Next.js)    │  │   (Go/Gin)     │  │    (tman)     │ │
│  │   Port: 3001   │  │   Port: 8080   │  │  Port: 49483  │ │
│  └────────────────┘  └────────────────┘  └───────────────┘ │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │          TEN Agent Runtime (Extension Graph)            ││
│  │  ┌──────────┐ ┌──────────┐ ┌────────┐ ┌──────────────┐││
│  │  │Agora RTC │ │   STT    │ │  LLM   │ │     TTS      │││
│  │  │          │→│ (FunASR) │→│(OpenAI)│→│ (CosyVoice)  │││
│  │  └──────────┘ └──────────┘ └────────┘ └──────────────┘││
│  └─────────────────────────────────────────────────────────┘│
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌───────────────┐ ┌─────────────┐ ┌────────────────────┐
│  CosyVoice    │ │   FunASR    │ │   DeepSeek API     │
│  TTS Server   │ │  ASR Server │ │   (Cloud Service)  │
│ (Mac Host)    │ │(Mac Host)   │ │                    │
│ Port: 8090    │ │Port: 10095  │ │ api.deepseek.com   │
└───────────────┘ └─────────────┘ └────────────────────┘
```

---

## 组件清单

### 1. CosyVoice TTS Server (宿主机运行)
- **位置**: `/tmp/CosyVoice/`
- **模型**: CosyVoice2-0.5B
- **模型路径**: `/tmp/CosyVoice/pretrained_models/CosyVoice2-0.5B/`
- **启动脚本**: `http_api_server.py`
- **端口**: 8090
- **运行环境**: Python 3.10 venv

### 2. TEN Agent Docker Container
- **容器名称**: `ten_agent_dev`
- **镜像**: `ghcr.io/ten-framework/ten_agent_build:0.7.9`
- **工作目录**: `/app/agents/examples/voice-assistant/`

#### 子组件:
- **Frontend (Next.js)**
  - 端口: 3000 (默认)
  - 注意: 如果 3000 被占用，会自动使用 3001
  - 工作目录: `/app/playground/`

- **Backend API (Go)**
  - 端口: 8080
  - 可执行文件: `./bin/api`

- **Graph Designer**
  - 端口: 49483
  - 命令: `tman designer`

### 3. FunASR Server (宿主机运行)
- **端口**: 10095 (WebSocket)
- **语言**: 中文 (zh)
- **模型**: paraformer-zh

### 4. 外部服务
- **DeepSeek API**: https://api.deepseek.com (OpenAI 兼容接口)
- **Agora RTC**: 实时音视频服务

---

## 启动顺序

### 步骤 1: 启动 CosyVoice TTS Server

```bash
# 1. 进入 CosyVoice 目录
cd /tmp/CosyVoice

# 2. 激活虚拟环境
source venv/bin/activate

# 3. 启动服务器
python http_api_server.py --port 8090 --model_dir pretrained_models/CosyVoice2-0.5B

# 验证启动成功
curl http://localhost:8090/health
# 预期输出: {"status":"healthy","model":"CosyVoice2"}
```

**日志位置**: stdout 或可重定向到 `/tmp/cosyvoice.log`

### 步骤 2: 启动 FunASR Server

```bash
# 确认 FunASR 在 WebSocket 端口 10095 上运行
# (具体启动命令取决于 FunASR 安装方式)
```

### 步骤 3: 启动 TEN Agent Container

```bash
# 1. 确保容器正在运行
docker ps | grep ten_agent_dev

# 2. 如果容器未运行，启动它
docker start ten_agent_dev

# 3. 进入容器并启动所有服务
docker exec ten_agent_dev bash -c "cd /app/agents/examples/voice-assistant && task run"
```

这个命令会并行启动:
- Backend API Server (port 8080)
- Frontend (port 3001)
- Graph Designer (port 49483)

**等待时间**: 约 10-15 秒直到所有服务完全启动

### 步骤 4: 验证所有服务

```bash
# 检查 Backend API
curl http://localhost:8080/health
# 预期: {"code":"0","data":null,"msg":"ok"}

# 检查 Frontend
curl -I http://localhost:3000
# 预期: HTTP/1.1 200 OK

# 检查 CosyVoice
curl http://localhost:8090/health
# 预期: {"status":"healthy","model":"CosyVoice2"}

# 检查 Graphs 配置
curl http://localhost:8080/graphs
# 预期: {"code":"0","data":[{"auto_start":true,"graph_id":"voice_assistant","name":"voice_assistant"}],"msg":"success"}
```

---

## 配置文件

### 1. 主配置文件: property.json

**位置**: `/Users/leihua/Documents/GitHub/ten-framework/ai_agents/agents/examples/voice-assistant/tenapp/property.json`

**容器内路径**: `/app/agents/examples/voice-assistant/tenapp/property.json`

**关键配置节点**:

#### Agora RTC (音视频)
```json
{
  "name": "agora_rtc",
  "addon": "agora_rtc",
  "property": {
    "app_id": "${env:AGORA_APP_ID}",
    "app_certificate": "${env:AGORA_APP_CERTIFICATE|}",
    "channel": "ten_agent_test",
    "stream_id": 1234,
    "remote_stream_id": 123,
    "subscribe_audio": true,
    "publish_audio": true,
    "publish_data": true
  }
}
```

#### STT (语音识别)
```json
{
  "name": "stt",
  "addon": "funasr_asr_python",
  "property": {
    "ws_url": "ws://host.docker.internal:10095",
    "mode": "2pass",
    "language": "zh",
    "model": "paraformer-zh"
  }
}
```

#### LLM (语言模型) - **DeepSeek**
```json
{
  "name": "llm",
  "addon": "openai_llm2_python",
  "property": {
    "base_url": "${env:OPENAI_API_BASE|https://api.openai.com/v1}",
    "api_key": "${env:OPENAI_API_KEY}",
    "model": "${env:OPENAI_MODEL}",
    "max_tokens": 512,
    "frequency_penalty": 0.9
  }
}
```

**当前配置** (使用 DeepSeek):
- Base URL: `https://api.deepseek.com`
- Model: `deepseek-chat`
- API Key: DeepSeek API Key (通过 OPENAI_API_KEY 环境变量传递)

#### TTS (语音合成) - **CosyVoice**
```json
{
  "name": "tts",
  "addon": "fish_tts_local_python",
  "property": {
    "base_url": "http://host.docker.internal:8090",
    "dump": false,
    "params": {
      "text": "",
      "spk_id": "中文男"
    }
  }
}
```

**注意**: CosyVoice2-0.5B 使用零样本推理，spk_id 可以是任意描述性文本（如"中文男"、"中文女"），但实际音色由 prompt 音频决定。

**重要**:
- `host.docker.internal` 允许 Docker 容器访问宿主机服务
- 端口 8090 对应 CosyVoice TTS Server

### 切换到线上 TTS 服务

系统支持通过修改配置文件在本地 TTS 和线上 TTS 之间切换。

#### 方式一：阿里云通义千问 TTS (推荐)

**优势**：
- 无需部署本地服务，降低资源消耗
- 更快的响应速度和更高的并发能力
- 支持多种音色和语言
- WebSocket 实时流式传输，低延迟

**配置步骤**：

1. **获取 API Key**：访问 [阿里云 DashScope](https://dashscope.console.aliyun.com/) 获取 API Key

2. **修改 property.json**：将 TTS 配置块替换为：

```json
{
  "name": "tts",
  "addon": "aliyun_tts_realtime_python",
  "extension_group": "tts",
  "property": {
    "api_key": "${env:ALIYUN_TTS_API_KEY}",
    "model": "qwen-tts-realtime-latest",
    "ws_url": "wss://dashscope.aliyuncs.com/api-ws/v1/realtime",
    "voice": "longxiaochun",
    "format": "pcm",
    "sample_rate": 16000,
    "mode": "server_commit"
  }
}
```

3. **设置环境变量** (`.env` 或 docker-compose.yml)：

```bash
# 阿里云通义千问 TTS
ALIYUN_TTS_API_KEY=sk-xxxxxxxxxxxxxx
```

4. **重启服务**：

```bash
# 停止现有服务
docker exec ten_agent_dev pkill -f "task run"

# 重新启动
docker exec ten_agent_dev bash -c "cd /app/agents/examples/voice-assistant && task run"
```

**配置参数说明**：

| 参数 | 说明 | 可选值 |
|------|------|--------|
| `model` | 模型名称 | `qwen-tts-realtime-latest` |
| `voice` | 音色 | `longxiaochun`（龙小春）, `longwan`（龙婉）, `longshuo`（龙硕）, `longzhe`（龙哲） |
| `format` | 音频格式 | `pcm`, `mp3`, `wav` |
| `sample_rate` | 采样率 | `8000`, `16000`, `24000`, `48000` |
| `mode` | 合成模式 | `server_commit`（智能分段）, `commit`（手动控制） |

**合成模式选择**：

- **`server_commit` 模式**（推荐）：
  - 服务端智能判断文本分段和合成时机
  - 适合低延迟场景，如 GPS 导航、实时对话
  - 客户端只需发送文本，无需手动控制

- **`commit` 模式**：
  - 客户端主动控制合成时机
  - 适合需要精细控制断句和停顿的场景，如新闻播报

#### 方式二：其他线上 TTS 服务

系统也支持其他线上 TTS 服务，如：

**ElevenLabs**（标准配置）：
```json
{
  "name": "tts",
  "addon": "elevenlabs_tts2_python",
  "extension_group": "tts",
  "property": {
    "params": {
      "key": "${env:ELEVENLABS_TTS_KEY}",
      "model_id": "eleven_multilingual_v2",
      "voice_id": "pNInz6obpgDQGcFmaJgB",
      "output_format": "pcm_16000"
    }
  }
}
```

**Azure TTS**：
```json
{
  "name": "tts",
  "addon": "azure_tts_python",
  "extension_group": "tts",
  "property": {
    "api_key": "${env:AZURE_TTS_KEY}",
    "region": "${env:AZURE_TTS_REGION}",
    "voice_name": "zh-CN-XiaoxiaoNeural",
    "output_format": "raw-16khz-16bit-mono-pcm"
  }
}
```

**OpenAI TTS**：
```json
{
  "name": "tts",
  "addon": "openai_tts2_python",
  "extension_group": "tts",
  "property": {
    "api_key": "${env:OPENAI_API_KEY}",
    "model": "tts-1",
    "voice": "alloy",
    "response_format": "pcm"
  }
}
```

#### TTS 配置对比

| 特性 | CosyVoice (本地) | 阿里云通义千问 | ElevenLabs | Azure TTS |
|------|------------------|----------------|------------|-----------|
| **部署方式** | 本地服务 | 云服务 | 云服务 | 云服务 |
| **成本** | 免费（硬件成本） | 按量计费 | 按字符计费 | 按字符计费 |
| **延迟** | 低（本地网络） | 低（WebSocket 流式） | 中 | 低 |
| **并发能力** | 受限于本地资源 | 高 | 高 | 高 |
| **音色定制** | 支持（零样本克隆） | 预设音色 | 多种音色 | 神经网络音色 |
| **离线可用** | ✅ | ❌ | ❌ | ❌ |
| **配置复杂度** | 高（需部署服务） | 低 | 低 | 低 |
| **适用场景** | 离线/内网/定制化 | 在线/实时对话 | 高质量语音 | 企业级应用 |

#### 快速切换配置脚本

创建 `/tmp/switch_tts_config.sh` 方便快速切换：

```bash
#!/bin/bash

PROPERTY_FILE="/Users/leihua/Documents/GitHub/ten-framework/ai_agents/agents/examples/voice-assistant/tenapp/property.json"

case "$1" in
  local)
    echo "切换到本地 CosyVoice TTS..."
    # 备份当前配置
    cp "$PROPERTY_FILE" "$PROPERTY_FILE.backup.$(date +%Y%m%d%H%M%S)"
    # 使用 jq 修改配置（需要安装 jq）
    jq '.ten.predefined_graphs[0].graph.nodes |= map(
      if .name == "tts" then
        .addon = "fish_tts_local_python" |
        .property = {
          "base_url": "http://host.docker.internal:8090",
          "dump": false,
          "params": {
            "text": "",
            "spk_id": "中文男",
            "sample_rate": 16000,
            "format": "pcm"
          }
        }
      else . end
    )' "$PROPERTY_FILE" > "$PROPERTY_FILE.tmp" && mv "$PROPERTY_FILE.tmp" "$PROPERTY_FILE"
    echo "✅ 已切换到本地 CosyVoice"
    ;;

  aliyun)
    echo "切换到阿里云通义千问 TTS..."
    # 备份当前配置
    cp "$PROPERTY_FILE" "$PROPERTY_FILE.backup.$(date +%Y%m%d%H%M%S)"
    # 使用 jq 修改配置
    jq '.ten.predefined_graphs[0].graph.nodes |= map(
      if .name == "tts" then
        .addon = "aliyun_tts_realtime_python" |
        .property = {
          "api_key": "${env:ALIYUN_TTS_API_KEY}",
          "model": "qwen-tts-realtime-latest",
          "ws_url": "wss://dashscope.aliyuncs.com/api-ws/v1/realtime",
          "voice": "longxiaochun",
          "format": "pcm",
          "sample_rate": 16000,
          "mode": "server_commit"
        }
      else . end
    )' "$PROPERTY_FILE" > "$PROPERTY_FILE.tmp" && mv "$PROPERTY_FILE.tmp" "$PROPERTY_FILE"
    echo "✅ 已切换到阿里云通义千问 TTS"
    ;;

  elevenlabs)
    echo "切换到 ElevenLabs TTS..."
    cp "$PROPERTY_FILE" "$PROPERTY_FILE.backup.$(date +%Y%m%d%H%M%S)"
    jq '.ten.predefined_graphs[0].graph.nodes |= map(
      if .name == "tts" then
        .addon = "elevenlabs_tts2_python" |
        .property = {
          "params": {
            "key": "${env:ELEVENLABS_TTS_KEY}",
            "model_id": "eleven_multilingual_v2",
            "voice_id": "pNInz6obpgDQGcFmaJgB",
            "output_format": "pcm_16000"
          }
        }
      else . end
    )' "$PROPERTY_FILE" > "$PROPERTY_FILE.tmp" && mv "$PROPERTY_FILE.tmp" "$PROPERTY_FILE"
    echo "✅ 已切换到 ElevenLabs TTS"
    ;;

  *)
    echo "Usage: $0 {local|aliyun|elevenlabs}"
    echo ""
    echo "Examples:"
    echo "  $0 local       # 切换到本地 CosyVoice"
    echo "  $0 aliyun      # 切换到阿里云通义千问"
    echo "  $0 elevenlabs  # 切换到 ElevenLabs"
    exit 1
    ;;
esac

echo ""
echo "重启服务以应用新配置："
echo "  docker exec ten_agent_dev pkill -f 'task run'"
echo "  docker exec ten_agent_dev bash -c 'cd /app/agents/examples/voice-assistant && task run'"
```

**使用方法**：

```bash
# 安装 jq（如果未安装）
brew install jq  # macOS
# sudo apt install jq  # Ubuntu/Debian

# 添加执行权限
chmod +x /tmp/switch_tts_config.sh

# 切换到阿里云 TTS
/tmp/switch_tts_config.sh aliyun

# 切换回本地 TTS
/tmp/switch_tts_config.sh local

# 切换到 ElevenLabs
/tmp/switch_tts_config.sh elevenlabs
```

### 2. CosyVoice 配置

**服务器配置**: `/tmp/CosyVoice/http_api_server.py`

**关键参数**:
- **推理方法**: `inference_zero_shot` (零样本语音克隆)
- **采样率**: 16kHz
- **位深度**: 16-bit
- **声道**: Mono (单声道)
- **输出格式**: Streaming PCM

**Prompt 音频**: `/tmp/CosyVoice/asset/zero_shot_prompt.wav` (111KB)

### 3. 环境变量

**容器内环境变量** (可在 `.env` 或 Docker 启动时设置):

```bash
# Agora
AGORA_APP_ID=<your_agora_app_id>
AGORA_APP_CERTIFICATE=<your_agora_certificate>

# LLM - DeepSeek (OpenAI 兼容接口)
OPENAI_API_BASE=https://api.deepseek.com
OPENAI_API_KEY=<your_deepseek_api_key>
OPENAI_MODEL=deepseek-chat
DEEPSEEK_API_KEY=<your_deepseek_api_key>  # 备用

# 如果使用原版 OpenAI
# OPENAI_API_BASE=https://api.openai.com/v1
# OPENAI_MODEL=gpt-4

# Weather API (如果使用)
WEATHERAPI_API_KEY=<your_weather_key>
```

---

## 端口映射

| 服务 | 宿主机端口 | 容器端口 | 协议 | 说明 |
|------|-----------|---------|------|------|
| Frontend | 3000 | 3000 | HTTP | Next.js Web UI (默认端口) |
| Backend API | 8080 | 8080 | HTTP | Go Gin REST API |
| Graph Designer | 49483 | 49483 | HTTP | TEN Graph 管理工具 |
| CosyVoice TTS | 8090 | - | HTTP | 运行在宿主机 |
| FunASR | 10095 | - | WebSocket | 运行在宿主机 |
| UDP Range | 4000-4010 | 4000-4010 | UDP | Agora RTC 数据通道 |

**注意**: Frontend 如果 3000 端口被占用，Next.js 会自动尝试使用 3001。

**Docker 端口映射**:
```
0.0.0.0:3000->3000/tcp
0.0.0.0:8080->8080/tcp
0.0.0.0:9000-9001->9000-9001/tcp
0.0.0.0:49483->49483/tcp
0.0.0.0:4000-4010->4000-4010/udp
```

---

## 组件交互流程

### 完整对话流程

```
1. 用户说话 (浏览器麦克风)
   │
   ▼
2. Agora RTC 采集音频
   │ PCM 音频流 @ 16kHz
   ▼
3. StreamID Adapter (流 ID 适配)
   │
   ▼
4. FunASR (STT)
   │ ws://host.docker.internal:10095
   ▼
   识别结果: "你好，现在天气怎么样？"
   │
   ▼
5. Main Control Extension
   │ 接收 asr_result
   ▼
6. DeepSeek LLM (deepseek-chat)
   │ https://api.deepseek.com (OpenAI 兼容接口)
   ▼
   生成回复: "今天天气晴朗，温度约 20°C"
   │
   ▼
7. CosyVoice TTS
   │ POST http://host.docker.internal:8090/v1/tts
   │ 生成时间: ~9.4秒 (14个中文字符)
   ▼
   返回: Streaming PCM @ 16kHz, 16-bit, mono
   │
   ▼
8. Agora RTC 发送音频
   │
   ▼
9. 用户听到语音回复 (浏览器扬声器)
```

### 数据流向

```
[麦克风输入]
    → [Agora RTC: pcm_frame]
    → [StreamID Adapter]
    → [FunASR: asr_result]
    → [Main Control: data]
    → [DeepSeek LLM: llm_response]
    → [CosyVoice TTS: pcm_frame]
    → [Agora RTC: audio output]
    → [扬声器输出]
```

### API 调用示例

#### 1. CosyVoice TTS 请求
```bash
curl -X POST http://localhost:8090/v1/tts \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "你好，这是CosyVoice中文TTS测试。",
    "spk_id": "中文女"
  }' \
  --output test.pcm

# 响应头:
# Content-Type: audio/pcm
# X-Sample-Rate: 16000
# X-Bit-Depth: 16
# X-Channels: 1
```

#### 2. Backend API - 获取 Graphs
```bash
curl http://localhost:8080/graphs

# 响应:
{
  "code": "0",
  "data": [
    {
      "auto_start": true,
      "graph_id": "voice_assistant",
      "name": "voice_assistant"
    }
  ],
  "msg": "success"
}
```

#### 3. Backend API - 健康检查
```bash
curl http://localhost:8080/health

# 响应:
{"code":"0","data":null,"msg":"ok"}
```

---

## 健康检查

### 自动化健康检查脚本

创建文件 `/tmp/ten_agent_health_check.sh`:

```bash
#!/bin/bash

echo "=== TEN Agent 系统健康检查 ==="
echo ""

# 1. CosyVoice TTS
echo "1. CosyVoice TTS Server:"
COSY_HEALTH=$(curl -s http://localhost:8090/health 2>&1)
if echo "$COSY_HEALTH" | grep -q "healthy"; then
    echo "   ✅ 正常 - $COSY_HEALTH"
else
    echo "   ❌ 异常 - $COSY_HEALTH"
fi
echo ""

# 2. Backend API
echo "2. Backend API Server:"
API_HEALTH=$(curl -s http://localhost:8080/health 2>&1)
if echo "$API_HEALTH" | grep -q "ok"; then
    echo "   ✅ 正常 - $API_HEALTH"
else
    echo "   ❌ 异常 - $API_HEALTH"
fi
echo ""

# 3. Frontend
echo "3. Frontend (Next.js):"
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 2>&1)
if [ "$FRONTEND_STATUS" = "200" ]; then
    echo "   ✅ 正常 - HTTP $FRONTEND_STATUS"
else
    echo "   ❌ 异常 - HTTP $FRONTEND_STATUS"
fi
echo ""

# 4. Docker Container
echo "4. Docker Container:"
CONTAINER_STATUS=$(docker ps --filter "name=ten_agent_dev" --format "{{.Status}}")
if [ -n "$CONTAINER_STATUS" ]; then
    echo "   ✅ 正常 - $CONTAINER_STATUS"
else
    echo "   ❌ 容器未运行"
fi
echo ""

# 5. Graphs 配置
echo "5. Graphs 配置:"
GRAPHS=$(curl -s http://localhost:8080/graphs 2>&1)
if echo "$GRAPHS" | grep -q "voice_assistant"; then
    echo "   ✅ 已加载 - voice_assistant graph"
else
    echo "   ❌ 未找到 voice_assistant graph"
fi
echo ""

echo "=== 检查完成 ==="
```

使用方法:
```bash
chmod +x /tmp/ten_agent_health_check.sh
/tmp/ten_agent_health_check.sh
```

---

## 问题排查

### 常见问题及解决方案

#### 1. Frontend 显示 500 错误或无法访问

**症状**: 浏览器控制台显示:
```
POST http://localhost:3000/api/agents/ping 500 (Internal Server Error)
GET http://localhost:3000/api/agents/graphs 500 (Internal Server Error)
```

**可能原因**:
1. Backend API 未启动或无法连接
2. 端口被占用，Frontend 运行在其他端口
3. 服务未完全启动

**解决方案**:
```bash
# 1. 检查 Backend API 是否正常
curl http://localhost:8080/health

# 2. 检查 Frontend 实际运行端口
docker exec ten_agent_dev bash -c "ps aux | grep next"

# 3. 如果 3000 被占用，尝试 3001
open http://localhost:3001

# 4. 查看 Frontend 日志
docker exec ten_agent_dev bash -c "ps aux | grep next" | grep PORT
```

#### 2. TTS 没有声音输出

**症状**: 识别成功，LLM 回复正常，但没有语音输出

**排查步骤**:
```bash
# 1. 检查 CosyVoice 是否运行
curl http://localhost:8090/health

# 2. 测试 TTS 直接生成
curl -X POST http://localhost:8090/v1/tts \
  -H 'Content-Type: application/json' \
  -d '{"text":"测试","spk_id":"中文女"}' \
  --output /tmp/test.pcm

# 3. 检查容器是否能访问宿主机
docker exec ten_agent_dev curl -s http://host.docker.internal:8090/health

# 4. 查看 TTS 扩展日志
docker exec ten_agent_dev tail -100 /tmp/api.log | grep -i tts
```

**常见原因**:
- CosyVoice 未启动
- 端口配置错误 (检查 property.json 中的 base_url)
- Docker 网络问题 (host.docker.internal 无法解析)

#### 3. ASR 不识别语音

**症状**: 说话后没有文字识别结果

**排查步骤**:
```bash
# 1. 检查 FunASR 服务
# (取决于 FunASR 安装方式)

# 2. 检查 WebSocket 连接
docker exec ten_agent_dev bash -c "curl -i -N \
  -H 'Connection: Upgrade' \
  -H 'Upgrade: websocket' \
  ws://host.docker.internal:10095"

# 3. 查看 ASR 日志
docker exec ten_agent_dev tail -100 /tmp/api.log | grep -i asr
```

#### 4. 容器内进程冲突

**症状**: 启动时出现 "address already in use"

**解决方案**:
```bash
# 1. 停止所有后台任务
docker exec ten_agent_dev pkill -f "task run"
docker exec ten_agent_dev pkill -f "./bin/api"
docker exec ten_agent_dev pkill -f "next dev"

# 2. 等待 3 秒
sleep 3

# 3. 重新启动
docker exec ten_agent_dev bash -c "cd /app/agents/examples/voice-assistant && task run"
```

#### 5. CosyVoice 推理错误

**症状**: TTS 请求返回 500 错误

**日志检查**:
```bash
# 查看 CosyVoice 日志
tail -50 /tmp/cosyvoice.log  # 如果有重定向日志
# 或
ps aux | grep http_api_server  # 找到进程，查看 stdout
```

**常见错误**:
- `KeyError: '中文女'` - 使用了不支持的 speaker ID
  - **解决**: CosyVoice2 使用 zero-shot 推理，不需要预定义的 speaker
- 模型未加载 - 检查模型路径是否正确

#### 6. DeepSeek API 错误

**症状**: LLM 响应失败，返回 401 或超时

**排查**:
```bash
# 检查环境变量
docker exec ten_agent_dev env | grep -E "(OPENAI|DEEPSEEK)"

# 测试 DeepSeek API Key
curl https://api.deepseek.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# 或使用 OpenAI CLI 测试
curl https://api.deepseek.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"Hello"}]}'
```

**常见问题**:
- API Key 错误或过期
- Base URL 配置错误（应该是 `https://api.deepseek.com`）
- 网络连接问题
- API 配额用尽

---

## 常用命令

### Docker 容器管理

```bash
# 启动容器
docker start ten_agent_dev

# 停止容器
docker stop ten_agent_dev

# 重启容器
docker restart ten_agent_dev

# 查看容器日志
docker logs ten_agent_dev

# 进入容器
docker exec -it ten_agent_dev bash

# 查看容器资源使用
docker stats ten_agent_dev
```

### 服务启动和停止

```bash
# 启动 TEN Agent 所有服务
docker exec ten_agent_dev bash -c "cd /app/agents/examples/voice-assistant && task run &"

# 停止所有服务
docker exec ten_agent_dev pkill -f "task run"
docker exec ten_agent_dev pkill -f "./bin/api"
docker exec ten_agent_dev pkill -f "next dev"
docker exec ten_agent_dev pkill -f "tman designer"

# 启动 CosyVoice (宿主机)
cd /tmp/CosyVoice && source venv/bin/activate && \
python http_api_server.py --port 8090 --model_dir pretrained_models/CosyVoice2-0.5B > /tmp/cosyvoice.log 2>&1 &

# 停止 CosyVoice
pkill -f http_api_server.py
```

### 日志查看

```bash
# Backend API 日志
docker exec ten_agent_dev tail -f /tmp/api.log

# 筛选特定关键词
docker exec ten_agent_dev tail -f /tmp/api.log | grep -E "(asr_result|tts|error)"

# Task 运行日志
docker exec ten_agent_dev tail -f /tmp/task_run.log

# CosyVoice 日志
tail -f /tmp/cosyvoice.log  # 如果重定向了输出
```

### 配置更新

```bash
# 修改配置后重启服务
# 1. 编辑配置文件
vi /Users/leihua/Documents/GitHub/ten-framework/ai_agents/agents/examples/voice-assistant/tenapp/property.json

# 2. 重启容器内的服务
docker exec ten_agent_dev pkill -f "task run"
sleep 3
docker exec ten_agent_dev bash -c "cd /app/agents/examples/voice-assistant && task run &"
```

### 性能测试

```bash
# TTS 性能测试
time curl -X POST http://localhost:8090/v1/tts \
  -H 'Content-Type: application/json' \
  -d '{"text":"这是一个性能测试，包含十四个中文字符。","spk_id":"中文女"}' \
  --output /tmp/perf_test.pcm

# 预期: ~9-10 秒

# 完整对话流测试
# 1. 打开浏览器 http://localhost:3001
# 2. 允许麦克风权限
# 3. 说话: "你好，今天天气怎么样？"
# 4. 观察控制台和日志，确认各阶段延迟
```

---

## 系统要求

### 硬件要求

- **CPU**: Apple Silicon (M1/M2/M3) 或 x86_64 with AVX2
- **内存**: 最低 16GB RAM (推荐 32GB)
- **存储**: 最低 20GB 可用空间
  - CosyVoice 模型: ~3GB
  - Docker 镜像: ~5GB
  - 依赖和缓存: ~2GB

### 软件要求

- **操作系统**: macOS 12+ 或 Linux
- **Docker**: 20.10+
- **Python**: 3.10+ (用于 CosyVoice)
- **Node.js**: 18+ (用于 Frontend，已包含在容器中)
- **网络**: 稳定的互联网连接 (用于 OpenAI API)

---

## 性能基准

### TTS 性能 (CosyVoice2-0.5B on Apple M-series)

| 文本长度 | 生成时间 | 音频时长 | RTF (Real-Time Factor) |
|---------|---------|---------|------------------------|
| 14 字符 (中文) | 9.4 秒 | 1.36 秒 | ~6.9x |
| 30 字符 (中文) | ~20 秒 | ~3 秒 | ~6.7x |

**注**: RTF = 生成时间 / 音频时长，数值越小越好

### 对比: Fish Speech (已弃用)
- 14 字符 (中文): 100+ 秒
- RTF: ~73x
- **CosyVoice 比 Fish Speech 快 10 倍以上**

---

## 维护和备份

### 定期维护任务

```bash
# 1. 清理 Docker 资源
docker system prune -a --volumes -f

# 2. 重建容器 (如果需要)
docker stop ten_agent_dev
docker rm ten_agent_dev
# 重新创建容器...

# 3. 更新模型 (CosyVoice)
cd /tmp/CosyVoice
source venv/bin/activate
python3 -c "from modelscope import snapshot_download; \
snapshot_download('iic/CosyVoice2-0.5B', local_dir='pretrained_models/CosyVoice2-0.5B')"
```

### 配置备份

```bash
# 备份关键配置
cp /Users/leihua/Documents/GitHub/ten-framework/ai_agents/agents/examples/voice-assistant/tenapp/property.json \
   /Users/leihua/Documents/GitHub/ten-framework/property.json.backup.$(date +%Y%m%d)

# 备份 CosyVoice 服务器
cp /tmp/CosyVoice/http_api_server.py \
   /tmp/CosyVoice/http_api_server.py.backup.$(date +%Y%m%d)
```

---

## 附录

### A. 快速启动脚本

创建 `/tmp/start_ten_agent.sh`:

```bash
#!/bin/bash
set -e

echo "=== 启动 TEN Agent 系统 ==="

# 1. 启动 CosyVoice
echo "1. 启动 CosyVoice TTS..."
cd /tmp/CosyVoice
source venv/bin/activate
python http_api_server.py --port 8090 --model_dir pretrained_models/CosyVoice2-0.5B > /tmp/cosyvoice.log 2>&1 &
COSY_PID=$!
echo "   CosyVoice 已启动 (PID: $COSY_PID)"
sleep 3

# 2. 检查 CosyVoice 健康
COSY_HEALTH=$(curl -s http://localhost:8090/health 2>&1)
if echo "$COSY_HEALTH" | grep -q "healthy"; then
    echo "   ✅ CosyVoice 健康检查通过"
else
    echo "   ❌ CosyVoice 启动失败"
    exit 1
fi

# 3. 启动 Docker 容器服务
echo "2. 启动 TEN Agent 容器服务..."
docker start ten_agent_dev 2>/dev/null || echo "   容器已在运行"
sleep 2

# 清理旧进程
docker exec ten_agent_dev pkill -f "task run" 2>/dev/null || true
sleep 2

# 启动新进程
docker exec ten_agent_dev bash -c "cd /app/agents/examples/voice-assistant && task run" > /tmp/ten_agent.log 2>&1 &
echo "   TEN Agent 服务已启动"
sleep 8

# 4. 健康检查
echo "3. 进行健康检查..."
bash /tmp/ten_agent_health_check.sh

echo ""
echo "=== 启动完成 ==="
echo "前端访问: http://localhost:3000"
echo "API 文档: http://localhost:8080"
echo ""
echo "日志查看:"
echo "  - CosyVoice: tail -f /tmp/cosyvoice.log"
echo "  - TEN Agent: docker exec ten_agent_dev tail -f /tmp/api.log"
```

使用:
```bash
chmod +x /tmp/start_ten_agent.sh
/tmp/start_ten_agent.sh
```

### B. 快速停止脚本

创建 `/tmp/stop_ten_agent.sh`:

```bash
#!/bin/bash

echo "=== 停止 TEN Agent 系统 ==="

# 1. 停止 CosyVoice
echo "1. 停止 CosyVoice TTS..."
pkill -f http_api_server.py
echo "   ✅ CosyVoice 已停止"

# 2. 停止容器内服务
echo "2. 停止 TEN Agent 容器服务..."
docker exec ten_agent_dev pkill -f "task run" 2>/dev/null || true
docker exec ten_agent_dev pkill -f "./bin/api" 2>/dev/null || true
docker exec ten_agent_dev pkill -f "next dev" 2>/dev/null || true
docker exec ten_agent_dev pkill -f "tman designer" 2>/dev/null || true
echo "   ✅ 容器服务已停止"

# 3. 可选: 停止容器
# docker stop ten_agent_dev

echo "=== 停止完成 ==="
```

使用:
```bash
chmod +x /tmp/stop_ten_agent.sh
/tmp/stop_ten_agent.sh
```

### C. 完整系统诊断脚本

创建 `/tmp/diagnose_ten_agent.sh`:

```bash
#!/bin/bash

echo "================================================"
echo "       TEN Agent 系统完整诊断报告"
echo "================================================"
echo ""

# 1. 系统信息
echo "【系统信息】"
echo "  操作系统: $(uname -s)"
echo "  内核版本: $(uname -r)"
echo "  架构: $(uname -m)"
echo "  内存: $(sysctl hw.memsize 2>/dev/null | awk '{print $2/1024/1024/1024 " GB"}' || echo 'N/A')"
echo ""

# 2. Docker 状态
echo "【Docker 状态】"
docker version --format '  Docker 版本: {{.Server.Version}}' 2>/dev/null || echo "  ❌ Docker 未安装或未运行"
docker ps --filter "name=ten_agent_dev" --format "  容器状态: {{.Status}}" || echo "  ❌ 容器未运行"
echo ""

# 3. 服务状态
echo "【服务状态】"

# CosyVoice
COSY_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8090/health 2>&1)
if [ "$COSY_STATUS" = "200" ]; then
    COSY_INFO=$(curl -s http://localhost:8090/health)
    echo "  ✅ CosyVoice: 正常 - $COSY_INFO"
else
    echo "  ❌ CosyVoice: 无响应 (HTTP $COSY_STATUS)"
fi

# Backend API
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health 2>&1)
if [ "$API_STATUS" = "200" ]; then
    echo "  ✅ Backend API: 正常"
else
    echo "  ❌ Backend API: 无响应 (HTTP $API_STATUS)"
fi

# Frontend
FE_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 2>&1)
if [ "$FE_STATUS" = "200" ]; then
    echo "  ✅ Frontend: 正常 (Port 3000)"
else
    FE_STATUS_3001=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3001 2>&1)
    if [ "$FE_STATUS_3001" = "200" ]; then
        echo "  ✅ Frontend: 正常 (Port 3001 - 3000 was occupied)"
    else
        echo "  ❌ Frontend: 无响应"
    fi
fi
echo ""

# 4. 配置检查
echo "【配置检查】"
if [ -f "/Users/leihua/Documents/GitHub/ten-framework/ai_agents/agents/examples/voice-assistant/tenapp/property.json" ]; then
    TTS_URL=$(grep -A 1 '"name": "tts"' /Users/leihua/Documents/GitHub/ten-framework/ai_agents/agents/examples/voice-assistant/tenapp/property.json | grep base_url | awk -F'"' '{print $4}')
    echo "  TTS 配置: $TTS_URL"

    STT_URL=$(grep -A 1 '"name": "stt"' /Users/leihua/Documents/GitHub/ten-framework/ai_agents/agents/examples/voice-assistant/tenapp/property.json | grep ws_url | awk -F'"' '{print $4}')
    echo "  STT 配置: $STT_URL"
else
    echo "  ❌ 配置文件未找到"
fi
echo ""

# 5. 进程检查
echo "【进程检查】"
echo "  CosyVoice 进程:"
ps aux | grep http_api_server | grep -v grep | awk '{print "    PID " $2 ": " $11 " " $12 " " $13}'

echo "  容器内进程:"
docker exec ten_agent_dev ps aux 2>/dev/null | grep -E "(api|next|tman)" | grep -v grep | head -3 | awk '{print "    PID " $2 ": " $11}'
echo ""

# 6. 网络检查
echo "【网络连接检查】"
echo -n "  容器访问宿主机 CosyVoice: "
docker exec ten_agent_dev curl -s -o /dev/null -w "%{http_code}" http://host.docker.internal:8090/health 2>&1 | \
    grep -q "200" && echo "✅ 正常" || echo "❌ 失败"

echo -n "  OpenAI API 连通性: "
curl -s -o /dev/null -w "%{http_code}" https://api.openai.com/v1/models 2>&1 | \
    grep -q "401\|200" && echo "✅ 可达" || echo "❌ 不可达"
echo ""

# 7. 磁盘空间
echo "【磁盘空间】"
echo "  /tmp 分区:"
df -h /tmp | tail -1 | awk '{print "    可用: " $4 " / 总计: " $2 " (" $5 " 已用)"}'

echo "  CosyVoice 模型:"
du -sh /tmp/CosyVoice/pretrained_models 2>/dev/null | awk '{print "    大小: " $1}' || echo "    未找到"
echo ""

# 8. 最近错误日志
echo "【最近错误日志】(最近 10 条)"
echo "  CosyVoice:"
tail -100 /tmp/cosyvoice.log 2>/dev/null | grep -i error | tail -3 | sed 's/^/    /' || echo "    无错误日志"

echo "  TEN Agent API:"
docker exec ten_agent_dev tail -100 /tmp/api.log 2>/dev/null | grep -i error | tail -3 | sed 's/^/    /' || echo "    无错误日志"
echo ""

echo "================================================"
echo "              诊断完成"
echo "================================================"
```

使用:
```bash
chmod +x /tmp/diagnose_ten_agent.sh
/tmp/diagnose_ten_agent.sh
```

---

## 工具和构建系统

### Taskfile 任务系统

TEN Agent 使用 [Task](https://taskfile.dev) 作为任务运行器（类似 Makefile，但使用 YAML 配置）。

#### 根目录 Taskfile (`/Taskfile.yml`)
```bash
task gen      # 生成 GN 构建文件（用于 C++ runtime）
task build    # 编译 C++ runtime 和核心组件
task clean    # 清理构建产物
```

#### AI Agents Taskfile (`/ai_agents/Taskfile.yml`)
```bash
task lint                    # Python 代码检查（flake8, mypy）
task format                  # 代码格式化（Black）
task test-server            # Go 服务器测试
task test-agent-extensions  # 扩展测试
task build-agent-deps       # 构建 agent 依赖
```

#### Voice Assistant Taskfile (`/ai_agents/agents/examples/voice-assistant/Taskfile.yml`)

**安装任务**:
```bash
task install                      # 安装所有依赖（组合任务）
  ├── task install-tenapp         # 安装 TEN 包依赖（tman install）
  ├── task install-tenapp-python-deps  # 安装 Python 依赖
  ├── task install-frontend       # 安装前端依赖（bun install）
  └── task build-api-server       # 编译 Go API 服务器
```

**运行任务**:
```bash
task run                          # 并行启动所有服务（组合任务）
  ├── task run-gd-server          # 启动 TMAN Graph Designer (port 49483)
  ├── task run-frontend           # 启动 Next.js 前端 (port 3000)
  └── task run-api-server         # 启动 Go API 服务器 (port 8080)

# 单独启动服务
task run-tenapp                   # 启动 TEN 应用（tman run start）
```

**发布任务**:
```bash
task release                      # 打包发布版本（调用 release.sh）
```

#### 使用示例
```bash
# 完整安装流程
cd /app/agents/examples/voice-assistant
task install

# 启动所有服务
task run

# 单独启动 API 服务器
task run-api-server
```

### manifest.json 依赖管理

**位置**: `tenapp/manifest.json`

**作用**: 定义应用的类型、版本和依赖关系

**示例结构**:
```json
{
  "type": "app",
  "name": "agent_demo",
  "version": "0.10.0",
  "dependencies": [
    {
      "type": "system",
      "name": "ten_runtime_go",
      "version": "0.11"
    },
    {
      "type": "extension",
      "name": "agora_rtc",
      "version": "=0.23.9-t1"
    },
    {
      "path": "../../../ten_packages/extension/streamid_adapter"
    }
  ],
  "scripts": {
    "start": "scripts/start.sh"
  }
}
```

**依赖类型**:
- `system`: 系统包（runtime、ten_ai_base 等）
- `extension`: 扩展包（ASR、TTS、LLM 等）
- `path`: 本地路径依赖

**安装依赖**: 执行 `tman install` 会根据 manifest.json 自动安装所有依赖

### release.sh 打包脚本

**位置**: `/ai_agents/agents/scripts/release.sh`

**功能**: 将 tenapp 打包为可部署的 release 版本

**执行流程**:
1. 创建 `.release/` 目录
2. 复制核心文件: `bin/`, `scripts/`, `manifest.json`, `property.json`
3. 根据 `.tenignore` 规则复制扩展包
4. 排除开发文件（源码、tests、__pycache__ 等）

**使用方法**:
```bash
cd /app/agents/examples/voice-assistant
task release

# 或直接调用
../../scripts/release.sh ./tenapp

# 查看输出
ls -la ./tenapp/.release/
```

**Dockerfile 集成**:
```dockerfile
RUN task clean && cd ${USE_AGENT} && \
  task install && task release
RUN mv ${USE_AGENT}/tenapp/.release/ agents/
```

**`.tenignore` 文件**: 类似 `.gitignore`，用于指定发布时排除的文件
```
__pycache__/
*.pyc
*.pyo
tests/
.pytest_cache/
venv/
.vscode/
```

### 构建工具链

| 工具 | 用途 | 配置文件 |
|------|------|----------|
| **GN** | C++ 构建文件生成 | `BUILD.gn` |
| **Ninja** | C++ 编译 | 由 GN 生成 |
| **Task** | 任务编排 | `Taskfile.yml` |
| **Tman** | TEN 包管理 | `manifest.json` |
| **Bun** | JavaScript 包管理和运行时 | `package.json` |
| **Go** | 后端编译 | `go.mod` |
| **Cargo** | Rust 编译（ten_manager） | `Cargo.toml` |

---

## 扩展包系统

### 扩展包位置
- **共享扩展包**: `/ai_agents/agents/ten_packages/extension/`
- **应用内扩展**: `tenapp/ten_packages/extension/`

### 可用扩展 (40+ 个)

#### ASR (语音识别) 扩展
- **云服务**: aliyun_asr, assemblyai_asr_python, aws_asr_python, azure_asr_python, bytedance_asr, deepgram_asr_python, gladia_asr_python, google_asr_python, openai_asr_python, soniox_asr_python, speechmatics_asr_python, tencent_asr_python, xfyun_asr_python
- **本地服务**: funasr_asr_python (FunASR WebSocket)

#### LLM (大语言模型) 扩展
- **openai_llm2_python**: 支持 OpenAI / DeepSeek / 任何 OpenAI 兼容接口
- **coze_llm2_python**: Coze 平台
- **dify_llm2_python**: Dify 平台
- **gemini_llm_python**: Google Gemini
- **bedrock_llm**: AWS Bedrock
- **litellm**: 统一 LLM 接口

#### TTS (语音合成) 扩展
- **云服务（实时流式）**: aliyun_tts_realtime_python (通义千问), elevenlabs_tts2_python, azure_tts_python, cartesia_tts2, google_tts_python, openai_tts2_python, groq_tts_python, minimax_tts_websocket_python, bytedance_tts_duplex
- **本地服务**: fish_tts_local_python, cosy_tts_python (CosyVoice)

#### 工具扩展
- **weatherapi_tool_python**: 天气查询
- **bingsearch_tool_python**: Bing 搜索

#### 其他扩展
- **streamid_adapter**: 流 ID 适配
- **message_collector2**: 消息收集
- **main_python**: 主控制逻辑

### 使用自定义扩展

#### 方法 1: 本地路径依赖 (manifest.json)
```json
{
  "dependencies": [
    {
      "path": "../../../ten_packages/extension/my_custom_extension"
    }
  ]
}
```

#### 方法 2: 版本依赖
```json
{
  "dependencies": [
    {
      "type": "extension",
      "name": "agora_rtc",
      "version": "=0.23.9-t1"
    }
  ]
}
```

#### 方法 3: 配置扩展 (property.json)
```json
{
  "nodes": [
    {
      "type": "extension",
      "name": "my_stt",
      "addon": "custom_asr_python",
      "extension_group": "stt",
      "property": {
        "api_key": "${env:MY_ASR_API_KEY}",
        "language": "en-US"
      }
    }
  ]
}
```

### 扩展开发

#### 创建阿里云通义千问 TTS 扩展

如果项目中没有 `aliyun_tts_realtime_python` 扩展，可以按以下步骤创建：

**1. 创建扩展目录结构**：

```bash
cd /app/agents/ten_packages/extension
mkdir -p aliyun_tts_realtime_python
cd aliyun_tts_realtime_python
```

**2. 创建 manifest.json**：

```json
{
  "type": "extension",
  "name": "aliyun_tts_realtime_python",
  "version": "0.1.0",
  "language": "python",
  "dependencies": [
    {
      "type": "system",
      "name": "ten_runtime_python",
      "version": "0.11"
    }
  ],
  "api": {
    "property": {
      "api_key": {
        "type": "string",
        "default": ""
      },
      "model": {
        "type": "string",
        "default": "qwen-tts-realtime-latest"
      },
      "ws_url": {
        "type": "string",
        "default": "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
      },
      "voice": {
        "type": "string",
        "default": "longxiaochun"
      },
      "format": {
        "type": "string",
        "default": "pcm"
      },
      "sample_rate": {
        "type": "int32",
        "default": 16000
      },
      "mode": {
        "type": "string",
        "default": "server_commit"
      }
    },
    "data_in": [
      {
        "name": "text_data",
        "property": {
          "text": {
            "type": "string"
          }
        }
      }
    ],
    "audio_frame_out": [
      {
        "name": "pcm_frame"
      }
    ]
  }
}
```

**3. 创建 extension.py**：

```python
import asyncio
import json
import base64
import websockets
from ten import (
    Extension,
    TenEnv,
    Cmd,
    Data,
    AudioFrame,
    AudioFrameDataFmt,
)

class AliyunTTSRealtimeExtension(Extension):
    def __init__(self, name: str):
        super().__init__(name)
        self.api_key = ""
        self.model = "qwen-tts-realtime-latest"
        self.ws_url = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
        self.voice = "longxiaochun"
        self.format = "pcm"
        self.sample_rate = 16000
        self.mode = "server_commit"
        self.websocket = None
        self.loop = None

    def on_init(self, ten_env: TenEnv) -> None:
        ten_env.log_info("AliyunTTSRealtimeExtension on_init")
        ten_env.on_init_done()

    def on_start(self, ten_env: TenEnv) -> None:
        ten_env.log_info("AliyunTTSRealtimeExtension on_start")

        # 读取配置
        try:
            self.api_key = ten_env.get_property_string("api_key")
            self.model = ten_env.get_property_string("model")
            self.ws_url = ten_env.get_property_string("ws_url")
            self.voice = ten_env.get_property_string("voice")
            self.format = ten_env.get_property_string("format")
            self.sample_rate = ten_env.get_property_int("sample_rate")
            self.mode = ten_env.get_property_string("mode")
        except Exception as e:
            ten_env.log_error(f"Failed to get properties: {e}")

        # 创建事件循环
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        ten_env.on_start_done()

    def on_stop(self, ten_env: TenEnv) -> None:
        ten_env.log_info("AliyunTTSRealtimeExtension on_stop")

        # 关闭 WebSocket
        if self.websocket:
            asyncio.run(self.websocket.close())

        # 停止事件循环
        if self.loop:
            self.loop.stop()

        ten_env.on_stop_done()

    def on_deinit(self, ten_env: TenEnv) -> None:
        ten_env.log_info("AliyunTTSRealtimeExtension on_deinit")
        ten_env.on_deinit_done()

    def on_data(self, ten_env: TenEnv, data: Data) -> None:
        """接收文本数据，触发 TTS 合成"""
        try:
            text = data.get_property_string("text")
            if not text:
                ten_env.log_warn("Received empty text")
                return

            ten_env.log_info(f"Synthesizing text: {text}")

            # 异步调用 TTS
            asyncio.run_coroutine_threadsafe(
                self._synthesize_text(ten_env, text),
                self.loop
            )
        except Exception as e:
            ten_env.log_error(f"Error in on_data: {e}")

    async def _connect_websocket(self, ten_env: TenEnv):
        """连接 WebSocket"""
        if self.websocket:
            return

        try:
            headers = {
                "X-DashScope-ApiKey": self.api_key,
            }
            self.websocket = await websockets.connect(
                self.ws_url,
                extra_headers=headers
            )
            ten_env.log_info("WebSocket connected")

            # 发送 session.update 初始化会话
            session_update = {
                "type": "session.update",
                "session": {
                    "mode": self.mode,
                    "model": self.model,
                    "voice": self.voice,
                    "output_format": self.format,
                    "sample_rate": self.sample_rate
                }
            }
            await self.websocket.send(json.dumps(session_update))

            # 等待 session.created 和 session.updated
            while True:
                response = await self.websocket.recv()
                event = json.loads(response)
                if event["type"] in ["session.created", "session.updated"]:
                    ten_env.log_info(f"Received: {event['type']}")
                if event["type"] == "session.updated":
                    break

        except Exception as e:
            ten_env.log_error(f"WebSocket connection failed: {e}")
            self.websocket = None
            raise

    async def _synthesize_text(self, ten_env: TenEnv, text: str):
        """合成文本为语音"""
        try:
            # 确保 WebSocket 已连接
            await self._connect_websocket(ten_env)

            # 发送文本
            append_event = {
                "type": "input_text_buffer.append",
                "text": text
            }
            await self.websocket.send(json.dumps(append_event))

            # 如果是 commit 模式，需要手动提交
            if self.mode == "commit":
                commit_event = {
                    "type": "input_text_buffer.commit"
                }
                await self.websocket.send(json.dumps(commit_event))

            # 接收音频流
            while True:
                response = await self.websocket.recv()
                event = json.loads(response)

                if event["type"] == "response.audio.delta":
                    # 解码音频数据
                    audio_data = base64.b64decode(event["delta"])

                    # 创建 AudioFrame
                    audio_frame = AudioFrame.create("pcm_frame")
                    audio_frame.set_sample_rate(self.sample_rate)
                    audio_frame.set_bytes_per_sample(2)  # 16-bit
                    audio_frame.set_number_of_channels(1)  # Mono
                    audio_frame.set_data_fmt(AudioFrameDataFmt.INTERLEAVE)
                    audio_frame.set_samples_per_channel(len(audio_data) // 2)
                    audio_frame.alloc_buf(len(audio_data))
                    audio_frame.lock_buf(lambda buf: buf[:] = audio_data)

                    # 发送音频帧
                    ten_env.send_audio_frame(audio_frame)

                elif event["type"] == "response.done":
                    ten_env.log_info("TTS synthesis completed")
                    break

                elif event["type"] == "error":
                    ten_env.log_error(f"TTS error: {event.get('error', {})}")
                    break

        except Exception as e:
            ten_env.log_error(f"Synthesis failed: {e}")
```

**4. 创建 __init__.py**：

```python
from .extension import AliyunTTSRealtimeExtension

__all__ = ["AliyunTTSRealtimeExtension"]
```

**5. 创建 requirements.txt**：

```
websocket-client==1.8.0
websockets
```

**6. 安装依赖**：

```bash
cd /app/agents/examples/voice-assistant/tenapp
./scripts/install_python_deps.sh
```

**7. 在 manifest.json 中添加依赖**：

```json
{
  "dependencies": [
    {
      "path": "../../../ten_packages/extension/aliyun_tts_realtime_python"
    }
  ]
}
```

#### 通用扩展结构

创建新扩展的基本结构:
```
my_extension/
├── manifest.json          # 扩展元数据
├── property.json          # 默认配置（可选）
├── extension.py           # Python 实现
├── __init__.py           # Python 包初始化
├── requirements.txt      # Python 依赖（可选）
└── README.md            # 说明文档
```

详见 TEN Framework 文档: https://doc.theten.ai

---

## 环境变量完整清单

基于 `/ai_agents/.env.example` 的完整环境变量列表:

### 日志和服务器配置
```bash
LOG_PATH=/tmp/ten_agent              # 日志目录路径
LOG_STDOUT=true                       # 是否输出日志到标准输出
GRAPH_DESIGNER_SERVER_PORT=49483     # Graph Designer 端口
SERVER_PORT=8080                      # API 服务器端口
WORKERS_MAX=100                       # 最大 worker 进程数
WORKER_QUIT_TIMEOUT_SECONDS=60       # Worker 退出超时（秒）
```

### RTC (实时通信)
```bash
AGORA_APP_ID=                        # Agora App ID（必填）
AGORA_APP_CERTIFICATE=               # Agora 证书（可选，如在 Agora 控制台启用）
```

### LLM 提供商

#### OpenAI / DeepSeek / OpenAI 兼容接口
```bash
OPENAI_API_BASE=https://api.openai.com/v1  # API Base URL
OPENAI_API_KEY=                             # API Key
OPENAI_MODEL=gpt-4o                         # 模型名称
OPENAI_PROXY_URL=                           # 代理 URL（可选）
```

**DeepSeek 配置示例**:
```bash
OPENAI_API_BASE=https://api.deepseek.com
OPENAI_API_KEY=sk-xxxxx
OPENAI_MODEL=deepseek-chat
```

#### Azure OpenAI
```bash
OPENAI_VENDOR=Azure                  # 设置为 Azure 时启用
OPENAI_AZURE_ENDPOINT=               # Azure OpenAI 端点
OPENAI_AZURE_API_VERSION=            # API 版本
AZURE_OPENAI_REALTIME_API_KEY=       # Realtime API Key
AZURE_OPENAI_REALTIME_BASE_URI=      # Realtime API Base URI
```

#### 其他 LLM 提供商
```bash
# Grok (X.AI)
GROK_API_BASE=https://api.x.ai/v1
GROK_API_KEY=
GROK_MODEL=

# Gemini (Google)
GEMINI_API_KEY=

# Qwen (阿里云通义千问)
QWEN_API_KEY=

# DeepSeek (独立配置)
DEEPSEEK_API_KEY=

# Stepfun (阶跃星辰)
STEPFUN_API_KEY=

# Gladia
GLADIA_API_KEY=

# AWS Bedrock
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=

# LiteLLM (统一接口)
LITELLM_MODEL=gpt-4o-mini
# 其他 LiteLLM 环境变量参考: https://docs.litellm.ai/docs/providers
```

### STT (语音识别) 提供商
```bash
# Deepgram
DEEPGRAM_API_KEY=

# Azure
AZURE_ASR_API_KEY=
AZURE_ASR_REGION=

# Speechmatics
SPEECHMATICS_API_KEY=

# AWS Transcribe
# 使用上面的 AWS_ACCESS_KEY_ID 和 AWS_SECRET_ACCESS_KEY
```

### TTS (语音合成) 提供商
```bash
# 阿里云通义千问 TTS (Realtime)
ALIYUN_TTS_API_KEY=

# ElevenLabs
ELEVENLABS_TTS_KEY=

# Azure
AZURE_TTS_KEY=
AZURE_TTS_REGION=

# Cartesia
CARTESIA_API_KEY=

# CosyVoice
COSY_TTS_KEY=

# Fish.audio
FISH_AUDIO_TTS_KEY=

# Minimax
MINIMAX_TTS_API_KEY=
MINIMAX_TTS_GROUP_ID=

# ByteDance (字节跳动)
BYTEDANCE_TTS_APPID=
BYTEDANCE_TTS_TOKEN=

# Dubverse
DUBVERSE_TTS_KEY=

# Groq
GROQ_CLOUD_API_KEY=

# AWS Polly
# 使用上面的 AWS_ACCESS_KEY_ID 和 AWS_SECRET_ACCESS_KEY
```

### 工具和数据库
```bash
# Weather API
WEATHERAPI_API_KEY=

# Bing 搜索
BING_API_KEY=

# Firestore (时序数据库)
FIRESTORE_PROJECT_ID=
FIRESTORE_PRIVATE_KEY_ID=
FIRESTORE_PRIVATE_KEY=
FIRESTORE_CLIENT_EMAIL=
FIRESTORE_CLIENT_ID=
FIRESTORE_CERT_URL=

# 阿里云 AnalyticDB 向量存储
ALIBABA_CLOUD_ACCESS_KEY_ID=
ALIBABA_CLOUD_ACCESS_KEY_SECRET=
ALIYUN_ANALYTICDB_ACCOUNT=
ALIYUN_ANALYTICDB_ACCOUNT_PASSWORD=
ALIYUN_ANALYTICDB_INSTANCE_ID=
ALIYUN_ANALYTICDB_INSTANCE_REGION=cn-shanghai
ALIYUN_ANALYTICDB_NAMESPACE=
ALIYUN_ANALYTICDB_NAMESPACE_PASSWORD=

# 阿里云文本嵌入
ALIYUN_TEXT_EMBEDDING_API_KEY=

# Azure AI Foundry
AZURE_AI_FOUNDRY_BASE_URI=
AZURE_AI_FOUNDRY_API_KEY=
```

---

## Voice Assistant 变体

TEN Framework 提供多个 voice-assistant 变体以满足不同需求:

| 变体名称 | 说明 | 镜像名 | 特点 |
|---------|------|--------|------|
| **voice-assistant** | 标准版本 | `ten_agent_example_voice_assistant` | Deepgram + OpenAI + ElevenLabs |
| **voice-assistant-realtime** | OpenAI Realtime API | `ten_agent_example_voice_assistant_realtime` | 使用 OpenAI 实时语音 API，超低延迟 |
| **voice-assistant-nodejs** | Node.js 扩展版 | `ten_agent_example_voice_assistant_nodejs` | 演示 Node.js 扩展开发 |
| **voice-assistant-local** | 本地服务版 | - | 使用本地 TTS/ASR（如本文档配置） |
| **voice-assistant-live2d** | Live2D 虚拟形象 | `ten_agent_example_voice_assistant_live2d` | 带 Live2D 动画角色 |
| **voice-assistant-video** | 视频通话版 | `ten_agent_example_voice_assistant_video` | 支持视频流处理 |
| **voice-assistant-with-memU** | 带记忆功能 | `ten_agent_example_voice_assistant_with_memu` | 集成 memU 记忆系统 |
| **voice-assistant-with-ten-vad** | 带语音活动检测 | `ten_agent_example_voice_assistant_with_ten_vad` | 本地 VAD，减少误触发 |
| **voice-assistant-sip-twilio** | SIP/Twilio 集成 | `ten_agent_example_voice_assistant_sip_twilio` | 电话呼叫集成 |

### 其他示例
- **demo**: 基础演示
- **transcription**: 转录服务
- **speechmatics-diarization**: 说话人分离
- **stepfun-demo**: Stepfun 集成演示

### 切换变体
```bash
# 方式 1: 使用不同目录
cd /app/agents/examples/voice-assistant-realtime
task install
task run

# 方式 2: 使用预构建 Docker 镜像
docker pull ghcr.io/ten-framework/ten_agent_example_voice_assistant_realtime:latest
docker run --rm -it --env-file .env -p 8080:8080 -p 3000:3000 \
  ghcr.io/ten-framework/ten_agent_example_voice_assistant_realtime:latest
```

详细说明见各变体目录下的 `README.md` 文件。

---

## CI/CD 和自动化

### GitHub Actions Workflows

#### Docker 镜像自动构建

**文件**: `.github/workflows/build_docker_for_ai_agents.yml`

**触发条件**:
- Push 到任何分支（`ai_agents/**` 路径变更）
- Pull Request 到 main 分支
- 手动触发 (workflow_dispatch)

**构建矩阵**: 并行构建 12 个示例的 Docker 镜像
- demo, voice-assistant, voice-assistant-realtime
- voice-assistant-nodejs, voice-assistant-video, voice-assistant-live2d
- voice-assistant-with-memU, voice-assistant-with-ten-vad
- voice-assistant-sip-twilio, speechmatics-diarization
- stepfun-demo, transcription

**镜像仓库**: GitHub Container Registry (ghcr.io)

**镜像命名规则**:
```
ghcr.io/{owner}/ten_agent_example_{name}:latest          # main 分支
ghcr.io/{owner}/ten_agent_example_{name}:{git-tag}      # 所有分支
```

**示例**:
```
ghcr.io/ten-framework/ten_agent_example_voice_assistant:latest
ghcr.io/ten-framework/ten_agent_example_voice_assistant:0.7.9
```

### 使用预构建镜像

```bash
# 拉取最新镜像
docker pull ghcr.io/ten-framework/ten_agent_example_voice_assistant:latest

# 运行
docker run --rm -it \
  --env-file .env \
  -p 8080:8080 \
  -p 3000:3000 \
  ghcr.io/ten-framework/ten_agent_example_voice_assistant:latest
```

### DevContainer 支持

**配置文件**: `.devcontainer/devcontainer.json`

**功能**:
- 基于 `ghcr.io/ten-framework/ten_agent_build:0.7.9` 镜像
- 自动安装 VS Code 扩展 (Go, C++)
- 预配置端口转发和标签
- 工作目录: `/workspaces/ten-framework/ai_agents`

**端口标签**:
| 端口 | 说明 |
|------|------|
| 3000 | Agent Example UI |
| 49483 | TMAN Designer |
| 8080 | TEN API Server |
| 49484 | TEN Service Hub |

**使用方法**:
1. 在 VS Code 中打开项目
2. 点击左下角 "Reopen in Container"
3. 等待容器构建完成
4. 终端自动进入 `/workspaces/ten-framework/ai_agents`

**GitHub Codespaces**: 支持在浏览器中直接打开完整开发环境

---

## 生产环境部署

### 推荐架构

```
                    ┌──────────────┐
                    │ Load Balancer│
                    │  (nginx)     │
                    └───────┬───────┘
                            │
            ┌───────────────┼───────────────┐
            │               │               │
      ┌─────▼─────┐   ┌────▼─────┐   ┌────▼─────┐
      │ Container │   │Container │   │Container │
      │    #1     │   │   #2     │   │   #3     │
      └───────────┘   └──────────┘   └──────────┘
            │               │               │
            └───────────────┴───────────────┘
                            │
                    ┌───────▼───────┐
                    │  Shared Cache │
                    │   (Redis)     │
                    └───────────────┘
```

### 部署清单

#### 1. 使用预构建镜像
```bash
docker pull ghcr.io/ten-framework/ten_agent_example_voice_assistant:latest
```

#### 2. 环境变量管理
- 使用 `.env` 文件或 Kubernetes Secrets
- **不要**将敏感信息提交到代码库
- 为不同环境 (dev/staging/prod) 使用不同配置

#### 3. Docker Compose 生产配置
```yaml
version: '3'
services:
  ten_agent:
    image: ghcr.io/ten-framework/ten_agent_example_voice_assistant:latest
    env_file:
      - .env.production
    ports:
      - "8080:8080"
      - "3000:3000"
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

#### 4. Kubernetes 部署示例
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ten-agent
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ten-agent
  template:
    metadata:
      labels:
        app: ten-agent
    spec:
      containers:
      - name: ten-agent
        image: ghcr.io/ten-framework/ten_agent_example_voice_assistant:latest
        ports:
        - containerPort: 8080
        - containerPort: 3000
        envFrom:
        - secretRef:
            name: ten-agent-secrets
        resources:
          limits:
            memory: "4Gi"
            cpu: "2000m"
          requests:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: ten-agent-service
spec:
  selector:
    app: ten-agent
  ports:
    - name: api
      port: 8080
      targetPort: 8080
    - name: frontend
      port: 3000
      targetPort: 3000
  type: LoadBalancer
```

### 性能优化建议

1. **使用 CDN** 分发前端静态资源
2. **启用 HTTP/2** 提升并发性能
3. **配置反向代理缓存** (nginx/Varnish)
4. **使用连接池** 管理数据库连接
5. **启用 Gzip/Brotli 压缩**
6. **实施 API 速率限制** 防止滥用
7. **监控和告警** (Prometheus + Grafana)

### 安全检查清单

- [ ] 所有 API Key 通过环境变量或 Secret 管理
- [ ] 启用 HTTPS（使用 Let's Encrypt 或云服务商证书）
- [ ] 配置 CORS 策略
- [ ] 实施身份验证和授权
- [ ] 容器以非 root 用户运行
- [ ] 定期更新基础镜像和依赖
- [ ] 配置防火墙规则，限制端口暴露
- [ ] 启用容器扫描（Trivy、Snyk）
- [ ] 实施日志审计
- [ ] API Key 定期轮换

### 监控指标

**关键指标**:
- API 响应时间 (p50, p95, p99)
- 错误率 (4xx, 5xx)
- 并发连接数
- TTS/ASR 处理延迟
- LLM Token 使用量
- 容器资源使用率 (CPU, Memory)

**推荐工具**:
- Prometheus: 指标收集
- Grafana: 可视化
- Loki: 日志聚合
- Jaeger: 分布式追踪

---

## 术语表

| 术语 | 全称 | 说明 |
|------|------|------|
| **TEN** | - | TEN Framework，可扩展的 AI 代理框架 |
| **TMAN** | TEN Manager | 用于管理和设计 TEN 应用的命令行工具 |
| **Graph** | Extension Graph | 扩展执行图，定义数据流和扩展连接关系 |
| **Extension** | - | 扩展，TEN 系统中的功能模块 (如 ASR, TTS, LLM) |
| **Addon** | - | 插件，扩展的具体实现 |
| **Property** | - | 配置属性，定义扩展的行为参数 |
| **RTC** | Real-Time Communication | 实时通信（如 Agora RTC） |
| **STT** | Speech-to-Text | 语音转文字（语音识别） |
| **ASR** | Automatic Speech Recognition | 自动语音识别（同 STT） |
| **TTS** | Text-to-Speech | 文字转语音（语音合成） |
| **LLM** | Large Language Model | 大语言模型 |
| **VAD** | Voice Activity Detection | 语音活动检测 |
| **PCM** | Pulse Code Modulation | 脉冲编码调制（音频格式） |
| **WebSocket** | - | 全双工通信协议 |
| **GN** | Generate Ninja | Google 的构建文件生成工具 |
| **Bun** | - | 高性能 JavaScript 运行时和包管理器 |

---

## 联系信息和资源

- **TEN Framework GitHub**: https://github.com/ten-framework/ten-framework
- **TEN Framework 文档**: https://doc.theten.ai
- **CosyVoice GitHub**: https://github.com/FunAudioLLM/CosyVoice
- **Agora 文档**: https://docs.agora.io/
- **问题反馈**: https://github.com/ten-framework/ten-framework/issues

---

**文档版本**: 1.2
**适用系统**: TEN Agent v0.7.9+ + CosyVoice2-0.5B / 阿里云通义千问 TTS
**最后更新**: 2025-10-31

---

## 文档更新日志

### v1.2 (2025-10-31)
- ✅ **新增线上 TTS 服务配置**
  - 添加阿里云通义千问 TTS (qwen-tts-realtime-latest) 配置说明
  - 提供本地 TTS 和线上 TTS 快速切换脚本
  - TTS 配置对比表格（CosyVoice、阿里云、ElevenLabs、Azure）
  - 完整的阿里云 TTS 扩展实现示例代码
- ✅ **环境变量更新**
  - 添加 `ALIYUN_TTS_API_KEY` 环境变量说明
- ✅ **扩展包系统增强**
  - 新增 `aliyun_tts_realtime_python` 扩展创建教程
  - 包含 manifest.json、extension.py 完整实现代码
  - WebSocket 实时流式 TTS 调用示例

### v1.1 (2025-10-31)
- ✅ 修正 Frontend 端口（3000 vs 3001）
- ✅ 修正 TTS speaker ID（"中文男"）
- ✅ 添加配置类型说明（自定义 vs 标准）
- ✅ 新增章节：工具和构建系统、扩展包系统、环境变量完整清单
- ✅ 新增章节：Voice Assistant 变体、CI/CD 和自动化、生产环境部署
- ✅ 添加术语表和完整的联系信息

### v1.0 (初始版本)
- 系统架构说明
- 组件清单和启动顺序
- 配置文件详解
- 健康检查和问题排查
- 常用命令和维护脚本
