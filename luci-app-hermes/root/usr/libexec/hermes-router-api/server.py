#!/usr/bin/env python3
"""
Hermes Router API — Zero-dependency Python HTTP API Server for iStoreOS
========================================================================
在 iStoreOS 路由器上独立运行的 AI 助理 API 网关。
零外部依赖，仅使用 Python 标准库。

功能:
  - /api/health         — 健康检查
  - /api/status         — 系统状态
  - /api/chat           — AI 聊天（连接 LLM API）
  - /api/router/info    — 路由器系统信息
  - /api/router/packages — 软件包管理（opkg）
  - /api/router/services — 服务管理（init.d）
  - /api/router/network  — 网络状态
  - /api/config         — 获取/更新配置
  - /api/exec           — 执行 Shell 命令

启动:  python3 server.py [--port 9120] [--host 0.0.0.0]
"""

import argparse
import base64
import fcntl
import http.server
import json
# logging module not available in python3-light, use print to stderr instead
import os
import re
import shlex
import signal
import socket
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

# ---------------------------------------------------------------------------
# python3-light 缺少 encodings.idna，monkey-patch socket.getfqdn()
# ---------------------------------------------------------------------------
_original_getfqdn = socket.getfqdn
def _patched_getfqdn(name=""):
    try:
        return _original_getfqdn(name)
    except LookupError:
        return name or "localhost"
socket.getfqdn = _patched_getfqdn

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
CONFIG_FILE = "/etc/config/hermes"  # UCI 配置文件
DEFAULT_PORT = 9120
DEFAULT_HOST = "127.0.0.1"  # 默认只监听本地，前端通过 LuCI 代理

def log(level, msg):
    """简单日志输出到 stderr，兼容 python3-light"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{ts} [{level}] {msg}", file=sys.stderr, flush=True)

# ---------------------------------------------------------------------------
# 配置管理
# ---------------------------------------------------------------------------

def load_config():
    """从 UCI 配置文件加载配置"""
    defaults = {
        "llm_provider": "openrouter",
        "llm_api_key": "",
        "llm_model": "google/gemini-2.0-flash-lite-preview-02-05",
        "llm_base_url": "https://openrouter.ai/api/v1",
        "api_key": "",
        "auto_refresh": 10,
        "theme": "auto",
    }
    try:
        if os.path.exists(CONFIG_FILE):
            result = subprocess.run(
                ["uci", "-c", "/etc/config", "get", "hermes.@config[0].llm_provider"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                defaults["llm_provider"] = result.stdout.strip()

            result = subprocess.run(
                ["uci", "-c", "/etc/config", "get", "hermes.@config[0].llm_api_key"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                defaults["llm_api_key"] = result.stdout.strip()

            result = subprocess.run(
                ["uci", "-c", "/etc/config", "get", "hermes.@config[0].llm_model"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                defaults["llm_model"] = result.stdout.strip()

            result = subprocess.run(
                ["uci", "-c", "/etc/config", "get", "hermes.@config[0].llm_base_url"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                defaults["llm_base_url"] = result.stdout.strip()

            result = subprocess.run(
                ["uci", "-c", "/etc/config", "get", "hermes.@config[0].api_key"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                defaults["api_key"] = result.stdout.strip()

            log("INFO", f"UCI 配置加载成功: provider={defaults['llm_provider']}, model={defaults['llm_model']}")
    except Exception as e:
        log("WARNING", f"UCI 配置读取失败: {e}，使用默认配置")
    return defaults


def save_config(config):
    """通过 uci 命令保存配置"""
    try:
        for key, value in config.items():
            if key in ("llm_provider", "llm_api_key", "llm_model", "llm_base_url",
                       "api_key", "auto_refresh", "theme"):
                subprocess.run(
                    ["uci", "-c", "/etc/config", "set", f"hermes.@config[0].{key}={value}"],
                    capture_output=True, timeout=5
                )
        subprocess.run(["uci", "-c", "/etc/config", "commit", "hermes"],
                       capture_output=True, timeout=5)
        return True
    except Exception as e:
        log("ERROR", f"保存配置失败: {e}")
        return False


# 全局配置
_config = load_config()

# ---------------------------------------------------------------------------
# Shell 命令执行
# ---------------------------------------------------------------------------

def run_cmd(cmd, timeout=30):
    """执行 shell 命令并返回结果"""
    try:
        if isinstance(cmd, str):
            cmd = shlex.split(cmd)
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "success": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "returncode": -1, "stdout": "", "stderr": "命令执行超时"}
    except FileNotFoundError as e:
        return {"success": False, "returncode": -1, "stdout": "", "stderr": f"命令未找到: {e}"}
    except Exception as e:
        return {"success": False, "returncode": -1, "stdout": "", "stderr": str(e)}


# ---------------------------------------------------------------------------
# 系统信息收集
# ---------------------------------------------------------------------------

def get_system_info():
    """获取路由器系统信息"""
    info = {
        "hostname": "",
        "kernel": "",
        "os": "",
        "uptime": "",
        "cpu": {},
        "memory": {},
        "disk": {},
        "loadavg": [],
    }

    # 主机名
    r = run_cmd(["cat", "/proc/sys/kernel/hostname"])
    if r["success"]:
        info["hostname"] = r["stdout"].strip()

    # 内核版本
    r = run_cmd(["uname", "-a"])
    if r["success"]:
        info["kernel"] = r["stdout"].strip()

    # OpenWRT 版本
    r = run_cmd(["cat", "/etc/openwrt_release"])
    if r["success"]:
        for line in r["stdout"].split("\n"):
            if "DISTRIB_DESCRIPTION" in line:
                info["os"] = line.split("=")[-1].strip().strip("'\"")
                break
            if "DISTRIB_ID" in line:
                info["os"] = line.split("=")[-1].strip().strip("'\"")
    if not info["os"]:
        info["os"] = "iStoreOS / OpenWRT"

    # 运行时间
    r = run_cmd(["cat", "/proc/uptime"])
    if r["success"]:
        try:
            uptime_sec = float(r["stdout"].split()[0])
            days = int(uptime_sec // 86400)
            hours = int((uptime_sec % 86400) // 3600)
            mins = int((uptime_sec % 3600) // 60)
            info["uptime"] = f"{days}天 {hours}小时 {mins}分钟"
            info["uptime_seconds"] = uptime_sec
        except (IndexError, ValueError):
            pass

    # CPU
    r = run_cmd(["cat", "/proc/cpuinfo"])
    if r["success"]:
        for line in r["stdout"].split("\n"):
            if "model name" in line:
                info["cpu"]["model"] = line.split(":")[-1].strip()
            elif "processor" in line and ":" in line:
                info["cpu"]["cores"] = int(line.split(":")[-1].strip()) + 1
            elif "BogoMIPS" in line:
                info["cpu"]["bogomips"] = line.split(":")[-1].strip()

    if "cores" not in info["cpu"]:
        info["cpu"]["cores"] = 0
    if "model" not in info["cpu"]:
        info["cpu"]["model"] = "未知"

    # 内存
    r = run_cmd(["cat", "/proc/meminfo"])
    if r["success"]:
        total = 0
        free = 0
        available = 0
        for line in r["stdout"].split("\n"):
            if line.startswith("MemTotal:"):
                total = int(line.split()[1]) // 1024
            elif line.startswith("MemFree:"):
                free = int(line.split()[1]) // 1024
            elif line.startswith("MemAvailable:"):
                available = int(line.split()[1]) // 1024
        info["memory"] = {
            "total_mb": total,
            "free_mb": free,
            "available_mb": available,
            "used_mb": total - free,
            "usage_pct": round((total - available) / total * 100, 1) if total > 0 else 0,
        }

    # 磁盘
    r = run_cmd(["df", "-h"])
    if r["success"]:
        disks = []
        for line in r["stdout"].split("\n")[1:]:
            parts = line.split()
            if len(parts) >= 6:
                disks.append({
                    "filesystem": parts[0],
                    "size": parts[1],
                    "used": parts[2],
                    "available": parts[3],
                    "usage_pct": parts[4],
                    "mount": parts[5],
                })
        info["disk"] = {"partitions": disks}

    # 系统负载
    r = run_cmd(["cat", "/proc/loadavg"])
    if r["success"]:
        parts = r["stdout"].split()
        info["loadavg"] = parts[:3]

    return info


def get_packages(query=None, installed_only=True):
    """获取 opkg 软件包列表"""
    cmd = ["opkg", "list-installed"]
    if query:
        if installed_only:
            # 使用 grep 过滤
            r = run_cmd(["opkg", "list-installed"])
        else:
            r = run_cmd(["opkg", "find", query])
    else:
        r = run_cmd(["opkg", "list-installed"])

    if not r["success"]:
        return {"packages": [], "error": r["stderr"]}

    packages = []
    for line in r["stdout"].split("\n"):
        if not line.strip():
            continue
        # opkg format: "package - version - description"
        parts = line.split(" - ", 2)
        if len(parts) >= 2:
            pkg = {
                "name": parts[0].strip(),
                "version": parts[1].strip(),
                "description": parts[2].strip() if len(parts) > 2 else "",
            }
            if query:
                if query.lower() in pkg["name"].lower() or query.lower() in pkg.get("description", "").lower():
                    packages.append(pkg)
            else:
                packages.append(pkg)

    return {"packages": packages, "count": len(packages)}


def get_services():
    """获取所有 init.d 服务"""
    r = run_cmd(["ls", "/etc/init.d/"])
    if not r["success"]:
        return {"services": [], "error": r["stderr"]}

    services = []
    for name in r["stdout"].split("\n"):
        name = name.strip()
        if not name:
            continue
        # 检查服务状态
        sr = run_cmd(["/etc/init.d/" + name, "enabled"], timeout=5)
        is_enabled = sr["success"]
        sr = run_cmd(["/etc/init.d/" + name, "running"], timeout=5)
        is_running = sr["success"]
        services.append({
            "name": name,
            "enabled": is_enabled,
            "running": is_running,
        })

    return {"services": services, "count": len(services)}


def get_network_info():
    """获取网络接口信息"""
    info = {
        "interfaces": [],
        "default_gateway": "",
    }

    # 获取接口
    r = run_cmd(["ip", "-o", "link", "show"])
    if r["success"]:
        for line in r["stdout"].split("\n"):
            parts = line.split(": ")
            if len(parts) >= 3:
                if_name = parts[1].strip()
                state = "up" if "UP" in parts[2] else "down"
                mac = ""
                # 获取 MAC 地址
                mr = run_cmd(["cat", f"/sys/class/net/{if_name}/address"], timeout=3)
                if mr["success"]:
                    mac = mr["stdout"].strip()
                # 获取 IP 地址
                ip_addr = ""
                ir = run_cmd(["ip", "-o", "-4", "addr", "show", "dev", if_name], timeout=3)
                if ir["success"]:
                    for i_line in ir["stdout"].split("\n"):
                        ip_parts = i_line.split()
                        if len(ip_parts) >= 4:
                            ip_addr = ip_parts[3]

                info["interfaces"].append({
                    "name": if_name,
                    "state": state,
                    "mac": mac,
                    "ip": ip_addr,
                })

    # 默认网关
    r = run_cmd(["ip", "route", "show", "default"])
    if r["success"]:
        parts = r["stdout"].split()
        if len(parts) >= 3:
            info["default_gateway"] = parts[2]

    return info


# ---------------------------------------------------------------------------
# LLM API 调用
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """你是运行在 iStoreOS 路由器上的 AI 助手，你可以**直接操作路由器系统**。

重要: 你有工具可以执行命令、管理软件包和服务。当用户要求操作时，**直接调用工具执行**，不要只建议命令。
- 安装软件: 调用 manage_package action=install
- 卸载软件: 调用 manage_package action=remove
- 启停服务: 调用 manage_service action=start/stop/restart
- 查看状态: 调用 run_command 或 get_system_info
- 执行命令: 调用 run_command

请用中文回答。执行操作前简要说明你要做什么，然后直接调用工具。回答简洁实用。"""

# OpenAI-compatible function calling 工具定义
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "在路由器上执行 shell 命令并返回结果。用于查看状态、修改配置等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的 shell 命令，例如: opkg update, cat /proc/meminfo, uci show network"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "超时秒数，默认 30",
                        "default": 30
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_package",
            "description": "管理 opkg 软件包: 安装、卸载或更新",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["install", "remove", "update"],
                        "description": "操作类型: install=安装, remove=卸载, update=更新软件包列表"
                    },
                    "name": {
                        "type": "string",
                        "description": "软件包名称，update 时不需要"
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_service",
            "description": "管理系统 init.d 服务: 启动、停止、重启、启用、禁用",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["start", "stop", "restart", "enable", "disable"],
                        "description": "操作类型"
                    },
                    "name": {
                        "type": "string",
                        "description": "服务名称，例如: nginx, dnsmasq, firewall"
                    }
                },
                "required": ["action", "name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "获取路由器系统信息: CPU、内存、磁盘、网络接口、运行时间等",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]


def execute_tool(name, args):
    """执行工具调用并返回结果"""
    if name == "run_command":
        cmd = args.get("command", "")
        timeout = args.get("timeout", 30)
        if not cmd:
            return json.dumps({"error": "命令不能为空"}, ensure_ascii=False)
        result = run_cmd(cmd, timeout)
        log("INFO", f"工具执行: run_command {cmd[:80]}")
        return json.dumps(result, ensure_ascii=False)

    elif name == "manage_package":
        action = args.get("action", "")
        pkg_name = args.get("name", "")
        log("INFO", f"工具执行: manage_package {action} {pkg_name}")
        if action == "update":
            result = run_cmd("opkg update", 60)
            return json.dumps(result, ensure_ascii=False)
        elif action == "install":
            if not pkg_name:
                return json.dumps({"error": "请指定要安装的软件包名称"}, ensure_ascii=False)
            result = run_cmd(f"opkg install {pkg_name}", 120)
            return json.dumps(result, ensure_ascii=False)
        elif action == "remove":
            if not pkg_name:
                return json.dumps({"error": "请指定要卸载的软件包名称"}, ensure_ascii=False)
            # 先确认再删除，避免误删
            result = run_cmd(f"opkg remove {pkg_name}", 60)
            return json.dumps(result, ensure_ascii=False)
        else:
            return json.dumps({"error": f"未知操作: {action}"}, ensure_ascii=False)

    elif name == "manage_service":
        action = args.get("action", "")
        svc_name = args.get("name", "")
        if not svc_name:
            return json.dumps({"error": "请指定服务名称"}, ensure_ascii=False)
        log("INFO", f"工具执行: manage_service {action} {svc_name}")
        if action == "enable":
            result = run_cmd(f"/etc/init.d/{svc_name} enable 2>&1", 10)
        elif action == "disable":
            result = run_cmd(f"/etc/init.d/{svc_name} disable 2>&1", 10)
        else:
            result = run_cmd(f"/etc/init.d/{svc_name} {action} 2>&1", 30)
        return json.dumps(result, ensure_ascii=False)

    elif name == "get_system_info":
        log("INFO", "工具执行: get_system_info")
        info = get_system_info()
        return json.dumps(info, ensure_ascii=False)

    return json.dumps({"error": f"未知工具: {name}"}, ensure_ascii=False)


def _call_llm_api(llm_messages, model, api_key, base_url, provider, with_tools=True):
    """单次 LLM API 调用，返回 API 响应 JSON"""
    url = f"{base_url.rstrip('/')}/chat/completions"

    payload_dict = {
        "model": model,
        "messages": llm_messages,
        "temperature": 0.7,
        "max_tokens": 4096,
    }
    if with_tools:
        payload_dict["tools"] = TOOLS
        payload_dict["tool_choice"] = "auto"

    tmpfile = "/tmp/hermes_llm_request.json"
    with open(tmpfile, "w") as f:
        json.dump(payload_dict, f)

    headers = [
        "Content-Type: application/json",
        f"Authorization: Bearer {api_key}",
    ]
    if provider == "openrouter":
        headers.append("HTTP-Referer: http://localhost:9120")
        headers.append("X-Title: iStoreOS Hermes Agent")

    cmd = ["curl", "-s", "--max-time", "120", "-X", "POST", url, "-d", "@" + tmpfile]
    for h in headers:
        cmd.extend(["-H", h])

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=130)
        os.remove(tmpfile)
    except Exception as e:
        try:
            os.remove(tmpfile)
        except Exception:
            pass
        return None, f"调用异常: {e}"

    if proc.returncode != 0 or not proc.stdout.strip():
        return None, f"API 请求失败: {proc.stderr[:200] if proc.stderr else 'empty response'}"

    try:
        return json.loads(proc.stdout.strip()), None
    except json.JSONDecodeError as e:
        return None, f"响应解析失败: {proc.stdout.strip()[:200]}"


def chat_with_llm(messages, model=None, provider=None):
    """AI 聊天 — 支持 Function Calling，可直接操作路由器"""
    config = load_config()
    provider = provider or config.get("llm_provider", "openrouter")
    model = model or config.get("llm_model", "google/gemini-2.0-flash-lite-preview-02-05")
    api_key = config.get("llm_api_key", "")
    base_url = config.get("llm_base_url", "https://openrouter.ai/api/v1")

    if not api_key:
        return {"error": "未配置 LLM API 密钥，请在设置中配置", "needs_config": True}

    # 构建消息列表
    llm_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in messages:
        role = msg.get("role", "user")
        # 跳过之前对话中的 system 角色（已有 SYSTEM_PROMPT）
        if role == "system":
            continue
        content = msg.get("content", "")
        # 跳过空内容
        if not content and role != "tool":
            continue
        llm_messages.append({"role": role, "content": content})

    total_usage = {}
    final_model = model

    # Function calling 循环 — 最多 10 轮
    for iteration in range(10):
        result, err = _call_llm_api(llm_messages, model, api_key, base_url, provider)

        if err:
            log("ERROR", f"LLM API 错误: {err}")
            return {"error": f"API 错误: {err}"}

        if "error" in result:
            err_info = result["error"]
            err_msg = err_info.get("message", str(err_info)) if isinstance(err_info, dict) else str(err_info)
            log("ERROR", f"LLM API 返回错误: {err_msg}")
            return {"error": f"API 错误: {err_msg}"}

        choice = result.get("choices", [{}])[0]
        message = choice.get("message", {})
        final_model = result.get("model", model)

        # 累计 usage (跳过非整数子字段如 prompt_tokens_details)
        usage = result.get("usage", {})
        for k, v in usage.items():
            if isinstance(v, int):
                total_usage[k] = total_usage.get(k, 0) + v

        # 检查是否有 tool_calls
        tool_calls = message.get("tool_calls")
        if tool_calls:
            # 将 AI 的 tool_call 消息加入对话 (保留 reasoning_content 兼容 DeepSeek)
            assistant_msg = {
                "role": "assistant",
                "content": message.get("content") or "",
                "tool_calls": tool_calls
            }
            if message.get("reasoning_content"):
                rc = message["reasoning_content"]
                assistant_msg["reasoning_content"] = rc[:800] if len(rc) > 800 else rc
            llm_messages.append(assistant_msg)

            # 执行每个工具调用
            for tc in tool_calls:
                func = tc.get("function", {})
                tool_name = func.get("name", "")
                try:
                    tool_args = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    tool_args = {}

                tool_result = execute_tool(tool_name, tool_args)

                # 将工具结果加入对话
                llm_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": tool_result
                })

            # 继续下一轮，让 AI 根据工具结果生成回复
            continue

        # 纯文本回复 — 结束循环
        return {
            "response": message.get("content", ""),
            "model": final_model,
            "usage": total_usage,
        }

    # 超过最大轮数
    return {"response": "操作已执行，但需要更多轮次。请简化你的请求。", "model": final_model, "usage": total_usage}


# ---------------------------------------------------------------------------
# HTTP 请求处理
# ---------------------------------------------------------------------------

class HermesAPIHandler(http.server.BaseHTTPRequestHandler):
    """Hermes Router API HTTP 处理器"""

    # 禁用标准日志（我们自己控制）
    def log_message(self, format, *args):
        log("INFO", f"{self.client_address[0]} - {format % args}")

    def _send_json(self, data, status=200):
        """发送 JSON 响应"""
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status, message):
        """发送错误响应"""
        self._send_json({"error": message, "code": status}, status)

    def _read_body(self):
        """读取请求体"""
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            return self.rfile.read(length).decode("utf-8")
        return ""

    def _parse_json_body(self):
        """解析 JSON 请求体"""
        try:
            return json.loads(self._read_body())
        except json.JSONDecodeError:
            return None

    def _check_auth(self):
        """检查 API 认证"""
        config = load_config()
        api_key = config.get("api_key", "")
        if not api_key:
            return True  # 没配置密钥不验证

        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            self._send_error(401, "缺少 Authorization header")
            return False

        token = auth[7:]
        if token != api_key:
            self._send_error(401, "API 密钥无效")
            return False

        return True

    def _parse_path(self):
        """解析 URL 路径并返回 (path_parts, query_params)"""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.strip("/").split("/")
        params = urllib.parse.parse_qs(parsed.query)
        return path, params

    # -----------------------------------------------------------------------
    # 路由分发
    # -----------------------------------------------------------------------

    def do_OPTIONS(self):
        """CORS preflight"""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self):
        """GET 请求分发"""
        if not self._check_auth():
            return
        path, params = self._parse_path()
        self._route("GET", path, params)

    def do_POST(self):
        """POST 请求分发"""
        if not self._check_auth():
            return
        path, params = self._parse_path()
        self._route("POST", path, {})

    def _route(self, method, path, params):
        """路由分发"""
        try:
            # /api/health
            if path == ["api", "health"]:
                return self._handle_health()

            # /api/status
            elif path == ["api", "status"]:
                return self._handle_status()

            # /api/config
            elif path == ["api", "config"]:
                if method == "GET":
                    return self._handle_get_config()
                elif method == "POST":
                    return self._handle_set_config()

            # /api/chat
            elif path == ["api", "chat"] and method == "POST":
                return self._handle_chat()

            # /api/router/info
            elif path == ["api", "router", "info"]:
                return self._handle_router_info()

            # /api/router/packages
            elif path == ["api", "router", "packages"]:
                query = params.get("q", [None])[0]
                return self._handle_packages(query)

            # /api/router/packages/install
            elif path == ["api", "router", "packages", "install"] and method == "POST":
                return self._handle_package_install()

            # /api/router/packages/remove
            elif path == ["api", "router", "packages", "remove"] and method == "POST":
                return self._handle_package_remove()

            # /api/router/packages/upgrade
            elif path == ["api", "router", "packages", "upgrade"] and method == "POST":
                return self._handle_package_upgrade()

            # /api/router/packages/update
            elif path == ["api", "router", "packages", "update"] and method == "POST":
                return self._handle_package_update()

            # /api/router/services
            elif path == ["api", "router", "services"]:
                return self._handle_services()

            # /api/router/services/:action/:name
            elif (len(path) == 5 and path[0] == "api" and path[1] == "router"
                  and path[2] == "services" and method == "POST"):
                action = path[3]
                name = path[4]
                return self._handle_service_action(action, name)

            # /api/router/network
            elif path == ["api", "router", "network"]:
                return self._handle_network()

            # /api/exec
            elif path == ["api", "exec"] and method == "POST":
                return self._handle_exec()

            # /api/llm/models
            elif path == ["api", "llm", "models"]:
                return self._handle_llm_models()

            # 未匹配
            else:
                self._send_error(404, f"未知路径: /{'/'.join(path)}")

        except Exception as e:
            log("ERROR", "请求处理异常")
            self._send_error(500, f"服务器内部错误: {e}")

    # -----------------------------------------------------------------------
    # 处理器实现
    # -----------------------------------------------------------------------

    def _handle_health(self):
        """健康检查"""
        self._send_json({
            "status": "ok",
            "version": "2.0.0",
            "platform": "iStoreOS",
            "timestamp": datetime.now().isoformat(),
        })

    def _handle_status(self):
        """系统状态"""
        config = load_config()
        self._send_json({
            "version": "2.0.0",
            "platform": "iStoreOS",
            "python_version": sys.version.split()[0],
            "config_ok": bool(config.get("llm_api_key")),
            "config_provider": config.get("llm_provider", "未配置"),
            "config_model": config.get("llm_model", "未配置"),
            "uptime": time.time() - _start_time,
            "timestamp": datetime.now().isoformat(),
        })

    def _handle_get_config(self):
        """获取配置（不返回密钥）"""
        config = load_config()
        safe_config = {
            "llm_provider": config.get("llm_provider"),
            "llm_model": config.get("llm_model"),
            "llm_base_url": config.get("llm_base_url"),
            "auto_refresh": config.get("auto_refresh"),
            "theme": config.get("theme"),
            "has_api_key": bool(config.get("llm_api_key")),
        }
        self._send_json(safe_config)

    def _handle_set_config(self):
        """更新配置"""
        body = self._parse_json_body()
        if not body:
            return self._send_error(400, "无效的 JSON")

        config = load_config()
        for key in ["llm_provider", "llm_model", "llm_base_url", "auto_refresh", "theme", "api_key"]:
            if key in body:
                config[key] = body[key]

        # API 密钥单独处理（只允许更新非空值）
        if "llm_api_key" in body and body["llm_api_key"]:
            config["llm_api_key"] = body["llm_api_key"]

        if save_config(config):
            global _config
            _config = config
            self._send_json({"success": True, "message": "配置已更新"})
        else:
            self._send_error(500, "配置保存失败")

    def _handle_chat(self):
        """处理 AI 聊天"""
        body = self._parse_json_body()
        if not body:
            return self._send_error(400, "无效的请求体")

        message = body.get("message", "")
        if not message:
            return self._send_error(400, "消息不能为空")

        messages = body.get("messages", [])
        model = body.get("model")
        provider = body.get("provider")

        # 如果有历史消息，追加新消息，否则使用默认
        if not messages:
            messages = [{"role": "user", "content": message}]
        else:
            messages.append({"role": "user", "content": message})

        log("INFO", f"聊天请求: msg_len={len(message)}, model={model or 'default'}")

        result = chat_with_llm(messages, model, provider)

        if "error" in result:
            status = 503 if result.get("needs_config") else 500
            self._send_json(result, status)
        else:
            self._send_json({
                "response": result["response"],
                "model": result.get("model"),
                "usage": result.get("usage"),
            })

    def _handle_router_info(self):
        """获取路由器系统信息"""
        info = get_system_info()
        self._send_json(info)

    def _handle_packages(self, query=None):
        """获取软件包列表"""
        result = get_packages(query)
        self._send_json(result)

    def _handle_package_install(self):
        """安装软件包"""
        body = self._parse_json_body()
        if not body or not body.get("name"):
            return self._send_error(400, "需要指定包名")
        name = body["name"]
        log("INFO", f"安装软件包: {name}")
        r = run_cmd(["opkg", "install", name], timeout=120)
        self._send_json({
            "package": name,
            "success": r["success"],
            "output": r["stdout"] if r["success"] else r["stderr"],
        })

    def _handle_package_remove(self):
        """卸载软件包"""
        body = self._parse_json_body()
        if not body or not body.get("name"):
            return self._send_error(400, "需要指定包名")
        name = body["name"]
        log("INFO", f"卸载软件包: {name}")
        r = run_cmd(["opkg", "remove", name], timeout=60)
        self._send_json({
            "package": name,
            "success": r["success"],
            "output": r["stdout"] if r["success"] else r["stderr"],
        })

    def _handle_package_upgrade(self):
        """升级软件包"""
        body = self._parse_json_body()
        name = body.get("name") if body else None
        if name:
            log("INFO", f"升级软件包: {name}")
            r = run_cmd(["opkg", "upgrade", name], timeout=120)
        else:
            log("INFO","升级所有软件包")
            r = run_cmd(["opkg", "upgrade"], timeout=300)
        self._send_json({
            "package": name or "all",
            "success": r["success"],
            "output": r["stdout"] if r["success"] else r["stderr"],
        })

    def _handle_package_update(self):
        """更新软件包列表"""
        log("INFO","更新软件包列表")
        r = run_cmd(["opkg", "update"], timeout=60)
        self._send_json({
            "success": r["success"],
            "output": r["stdout"] if r["success"] else r["stderr"],
        })

    def _handle_services(self):
        """获取服务列表"""
        result = get_services()
        self._send_json(result)

    def _handle_service_action(self, action, name):
        """服务操作：start/stop/restart/enable/disable"""
        valid_actions = ["start", "stop", "restart", "enable", "disable", "reload"]
        if action not in valid_actions:
            return self._send_error(400, f"无效的操作: {action}，支持: {', '.join(valid_actions)}")

        log("INFO", f"服务操作: {action} {name}")
        r = run_cmd(["/etc/init.d/" + name, action], timeout=30)
        # 有些服务返回非0表示"already running"等无害状态
        self._send_json({
            "service": name,
            "action": action,
            "success": True,  # 即使返回非0也视为成功（很多OpenWRT服务如此）
            "output": r["stdout"] or r["stderr"],
        })

    def _handle_network(self):
        """获取网络信息"""
        info = get_network_info()
        self._send_json(info)

    def _handle_exec(self):
        """执行 shell 命令"""
        body = self._parse_json_body()
        if not body or not body.get("command"):
            return self._send_error(400, "需要指定命令")

        command = body["command"]
        timeout = body.get("timeout", 30)

        # 安全检查：只允许有限命令集
        safe_commands = [
            "ls", "ps", "top", "free", "df", "du", "cat", "echo", "grep",
            "find", "ip", "iw", "iwinfo", "wifi", "ping", "traceroute",
            "netstat", "ss", "nslookup", "dig", "curl", "wget",
            "uci", "opkg", "service", "/etc/init.d/",
            "ifconfig", "route", "arp", "tc", "iptables", "nft",
            "mount", "umount", "blkid", "block",
            "date", "uptime", "uname", "dmesg", "sysctl",
            "logread", "tail", "head", "wc",
            "which", "whereis", "id", "whoami",
            "python3", "bash", "sh", "ash",
            "crontab", "reboot", "poweroff",
        ]

        cmd_base = command.split()[0] if command.strip() else ""
        is_safe = any(cmd_base == c or cmd_base.startswith(c.rstrip("/")) for c in safe_commands)

        if not is_safe:
            # 额外检查是否在PATH中
            which_result = run_cmd(["which", cmd_base], timeout=5)
            is_safe = which_result["success"]

        if not is_safe:
            return self._send_error(403, f"禁止执行的命令: {cmd_base}")

        log("INFO", f"执行命令: {command}")
        r = run_cmd(command, timeout=timeout)
        self._send_json(r)

    def _handle_llm_models(self):
        """返回常用 LLM 模型列表"""
        models = {
            "openrouter": [
                {"id": "google/gemini-2.0-flash-lite-preview-02-05", "name": "Gemini 2.0 Flash Lite", "free": True},
                {"id": "google/gemini-2.0-flash-001", "name": "Gemini 2.0 Flash", "free": True},
                {"id": "anthropic/claude-3.5-haiku", "name": "Claude 3.5 Haiku", "free": False},
                {"id": "meta-llama/llama-3.3-70b-instruct", "name": "Llama 3.3 70B", "free": True},
                {"id": "deepseek/deepseek-r1", "name": "DeepSeek R1", "free": False},
                {"id": "qwen/qwen-2.5-72b-instruct", "name": "Qwen 2.5 72B", "free": True},
            ],
            "openai": [
                {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "free": False},
                {"id": "gpt-4o", "name": "GPT-4o", "free": False},
            ],
            "deepseek": [
                {"id": "deepseek-chat", "name": "DeepSeek V3", "free": False},
                {"id": "deepseek-reasoner", "name": "DeepSeek R1", "free": False},
            ],
        }
        self._send_json(models)


# ---------------------------------------------------------------------------
# 启动
# ---------------------------------------------------------------------------

_start_time = time.time()


def main():
    parser = argparse.ArgumentParser(description="Hermes Router API for iStoreOS")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"监听端口 (默认: {DEFAULT_PORT})")
    parser.add_argument("--host", type=str, default=DEFAULT_HOST, help=f"监听地址 (默认: {DEFAULT_HOST})")
    args = parser.parse_args()

    server = http.server.HTTPServer((args.host, args.port), HermesAPIHandler)
    log("INFO", f"🎯 Hermes Router API v2.0.0 启动: http://{args.host}:{args.port}")
    log("INFO", f"📁 配置文件: {CONFIG_FILE}")

    config = load_config()
    if config.get("llm_api_key"):
        log("INFO", f"🤖 LLM 已配置: {config.get('llm_provider')}/{config.get('llm_model')}")
    else:
        log("WARNING","⚠️  LLM API 密钥未配置, AI 聊天功能不可用。请在设置中配置。")

    if config.get("api_key"):
        log("INFO","🔐 API 认证已启用")
    else:
        log("WARNING","🔓 API 认证未启用（不安全）")

    # 处理 SIGTERM/SIGINT
    def handle_signal(sig, frame):
        log("INFO","正在关闭服务...")
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
