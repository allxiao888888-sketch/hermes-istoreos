#!/usr/bin/env python3
"""
openclaw-api — Hermes Agent REST API 网关
为 iStoreOS LuCI 插件提供轻量级 HTTP API 接口。

启动方式:
  python3 server.py

可选参数:
  --port PORT      监听端口 (默认 9120)
  --hermes-port     Hermes Agent API 端口 (默认 9119)
  --api-key KEY     API 认证密钥 (可选)
"""

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime
from typing import Optional

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Header, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
HERMES_HOME = os.path.expanduser("~/.hermes")
HERMES_AGENT_DIR = os.path.join(HERMES_HOME, "hermes-agent")
HERMES_API_PORT = 9119  # Hermes Agent Web UI API 端口
HERMES_WEBHOOK_PORT = 8644  # Hermes Agent 平台 Webhook 端口

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("openclaw-api")

# FastAPI 应用
app = FastAPI(
    title="OpenClaw API Gateway",
    description="iStoreOS 插件用的 Hermes Agent HTTP API 网关",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# 全局状态
# ---------------------------------------------------------------------------
_API_KEY: Optional[str] = None
_hermes_api_base: str = f"http://127.0.0.1:{HERMES_API_PORT}"
_http_client: Optional[httpx.AsyncClient] = None


# ---------------------------------------------------------------------------
# 认证依赖
# ---------------------------------------------------------------------------
async def verify_api_key(authorization: Optional[str] = Header(None)) -> None:
    """验证 API Key（如果配置了的话）"""
    if not _API_KEY:
        return  # 没配置密钥，不验证
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


# ---------------------------------------------------------------------------
# 模型
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str = Field(..., description="要发送给 Hermes Agent 的消息")
    session_id: Optional[str] = Field(None, description="会话 ID（可选，留空自动创建新会话）")
    stream: bool = Field(False, description="是否流式响应")
    personality: Optional[str] = Field(None, description="角色设定 (helpful, concise, technical, etc.)")


class ChatResponse(BaseModel):
    session_id: str
    response: str
    model: Optional[str] = None
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    duration_ms: Optional[int] = None


class StatusResponse(BaseModel):
    hermes_api_running: bool
    openclaw_api_version: str = "1.0.0"
    hermes_version: Optional[str] = None
    session_count: Optional[int] = None


# ---------------------------------------------------------------------------
# Hermes Agent API 代理
# ---------------------------------------------------------------------------
async def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=30.0)
    return _http_client


async def _check_hermes_api() -> bool:
    """检查 Hermes Agent API 是否在线"""
    try:
        client = await _get_client()
        resp = await client.get(f"{_hermes_api_base}/api/status", timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Hermes Agent CLI 包装器（用于执行聊天）
# ---------------------------------------------------------------------------
def _run_hermes_chat(message: str) -> dict:
    """
    通过 Hermes Agent CLI 执行聊天。
    使用 hermes chat 命令或直接调用 Python API。
    返回包含响应文本的字典。
    """
    hermes_bin = os.path.join(HERMES_HOME, "hermes-agent", "venv", "bin", "hermes")
    if not os.path.exists(hermes_bin):
        hermes_bin = "hermes"  # 尝试 PATH

    start_time = time.time()

    try:
        # 方法 1: 使用 Python API 直接调用
        result = _call_hermes_python_api(message)
        duration = int((time.time() - start_time) * 1000)
        result["duration_ms"] = duration
        return result
    except Exception as e:
        logger.warning(f"Python API 调用失败: {e}，尝试 CLI 方式")

        # 方法 2: CLI 回退
        try:
            session_id = str(uuid.uuid4())[:8]
            cmd = [hermes_bin, "chat", "--no-stream", "--session", session_id, message]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
                cwd=HERMES_HOME,
            )
            duration = int((time.time() - start_time) * 1000)
            return {
                "session_id": session_id,
                "response": proc.stdout.strip() or proc.stderr.strip(),
                "model": None,
                "tokens_input": None,
                "tokens_output": None,
                "duration_ms": duration,
            }
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=504, detail="Hermes Agent 响应超时")
        except FileNotFoundError:
            raise HTTPException(
                status_code=503,
                detail="Hermes Agent CLI 未找到。请确保安装了 Hermes Agent。",
            )


def _call_hermes_python_api(message: str) -> dict:
    """
    通过 Python 直接调用 AIAgent，获取更完整的返回信息。
    """
    import importlib.util

    # 检查 hermes-agent 是否在 Python 路径中
    agent_dir = HERMES_AGENT_DIR
    sys.path.insert(0, agent_dir)

    try:
        from run_agent import AIAgent
    except ImportError:
        # 尝试从 venv 导入
        venv_python = os.path.join(agent_dir, "venv", "bin", "python3")
        if os.path.exists(venv_python):
            # 在子进程中执行
            script = f"""
import sys, json
sys.path.insert(0, '{agent_dir}')
from run_agent import AIAgent
agent = AIAgent(max_iterations=5, skip_context_files=False)
result = agent.chat('''{message.replace("'", "\\'")}''')
print(json.dumps({{
    "session_id": agent.session_id or "unknown",
    "response": result,
    "model": agent.model if hasattr(agent, 'model') else None,
    "tokens_input": None,
    "tokens_output": None,
}}))
"""
            proc = subprocess.run(
                [venv_python, "-c", script],
                capture_output=True,
                text=True,
                timeout=300,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
                cwd=agent_dir,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"Python API 返回错误: {proc.stderr}")
            return json.loads(proc.stdout.strip())
        raise

    # 直接使用 AIAgent (在同一个进程中)
    agent = AIAgent(max_iterations=5, skip_context_files=False, quiet_mode=True)
    result = agent.chat(message)
    return {
        "session_id": getattr(agent, "session_id", "unknown"),
        "response": result,
        "model": getattr(agent, "model", None),
        "tokens_input": None,
        "tokens_output": None,
    }


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------
@app.get("/api/status", response_model=StatusResponse, dependencies=[Depends(verify_api_key)])
async def get_status():
    """获取 OpenClaw API 网关和 Hermes Agent 的状态"""
    hermes_ok = await _check_hermes_api()

    hermes_version = None
    session_count = None
    if hermes_ok:
        try:
            client = await _get_client()
            resp = await client.get(f"{_hermes_api_base}/api/status")
            if resp.status_code == 200:
                data = resp.json()
                hermes_version = data.get("version")
                session_count = data.get("active_sessions", 0)
        except Exception:
            pass

    return StatusResponse(
        hermes_api_running=hermes_ok,
        hermes_version=hermes_version,
        session_count=session_count,
    )


@app.post("/api/chat", response_model=ChatResponse, dependencies=[Depends(verify_api_key)])
async def chat(request: ChatRequest):
    """发送消息给 Hermes Agent 并获取响应"""
    logger.info(f"收到聊天请求: session={request.session_id or 'new'}, msg_len={len(request.message)}")

    # 执行聊天
    result = _run_hermes_chat(request.message)

    return ChatResponse(
        session_id=result.get("session_id", str(uuid.uuid4())[:8]),
        response=result.get("response", ""),
        model=result.get("model"),
        tokens_input=result.get("tokens_input"),
        tokens_output=result.get("tokens_output"),
        duration_ms=result.get("duration_ms"),
    )


@app.get("/api/sessions", dependencies=[Depends(verify_api_key)])
async def list_sessions(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """获取会话列表（代理到 Hermes Agent API）"""
    if not await _check_hermes_api():
        raise HTTPException(status_code=503, detail="Hermes Agent API 未运行")
    try:
        client = await _get_client()
        resp = await client.get(
            f"{_hermes_api_base}/api/sessions",
            params={"limit": limit, "offset": offset},
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="获取会话列表失败")
        return resp.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"无法连接 Hermes Agent: {e}")


@app.get("/api/sessions/{session_id}/messages", dependencies=[Depends(verify_api_key)])
async def get_session_messages(session_id: str):
    """获取指定会话的消息"""
    if not await _check_hermes_api():
        raise HTTPException(status_code=503, detail="Hermes Agent API 未运行")
    try:
        client = await _get_client()
        resp = await client.get(
            f"{_hermes_api_base}/api/sessions/{session_id}/messages"
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="获取会话消息失败")
        return resp.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"无法连接 Hermes Agent: {e}")


@app.get("/api/health")
async def health_check():
    """健康检查"""
    hermes_ok = await _check_hermes_api()
    return {
        "status": "ok",
        "hermes_api_connected": hermes_ok,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# 启动
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="OpenClaw API Gateway for iStoreOS")
    parser.add_argument("--port", type=int, default=9120, help="监听端口 (默认: 9120)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="监听地址 (默认: 0.0.0.0)")
    parser.add_argument("--hermes-port", type=int, default=9119, help="Hermes Agent API 端口 (默认: 9119)")
    parser.add_argument("--api-key", type=str, default=None, help="API 认证密钥")
    parser.add_argument("--daemon", action="store_true", help="后台运行")

    args = parser.parse_args()

    global _API_KEY, _hermes_api_base
    _API_KEY = args.api_key or os.environ.get("OPENCLAW_API_KEY")
    _hermes_api_base = f"http://127.0.0.1:{args.hermes_port}"

    logger.info(f"启动 OpenClaw API 网关: {args.host}:{args.port}")
    logger.info(f"Hermes Agent API: {_hermes_api_base}")
    logger.info(f"API 认证: {'启用' if _API_KEY else '禁用（不安全）'}")

    if args.daemon:
        import daemon  # type: ignore
        with daemon.DaemonContext():
            uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    else:
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
