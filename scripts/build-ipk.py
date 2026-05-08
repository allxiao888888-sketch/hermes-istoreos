#!/usr/bin/env python3
"""
Hermes Agent for iStoreOS — .ipk 包构建器
使用 Python 生成标准 SVR4 ar 格式的 .ipk 文件
兼容 OpenWrt / iStoreOS 的 opkg 包管理器

文件结构参照 luci-app-picoclaw:
  luasrc/          → 安装到 /usr/lib/lua/luci/
  htdocs/           → 安装到 /www/luci-static/resources/
  root/etc/         → 安装到 /etc/
  root/usr/libexec/ → 安装到 /usr/libexec/
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
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
LUCI_APP_DIR = os.path.join(ROOT_DIR, "luci-app-hermes")
DIST_DIR = os.path.join(ROOT_DIR, "dist")

PKG_NAME = "luci-app-hermes"
PKG_VERSION = "2.0.0"
PKG_ARCH = "all"


def create_data_tar_gz() -> bytes:
    """创建 data.tar.gz — 所有要安装的文件"""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        # LuCI 源文件: luasrc/ → /usr/lib/lua/luci/
        luasrc_dir = os.path.join(LUCI_APP_DIR, "luasrc")
        for root, dirs, files in os.walk(luasrc_dir):
            for fname in files:
                src_path = os.path.join(root, fname)
                # 计算目标路径: luasrc/xxx → usr/lib/lua/luci/xxx
                rel_path = os.path.relpath(src_path, luasrc_dir)
                arcname = f"usr/lib/lua/luci/{rel_path}"
                tar.add(src_path, arcname=arcname)

        # 前端资源: htdocs/ → /www/luci-static/resources/hermes/
        htdocs_dir = os.path.join(LUCI_APP_DIR, "htdocs/luci-static/resources/hermes")
        if os.path.isdir(htdocs_dir):
            for fname in os.listdir(htdocs_dir):
                src_path = os.path.join(htdocs_dir, fname)
                if os.path.isfile(src_path):
                    tar.add(src_path, arcname=f"www/luci-static/resources/hermes/{fname}")

        # 配置文件: root/etc/config/ → /etc/config/
        config_file = os.path.join(LUCI_APP_DIR, "root/etc/config/hermes")
        if os.path.isfile(config_file):
            tar.add(config_file, arcname="etc/config/hermes")

        # init.d 服务脚本: root/etc/init.d/ → /etc/init.d/ (设置可执行权限)
        initd_src = os.path.join(LUCI_APP_DIR, "root/etc/init.d/hermes-router-api")
        if os.path.isfile(initd_src):
            initd_info = tar.gettarinfo(initd_src, arcname="etc/init.d/hermes-router-api")
            initd_info.mode = 0o755
            with open(initd_src, "rb") as f:
                tar.addfile(initd_info, f)

        # Python API 服务器: root/usr/libexec/ → /usr/libexec/
        server_py = os.path.join(LUCI_APP_DIR, "root/usr/libexec/hermes-router-api/server.py")
        if os.path.isfile(server_py):
            tar.add(server_py, arcname="usr/libexec/hermes-router-api/server.py")

        # PO 翻译文件: po/zh-cn/ → /usr/lib/lua/luci/po/zh-cn/
        po_dir = os.path.join(LUCI_APP_DIR, "po")
        if os.path.isdir(po_dir):
            for root, dirs, files in os.walk(po_dir):
                for fname in files:
                    src_path = os.path.join(root, fname)
                    rel_path = os.path.relpath(src_path, po_dir)
                    arcname = f"usr/lib/lua/luci/po/{rel_path}"
                    tar.add(src_path, arcname=arcname)

    return buf.getvalue()


def create_control_tar_gz(data_tar_gz_size: int) -> bytes:
    """创建 control.tar.gz — 包元数据和安装脚本"""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        # --- control 文件 (兼容旧版 opkg) ---
        control_content = (
            f"Package: {PKG_NAME}\n"
            f"Version: {PKG_VERSION}\n"
            f"Depends: python3, python3-light, luci-lib-jsonc, curl\n"
            f"Provides: luci-app-hermes\n"
            f"Source: https://github.com/allxiao888888-sketch/hermes-istoreos\n"
            f"License: MIT\n"
            f"Section: luci\n"
            f"Architecture: all\n"
            f"Maintainer: OpenClaw Hermes\n"
            f"Installed-Size: {data_tar_gz_size // 1024}\n"
            "Description: Hermes Agent - AI assistant + router management for iStoreOS.\n"
            " Chat with AI via LLM API, manage packages (opkg), services,\n"
            " and system configuration from the router web interface.\n"
            " No external server required.\n"
        ).encode("utf-8")
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


def build_ipk() -> str:
    """构建 .ipk 包并返回文件路径

    iStoreOS/OpenWrt 兼容格式: tar.gz 包裹 debian-binary + control.tar.gz + data.tar.gz
    """
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

    # [4] 打包为 .ipk (tar.gz 包裹格式，兼容 iStoreOS)
    print("[4/5] 打包 .ipk (tar.gz 包裹格式)...")

    os.makedirs(DIST_DIR, exist_ok=True)
    ipk_filename = f"{PKG_NAME}_{PKG_VERSION}_{PKG_ARCH}.ipk"
    ipk_path = os.path.join(DIST_DIR, ipk_filename)

    # 创建外层 tar.gz，包含 debian-binary, data.tar.gz, control.tar.gz
    outer_buf = io.BytesIO()
    with tarfile.open(fileobj=outer_buf, mode="w:gz") as outer_tar:
        # debian-binary
        dbinfo = tarfile.TarInfo(name="./debian-binary")
        dbinfo.size = len(debian_binary)
        dbinfo.mode = 0o644
        outer_tar.addfile(dbinfo, io.BytesIO(debian_binary))

        # data.tar.gz
        dinfo = tarfile.TarInfo(name="./data.tar.gz")
        dinfo.size = len(data_tar_gz)
        dinfo.mode = 0o644
        outer_tar.addfile(dinfo, io.BytesIO(data_tar_gz))

        # control.tar.gz
        cinfo = tarfile.TarInfo(name="./control.tar.gz")
        cinfo.size = len(control_tar_gz)
        cinfo.mode = 0o644
        outer_tar.addfile(cinfo, io.BytesIO(control_tar_gz))

    with open(ipk_path, "wb") as f:
        f.write(outer_buf.getvalue())

    # [5] 验证
    print("[5/5] 验证 ipk 文件...")
    file_size = os.path.getsize(ipk_path)
    md5_hash = hashlib.md5(open(ipk_path, "rb").read()).hexdigest()
    print(f"  ✓ {ipk_filename}")
    print(f"    大小: {file_size} bytes ({file_size / 1024:.1f} KB)")
    print(f"    MD5: {md5_hash}")

    # 验证 tar.gz 格式
    with open(ipk_path, "rb") as f:
        magic = f.read(2)
        assert magic == b"\x1f\x8b", f"Invalid gzip magic: {magic!r}"
        f.seek(0)
        tf = tarfile.open(fileobj=f, mode="r:gz")
        names = [m.name for m in tf.getmembers()]
        assert "./debian-binary" in names, "Missing debian-binary"
        assert "./data.tar.gz" in names, "Missing data.tar.gz"
        assert "./control.tar.gz" in names, "Missing control.tar.gz"
        print("  ✓ tar.gz 格式验证通过")

    print()
    print("=" * 50)
    print(" 构建成功！")
    print("=" * 50)
    print()
    print(f" 安装包: dist/{ipk_filename}")
    print()
    print("=== iStoreOS 安装方法 ===")
    print()
    print(" 方法 1: iStoreOS 商店 手动安装")
    print("   打开 iStoreOS Web 界面")
    print('   进入 iStore 商店')
    print("   点击右上角 手动安装")
    print(f"   选择 dist/{ipk_filename}")
    print("   上传后自动安装")
    print()
    print(" 方法 2: SSH 命令行安装")
    print(f"   1. 上传到路由器:")
    print(f"      scp dist/{ipk_filename} root@192.168.100.1:/tmp/")
    print()
    print("   2. SSH 安装:")
    print("      ssh root@192.168.100.1")
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
