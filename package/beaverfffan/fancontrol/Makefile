# SPDX-License-Identifier: GPL-2.0-only
#
# Copyright (C) 2026 JiaY-shi

include $(TOPDIR)/rules.mk

PKG_NAME:=fancontrol
PKG_VERSION:=2.1.0
PKG_RELEASE:=1

PKG_SOURCE:=$(PKG_NAME)-$(PKG_VERSION).tar.gz
PKG_SOURCE_URL:=https://codeload.github.com/JiaY-shi/fancontrol/tar.gz/v$(PKG_VERSION)?
PKG_HASH:=7827572025f285496d025e473a0a879c61dc86d3ac508444beb127dd18cc332f

PKG_MAINTAINER:=JiaY-shi <shi05275@163.com>
PKG_LICENSE:=MIT
PKG_LICENSE_FILES:=LICENSE

PKG_BUILD_PARALLEL:=1

include $(INCLUDE_DIR)/package.mk

define Package/fancontrol
  SECTION:=utils
  CATEGORY:=Utilities
  TITLE:=Generic hwmon PWM fan controller
  URL:=https://github.com/JiaY-shi/fancontrol
endef

define Package/fancontrol/description
  Temperature-based continuous PWM fan controller using the Linux
  hwmon ABI.
endef

define Package/fancontrol/conffiles
/etc/config/fancontrol
endef

MAKE_PATH:=fancontrol/src

# ★ 默认配置用**本包自带**的 files/fancontrol.config，而不是上游源码里那份：
#   上游 /etc/config/fancontrol 是 enabled='0'（温控关着），本固件要求开箱
#   即用 ⇒ 打开温控。差别只有这一个开关，其余参数与上游一致。
#   见 files/fancontrol.config 顶部的说明。
define Package/fancontrol/install
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/fancontrol/src/fancontrol $(1)/usr/bin/fancontrol
	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_CONF) ./files/fancontrol.config $(1)/etc/config/fancontrol
	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/fancontrol/files/fancontrol.init $(1)/etc/init.d/fancontrol
endef

$(eval $(call BuildPackage,fancontrol))
