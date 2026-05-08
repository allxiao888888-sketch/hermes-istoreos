#!/usr/bin/env python3
"""
Hermes Agent for iStoreOS — .ipk 包构建器
使用 Python 生成标准 SVR4 ar 格式的 .ipk 文件
兼容 OpenWrt / iStoreOS 的 opkg 包管理器
"""

import hashlib
import os
import shutil
import struct
import tarfile
import io
import textwrap

# =============================================================================
# 配置
# =============================================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HERMES_ROUTER_API_DIR = os.path.join(SCRIPT_DIR, "hermes-router-api")
LUCI_APP_DIR = os.path.join(SCRIPT_DIR, "luci-app-hermes")
DIST_DIR = os.path.join(SCRIPT_DIR, "dist")

PKG_NAME = "luci-app-hermes"
PKG_VERSION = "2.0.0"
PKG_ARCH = "all"


def create_data_tar_gz() -> bytes:
    """创建 data.tar.gz — 所有要安装的文件"""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        # LuCI 控制器
        tar.add(
            os.path.join(LUCI_APP_DIR, "root/usr/lib/lua/luci/controller/hermes.lua"),
            arcname="usr/lib/lua/luci/controller/hermes.lua",
        )
        # CBI 模型
        tar.add(
            os.path.join(LUCI_APP_DIR, "root/usr/lib/lua/luci/model/cbi/hermes.lua"),
            arcname="usr/lib/lua/luci/model/cbi/hermes.lua",
        )
        # 视图
        views_dir = os.path.join(LUCI_APP_DIR, "root/usr/lib/lua/luci/view/hermes")
        for fname in os.listdir(views_dir):
            if fname.endswith(".htm"):
                tar.add(
                    os.path.join(views_dir, fname),
                    arcname=f"usr/lib/lua/luci/view/hermes/{fname}",
                )
        # 前端资源
        htdocs_dir = os.path.join(LUCI_APP_DIR, "htdocs/luci-static/resources/hermes")
        for fname in os.listdir(htdocs_dir):
            tar.add(
                os.path.join(htdocs_dir, fname),
                arcname=f"www/luci-static/resources/hermes/{fname}",
            )
        # 配置文件
        tar.add(
            os.path.join(LUCI_APP_DIR, "root/etc/config/hermes"),
            arcname="etc/config/hermes",
        )
        # init.d 服务脚本 (设置可执行权限)
        initd_src = os.path.join(LUCI_APP_DIR, "root/etc/init.d/hermes-router-api")
        initd_info = tar.gettarinfo(initd_src, arcname="etc/init.d/hermes-router-api")
        initd_info.mode = 0o755
        with open(initd_src, "rb") as f:
            tar.addfile(initd_info, f)
        # Python API 服务器
        tar.add(
            os.path.join(HERMES_ROUTER_API_DIR, "server.py"),
            arcname="usr/libexec/hermes-router-api/server.py",
        )
    return buf.getvalue()


def create_control_tar_gz(data_tar_gz_size: int) -> bytes:
    """创建 control.tar.gz — 包元数据和安装脚本"""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        # --- control 文件 ---
        control_content = textwrap.dedent(f"""\
            Package: {PKG_NAME}
            Version: {PKG_VERSION}
            Depends: python3, python3-light
            Provides: luci-app-hermes
            Source: https://github.com/allxiao888888-sketch/hermes-istoreos
            License: GPL-2.0
            Section: luci
            Architecture: {PKG_ARCH}
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
             Installed-Size: {data_tar_gz_size // 1024}
        """).encode("utf-8")
        ci = tarfile.TarInfo(name="control")
        ci.size = len(control_content)
        ci.mode = 0o644
        tar.addfile(ci, io.BytesIO(control_content))

        # --- conffiles ---
        conf_content = b"/etc/config/hermes\n"
        confi = tarfile.TarInfo(name="conffiles")
        confi.size = len(conf_content)
        confi.mode = 0o644
        tar.addfile(confi, io.BytesIO(conf_content))

        # --- postinst ---
        postinst_content = textwrap.dedent("""\
            #!/bin/sh
            set -e
            /etc/init.d/uhttpd restart 2>/dev/null || true
            if [ -f /etc/init.d/hermes-router-api ]; then
                /etc/init.d/hermes-router-api enable 2>/dev/null || true
                /etc/init.d/hermes-router-api start 2>/dev/null || true
            fi
            rm -rf /usr/libexec/hermes-router-api/__pycache__ 2>/dev/null || true
            exit 0
        """).encode("utf-8")
        pi = tarfile.TarInfo(name="postinst")
        pi.size = len(postinst_content)
        pi.mode = 0o755
        tar.addfile(pi, io.BytesIO(postinst_content))

        # --- prerm ---
        prerm_content = textwrap.dedent("""\
            #!/bin/sh
            set -e
            if [ -f /etc/init.d/hermes-router-api ]; then
                /etc/init.d/hermes-router-api stop 2>/dev/null || true
                /etc/init.d/hermes-router-api disable 2>/dev/null || true
            fi
            exit 0
        """).encode("utf-8")
        pri = tarfile.TarInfo(name="prerm")
        pri.size = len(prerm_content)
        pri.mode = 0o755
        tar.addfile(pri, io.BytesIO(prerm_content))

    return buf.getvalue()


def ar_write_entry(f, name: bytes, data: bytes):
    """
    写入一个 ar 归档条目 (SVR4/GNU 格式，兼容 OpenWrt opkg)

    ar 条目格式:
    - 文件名: 16 字节，空格右填充，以 '/' 结尾
    - 修改时间: 12 字节，十进制
    - 所有者 ID: 6 字节
    - 组 ID: 6 字节
    - 文件模式: 8 字节，八进制
    - 文件大小: 10 字节，十进制
    - 结束符: 0x60 0x0a
    - 文件数据: N 字节 (偶数对齐)
    """
    # 确保文件名是 16 字节
    if len(name) < 16:
        name = name.ljust(16)
    elif len(name) > 16:
        # 对于长文件名，使用 GNU 扩展: "/<N>" 形式
        name = name[:16]

    # SVR4/GNU ar 格式: 所有字段都是 ASCII 字符串，空格填充
    header = (
        name.ljust(16)[:16] +                      # 文件名 (16 bytes)
        b"0".ljust(12) +                           # 修改时间 (12 bytes)
        b"0".ljust(6) +                            # 所有者 (6 bytes)
        b"0".ljust(6) +                            # 组 (6 bytes)
        b"100644".ljust(8) +                       # 文件模式 (8 bytes)
        str(len(data)).encode().ljust(10) +        # 文件大小 (10 bytes)
        b"`\n"                                     # 结束符 (2 bytes)
    )
    f.write(header)
    f.write(data)
    # 偶数对齐
    if len(data) % 2 == 1:
        f.write(b"\n")


def build_ipk() -> str:
    """构建 .ipk 包并返回文件路径"""
    print("=" * 50)
    print(" Hermes Agent for iStoreOS — .ipk 构建")
    print("=" * 50)
    print()

    # [1] 创建数据 tar
    print("[1/5] 创建 data.tar.gz...")
    data_tar_gz = create_data_tar_gz()
    data_size = len(data_tar_gz)
    print(f"  ✓ data.tar.gz: {data_size} bytes")

    # [2] 创建控制 tar
    print("[2/5] 创建 control.tar.gz...")
    control_tar_gz = create_control_tar_gz(data_size)
    control_size = len(control_tar_gz)
    print(f"  ✓ control.tar.gz: {control_size} bytes")

    # [3] debian-binary
    print("[3/5] 创建 debian-binary...")
    debian_binary = b"2.0\n"
    print(f"  ✓ debian-binary: {len(debian_binary)} bytes")

    # [4] 打包为 .ipk (SVR4 ar 格式)
    print("[4/5] 打包 .ipk (SVR4 ar 格式)...")

    os.makedirs(DIST_DIR, exist_ok=True)
    ipk_filename = f"{PKG_NAME}_{PKG_VERSION}_{PKG_ARCH}.ipk"
    ipk_path = os.path.join(DIST_DIR, ipk_filename)

    with open(ipk_path, "wb") as f:
        # ar 全局头
        f.write(b"!<arch>\n")
        # 条目 1: debian-binary
        ar_write_entry(f, b"debian-binary", debian_binary)
        # 条目 2: control.tar.gz
        ar_write_entry(f, b"control.tar.gz", control_tar_gz)
        # 条目 3: data.tar.gz
        ar_write_entry(f, b"data.tar.gz", data_tar_gz)

    # [5] 验证
    print("[5/5] 验证 ipk 文件...")
    file_size = os.path.getsize(ipk_path)
    md5_hash = hashlib.md5(open(ipk_path, "rb").read()).hexdigest()
    print(f"  ✓ {ipk_filename}")
    print(f"    大小: {file_size} bytes ({file_size / 1024:.1f} KB)")
    print(f"    MD5: {md5_hash}")

    # 验证 ar 格式
    with open(ipk_path, "rb") as f:
        magic = f.read(8)
        assert magic == b"!<arch>\n", f"Invalid ar magic: {magic!r}"
        print("  ✓ ar 格式验证通过")

    print()
    print("=" * 50)
    print(" ✅ 构建成功！")
    print("=" * 50)
    print()
    print(f"📦 安装包: dist/{ipk_filename}")
    print()
    print("=== iStoreOS 安装方法 ===")
    print()
    print("📱 方法 1: iStoreOS 商店 → 手动安装")
    print("   打开 iStoreOS Web 界面")
    print('   进入 「iStore 商店」')
    print("   点击右上角「手动安装」")
    print(f"   选择 dist/{ipk_filename}")
    print("   上传后自动安装")
    print()
    print("💻 方法 2: SSH 命令行安装")
    print(f"   1. 上传到路由器:")
    print(f"      scp dist/{ipk_filename} root@192.168.1.1:/tmp/")
    print()
    print("   2. SSH 安装:")
    print("      ssh root@192.168.1.1")
    print(f"      opkg install /tmp/{ipk_filename}")
    print()
    print("=== 首次配置 ===")
    print()
    print("   1. 进入: 服务 > Hermes Agent > 设置")
    print("   2. 填写 LLM API 密钥")
    print("   3. 选择 AI 提供商和模型")
    print("   4. 开始使用！")
    print()

    return ipk_path


if __name__ == "__main__":
    build_ipk()
