#!/bin/bash
# =============================================================================
# Hermes Agent for iStoreOS v2.0 — 构建脚本
# 路由器本地运行版 — 无需 macOS 外部服务器
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HERMES_ROUTER_API_DIR="$SCRIPT_DIR/hermes-router-api"
LUCI_APP_DIR="$SCRIPT_DIR/luci-app-hermes"
DIST_DIR="$SCRIPT_DIR/dist"

echo "========================================"
echo " Hermes Agent for iStoreOS v2.0 构建"
echo " 路由器本地运行版"
echo "========================================"
echo ""

# =============================================================================
# 1. 验证
# =============================================================================
echo "[1/3] 验证文件结构..."

# 检查所有必需文件
REQUIRED_FILES=(
    "$HERMES_ROUTER_API_DIR/server.py"
    "$LUCI_APP_DIR/Makefile"
    "$LUCI_APP_DIR/store.json"
    "$LUCI_APP_DIR/root/usr/lib/lua/luci/controller/hermes.lua"
    "$LUCI_APP_DIR/root/usr/lib/lua/luci/model/cbi/hermes.lua"
    "$LUCI_APP_DIR/root/usr/lib/lua/luci/view/hermes/dashboard.htm"
    "$LUCI_APP_DIR/root/usr/lib/lua/luci/view/hermes/chat.htm"
    "$LUCI_APP_DIR/root/usr/lib/lua/luci/view/hermes/control.htm"
    "$LUCI_APP_DIR/root/usr/lib/lua/luci/view/hermes/about.htm"
    "$LUCI_APP_DIR/root/etc/config/hermes"
    "$LUCI_APP_DIR/root/etc/init.d/hermes-router-api"
    "$LUCI_APP_DIR/htdocs/luci-static/resources/hermes/hermes.js"
    "$LUCI_APP_DIR/htdocs/luci-static/resources/hermes/chat.js"
    "$LUCI_APP_DIR/htdocs/luci-static/resources/hermes/control.js"
    "$LUCI_APP_DIR/htdocs/luci-static/resources/hermes/style.css"
)

MISSING=0
for f in "${REQUIRED_FILES[@]}"; do
    if [ -f "$f" ]; then
        echo "  ✓ $(basename "$(dirname "$f")")/$(basename "$f")"
    else
        echo "  ✗ 缺少: $f"
        MISSING=$((MISSING + 1))
    fi
done

if [ $MISSING -gt 0 ]; then
    echo ""
    echo "错误: 缺少 $MISSING 个文件，构建终止"
    exit 1
fi

echo "  ✓ 所有文件存在"

# =============================================================================
# 2. 构建 iStoreOS 插件
# =============================================================================
echo ""
echo "[2/3] 构建 iStoreOS 插件..."

# 准备构建目录
BUILD_DIR="$DIST_DIR/hermes-build"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# ---- 复制 LuCI 插件文件 ----
echo "  复制 LuCI 插件文件..."

# 控制器
mkdir -p "$BUILD_DIR/root/usr/lib/lua/luci/controller"
cp "$LUCI_APP_DIR/root/usr/lib/lua/luci/controller/hermes.lua" "$BUILD_DIR/root/usr/lib/lua/luci/controller/"

# CBI 模型
mkdir -p "$BUILD_DIR/root/usr/lib/lua/luci/model/cbi"
cp "$LUCI_APP_DIR/root/usr/lib/lua/luci/model/cbi/hermes.lua" "$BUILD_DIR/root/usr/lib/lua/luci/model/cbi/"

# 视图
mkdir -p "$BUILD_DIR/root/usr/lib/lua/luci/view/hermes"
cp "$LUCI_APP_DIR/root/usr/lib/lua/luci/view/hermes/"*.htm "$BUILD_DIR/root/usr/lib/lua/luci/view/hermes/"

# 前端资源
mkdir -p "$BUILD_DIR/www/luci-static/resources/hermes"
cp "$LUCI_APP_DIR/htdocs/luci-static/resources/hermes/"*.js "$BUILD_DIR/www/luci-static/resources/hermes/"
cp "$LUCI_APP_DIR/htdocs/luci-static/resources/hermes/style.css" "$BUILD_DIR/www/luci-static/resources/hermes/"

# 配置文件
mkdir -p "$BUILD_DIR/root/etc/config"
cp "$LUCI_APP_DIR/root/etc/config/hermes" "$BUILD_DIR/root/etc/config/"

# init.d 服务
mkdir -p "$BUILD_DIR/root/etc/init.d"
cp "$LUCI_APP_DIR/root/etc/init.d/hermes-router-api" "$BUILD_DIR/root/etc/init.d/"
chmod +x "$BUILD_DIR/root/etc/init.d/hermes-router-api"

# Python API 服务器
mkdir -p "$BUILD_DIR/root/usr/libexec/hermes-router-api"
cp "$HERMES_ROUTER_API_DIR/server.py" "$BUILD_DIR/root/usr/libexec/hermes-router-api/"

echo "  ✓ 构建目录准备完毕: $BUILD_DIR"

# =============================================================================
# 3. 生成安装包
# =============================================================================
echo ""
echo "[3/3] 生成安装包..."

mkdir -p "$DIST_DIR"

# 生成离线安装 tar.gz
cd "$BUILD_DIR"
tar czf "$DIST_DIR/luci-app-hermes.tar.gz" .
echo "  ✓ 离线安装包: $DIST_DIR/luci-app-hermes.tar.gz"

# 生成完整源码包
cd "$SCRIPT_DIR"
tar czf "$DIST_DIR/hermes-istoreos-full-src.tar.gz" \
    --exclude="dist" \
    --exclude="venv" \
    --exclude="*.pyc" \
    --exclude="__pycache__" \
    --exclude=".DS_Store" \
    .
echo "  ✓ 完整源码包: $DIST_DIR/hermes-istoreos-full-src.tar.gz"

echo ""
echo "========================================"
echo " 构建成功！"
echo "========================================"
echo ""
echo "=== 安装在 iStoreOS 上 ==="
echo ""
echo "方法 1: iStoreOS 商店手动安装"
echo "  上传 dist/luci-app-hermes.tar.gz"
echo ""
echo "方法 2: SSH 手动安装"
echo "  scp dist/luci-app-hermes.tar.gz root@192.168.1.1:/tmp/"
echo "  ssh root@192.168.1.1"
echo "  cd /tmp && tar xzf luci-app-hermes.tar.gz"
echo "  cp -r root/* /"
echo "  cp -r www/* /www/"
echo "  /etc/init.d/uhttpd restart"
echo ""
echo "=== 安装后配置 ==="
echo ""
echo "1. 安装 Python3 (首次需要):"
echo "   opkg update && opkg install python3"
echo ""
echo "2. 启动 Hermes API 服务:"
echo "   /etc/init.d/hermes-router-api enable"
echo "   /etc/init.d/hermes-router-api start"
echo ""
echo "3. 在 iStoreOS 中进入: 服务 > Hermes Agent > 设置"
echo "   填写 LLM API 密钥 (推荐免费使用 OpenRouter)"
echo "   开始使用 AI 聊天和路由器管理！"
echo ""
