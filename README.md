<p align="center">
  <h1 align="center">🦞 luci-app-hermes</h1>
</p>

<p align="center">
  <b>把你的路由器变成 AI 助手 — 在浏览器里管理 Hermes Agent</b><br>
  <sub>AI 聊天 · 软件包管理 · 服务控制 · 系统监控</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/OpenWrt-21.02%20%7C%2022.03%20%7C%20iStoreOS-blue?logo=openwrt" alt="OpenWrt">
  <img src="https://img.shields.io/badge/Version-2.0.0-brightgreen" alt="Version">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

<p align="center">
  🌐 <a href="https://raw.githack.com/allxiao888888-sketch/hermes-istoreos/main/docs/hermes-istoreos-operation-guide.html">图形操作指南</a>
</p>

---

## 这是什么？

**Hermes Agent** 是一个运行在 iStoreOS 路由器上的 AI 助手程序，它可以让你的路由器接入大语言模型（如 OpenRouter、OpenAI、DeepSeek 等），通过浏览器直接对话，并控制路由器的软件包、服务和系统配置。

**本项目给路由器加一个网页管理界面**（LuCI 插件），让你在浏览器里就能完成所有操作——AI 对话、安装软件包、管理服务、执行命令，不需要敲 SSH 命令行。

> **LuCI** 是 OpenWrt 路由器的 Web 管理界面框架，你平时进路由器后台（如 192.168.1.1）看到的就是 LuCI。

## 📸 截图

| 仪表盘 | AI 聊天 |
|:---:|:---:|
| ![仪表盘](Screenshots/dashboard.png) | ![AI聊天](Screenshots/chat.png) |

| 路由器管理 | 设置 |
|:---:|:---:|
| ![路由器管理](Screenshots/control.png) | ![设置](Screenshots/settings.png) |

> 💡 截图待补充 — 请将实际截图放入 `Screenshots/` 目录

## ✨ 功能

- 🤖 **AI 聊天** — 通过 LLM API 智能对话，支持路由器控制指令
- 📦 **软件包管理** — opkg 安装/卸载/更新/搜索，Web 界面直接操作
- ⚙️ **服务管理** — 一键启动/停止/重启系统服务
- 🖥️ **系统信息** — CPU、内存、磁盘、运行时间实时监控
- 🌐 **网络状态** — 接口信息、MAC 地址、IP 地址
- 💻 **命令终端** — Web 界面直接执行 Shell 命令
- 🔄 **自动刷新** — 仪表盘数据自动更新
- 🌙 **深色主题** — 适配 iStoreOS 深色/浅色主题
- 🔐 **API 认证** — 可选本地 API 密钥保护
- ⚡ **开机自启** — 路由器启动自动运行

## 📋 系统要求

| | 说明 |
|---|---|
| **路由器系统** | OpenWrt 21.02+ 或 iStoreOS（需有 LuCI 界面） |
| **Python** | 必须先安装 Python3 — `opkg update && opkg install python3` |
| **路由器架构** | 不限（纯 Python + Lua，所有架构通用：x86_64、aarch64、mipsel） |
| **内存** | ≥ 256MB（推荐 512MB+） |
| **存储** | ≥ 64MB 空闲空间 |
| **网络** | 路由器能访问 LLM API（OpenRouter 等） |

## 🚀 安装

### 前置：安装 Python3

通过 SSH 登录路由器：

```bash
opkg update
opkg install python3 python3-light
python3 --version  # 确认安装成功
```

### 方式一：iStore 商店（推荐，最简单）

在路由器后台打开 iStore → 点击右上角「手动安装」→ 上传 `.ipk` 文件 → 点击安装

> 最新 .ipk 安装包请到 [GitHub Releases](https://github.com/allxiao888888-sketch/hermes-istoreos/releases) 下载

### 方式二：命令行安装 IPK

```bash
cd /tmp
wget https://github.com/allxiao888888-sketch/hermes-istoreos/releases/latest/download/luci-app-hermes_2.0.0_all.ipk
opkg install luci-app-hermes_2.0.0_all.ipk
rm -rf /tmp/luci-*   # 清除 LuCI 缓存
```

### 方式三：手动安装

```bash
# 1. 复制安装包到路由器
scp dist/luci-app-hermes.tar.gz root@192.168.1.1:/tmp/

# 2. SSH 到路由器
ssh root@192.168.1.1
cd /tmp
tar xzf luci-app-hermes.tar.gz
cp -r root/* /
cp -r www/* /www/
/etc/init.d/uhttpd restart
```

安装完成后，打开浏览器访问：`http://<路由器IP>/cgi-bin/luci/admin/services/hermes`

## 🤖 AI 配置

Hermes Agent 需要接入大语言模型才能工作。它本身不包含 AI，而是调用各家 AI 服务的接口。你需要提供 **API Key**（类似密码）。

**配置步骤：**

1. 进入 iStoreOS: **服务 → Hermes Agent → 设置**
2. 选择 AI 提供商（推荐 OpenRouter，有免费模型）
3. 填入你的 **API Key**（在各 AI 供应商官网注册后获取）
4. 选择模型
5. 点击**保存**，然后点击**测试连接**

**支持供应商：**

| 提供商 | 免费额度 | 推荐模型 | 获取方式 |
|--------|:---:|------|---------|
| **OpenRouter** 🥇 | ✅ | `google/gemini-2.0-flash-lite` | [openrouter.ai/keys](https://openrouter.ai/keys) |
| **DeepSeek** | ✅ | `deepseek-chat` | [platform.deepseek.com](https://platform.deepseek.com) |
| **OpenAI** | ❌ | `gpt-4o-mini` | [platform.openai.com](https://platform.openai.com) |
| **自定义** | — | 任意 OpenAI 兼容 | 自定 API 地址 |

> 💡 **没有 API Key？** OpenRouter 注册即送免费额度，支持 Google/GitHub 账号直接登录。

> 🔒 API Key 存储在路由器本地配置文件中，不会上传到任何第三方服务器。

## ❓ 常见问题

| 问题 | 解答 |
|---|---|
| 安装后页面打不开？ | 需要先安装 Python3（`opkg install python3`），然后确保 API 服务运行中 |
| 仪表盘显示"未连接"？ | API 服务未启动，SSH 执行：`/etc/init.d/hermes-router-api start` |
| AI 回复"API 错误"？ | API Key 未配置或无效，进入设置检查并保存 |
| 软件包列表空白？ | 点击"更新列表"按钮，或 SSH 执行 `opkg update` |
| 服务操作无反应？ | 确认以 root 权限运行 |
| 如何查看日志？ | `logread \| grep hermes` 或 `/etc/init.d/hermes-router-api status` |
| 路由器架构怎么看？ | SSH 执行 `uname -m`，常见有 x86_64、aarch64、mipsel |

## 📦 项目结构

```
hermes-istoreos-plugin/
├── hermes-router-api/                   # 路由器端 API 服务器（纯 Python 标准库）
│   └── server.py                        # 零外部依赖 HTTP API 服务器
│
├── luci-app-hermes/                     # iStoreOS LuCI 插件
│   ├── Makefile                         # OpenWRT SDK 构建文件
│   └── root/                            # 路由器文件系统
│       ├── etc/config/hermes            # 默认配置
│       ├── etc/init.d/hermes-router-api # 开机自启脚本
│       └── usr/lib/lua/luci/            # LuCI 控制器/模型/视图
│   └── htdocs/luci-static/resources/hermes/  # 前端资源 (JS/CSS)
│
├── istore/                              # iStoreOS 商店集成
│   └── store.json                       # 商店元数据
│
├── scripts/                             # 构建脚本
│   ├── build.sh                         # 完整构建
│   ├── build-ipk.sh                     # .ipk 包构建
│   └── build-ipk.py                     # .ipk 包构建 (Python)
│
├── Images/                               # 图片资源
│   └── .gitkeep
├── Screenshots/                         # 截图（待补充）
├── docs/                                # 文档
│   ├── operation-guide.md               # 图形操作指南
│   └── hermes-istoreos-operation-guide.html  # 在线操作指南
├── release/                             # 发布目录
│   └── .gitkeep
├── CHANGELOG.md                         # 更新日志
├── LICENSE                              # MIT 许可证
└── README.md                            # 本文件
```

## 🔧 API 端点

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

## 🏗️ 开发

### 构建安装包

```bash
# 完整构建（tar.gz）
bash scripts/build.sh

# 构建 .ipk
bash scripts/build-ipk.sh
# 或 Python 版本
python3 scripts/build-ipk.py
```

输出在 `dist/` 目录（不在 Git 版本控制中）。

### 在 OpenWRT SDK 中编译

```bash
# 将 luci-app-hermes 放入 SDK 的 package/ 目录
# 启用 LuCI 后执行
make package/luci-app-hermes/compile V=s
```

## 更新日志

详见 [CHANGELOG.md](CHANGELOG.md)。

## 📜 开源协议

本项目遵循 **MIT License**，可自由使用、修改与分发，但请保留作者署名。

欢迎提交 Issue / Pull Request 一起完善项目 💡

---

<p align="center">
  Made with ❤️ for the OpenWrt/iStoreOS community
</p>
