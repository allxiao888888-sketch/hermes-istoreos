# 🦞 Hermes Agent for iStoreOS v2.0

> **全新架构：所有组件直接运行在 iStoreOS 路由器上 **

## 📖 图形操作指南

> 浏览器直接打开以下 HTML 文件即可查看完整的图形化操作指南（含界面截图和操作流程）：
>
> 👉 **[`hermes-istoreos-operation-guide.html`](./hermes-istoreos-operation-guide.html)** — 双击打开，无需任何服务器

将 AI 能力直接集成到你的 iStoreOS 路由器中。通过 LLM API（OpenRouter/OpenAI/DeepSeek）实现智能对话，并直接控制路由器的软件包、服务和系统配置。

## 系统架构

```
┌─────────────────────────────────────────────────┐
│               iStoreOS 路由器                      │
│                                                  │
│  ┌─────────────────────────────────────────┐    │
│  │  LuCI Web UI (浏览器)                    │    │
│  │    ├── 仪表盘 (路由器状态)               │    │
│  │    ├── AI 聊天 ──────┐                  │    │
│  │    ├── 路由器管理     │                  │    │
│  │    └── 设置          │                  │    │
│  └─────────────────────│──────────────────┘    │
│                        │ HTTP (127.0.0.1)       │
│  ┌─────────────────────▼──────────────────┐    │
│  │  Hermes Router API (Python stdlib)     │    │
│  │  零外部依赖，纯 Python 标准库            │    │
│  │                                        │    │
│  │  /api/status        ── 系统状态         │    │
│  │  /api/chat          ── LLM API 聊天     │    │
│  │  /api/router/packages ── opkg 包管理    │    │
│  │  /api/router/services  ── 服务管理      │    │
│  │  /api/router/info   ── 系统信息         │    │
│  │  /api/router/network  ── 网络状态       │    │
│  │  /api/exec          ── Shell 命令       │    │
│  └─────────────────────┬──────────────────┘    │
│                        │                       │
│  ┌─────────────────────▼──────────────────┐    │
│  │  路由器系统                              │    │
│  │    ├── opkg 包管理器                    │    │
│  │    ├── /etc/init.d/ 服务系统             │    │
│  │    ├── uci / sysctl / ip 等系统工具      │    │
│  │    └── CPU / 内存 / 磁盘 / 网络          │    │
│  └─────────────────────────────────────────┘    │
│                                                  │
│  ┌─────────────────────────────────────────┐    │
│  │  🤖 LLM API (外部)                       │    │
│  │  OpenRouter / OpenAI / DeepSeek / 自定义  │    │
│  └─────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
```

## 功能特性

| 功能 | 说明 |
|------|------|
| 🤖 **AI 聊天** | 通过 LLM API 智能对话，支持路由器控制 |
| 📦 **软件包管理** | opkg 安装/卸载/更新/搜索 |
| ⚙️ **服务管理** | 启动/停止/重启系统服务 |
| 🖥️ **系统信息** | CPU、内存、磁盘、运行时间 |
| 🌐 **网络状态** | 接口信息、MAC 地址、IP 地址 |
| 💻 **命令终端** | Web 界面直接执行 Shell 命令 |
| 🔄 **自动刷新** | 仪表盘数据自动更新 |
| 🌙 **深色主题** | 适配 iStoreOS 深色/浅色主题 |
| 🔐 **API 认证** | 可选本地 API 密钥保护 |

## 安装指南

### 前置要求

- iStoreOS 路由器（OpenWRT 21.02+）
- 已安装 Python3

### 方法 1: iStoreOS 商店

1. 进入 iStoreOS Web 管理界面
2. 打开 **iStore 商店**
3. 点击右上角 **「手动安装」**
4. 上传 `dist/luci-app-hermes.tar.gz`
5. 安装后刷新页面，在 **「服务」** 菜单中找到 **「Hermes Agent」**

### 方法 2: SSH 手动安装

```bash
# 1. 复制安装包到路由器
scp dist/luci-app-hermes.tar.gz root@192.168.1.1:/tmp/

# 2. SSH 到路由器
ssh root@192.168.1.1

# 3. 安装插件
cd /tmp
tar xzf luci-app-hermes.tar.gz
cp -r root/* /
cp -r www/* /www/
/etc/init.d/uhttpd restart
```

### 首次配置

```bash
# 1. 安装 Python3（如果尚未安装）
opkg update && opkg install python3

# 2. 启动 Hermes API 服务
/etc/init.d/hermes-router-api enable
/etc/init.d/hermes-router-api start
```

3. 进入 iStoreOS: **服务 > Hermes Agent > 设置**
4. 填写 **LLM API 密钥**（推荐免费使用 OpenRouter）
5. 选择 AI 提供商和模型
6. 开始使用！

## 项目结构

```
hermes-istoreos-plugin/
├── hermes-router-api/                   # 路由器端 API 服务器
│   └── server.py                        # Zero-dependency Python HTTP 服务器
│
├── luci-app-hermes/                     # iStoreOS LuCI 插件
│   ├── Makefile                         # OpenWRT SDK 构建文件
│   ├── store.json                       # iStoreOS 商店元数据
│   └── root/
│       ├── etc/config/hermes            # 默认配置
│       ├── etc/init.d/hermes-router-api # 开机自启脚本
│       └── usr/lib/lua/luci/
│           ├── controller/hermes.lua    # 路由控制器
│           ├── model/cbi/hermes.lua     # 配置表单模型
│           └── view/hermes/
│               ├── dashboard.htm        # 仪表盘
│               ├── chat.htm             # AI 聊天
│               ├── control.htm          # 路由器管理
│               └── about.htm            # 关于
│   └── htdocs/luci-static/resources/hermes/
│       ├── hermes.js                    # API 客户端 + 仪表盘 JS
│       ├── chat.js                      # 聊天 JS
│       ├── control.js                   # 路由器管理 JS
│       └── style.css                    # 样式
│
├── build.sh                             # 构建脚本
└── README.md                            # 本文件
```

## API 端点

所有 API 通过 LuCI Lua 代理转发到本地 Python 服务（127.0.0.1:9120）。

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/status` | GET | API 系统状态 |
| `/api/config` | GET/POST | 获取/更新配置 |
| `/api/chat` | POST | AI 聊天 |
| `/api/router/info` | GET | 路由器系统信息 |
| `/api/router/packages` | GET | 软件包列表 |
| `/api/router/packages/install` | POST | 安装软件包 |
| `/api/router/packages/remove` | POST | 卸载软件包 |
| `/api/router/packages/update` | POST | 更新软件包列表 |
| `/api/router/services` | GET | 服务列表 |
| `/api/router/services/:action/:name` | POST | 服务操作 |
| `/api/router/network` | GET | 网络状态 |
| `/api/exec` | POST | 执行命令 |

## 支持的 LLM 提供商

- **OpenRouter**（推荐）— 免费模型可用
- **OpenAI** — GPT-4o / GPT-4o-mini
- **DeepSeek** — DeepSeek V3 / R1
- **自定义** — 兼容 OpenAI API 的任何服务

## 开发

### 构建安装包

```bash
chmod +x build.sh
./build.sh
```

输出在 `dist/` 目录：
- `luci-app-hermes.tar.gz` — iStoreOS 离线安装包
- `hermes-istoreos-full-src.tar.gz` — 完整源码包

### 在 OpenWRT SDK 中编译

```bash
# 将 luci-app-hermes 放入 SDK 的 package/ 目录
# 启用 LuCI 后执行
make package/luci-app-hermes/compile V=s
```

## 从 v1.x 升级


**升级步骤:**
1. 卸载旧版插件
2. 安装新版
3. 配置 LLM API 密钥（首次）

## 许可证

GNU General Public License v2
