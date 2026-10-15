#
# Copyright (C) 2020 Nate Ding
#
# This is free software, licensed under the GUN General Public License v3.
# See /LICENSE for more information.
#
# HinLink 适配说明（2026-10-15）
# ----------------------------
# 本包取自 jjm2473/luci-app-oled（master，commit 48ed048），血统为
#   NateLol/luci-app-oled  ->  unifreq/luci-app-oled  ->  jjm2473/luci-app-oled
# 它与 immortalwrt 官方 luci feed 里那份**同名包**（unifreq 血统）在 H69K 的
# 适配上是不同的：本版 netsource=wwan0（H69K 是 5G 机型，屏上显示 5G 网速），
# 另有 easepi A2/R2 支持、ucitrack 注册、配置幂等写入。
#
# ★★ 必须避免与 feed 里的同名包冲突 ★★
#   `./scripts/feeds install -a` 会在 package/feeds/luci/ 下建出
#   luci-app-oled 的软链；而 OpenWrt 扫描 package/ 时，package/feeds/*
#   的字母序晚于 package/beaverfffan/* ⇒ **会把本包顶掉**，固件里装的
#   就成了 feed 那版（表现为 H69K 屏上 netsource 变成 eth0）。
#   安装 feeds 之后必须执行其一：
#       ./scripts/feeds uninstall luci-app-oled
#       rm -rf package/feeds/luci/luci-app-oled
#   （tools/build_single.sh 已在编译前自动兜底删除）
#

include $(TOPDIR)/rules.mk

LUCI_TITLE:=LuCI support for ssd1306 0.91\' 138x32 display
# luci-compat: 本包是旧式 luasrc/ 应用，26.x 的 LuCI 靠 luci-compat 提供兼容层
LUCI_DEPENDS:=+luci-compat +i2c-tools
PKG_VERSION:=2023.07.03-r1
PKG_RELEASE:=

PKG_LICENSE:=GPLv3
PKG_LINCESE_FILES:=LICENSE
PKG_MAINTAINER:=natelol <natelol@github.com>

define Package/luci-app-oled/conffiles
/etc/config/oled
endef

include $(TOPDIR)/feeds/luci/luci.mk

# call BuildPackage - OpenWrt buildroot signature
