#
# Copyright (C) 2026 OpenClaw for iStoreOS
#
# This is free software, licensed under the MIT License.
#

include $(TOPDIR)/rules.mk

PKG_NAME:=luci-app-hermes
PKG_VERSION:=2.0.0
PKG_RELEASE:=1

PKG_LICENSE:=MIT
PKG_MAINTAINER:=Hermes Agent

LUCI_TITLE:=Hermes Agent - Local AI assistant for iStoreOS
LUCI_DESCRIPTION:=AI assistant running directly on iStoreOS router. Chat with AI \
	via LLM API, manage packages (opkg), services, and system configuration from \
	the router web interface. No external server required.
LUCI_DEPENDS:=+python3 +python3-light +luci-lib-jsonc
LUCI_PKGARCH:=all

include $(TOPDIR)/feeds/luci/luci.mk

# call BuildPackage - OpenWrt buildroot signature
