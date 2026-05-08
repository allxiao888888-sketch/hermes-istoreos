# Hermes Agent for iStoreOS 安装指南

## 前置要求

- iStoreOS 路由器（OpenWrt 21.02+），本指南以 **GL-MT3000** 为例
- 已安装 `python3`：`opkg update && opkg install python3 python3-light`
- 一个 LLM API 密钥（推荐 [OpenRouter](https://openrouter.ai/keys)，免费额度可用）

## 安装步骤

### 1. 上传 .ipk 到路由器

```bash
# SCP 上传（替换为你的路由器 IP）
scp dist/luci-app-hermes_2.0.0_all.ipk root@192.168.100.1:/tmp/

# 密码：路由器管理员密码
```

### 2. SSH 安装

```bash
ssh root@192.168.100.1

# 安装
opkg install /tmp/luci-app-hermes_2.0.0_all.ipk

# 如果提示依赖缺失，先安装：
# opkg update && opkg install python3 python3-light luci-lib-jsonc
```

### 3. 启动 API 服务

```bash
# 方法 A：使用 init.d 服务（推荐，开机自启）
/etc/init.d/hermes-router-api enable
/etc/init.d/hermes-router-api start

# 方法 B：直接启动（仅当前会话）
python3 /usr/libexec/hermes-router-api/server.py --port 9120 --host 127.0.0.1 &
```

### 4. 配置 AI 提供商

1. 打开 iStoreOS 管理界面：`http://192.168.100.1:8080`
2. 进入：**服务** → **Hermes Agent** → **设置**
3. 填写参数：

| 设置项 | 推荐值 | 说明 |
|--------|--------|------|
| AI 提供商 | OpenRouter | 免费可用 |
| 模型 | `google/gemini-2.0-flash-lite-preview-02-05` | 轻量快速 |
| API 密钥 | `sk-or-v1-...` | 从 openrouter.ai/keys 获取 |
| 本地端口 | `9120` | 保持默认 |
| 主题 | 自动 | 跟随系统深色/浅色 |

4. 点击 **保存并应用**

### 5. 测试连接

进入 **设置** 页面，点击 **测试连接** 按钮：
- ✓ 本地 Hermes API 服务器运行正常
- ✓ AI 提供商连接成功

## 功能说明

| 功能 | 说明 |
|------|------|
| **仪表盘** | 路由器 CPU/内存/磁盘/网络状态概览 |
| **AI 聊天** | 通过 LLM API 对话，管理路由器 |
| **路由器管理** | 软件包管理 + 服务管理 + 系统信息 + 命令终端 |
| **设置** | 配置 AI 提供商、端口、主题 |

## 升级

```bash
# SCP 上传新版本 .ipk
scp luci-app-hermes_2.0.0_all.ipk root@192.168.100.1:/tmp/

# 强制重装
ssh root@192.168.100.1 "opkg install --force-reinstall /tmp/luci-app-hermes_2.0.0_all.ipk"
```

## 卸载

```bash
ssh root@192.168.100.1

# 停止并禁用服务
/etc/init.d/hermes-router-api stop
/etc/init.d/hermes-router-api disable

# 卸载包
opkg remove luci-app-hermes

# 清理残留
rm -rf /usr/libexec/hermes-router-api
```

## 故障排除

### API 服务器未运行

```bash
# 检查状态
/etc/init.d/hermes-router-api status

# 查看日志
logread | grep hermes-router-api

# 手动测试
python3 /usr/libexec/hermes-router-api/server.py --port 9120
```

### AI 聊天无响应

1. 确认 API 密钥已填写（服务 → Hermes Agent → 设置）
2. 确认路由器能访问外网：`ping openrouter.ai`
3. 确认端口监听：`netstat -an | grep 9120`

### 页面不显示

```bash
# 重启 uhttpd 刷新 LuCI
/etc/init.d/uhttpd restart

# 清除浏览器缓存后重新打开
```

### 依赖问题

```bash
opkg update
opkg install python3 python3-light luci-lib-jsonc
```
