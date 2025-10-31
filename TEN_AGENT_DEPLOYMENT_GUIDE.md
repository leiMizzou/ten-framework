# TEN Agent 部署和运维指南

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

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                         浏览器客户端                          │
│                   http://localhost:3001                      │
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
  - 端口: 3001 (如果3000被占用)
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
curl -I http://localhost:3001
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
      "spk_id": "中文女"
    }
  }
}
```

**重要**:
- `host.docker.internal` 允许 Docker 容器访问宿主机服务
- 端口 8090 对应 CosyVoice TTS Server

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
| Frontend | 3001 | 3001 | HTTP | Next.js Web UI (如果3000被占用) |
| Backend API | 8080 | 8080 | HTTP | Go Gin REST API |
| Graph Designer | 49483 | 49483 | HTTP | TEN Graph 管理工具 |
| CosyVoice TTS | 8090 | - | HTTP | 运行在宿主机 |
| FunASR | 10095 | - | WebSocket | 运行在宿主机 |
| UDP Range | 4000-4010 | 4000-4010 | UDP | Agora RTC 数据通道 |

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
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3001 2>&1)
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

#### 1. Frontend 显示 500 错误

**症状**: 浏览器控制台显示:
```
POST http://localhost:3000/api/agents/ping 500 (Internal Server Error)
GET http://localhost:3000/api/agents/graphs 500 (Internal Server Error)
```

**原因**: 端口错误，Frontend 实际运行在 3001

**解决方案**:
```bash
# 检查 Frontend 实际端口
docker exec ten_agent_dev bash -c "ps aux | grep next"

# 访问正确的 URL
open http://localhost:3001
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
echo "前端访问: http://localhost:3001"
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
FE_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3001 2>&1)
if [ "$FE_STATUS" = "200" ]; then
    echo "  ✅ Frontend: 正常 (Port 3001)"
else
    FE_STATUS_3000=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 2>&1)
    if [ "$FE_STATUS_3000" = "200" ]; then
        echo "  ✅ Frontend: 正常 (Port 3000)"
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

## 联系信息

- **TEN Framework**: https://github.com/ten-framework/ten-framework
- **CosyVoice**: https://github.com/FunAudioLLM/CosyVoice
- **文档最后更新**: 2025-10-31

---

**文档版本**: 1.0
**适用系统**: TEN Agent v0.7.9 + CosyVoice2-0.5B
