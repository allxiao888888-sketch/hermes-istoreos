<p align="center">
  <h1 align="center">luci-app-hermes</h1>
</p>

<p align="center">
  <b>把路由器变成 AI 助手 — 在浏览器里对话并直接操作系统</b><br>
  <sub>AI 聊天 · Function Calling · 联网搜索 · 软件包管理 · 服务控制 · 系统监控</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/OpenWrt-21.02%20%7C%2022.03%20%7C%20iStoreOS-blue?logo=openwrt" alt="OpenWrt">
  <img src="https://img.shields.io/badge/Version-2.2.0-brightgreen" alt="Version">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

---

## 这是什么？

**Hermes Agent** 是 iStoreOS 路由器上的 AI 助手插件。通过 LuCI Web 界面与 AI 对话，**直接操作路由器系统** — 安装软件、管理服务、执行命令、查看状态，不需要 SSH。

> **LuCI** 是 OpenWrt 路由器的 Web 管理界面框架。

## 操作指南

### 快速开始

1. 打开 `http://192.168.100.1:8080` → 服务 → **Hermes Agent**
2. 进入**设置**，填入 AI 提供商和 API Key（推荐 [OpenRouter](https://openrouter.ai/keys) 免费额度）
3. 返回 **AI 聊天**，开始对话

### AI 直接操作路由器

AI 支持 **Function Calling**，可以直接执行操作：

| 你说 | AI 做的事 |
|------|----------|
| "安装 nginx" | 调用 opkg 安装，返回结果 |
| "重启 dnsmasq" | 执行 `/etc/init.d/dnsmasq restart` |
| "查看 CPU 和内存" | 读取系统信息，组织成表格回复 |
| "启动 OpenClash" | 自动启用服务 + 启动，验证状态 |
| "查看运行的进程" | 执行 `ps` 命令并分析 Top 5 |

### 联网搜索

| 你说 | AI 做的事 |
|------|----------|
| "深圳天气怎么样" | 调用 wttr.in 获取实时天气 |
| "什么是 WireGuard" | 查 Wikipedia 百科摘要 |
| "Docker 安装教程" | DuckDuckGo 网页搜索 |

### 对话管理

- 内存使用 < 90%：完整保留对话历史
- 内存 ≥ 90%：自动清空历史，只保留最后一条

### 仪表盘

实时显示：API 状态、AI 连接、CPU/内存/磁盘/软件包/网络接口

### 路由器管理

| 标签 | 功能 |
|------|------|
| 软件包管理 | 搜索、安装、卸载、更新 opkg 包 |
| 服务管理 | 查看、启动、停止、重启 init.d 服务 |
| 系统信息 | 主机名、内核、CPU、内存、磁盘、负载 |
| 命令终端 | 直接在网页执行 Shell 命令 |

### 设置

| 配置项 | 说明 |
|--------|------|
| AI 提供商 | OpenRouter / OpenAI / DeepSeek / 自定义 |
| 模型 | 如 `deepseek-v4-flash`、`google/gemini-2.0-flash` |
| API 密钥 | 从对应平台获取 |
| API 地址 | 自定义 API endpoint |
| 本地端口 | 默认 9120 |
| 主题 | 自动 / 深色 / 浅色 |

### SSH 常用命令

```bash
/etc/init.d/hermes-router-api start    # 启动服务
/etc/init.d/hermes-router-api status   # 查看状态
logread | grep hermes                   # 查看日志
curl http://127.0.0.1:9120/api/health  # 测试 API
```

## 功能

- **AI 聊天** — Function Calling 直接操作路由器
- **联网搜索** — wttr.in 天气 / Wikipedia / DuckDuckGo
- **软件包管理** — opkg 安装/卸载/更新，Web 界面操作
- **服务管理** — 启停系统服务，自动检查运行状态
- **系统监控** — CPU、内存、磁盘、网络实时信息
- **命令终端** — Web 界面执行 Shell 命令
- **毛玻璃 UI** — backdrop-filter 半透明效果
- **智能对话管理** — 基于内存自动裁剪历史
- **开机自启** — init.d 服务，路由器启动自动运行

## 系统要求

| | 说明 |
|---|---|
| **路由器系统** | OpenWrt 21.02+ 或 iStoreOS |
| **Python** | python3 + python3-light + curl |
| **架构** | 不限（纯 Python + Lua） |
| **内存** | ≥ 256MB（推荐 512MB+） |
| **存储** | ≥ 64MB 空闲 |
| **网络** | 路由器能访问 LLM API |

## 安装

### 前置：安装依赖

```bash
opkg update
opkg install python3 python3-light curl luci-lib-jsonc
```

### 方式一：iStore 商店手动安装

iStore → 右上角「手动安装」→ 上传 `.ipk` → 安装

### 方式二：命令行

```bash
scp luci-app-hermes_2.2.0_all.ipk root@192.168.100.1:/tmp/
ssh root@192.168.100.1 opkg install /tmp/luci-app-hermes_2.2.0_all.ipk --force-depends
```

安装后访问：`http://<路由器IP>/cgi-bin/luci/admin/services/hermes`

### 升级

```bash
ssh root@192.168.100.1 opkg install /tmp/luci-app-hermes_2.2.0_all.ipk --force-depends
```

### 卸载

```bash
ssh root@192.168.100.1
/etc/init.d/hermes-router-api stop
/etc/init.d/hermes-router-api disable
opkg remove luci-app-hermes
rm -rf /usr/libexec/hermes-router-api
```

## AI 配置

| 提供商 | 免费额度 | 获取方式 |
|--------|:---:|------|
| **OpenRouter** | ✅ | [openrouter.ai/keys](https://openrouter.ai/keys) |
| **DeepSeek** | ✅ | [platform.deepseek.com](https://platform.deepseek.com) |
| **OpenAI** | ❌ | [platform.openai.com](https://platform.openai.com) |
| **自定义** | — | 任意 OpenAI 兼容 API |

配置步骤：服务 → Hermes Agent → 设置 → 选择提供商 → 填入 API Key → 保存

## 常见问题

| 问题 | 解答 |
|---|---|
| AI 回复"API 错误"？ | API Key 未配置或无效，进入设置检查 |
| 仪表盘显示"未连接"？ | `/etc/init.d/hermes-router-api start` |
| 软件包列表空白？ | 点击"更新列表"，或 `opkg update` |
| AI 说"启动成功"但没启动？ | 部分服务需先启用（如 OpenClash），AI 现已自动处理 |
| 如何查看日志？ | `logread \| grep hermes` |

## API 端点

所有请求通过 LuCI 代理转发到本地 `127.0.0.1:9120`。

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/status` | GET | 系统状态 |
| `/api/chat` | POST | AI 聊天 (Function Calling) |
| `/api/router/info` | GET | 路由器系统信息 |
| `/api/router/packages` | GET | 软件包列表 |
| `/api/router/services` | GET | 服务列表 |
| `/api/router/network` | GET | 网络状态 |
| `/api/exec` | POST | 执行命令 |
| `/api/config` | GET/POST | 获取/更新配置 |

## 项目结构

```
├── luci-app-hermes/              # LuCI 插件
│   ├── luasrc/                   # Lua 源码 (controller/model/view)
│   ├── htdocs/                   # 前端 JS/CSS
│   ├── root/                     # 路由器文件系统
│   │   ├── etc/config/hermes     # UCI 配置
│   │   ├── etc/init.d/           # init.d 服务脚本
│   │   └── usr/libexec/          # Python API 服务器
│   ├── po/zh-cn/                 # 中文翻译
│   └── Makefile                  # OpenWrt SDK 构建
├── istore/                       # iStoreOS 商店元数据
├── scripts/                      # 构建脚本
├── INSTALL.md                    # 安装指南
├── OPERATION.md                  # 操作指南
└── README.md                     # 本文件
```

## 构建

```bash
# 构建 .ipk
python3 scripts/build-ipk.py
```

输出在 `dist/` 目录。

## 开源协议

MIT License

---

<p align="center">
  Made for the OpenWrt/iStoreOS community
</p>
