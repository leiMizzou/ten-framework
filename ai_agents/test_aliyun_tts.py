#!/usr/bin/env python3
"""
独立测试 Aliyun TTS Realtime API
"""
import asyncio
import json
import base64
import websockets
import os
import sys

async def test_aliyun_tts():
    # 从环境变量读取 API key
    api_key = os.getenv("ALIYUN_TTS_API_KEY")

    if not api_key:
        print("❌ 错误: ALIYUN_TTS_API_KEY 环境变量未设置")
        sys.exit(1)

    print(f"✓ API Key: {api_key[:15]}... (长度: {len(api_key)})")

    # 配置
    model = "qwen3-tts-flash-realtime"
    ws_url = f"wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model={model}"
    test_text = "你好，这是一个测试。"

    print(f"\n📡 连接到: {ws_url}")
    print(f"🎤 模型: {model}")
    print(f"💬 测试文本: {test_text}\n")

    try:
        # 连接 WebSocket
        print("1️⃣ 正在连接 WebSocket...")
        websocket = await websockets.connect(
            ws_url,
            additional_headers={
                "Authorization": f"Bearer {api_key}",
            },
            ping_interval=20,
            ping_timeout=10
        )
        print("✓ WebSocket 连接成功")

        # 等待 session.created 事件
        print("\n2️⃣ 等待 session.created 事件...")
        response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
        event = json.loads(response)

        if event.get("type") == "session.created":
            print(f"✓ Session 创建成功")
            print(f"   Session ID: {event.get('session', {}).get('id', 'N/A')}")
        else:
            print(f"❌ 意外事件: {event.get('type')}")
            return

        # 发送文本
        print(f"\n3️⃣ 发送文本: '{test_text}'")
        append_event = {
            "type": "input_text_buffer.append",
            "text": test_text
        }
        await websocket.send(json.dumps(append_event))
        print("✓ 文本已发送")

        # 发送 commit 事件
        print("\n4️⃣ 发送 commit 事件...")
        commit_event = {"type": "input_text_buffer.commit"}
        await websocket.send(json.dumps(commit_event))
        print("✓ Commit 事件已发送")

        # 接收音频流
        print("\n5️⃣ 接收音频流...")
        audio_chunks = 0
        total_bytes = 0

        while True:
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                event = json.loads(response)
                event_type = event.get("type")

                if event_type == "response.audio.delta":
                    # 音频数据块
                    audio_b64 = event.get("delta", "")
                    if audio_b64:
                        audio_data = base64.b64decode(audio_b64)
                        audio_chunks += 1
                        total_bytes += len(audio_data)
                        if audio_chunks == 1:
                            print(f"✓ 收到第一个音频块: {len(audio_data)} 字节")
                        elif audio_chunks % 10 == 0:
                            print(f"  已收到 {audio_chunks} 个音频块，共 {total_bytes} 字节")

                elif event_type == "response.done":
                    print(f"\n✓ TTS 完成！")
                    print(f"   总音频块数: {audio_chunks}")
                    print(f"   总字节数: {total_bytes}")
                    print(f"   平均块大小: {total_bytes // audio_chunks if audio_chunks > 0 else 0} 字节")
                    break

                elif event_type == "error":
                    error_info = event.get("error", {})
                    print(f"\n❌ TTS 错误: {error_info.get('message', 'Unknown error')}")
                    print(f"   完整错误: {json.dumps(error_info, indent=2, ensure_ascii=False)}")
                    break

                elif event_type in ["response.created", "response.output_item.added",
                                   "response.content_part.added", "response.audio.done",
                                   "response.content_part.done", "response.output_item.done"]:
                    # 信息事件
                    print(f"  📝 事件: {event_type}")

            except asyncio.TimeoutError:
                print("\n❌ 超时: 等待音频响应超过30秒")
                break

        # 关闭连接
        print("\n6️⃣ 关闭连接...")
        finish_event = {"type": "session.finish"}
        await websocket.send(json.dumps(finish_event))
        await websocket.close()
        print("✓ 连接已关闭")

        # 总结
        print("\n" + "="*50)
        if audio_chunks > 0:
            print("✅ 测试成功！Aliyun TTS 工作正常")
        else:
            print("❌ 测试失败：未收到音频数据")
        print("="*50)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_aliyun_tts())
