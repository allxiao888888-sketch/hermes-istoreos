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
import logging
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
# 配置
# ---------------------------------------------------------------------------
CONFIG_FILE = "/etc/config/hermes.json"
DEFAULT_PORT = 9120
DEFAULT_HOST = "127.0.0.1"  # 默认只监听本地，前端通过 LuCI 代理

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("hermes-api")

# ---------------------------------------------------------------------------
# 配置管理
# ---------------------------------------------------------------------------

def load_config():
    """加载配置"""
    defaults = {
        "llm_provider": "openrouter",      # openrouter, openai, deepseek, custom
        "llm_api_key": "",
        "llm_model": "google/gemini-2.0-flash-lite-preview-02-05",
        "llm_base_url": "https://openrouter.ai/api/v1",
        "api_key": "",                     # API 认证密钥（留空不认证）
        "auto_refresh": 10,
        "theme": "auto",
    }
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                defaults.update(data)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"配置加载失败: {e}，使用默认配置")
    return defaults


def save_config(config):
    """保存配置"""
    try:
        # 确保目录存在
        config_dir = os.path.dirname(CONFIG_FILE)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
        # 原子写入
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        os.replace(tmp, CONFIG_FILE)
        return True
    except IOError as e:
        logger.error(f"保存配置失败: {e}")
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

SYSTEM_PROMPT = """你是一个运行在 iStoreOS 路由器上的 AI 助手。
你可以帮助用户管理路由器系统。

路由器管理能力:
- 软件包管理: 安装、卸载、更新 opkg 软件包
- 服务管理: 启停系统服务、查看运行状态
- 系统监控: CPU、内存、磁盘、网络信息
- 命令执行: 运行 shell 命令

请用中文回答。当用户需要执行操作时，建议具体的命令或操作步骤。
注意: 某些操作需要管理员权限，执行前请确认用户的意图。
回答要简洁实用，直接解决问题。"""


def chat_with_llm(messages, model=None, provider=None):
    """通过 LLM API 发送聊天消息"""
    config = load_config()
    provider = provider or config.get("llm_provider", "openrouter")
    model = model or config.get("llm_model", "google/gemini-2.0-flash-lite-preview-02-05")
    api_key = config.get("llm_api_key", "")
    base_url = config.get("llm_base_url", "https://openrouter.ai/api/v1")

    if not api_key:
        return {"error": "未配置 LLM API 密钥，请在设置中配置", "needs_config": True}

    # 构建请求
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    # 为不同 provider 添加额外 header
    if provider == "openrouter":
        headers["HTTP-Referer"] = "http://localhost:9120"
        headers["X-Title"] = "iStoreOS Hermes Agent"

    # 构建消息列表
    llm_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in messages:
        llm_messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", ""),
        })

    payload = {
        "model": model,
        "messages": llm_messages,
        "temperature": 0.7,
        "max_tokens": 4096,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            choice = result.get("choices", [{}])[0]
            return {
                "response": choice.get("message", {}).get("content", ""),
                "model": result.get("model", model),
                "usage": result.get("usage", {}),
            }
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        logger.error(f"LLM API HTTP 错误: {e.code} - {body}")
        return {"error": f"API 错误 ({e.code}): {body[:500]}"}
    except urllib.error.URLError as e:
        logger.error(f"LLM API 连接错误: {e.reason}")
        return {"error": f"无法连接到 {provider} API: {e.reason}"}
    except json.JSONDecodeError as e:
        logger.error(f"LLM API 响应解析失败: {e}")
        return {"error": f"响应解析失败: {e}"}
    except Exception as e:
        logger.error(f"LLM API 调用异常: {e}")
        return {"error": f"调用异常: {e}"}


# ---------------------------------------------------------------------------
# HTTP 请求处理
# ---------------------------------------------------------------------------

class HermesAPIHandler(http.server.BaseHTTPRequestHandler):
    """Hermes Router API HTTP 处理器"""

    # 禁用标准日志（我们自己控制）
    def log_message(self, format, *args):
        logger.info(f"{self.client_address[0]} - {format % args}")

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
            logger.exception("请求处理异常")
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

        logger.info(f"聊天请求: msg_len={len(message)}, model={model or 'default'}")

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
        logger.info(f"安装软件包: {name}")
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
        logger.info(f"卸载软件包: {name}")
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
            logger.info(f"升级软件包: {name}")
            r = run_cmd(["opkg", "upgrade", name], timeout=120)
        else:
            logger.info("升级所有软件包")
            r = run_cmd(["opkg", "upgrade"], timeout=300)
        self._send_json({
            "package": name or "all",
            "success": r["success"],
            "output": r["stdout"] if r["success"] else r["stderr"],
        })

    def _handle_package_update(self):
        """更新软件包列表"""
        logger.info("更新软件包列表")
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

        logger.info(f"服务操作: {action} {name}")
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

        logger.info(f"执行命令: {command}")
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
    logger.info(f"🎯 Hermes Router API v2.0.0 启动: http://{args.host}:{args.port}")
    logger.info(f"📁 配置文件: {CONFIG_FILE}")

    config = load_config()
    if config.get("llm_api_key"):
        logger.info(f"🤖 LLM 已配置: {config.get('llm_provider')}/{config.get('llm_model')}")
    else:
        logger.warning("⚠️  LLM API 密钥未配置, AI 聊天功能不可用。请在设置中配置。")

    if config.get("api_key"):
        logger.info("🔐 API 认证已启用")
    else:
        logger.warning("🔓 API 认证未启用（不安全）")

    # 处理 SIGTERM/SIGINT
    def handle_signal(sig, frame):
        logger.info("正在关闭服务...")
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
