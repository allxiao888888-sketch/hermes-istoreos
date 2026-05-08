# Changelog

All notable changes to `luci-app-hermes` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.0] - 2026-05-07

### Added
- **全新架构：全路由器本地运行** — 所有组件直接运行在 iStoreOS 路由器上，无需外部服务器
- **Hermes Router API** — 纯 Python 标准库实现的 HTTP API 服务器，零外部依赖
- **AI 聊天** — 支持 OpenRouter（推荐免费）、OpenAI、DeepSeek 及自定义 OpenAI 兼容 API
- **软件包管理** — opkg 安装/卸载/更新/搜索，Web 界面直接操作
- **服务管理** — 启动/停止/重启系统服务（/etc/init.d/）
- **系统信息** — CPU、内存、磁盘、运行时间、网络接口状态
- **命令终端** — Web 界面直接执行 Shell 命令
- **开机自启** — init.d 服务脚本，路由器启动自动运行
- **仪表盘** — 系统状态概览，自动刷新
- **深色主题** — 适配 iStoreOS 深色/浅色主题
- **API 认证** — 可选本地 API 密钥保护
- **.ipk 包构建** — 支持 opkg 标准安装格式

### Changed
- 完全重构架构，移除对 macOS 外部服务器的依赖
- 改为 MIT 许可证

### Removed
- 对 macOS 外部服务器的依赖
- Flask/Python 第三方依赖，改为纯标准库

---

## [1.0.0] - 2026-05-01

### Added
- 初始版本
- LuCI Web 界面
- 基础 API 代理
