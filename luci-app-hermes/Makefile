#
# Copyright (C) 2024 OpenClaw for iStoreOS
#
# This is free software, licensed under the GNU General Public License v2.
#

include $(TOPDIR)/rules.mk

PKG_NAME:=luci-app-hermes
PKG_VERSION:=2.0.0
PKG_RELEASE:=1

PKG_LICENSE:=GPL-2.0
PKG_MAINTAINER:=OpenClaw Hermes

LUCI_TITLE:=Hermes Agent - Local AI assistant for iStoreOS
LUCI_DESCRIPTION:=AI assistant running directly on iStoreOS router. Chat with AI via LLM API, manage packages (opkg), services, and system configuration from the router web interface. No external server required.
LUCI_DEPENDS:=+python3 +python3-light
LUCI_PKGARCH:=all

include $(TOPDIR)/feeds/luci/luci.mk

# override build, package, install targets
define Package/luci-app-hermes/install
	$(INSTALL_DIR) $(1)/usr/lib/lua/luci/controller
	$(INSTALL_DATA) ./root/usr/lib/lua/luci/controller/hermes.lua $(1)/usr/lib/lua/luci/controller/hermes.lua
	
	$(INSTALL_DIR) $(1)/usr/lib/lua/luci/model/cbi
	$(INSTALL_DATA) ./root/usr/lib/lua/luci/model/cbi/hermes.lua $(1)/usr/lib/lua/luci/model/cbi/hermes.lua
	
	$(INSTALL_DIR) $(1)/usr/lib/lua/luci/view/hermes
	$(INSTALL_DATA) ./root/usr/lib/lua/luci/view/hermes/dashboard.htm $(1)/usr/lib/lua/luci/view/hermes/dashboard.htm
	$(INSTALL_DATA) ./root/usr/lib/lua/luci/view/hermes/chat.htm $(1)/usr/lib/lua/luci/view/hermes/chat.htm
	$(INSTALL_DATA) ./root/usr/lib/lua/luci/view/hermes/control.htm $(1)/usr/lib/lua/luci/view/hermes/control.htm
	$(INSTALL_DATA) ./root/usr/lib/lua/luci/view/hermes/about.htm $(1)/usr/lib/lua/luci/view/hermes/about.htm
	
	$(INSTALL_DIR) $(1)/www/luci-static/resources/hermes
	$(INSTALL_DATA) ./htdocs/luci-static/resources/hermes/hermes.js $(1)/www/luci-static/resources/hermes/hermes.js
	$(INSTALL_DATA) ./htdocs/luci-static/resources/hermes/chat.js $(1)/www/luci-static/resources/hermes/chat.js
	$(INSTALL_DATA) ./htdocs/luci-static/resources/hermes/control.js $(1)/www/luci-static/resources/hermes/control.js
	$(INSTALL_DATA) ./htdocs/luci-static/resources/hermes/style.css $(1)/www/luci-static/resources/hermes/style.css
	
	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_CONF) ./root/etc/config/hermes $(1)/etc/config/hermes
	
	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) ./root/etc/init.d/hermes-router-api $(1)/etc/init.d/hermes-router-api
	
	$(INSTALL_DIR) $(1)/usr/libexec/hermes-router-api
	$(INSTALL_DATA) ../../hermes-router-api/server.py $(1)/usr/libexec/hermes-router-api/server.py
endef

$(eval $(call BuildPackage,luci-app-hermes))
