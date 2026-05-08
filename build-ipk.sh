#!/bin/bash
# =============================================================================
# Hermes Agent for iStoreOS — .ipk 包构建脚本
# 生成可直接在 iStoreOS 中安装的 .ipk 文件
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HERMES_ROUTER_API_DIR="$SCRIPT_DIR/hermes-router-api"
LUCI_APP_DIR="$SCRIPT_DIR/luci-app-hermes"
DIST_DIR="$SCRIPT_DIR/dist"
PKG_NAME="luci-app-hermes"
PKG_VERSION="2.0.0"
PKG_ARCH="all"

echo "=========================================="
echo " Hermes Agent for iStoreOS — .ipk 构建"
echo "=========================================="
echo ""

# =============================================================================
# 1. 准备构建目录
# =============================================================================
echo "[1/5] 准备构建目录..."

BUILD_DIR="/tmp/hermes-ipk-build"
IPK_DIR="$BUILD_DIR/ipk"
CONTROL_DIR="$BUILD_DIR/control"
DATA_DIR="$BUILD_DIR/data"

rm -rf "$BUILD_DIR"
mkdir -p "$CONTROL_DIR"
mkdir -p "$DATA_DIR"

# =============================================================================
# 2. 准备数据文件 (data.tar.gz)
# =============================================================================
echo "[2/5] 准备数据文件..."

# LuCI 控制器
mkdir -p "$DATA_DIR/usr/lib/lua/luci/controller"
cp "$LUCI_APP_DIR/root/usr/lib/lua/luci/controller/hermes.lua" \
   "$DATA_DIR/usr/lib/lua/luci/controller/hermes.lua"

# CBI 模型
mkdir -p "$DATA_DIR/usr/lib/lua/luci/model/cbi"
cp "$LUCI_APP_DIR/root/usr/lib/lua/luci/model/cbi/hermes.lua" \
   "$DATA_DIR/usr/lib/lua/luci/model/cbi/hermes.lua"

# 视图
mkdir -p "$DATA_DIR/usr/lib/lua/luci/view/hermes"
cp "$LUCI_APP_DIR/root/usr/lib/lua/luci/view/hermes/"*.htm \
   "$DATA_DIR/usr/lib/lua/luci/view/hermes/"

# 前端资源 (LuCI 插件用 www/ 路径兼容 OpenWrt)
mkdir -p "$DATA_DIR/www/luci-static/resources/hermes"
cp "$LUCI_APP_DIR/htdocs/luci-static/resources/hermes/"*.js \
   "$DATA_DIR/www/luci-static/resources/hermes/"
cp "$LUCI_APP_DIR/htdocs/luci-static/resources/hermes/style.css" \
   "$DATA_DIR/www/luci-static/resources/hermes/"

# 配置文件
mkdir -p "$DATA_DIR/etc/config"
cp "$LUCI_APP_DIR/root/etc/config/hermes" \
   "$DATA_DIR/etc/config/hermes"

# init.d 服务脚本
mkdir -p "$DATA_DIR/etc/init.d"
cp "$LUCI_APP_DIR/root/etc/init.d/hermes-router-api" \
   "$DATA_DIR/etc/init.d/hermes-router-api"
chmod 755 "$DATA_DIR/etc/init.d/hermes-router-api"

# Python API 服务器
mkdir -p "$DATA_DIR/usr/libexec/hermes-router-api"
cp "$HERMES_ROUTER_API_DIR/server.py" \
   "$DATA_DIR/usr/libexec/hermes-router-api/server.py"

echo "  ✓ 数据文件准备完毕"

# =============================================================================
# 3. 准备控制文件 (control.tar.gz)
# =============================================================================
echo "[3/5] 准备控制文件..."

# control 文件
cat > "$CONTROL_DIR/control" << 'CTRL'
Package: luci-app-hermes
Version: 2.0.0
Depends: python3, python3-light
Provides: luci-app-hermes
Source: https://github.com/allxiao888888-sketch/hermes-istoreos
License: GPL-2.0
Section: luci
Architecture: all
Maintainer: OpenClaw Hermes
Priority: optional
Description: Hermes Agent - AI assistant + router management for iStoreOS
 AI assistant running directly on iStoreOS router. Chat with AI via LLM API,
 manage packages (opkg), services, and system configuration from the router
 web interface. No external server required.
 .
 Features:
  - AI Chat (OpenRouter/OpenAI/DeepSeek)
  - Package management (opkg install/remove/update)
  - Service management (start/stop/restart)
  - System info (CPU, memory, disk, network)
  - Command terminal (Shell execution)
  - Auto-start service (init.d)
CTRL

# conffiles — 标记配置文件，升级时保留用户修改
cat > "$CONTROL_DIR/conffiles" << 'CONF'
/etc/config/hermes
CONF

# postinst — 安装后脚本
cat > "$CONTROL_DIR/postinst" << 'POSTINST'
#!/bin/sh
set -e

# 重启 uhttpd 以加载新 LuCI 模块
/etc/init.d/uhttpd restart 2>/dev/null || true

# 启用并启动 Hermes API 服务
if [ -f /etc/init.d/hermes-router-api ]; then
    /etc/init.d/hermes-router-api enable 2>/dev/null || true
    /etc/init.d/hermes-router-api start 2>/dev/null || true
fi

# 清理 Python 缓存
rm -rf /usr/libexec/hermes-router-api/__pycache__ 2>/dev/null || true

exit 0
POSTINST
chmod 755 "$CONTROL_DIR/postinst"

# prerm — 卸载前脚本
cat > "$CONTROL_DIR/prerm" << 'PRERM'
#!/bin/sh
set -e

# 停止并禁用服务
if [ -f /etc/init.d/hermes-router-api ]; then
    /etc/init.d/hermes-router-api stop 2>/dev/null || true
    /etc/init.d/hermes-router-api disable 2>/dev/null || true
fi

exit 0
PRERM
chmod 755 "$CONTROL_DIR/prerm"

echo "  ✓ 控制文件准备完毕"

# =============================================================================
# 4. 打包
# =============================================================================
echo "[4/5] 打包 .ipk..."

# 创建 data.tar.gz
cd "$DATA_DIR"
tar czf "$BUILD_DIR/data.tar.gz" .

# 创建 control.tar.gz
cd "$CONTROL_DIR"
tar czf "$BUILD_DIR/control.tar.gz" .

# 创建 debian-binary
echo "2.0" > "$BUILD_DIR/debian-binary"

# 创建 ipk 目录
mkdir -p "$IPK_DIR"

# 用 ar 打包成 .ipk
cd "$BUILD_DIR"
IPK_FILE="$IPK_DIR/${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}.ipk"
ar rc "$IPK_FILE" debian-binary control.tar.gz data.tar.gz

echo "  ✓ .ipk 生成完毕"

# =============================================================================
# 5. 复制到 dist 目录
# =============================================================================
echo "[5/5] 复制到 dist/..."

mkdir -p "$DIST_DIR"
cp "$IPK_FILE" "$DIST_DIR/"
echo "  ✓ 已复制到 dist/"

# 计算文件大小和 MD5
FILESIZE=$(du -h "$DIST_DIR/${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}.ipk" | cut -f1)
MD5SUM=$(md5 -q "$DIST_DIR/${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}.ipk")

# 清理临时文件
rm -rf "$BUILD_DIR"

echo ""
echo "=========================================="
echo " ✅ 构建成功！"
echo "=========================================="
echo ""
echo "📦 安装包: dist/${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}.ipk"
echo "   大小: $FILESIZE"
echo "   MD5: $MD5SUM"
echo ""
echo "=== iStoreOS 安装方法 ==="
echo ""
echo "📱 方法 1: iStoreOS 商店 → 手动安装"
echo "   打开 iStoreOS Web 界面"
echo "   进入 「iStore 商店」"
echo "   点击右上角「手动安装」"
echo "   选择 dist/${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}.ipk"
echo "   上传后自动安装"
echo ""
echo "💻 方法 2: SSH 命令行安装"
echo "   1. 上传到路由器:"
echo "      scp dist/${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}.ipk root@192.168.1.1:/tmp/"
echo ""
echo "   2. SSH 安装:"
echo "      ssh root@192.168.1.1"
echo "      opkg install /tmp/${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}.ipk"
echo ""
echo "=== 首次配置 ==="
echo ""
echo "   1. 进入: 服务 > Hermes Agent > 设置"
echo "   2. 填写 LLM API 密钥"
echo "   3. 选择 AI 提供商和模型"
echo "   4. 开始使用！"
echo ""
