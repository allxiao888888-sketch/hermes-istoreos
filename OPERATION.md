# Hermes Agent 操作指南

Hermes Agent 是运行在 iStoreOS 路由器上的 AI 助手插件，可通过网页直接对话操作路由器。

## 快速开始

1. 打开 `http://192.168.100.1:8080` → 服务 → **Hermes Agent**
2. 进入**设置**，填入 AI 提供商和 API Key（推荐 OpenRouter 免费额度）
3. 返回 **AI 聊天**，开始对话

## AI 聊天

### 对话操作

直接在输入框打字，Enter 发送，Shift+Enter 换行。

### 路由器管理

AI 可以**直接执行**操作，不需要你手动敲命令：

| 你说 | AI 做的事 |
|------|----------|
| "安装 nginx" | 调用 opkg 安装，返回结果 |
| "重启 dnsmasq" | 执行 `/etc/init.d/dnsmasq restart` |
| "查看 CPU 和内存" | 读取系统信息，组织成表格回复 |
| "查看运行的进程" | 执行 `ps` 命令并分析 |
| "启动 OpenClash" | 自动启用服务 + 启动，验证状态 |

### 联网搜索

| 你说 | AI 做的事 |
|------|----------|
| "深圳天气怎么样" | 调用 wttr.in 获取实时天气 |
| "什么是 WireGuard" | 查 Wikipedia 百科摘要 |
| "Docker 安装教程" | DuckDuckGo 网页搜索 |

### 对话管理

- 内存使用 < 90%：完整保留对话历史
- 内存 ≥ 90%：自动清空历史，只保留最后一条

## 仪表盘

实时显示路由器状态：
- API 状态、AI 连接状态
- 主机名、运行时间
- CPU/内存/存储/软件包数量
- 网络接口列表（IP、MAC、状态）

## 路由器管理

| 标签 | 功能 |
|------|------|
| **软件包管理** | 搜索、安装、卸载、更新 opkg 包 |
| **服务管理** | 查看、启动、停止、重启 init.d 服务 |
| **系统信息** | 主机名、内核、CPU、内存、磁盘、负载 |
| **命令终端** | 直接在网页执行 Shell 命令 |

## 设置

| 配置项 | 说明 |
|--------|------|
| AI 提供商 | OpenRouter / OpenAI / DeepSeek / 自定义 |
| 模型 | 如 `deepseek-v4-flash`、`google/gemini-2.0-flash` |
| API 密钥 | 从对应平台获取 |
| API 地址 | 自定义提供商的 API endpoint |
| 本地端口 | 默认 9120 |
| 主题 | 自动 / 深色 / 浅色 |

## SSH 命令

```bash
# 手动启动 API 服务
/etc/init.d/hermes-router-api start

# 查看状态
/etc/init.d/hermes-router-api status

# 查看日志
logread | grep hermes

# 手动测试 API
curl http://127.0.0.1:9120/api/health
```

## 更新

```bash
# 上传新版本
scp luci-app-hermes_*.ipk root@192.168.100.1:/tmp/

# 安装
ssh root@192.168.100.1 opkg install /tmp/luci-app-hermes_*.ipk --force-depends
```

## 卸载

```bash
ssh root@192.168.100.1
/etc/init.d/hermes-router-api stop
/etc/init.d/hermes-router-api disable
opkg remove luci-app-hermes
rm -rf /usr/libexec/hermes-router-api
```
