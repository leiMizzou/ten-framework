# TEN Agent 服务管理脚本

本目录包含了便捷的服务管理脚本，用于启动、停止、重启和检查 TEN Agent 系统状态。

## 📜 可用脚本

### 1. `./start.sh` - 启动所有服务

启动 Docker 容器和所有服务（Backend API、Frontend、Designer）。

```bash
./start.sh
```

**服务端口：**
- Frontend (用户界面): http://localhost:3000
- Backend API: http://localhost:8080
- TMAN Designer: http://localhost:49483

---

### 2. `./stop.sh` - 停止所有服务

停止所有服务进程并停止 Docker 容器。

```bash
./stop.sh
```

**注意：** 这不会删除容器，只是停止运行。

---

### 3. `./restart.sh` - 重启所有服务

先停止再启动所有服务，常用于应用代码更改。

```bash
./restart.sh
```

**使用场景：**
- 修改了 TTS 扩展代码
- 更新了配置文件
- 服务出现异常需要重启

---

### 4. `./status.sh` - 检查服务状态

查看所有服务的运行状态和最近的日志。

```bash
./status.sh
```

**显示内容：**
- Docker 容器状态
- 服务进程状态
- HTTP 服务响应状态
- 最近的日志输出

---

## 🔍 查看日志

### 实时查看日志

```bash
# Backend API 日志
docker exec ten_agent_dev tail -f /tmp/api.log

# Frontend 日志
docker exec ten_agent_dev tail -f /tmp/playground.log

# TMAN Designer 日志
docker exec ten_agent_dev tail -f /tmp/tman.log
```

### 查看最近 N 行日志

```bash
# 查看最近 100 行
docker exec ten_agent_dev tail -100 /tmp/api.log

# 搜索特定内容
docker exec ten_agent_dev grep "TTS" /tmp/api.log
```

---

## 🐛 故障排查

### 服务无法启动

1. **检查 Docker 容器状态：**
   ```bash
   docker ps -a | grep ten_agent_dev
   ```

2. **检查端口占用：**
   ```bash
   lsof -i :3000  # Frontend
   lsof -i :8080  # API
   lsof -i :49483 # Designer
   ```

3. **查看容器日志：**
   ```bash
   docker logs ten_agent_dev
   ```

### Python 依赖问题

如果遇到 `ModuleNotFoundError`，重新安装依赖：

```bash
docker exec ten_agent_dev bash -c "cd /app/agents && python3 -m pip install -q pydantic websockets openai numpy requests pillow aiofiles aiohttp httpx"
```

### 完全重置

如果需要完全重置环境：

```bash
# 停止并删除容器
docker-compose down

# 重新创建容器并启动
docker-compose up -d
./start.sh
```

---

## ⚙️ 高级配置

### 修改 .env 文件

编辑 `.env` 文件可以修改 API 密钥和其他配置：

```bash
vi .env
```

**重要配置项：**
- `ALIYUN_TTS_API_KEY`: 阿里云 TTS API 密钥
- `OPENAI_API_KEY`: OpenAI API 密钥
- `AGORA_APP_ID`: Agora 应用 ID

修改后需要重启服务：
```bash
./restart.sh
```

---

## 📚 其他资源

- **项目文档**: `/agents/examples/voice-assistant/README.md`
- **Taskfile**: `/agents/examples/voice-assistant/Taskfile.yml`
- **Docker Compose**: `docker-compose.yml`

---

## 🎉 快速开始

首次使用按以下步骤操作：

```bash
# 1. 确保 .env 文件已配置
cp .env.example .env
vi .env  # 填入你的 API 密钥

# 2. 启动服务
./start.sh

# 3. 检查状态
./status.sh

# 4. 访问前端
open http://localhost:3000
```

---

## 💡 提示

- 每次修改扩展代码后，使用 `./restart.sh` 重启服务
- 使用 `./status.sh` 快速检查所有服务是否正常
- 查看日志时使用 `tail -f` 可以实时跟踪
- 出现问题时，先查看对应服务的日志文件

---

**最后更新**: 2025-11-01
