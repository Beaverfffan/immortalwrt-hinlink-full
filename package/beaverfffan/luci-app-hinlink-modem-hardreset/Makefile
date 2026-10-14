#
# Copyright (C) 2026 Beaverfffan
# SPDX-License-Identifier: Apache-2.0
#
# HinLink 5G 模组复位 / 日志 —— LuCI 应用
#
# 为什么从 base-files 裸文件改成正式包
# ------------------------------------
# 原来这 10 个文件直接躺在
#   target/linux/rockchip/armv8/base-files/
# 里，只能随固件一起编进去：不能单独装、不能卸、不能升级，也没法让用户
# 在 menuconfig 里勾选。包化之后它就是一个正常 ipk，同时仍然是固件默认
# 的一部分（configs/*.config 里 CONFIG_PACKAGE_luci-app-hinlink-modem-hardreset=y）。
#
# 为什么不 include luci.mk
# ------------------------
# luci.mk 位于 feeds/luci 下、靠相对路径 `../../luci.mk` 引入。本包在
# package/beaverfffan/ 里，没有那个相对关系；改成绝对路径又会绑死 feeds
# 布局。手写 install 段反而更清楚，顺便把文件权限一次性钉死
# （脚本 0755 / 数据 0644 —— 权限错了 LuCI 会 404 或 rpcd 不加载插件）。
#
include $(TOPDIR)/rules.mk

PKG_NAME:=luci-app-hinlink-modem-hardreset
PKG_VERSION:=2026.10.14
PKG_RELEASE:=1

PKG_LICENSE:=Apache-2.0
PKG_MAINTAINER:=Beaverfffan <beaverfffan@users.noreply.github.com>

include $(INCLUDE_DIR)/package.mk

# 纯 files/ 包，没有任何下载与编译动作。这三段必须显式清空，
# 否则 package.mk 的默认 Build/Prepare 会去找 PKG_SOURCE 解压。
define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
endef

define Build/Configure
endef

define Build/Compile
endef

define Package/luci-app-hinlink-modem-hardreset
  SECTION:=luci
  CATEGORY:=LuCI
  SUBMENU:=3. Applications
  TITLE:=HinLink 5G modem hard reset / event log
  DEPENDS:=+luci-base +rpcd +usbutils +kmod-usb-serial-option
endef

define Package/luci-app-hinlink-modem-hardreset/description
  HinLink H 系列路由器（RK3528 / RK3568 / RK3588）的 5G 模组控制面板：
  断电 / 上电 / 软复位 / 仅 USB 重新枚举，以及模组、串口、网卡的插拔日志。

  底层只依赖 DTS 里的 rfkill-gpio ——
  /sys/class/rfkill/rfkillN/state 是 DEVICE_ATTR_RW，可写：
    echo 0 -> 拉复位（H69K 单路机型上同时就是断电）
    echo 1 -> 释放
  所以「0 -> 等 hold_ms -> 1」就是一次硬复位脉冲，不需要额外命令或驱动。

  模组识别按**接口结构判据**（导出了 ttyUSB*/ttyACM*/cdc-wdm*，或者有
  USB 网卡 + vendor-specific(0xff) 接口），不看 VID 白名单，换任何厂家的
  4G/5G 模组都不用改代码。
endef

define Package/luci-app-hinlink-modem-hardreset/conffiles
/etc/config/hinlink-modem-hardreset
endef

define Package/luci-app-hinlink-modem-hardreset/install
	$(INSTALL_DIR) $(1)/etc/config $(1)/etc/init.d
	$(INSTALL_CONF) ./files/etc/config/hinlink-modem-hardreset $(1)/etc/config/
	$(INSTALL_BIN)  ./files/etc/init.d/hinlink-modem-hardreset $(1)/etc/init.d/

	$(INSTALL_DIR) $(1)/etc/hotplug.d/usb $(1)/etc/hotplug.d/tty $(1)/etc/hotplug.d/net
	$(INSTALL_BIN)  ./files/etc/hotplug.d/usb/50-hinlink-modem-hardreset $(1)/etc/hotplug.d/usb/
	$(INSTALL_BIN)  ./files/etc/hotplug.d/tty/50-hinlink-modem-hardreset $(1)/etc/hotplug.d/tty/
	$(INSTALL_BIN)  ./files/etc/hotplug.d/net/50-hinlink-modem-hardreset $(1)/etc/hotplug.d/net/

	$(INSTALL_DIR) $(1)/usr/libexec/rpcd
	$(INSTALL_BIN)  ./files/usr/libexec/hinlink-modem-hardreset $(1)/usr/libexec/
	$(INSTALL_BIN)  ./files/usr/libexec/rpcd/hinlink-modem-hardreset $(1)/usr/libexec/rpcd/

	$(INSTALL_DIR) $(1)/usr/share/luci/menu.d $(1)/usr/share/rpcd/acl.d
	$(INSTALL_DATA) ./files/usr/share/luci/menu.d/luci-app-hinlink-modem-hardreset.json $(1)/usr/share/luci/menu.d/
	$(INSTALL_DATA) ./files/usr/share/rpcd/acl.d/luci-app-hinlink-modem-hardreset.json $(1)/usr/share/rpcd/acl.d/

	$(INSTALL_DIR) $(1)/www/luci-static/resources/view
	$(INSTALL_DATA) ./files/www/luci-static/resources/view/hinlink-modem-hardreset.js $(1)/www/luci-static/resources/view/
endef

# 装完让 LuCI 立刻看到菜单（不重启整机）：
#   · 清掉菜单缓存（否则“网络 → 5G复位”要等下一次缓存失效才出现）
#   · 重启 rpcd 让新的 shell 插件对象注册上去
define Package/luci-app-hinlink-modem-hardreset/postinst
#!/bin/sh
[ -n "$${IPKG_INSTROOT}" ] || {
	rm -f /tmp/luci-indexcache* 2>/dev/null
	/etc/init.d/rpcd restart 2>/dev/null
}
exit 0
endef

$(eval $(call BuildPackage,luci-app-hinlink-modem-hardreset))
