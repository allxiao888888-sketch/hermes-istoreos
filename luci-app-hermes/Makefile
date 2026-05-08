#
# Copyright (C) 2024-2026 Hermes Agent for iStoreOS
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

# Install server.py to non-standard path (luci.mk doesn't handle /usr/libexec)
define Package/luci-app-hermes/install
	$(INSTALL_DIR) $(1)/usr/libexec/hermes-router-api
	$(INSTALL_DATA) ./root/usr/libexec/hermes-router-api/server.py \
		$(1)/usr/libexec/hermes-router-api/server.py
endef

# call BuildPackage - OpenWrt buildroot signature
