# 应用到 immortalwrt/immortalwrt

本仓库是**支线仓库**，只提供补丁文件，不含完整 OpenWrt 源码。
按以下步骤应用到 immortalwrt（`master` 分支，内核 6.18）。

## 前提确认

先确认 immortalwrt 目标内核是否已有 H68K 公共设备树：

```sh
ls target/linux/rockchip/patches-6.18/ | grep -i hinlink
# 或直接看内核 dts 目录
```

- **若有** `101-arm64-dts-rockchip-Add-HINLINK-H28K.patch` 而无 h68k 相关 patch
  → 走方案 A
- **若已有** `rk3568-hinlink-opc.dtsi`（在 target dts 里）
  → 走方案 B

## 方案 A：内核尚无 hinlink 支持

把 DTS 直接放进内核树：

```sh
cp target/linux/rockchip/files/arch/arm64/boot/dts/rockchip/rk3568-hinlink-* \
   target/linux/rockchip/files/arch/arm64/boot/dts/rockchip/

# 若内核 Makefile 需要登记，按现有格式追加
```

然后在 `target/linux/rockchip/image/armv8.mk` 末尾追加
`armv8.mk.hinlink` 的内容。

## 方案 B：内核已有 h68k

只改target 层：

```sh
# armv8.mk 追加设备定义
cat armv8.mk.hinlink >> target/linux/rockchip/image/armv8.mk

# board.d 合并（不要直接覆盖，需与原文件合并 case 分支）
# 把 02_network / 01_leds 中的 hinlink case 段落并入对应文件
```

## U-Boot

`armv8.mk.hinlink` 每机型指定了 `UBOOT_DEVICE_NAME`（如
`hinlink-h68k-a-rk3568`）。

**首次验证建议统一改为 `generic-rk3568`**（immortalwrt 已有），待能启动后再做专属 port。

## 编译

```sh
make menuconfig
# Target Devices → Rockchip platform → 勾选机型
make download -j$(nproc)
make -j$(nproc)
```

## 已验证 / 未验证

| 项 | 状态 |
|---|---|
| DTS 语法结构 | 已验证（`immortalwrt/dts_syntax_check.py`，已用主线原生 DTS 校准） |
| dtc 完整编译 | **未验证** —— 测试环境 dtc 1.7.2 太老，连主线官方 `rk3568.dtsi` 都编译失败（对照组同样失败，属环境问题） |
| phandle 交叉引用 | 未验证（离线检查器不覆盖） |
| 实机启动 | 未验证（无实机） |
| LED 颜色与 GPIO | 待实机确认 |

## 需实机确认的项

1. **H69K 的 WiFi 复位引脚** —— 点亮脚本用 GPIO3_A0，2022 厂商 dtb 用 GPIO3_D5，本方案取 D5
2. **H69K-mini 的实际屏蔽配置** —— 当前按「屏蔽 1 GMAC + 1 PCIe」
3. **H68K new 的 WiFi 型号** —— 当前按 AIC8800
4. **各机型 LED 颜色/闪烁规则**
5. **H69K 5G 模组电源** —— 抄 iStoreOS 的 GPIO0_PC0 + 2s 延时
