# immortalwrt · HinLink H 系列全设备固件（clone 即编译）

基于 [immortalwrt](https://github.com/immortalwrt/immortalwrt) master
（base commit `305089f`，内核 **6.18.55**），把 HinLink（HLK）H 系列
**16 个机型**的适配**全部固化在源码树里**。

> 与「适配层」仓库的区别：那个仓库只有几十 KB 的增量文件，还需要先 clone
> 官方源码再跑一次集成脚本；**这个仓库本身就是一棵完整的 immortalwrt 源码树**，
> 适配已经在里面了 —— 选一个 config 就能直接编。

---

## 一、快速开始

### 0. 环境

Ubuntu 22.04+ / Debian 12+（x86_64），**磁盘 ≥ 25 GB**（`dl/` 与 `build_dir/` 很吃空间）：

```sh
sudo apt update
sudo apt install -y build-essential clang flex bison g++ gawk gcc-multilib \
  g++-multilib gettext git libncurses-dev libssl-dev python3-distutils \
  python3-setuptools rsync unzip zlib1g-dev file wget
```

### 1. 取源码

```sh
git clone https://github.com/Beaverfffan/immortalwrt-hinlink-full.git
cd immortalwrt-hinlink-full
```

### 2. 更新 feeds（**必做**，本仓库不含 feeds 内容）

```sh
./scripts/feeds update -a
./scripts/feeds install -a
```

> `package/beaverfffan/` 下是本仓库自带的插件，**不需要** feeds，也不会被
> 上面两条命令动到。

### 3. 选机型

```sh
cp configs/h69k.config .config
make defconfig
```

### 4. 编译

```sh
make -j$(nproc) download     # 先把源码包下齐，避免编到一半断网
make -j$(nproc)
```

首次编译（16 核）约 25~40 分钟。产物在 `bin/targets/rockchip/armv8/`：

| 文件 | 用途 |
|---|---|
| `*squashfs-sysupgrade.img.gz` | **系统内升级**（`sysupgrade -n`），日常用这个 |
| `*squashfs-factory.img.gz` | 首次刷机（原厂固件 → 本固件） |
| `*ext4-sysupgrade.img.gz` | ext4 版（需要可写根分区时用） |

单个机型 config 只编一个机型，产物名里带机型标识，比如
`immortalwrt-...-hinlink_opc-h69k-squashfs-sysupgrade.img.gz`。

### 5. 刷机

```sh
# 本固件 → 本固件（不保留配置）
sysupgrade -n /tmp/xxx-squashfs-sysupgrade.img.gz

# 原厂固件 → 本固件：用 factory 镜像，按机型走线刷 / TF 卡刷
```

首次刷入后 **LAN 口默认地址是 `192.168.100.1`**（无密码），
5G 模组控制面板在 **网络 → 5G复位**。

---

## 二、支持的机型（16）

### RK3568 — H66K / H68K / H69K（8）

| 机型 | config | 口数 | 网络构成 | 板载 WiFi | 存储 |
|---|---|---|---|---|---|
| h66k | `configs/h66k.config` | 2 | 2×RTL8125（无 GMAC） | — | SATA |
| h68k-a-b | `configs/h68k-a-b.config` | 2 | 2×GMAC | AP6256 | **SATA** |
| h68k-a-b-usb | `configs/h68k-a-b-usb.config` | 2 | 2×GMAC | AP6256 | USB3.0 |
| h68k-c-d-f | `configs/h68k-c-d-f.config` | 4 | 2×GMAC + 2×RTL8125 | M.2 | **SATA** |
| h68k-c-d-f-usb | `configs/h68k-c-d-f-usb.config` | 4 | 2×GMAC + 2×RTL8125 | M.2 | USB3.0 |
| h68k-new | `configs/h68k-new.config` | 4 | 2×GMAC + 2×RTL8125 | AIC8800 | USB3 + SATA |
| h69k | `configs/h69k.config` | **3** | 1×GMAC(gmac1) + 2×RTL8125 | AIC8800 | USB3 + SATA |
| h69k-mini | `configs/h69k-mini.config` | 4 | 2×GMAC + 2×RTL8125 | AIC8800 | USB3 + SATA |

> **命名约定**：无后缀 = SATA，`-usb` = USB3.0（OpenWrt / lede / iStoreOS 互认）。
> `a-b` = A/B 板世代，`c-d-f` = C/D/F 板世代。
> **`h68k-a-b` 与 `h68k-a-b-usb` 不能合并** —— RK3568 上 `sata0` 与 USB3.0
> 争同一颗 `combphy0`，硬件二选一。

### RK3528 — H28K / H29K / HT2（5）

| 机型 | config | 屏 | 口数 | 板载 WiFi |
|---|---|---|---|---|
| h28k | `configs/h28k.config` | 无 | 2（RGMII + PCIe RTL8111H） | **无** |
| h29k-v1.3-1.14 | `configs/h29k-v1.3-1.14.config` | 1.14″ 135×240 rot270 | 1 | SDIO |
| h29k-v5-1.14 | `configs/h29k-v5-1.14.config` | 1.14″ 135×240 rot90 | 1 | SDIO |
| h29k-v5-1.49 | `configs/h29k-v5-1.49.config` | 1.49″ 172×320 GC9307 + **电容触控** | 1 | SDIO |
| ht2 | `configs/ht2.config` | 无 | 1 | SDIO SDR50 |

> H29K 全系与 HT2 是**单网口**（只有板载 RGMII(gmac1)）。

### RK3588 — H88K / H89K（3）

| 机型 | config | 存储 | 屏 | 口数 |
|---|---|---|---|---|
| h88k-v2 | `configs/h88k-v2.config` | combphy0_ps + SATA | — | 2 |
| h88k-v3 | `configs/h88k-v3.config` | M.2 NVMe (pcie3x4) | SPI ST7789V | 3 |
| h89k | `configs/h89k.config` | 无 SATA | ST7789V 135×240 rot90 | 3 |

> `pcie3x4` **不是板载网口**：v2 上是 PCIe x4 插槽，v3 上改跑 M.2 NVMe。

每个机型的硬件细节、WAN 口枚举、已知限制见 **`docs/devices/<机型>.md`**。

---

## 三、固件自带什么

### 3.1 无线驱动（6 组，全部默认编入）

| 组件 | 驱动包 | 固件包 |
|---|---|---|
| MT7921 | `kmod-mt7921e` / `-s` / `-u` | `kmod-mt7921-firmware` |
| MT7922 | （共用 mt7921e） | `kmod-mt7922-firmware` |
| **MT7925** | `kmod-mt7925e` | `kmod-mt7925-firmware` |
| MT7915 / **MT7916** | `kmod-mt7915e` | `kmod-mt7915-firmware` + `kmod-mt7916-firmware` |
| **NFA765**（QCNFA765 / WCN6855） | `kmod-ath11k` + `kmod-ath11k-pci` | `ath11k-firmware-wcn6855` |
| AIC8800 | `kmod-aic8800-pcie` / `-sdio` / `-usb` | 随驱动 |

> ⚠️ **驱动 ≠ 固件**：`kmod-mt7915e` **一个驱动同时支持 MT7915 与 MT7916**，
> 但固件是两个独立包，而且**不在驱动的 DEPENDS 里** —— 漏掉就是
> `Direct firmware load for mediatek/mt7916_wm.bin failed`。
> 7925 同理（只有 `-common` 是不够的，必须带 `-firmware`）。

### 3.2 其它默认编入

- **LuCI**（完整）
- `usbutils`（`lsusb` / `usbreset`，5G 排查用）
- `kmod-usb-serial-option`（4G/5G 模组的 AT 口）
- 风扇温控、SSD1306 OLED、5G 复位面板 —— 见下一节

### 3.3 ⚠️ 关于板载屏幕：**能亮，但没有程序驱动它**

H29K 全系（1.14″ / 1.49″）与 H88K-v3、H89K 的 DTS 里都有 SPI 面板节点，内核侧
也打了 fbtft 驱动并内建 `CONFIG_FB`：

| 机型 | 面板 | 内核侧 |
|---|---|---|
| h29k-v1.3-1.14 / h29k-v5-1.14 | 1.14″ 135×240 | fbtft（`9530-fbtft-add-gc9307-driver.patch`） |
| h29k-v5-1.49 | 1.49″ 172×320 GC9307 + 电容触控 | 同上 |
| h88k-v3 / h89k | ST7789V 135×240 | fbtft + `9999-fbtft-read-display-offset-from-dt.patch` |

所以**屏会点亮、系统里会出现 `/dev/fbX`**。

**但固件里没有任何用户态程序去驱动它** —— 屏上不会显示 IP、温度、速率之类的
内容（不是坏了，是本来就没写这个程序）。要显示内容得自己写应用往 `/dev/fbX`
写，或参照 `luci-app-oled` 的思路另做一个。

> ⚠️ **别把两者混淆**：`luci-app-oled` 驱动的是**外接的 I2C SSD1306（0.91″
> 128×32）**，与这些**板载 SPI 屏**完全无关。

---

## 四、`package/beaverfffan/` —— 本仓库自维护的插件

| 包 | 作用 | 默认状态 | 来源 |
|---|---|---|---|
| `fancontrol` | 通用 hwmon PWM 风扇温控守护进程 | **温控默认开启** | [JiaY-shi/fancontrol](https://github.com/JiaY-shi/fancontrol) v2.1.0 |
| `luci-app-fancontrol` | 风扇温控 LuCI 面板（服务 → Fan Control） | 选中 | feeds/luci（JiaY-shi） |
| `luci-app-hinlink-modem-hardreset` | **5G 模组复位 / 日志面板**（网络 → 5G复位） | 选中 | 本仓库自研 |
| `luci-app-oled` | SSD1306 0.91″ OLED 屏（状态显示） | 选中 | [jjm2473/luci-app-oled](https://github.com/jjm2473/luci-app-oled) |
| `aic8800` | AIC8800 WiFi 驱动（PCIe / SDIO / USB） | 选中 | lede / immortalwrt |

### 4.1 风扇为什么「默认就开」

上游 `fancontrol` 的 `/etc/config/fancontrol` 是 `enabled='0'`（装了但关着）。
本固件要求**开箱即用**，所以包内自带一份默认配置（只改了 `enabled='1'`，
其余参数与上游一致）：

```
start_temp 45 °C → full_speed_temp 85 °C 线性调速
hysteresis 3 °C 回差防抖
kick_speed 255 / kick_ms 500   起步脉冲，防低速堵转
fail_safe_speed 255            温度读不到就全速（宁可吵，不可烧）
thermal_file / fan_file = auto 自动扫 hwmon，不按机型硬编码
```

要改：LuCI「服务 → Fan Control」，或编辑 `/etc/config/fancontrol` 后
`/etc/init.d/fancontrol restart`。

### 4.2 5G 复位面板做什么

H 系列的 5G「复位/使能」脚在 DTS 里交给了 **`rfkill-gpio`**，
内核会建一个 `type=wwan` 的 rfkill 设备，其 `state` 属性可写：

```sh
echo 0 > /sys/class/rfkill/rfkillN/state   # 拉复位（H69K 单路机型上同时就是断电）
echo 1 > /sys/class/rfkill/rfkillN/state   # 释放
```

面板提供 **断电 → 上电 → 软复位 → 仅 USB 重新枚举** 四个动作
（软复位 = 断电 + 等 hold_ms + 上电），以及模组 / 串口 / 网卡的插拔日志。

**模组识别按「接口结构判据」，不看 VID**：只要设备导出了
`ttyUSB*` / `ttyACM*` / `cdc-wdm*`，或者有 USB 网卡 + `0xff` 接口，
就当模组 —— 换任何厂家的 4G/5G 模组都不需要改代码。
详见 [`docs/HARDWARE.md`](docs/HARDWARE.md)。

---

## 五、目录结构

```
├── configs/                     16 个机型的 defconfig（★ 从这里选）
│   ├── README.md
│   └── h28k.config … h89k.config
├── docs/
│   ├── devices/                 每机型一份说明（硬件 / 网口 / 限制）
│   │   └── h28k.md … h89k.md
│   ├── HARDWARE.md              硬件机理（GPIO / 屏幕 / 网口 / 5G）
│   └── APPLY.md                 适配层的注入方法（历史参考）
├── package/beaverfffan/         自维护插件（见 §四）
├── target/linux/rockchip/       HinLink 的 DTS / target 定义 / board.d
├── package/boot/uboot-rockchip/patches/  U-Boot 板级支持（106~109）
├── patches/                     内核 patch（屏幕等）
└── (其余为 immortalwrt 上游源码)
```

---

## 六、上游同步

本仓库是 immortalwrt 的**单提交快照**（base `305089f`），不带上游历史。
想跟进官方更新，用官方 remote 合并：

```sh
git remote add upstream https://github.com/immortalwrt/immortalwrt.git
git fetch --depth=1 upstream master
git merge --allow-unrelated-histories upstream/master   # 冲突点基本都在 target/linux/rockchip
```

`target/linux/rockchip/` 与本仓库自维护的 `package/beaverfffan/` 是冲突高发区，
合并后记得重新 `make defconfig` 验证 configs/ 里的文件仍然有效。

---

## 七、许可

本仓库的适配部分（`target/linux/rockchip/`、`package/beaverfffan/`、
`configs/`、`docs/`）为 **Apache-2.0**；其余为 immortalwrt 上游各自的许可
（主要为 GPL-2.0）。`docs/` 与 `configs/` 里的说明文字可自由取用。
