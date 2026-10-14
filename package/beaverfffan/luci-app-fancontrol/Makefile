# SPDX-License-Identifier: Apache-2.0
#
# Copyright (C) 2026 JiaY-shi

include $(TOPDIR)/rules.mk

LUCI_TITLE:=LuCI support for the generic PWM fan controller
LUCI_DEPENDS:=+luci-base +fancontrol

PKG_LICENSE:=Apache-2.0
PKG_MAINTAINER:=JiaY-shi <shi05275@163.com>

# ★ 上游这个包在 feeds/luci/applications/ 下，靠相对路径 `../../luci.mk`
#   引入构建规则。搬进 package/beaverfffan/ 之后那个相对路径会指向
#   package/luci.mk（不存在）⇒ 改成绝对路径引用 feeds 里那份。
include $(TOPDIR)/feeds/luci/luci.mk

# call BuildPackage - OpenWrt buildroot signature
