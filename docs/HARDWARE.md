# 特殊硬件清单

本文档逐项列出 HinLink 全系机型的**非网口类**特殊硬件：屏幕、风扇、WiFi、
5G/4G 模组供电与复位 IO、SARADC、按键、LED。

数据来源优先级（见 README §七的方法论）：
**厂商 dtb > 厂商 DTS > iStoreOS DTS > 上游 unifreq DTS > 推断（需实机确认）**

---

## ★ 0. 默认固件的预置策略（2026-10-10 起）

从这一版起，**所有机型（现 16 个）共用同一套预置包**（`Device/hinlink_common`），
不再按机型裁剪无线驱动：

* **无线网卡驱动全带上**（M.2/PCIe + SDIO + USB 三条总线穷举）
  ⇒ 一块固件，插 AP6256 / AIC8800 / 任意 mt76·rtw88·rtw89 模组都能认，
  不必先知道机器是哪一代。
* ★ **驱动 ≠ 固件：固件包必须单独装**（2026-10-12 补）
  `kmod-mt7915e` 这**一个驱动同时支持 MT7915 与 MT7916**，但它
  **DEPENDS 里不含任何固件包**，必须显式加：
  `kmod-mt7915-firmware`（`mt7915_{wa,wm,rom_patch}.bin`）+ 
  `kmod-mt7916-firmware`（`mt7916_{wa,wm,rom_patch}.bin`）。
  漏了就会出现「驱动加载了但没有固件可用」：
  ```
  dmesg | grep -i "firmware load"
  → Direct firmware load for mediatek/mt7916_wm.bin failed
  ```
  H69K / H88K / H89K 的 M.2 / PCIe 位插 MT7916 就靠这两个。
  （对照：`kmod-mt7921e` 的 DEPENDS 自带 `kmod-mt7921-firmware`，
  所以那一路不用手写 —— mt7915e 就是漏在这一条上。）
* **风扇驱动全带上**：`kmod-hwmon-pwmfan` + `kmod-hwmon-gpiofan` +
  `kmod-thermal` + `fancontrol` + `luci-app-fancontrol`（含简体中文）
  ⇒ LuCI「系统 → 风扇控制」直接可调。
* **fbtft 小屏栈改为内核内建**（`CONFIG_FB_TFT*` = y，含本仓库新增的
  GC9307 驱动）—— rockchip 上 package 层的 `kmod-fb*` 被
  `FBDEV_TARGETS` 限制成 bcm27xx/sunxi/x86 专用，拿不到。
* 5G/4G 模组的网络侧驱动也预置：`qmi-wwan` / `cdc-mbim` /
  `usb-serial-option` / `usb-serial-qualcomm` / `usb-modeswitch`。

详细包清单与踩坑见 `README.md §4.12`。

---

---

## 一、屏幕

### 驱动方式分两类

| 类型 | 机型 | 驱动 | 说明 |
|---|---|---|---|
| **fbtft**（内核**内建** =y） | H29K 全系（1.14" / 1.49"）、H89K | `fb_st7789v` / `fb_gc9307` | 屏节点写 `compatible = "sitronix,xxx"` + `width`/`height`/`rotate` |
| **spidev + 用户态** | H88K v3 | `CONFIG_SPI_SPIDEV=y`（内建）+ `kmsd`/`fb_ili9341` 类工具 | iStoreOS 的做法，DTS 里只有 `spidev@0`，**不带屏参数** |

⚠️ `fb_gc9307` 是**本仓库新增**的驱动（`patches/9530-fbtft-add-gc9307-driver.patch`）：
主线 6.18 的 `drivers/staging/fbtft/` 里 grep `gc9307` 零命中，只有 `fb_st7789v.c`。
H29K v5 1.49" 原厂用的就是 GC9307，所以此前这块屏**无驱动可用**。

⚠️ **这个差异很重要**：H88K v3 的屏在 DTS 里**没有** `width`/`height`/`rotate`，
所以它**用不到** fbtft 的偏移 patch。刷 H88K v3 时不要装 fbtft 的包。

###逐机型明细

| 机型 | 屏驱动 | 分辨率 | rotate | SPI 频率 | DC 引脚 | 背光 | 偏移 patch |
|---|---|---|---|---|---|---|---|
| H29K v1.3 1.14" | st7789v | 135×240 | **270** | 6 MHz | GPIO1_B4 | GPIO0_A0 恒亮 | ✅ 40/52 |
| H29K v5 1.14" | st7789v | 135×240 | **90** | 6 MHz | GPIO1_B4 | GPIO0_A0 恒亮 | ✅ 40/52 |
| H29K v5 1.49" | **gc9307** | **172×320** | 270 | 6 MHz | GPIO1_B4 | **PWM3/GPIO4_B6** | ⚠️ **未提供** |
| H89K | st7789v | 135×240 | 90 | **1 MHz** | GPIO1_A4 | 未配置 | ✅ 40/52（推断） |
| H88K v3 | spidev | — | — | 50 MHz | GPIO1_A4 | — | 不适用 |
| 其余机型 | 无屏 | — | — | — | — | — | — |

**背光是架构级差异**：1.49 寸是唯一支持**亮度调节**的机型
（`pwm-backlight`，256 级，`pwms = <&pwm3 0 25000>`，默认亮度 153）；
其他屏是 GPIO 恒亮（`backlight-gpios`，低有效）。

**触控**：只有 1.49 寸有电容触控（`chipone,axs5106` @ I2C1 addr 0x63，
irq=GPIO4_B2，reset=GPIO4_B3，`inverted-x` + `inverted-y` 双轴反向）。

### 显示偏移 patch

```
patches/9999-fbtft-read-display-offset-from-dt.patch
```

ST7789V 135×240 在 rotate 后显存窗口需平移才能对上可见区。本patch
**从 DT 读偏移量**，不在内核里按机型硬编码：

```dts
x-offset    = <40>;   /* rotate 90/270 时 x += 40 */
y-offset    = <52>;   /* rotate 90/270 时 y += 52 */
x-offset-0  = <52>;   /* rotate 0/180  时 x += 52 */
y-offset-0  = <40>;   /* rotate 0/180  时 y += 40 */
```

> ★ 为什么改成读 DT：H29K 与 H89K 都是 135×240 但 rotate 不同，
> 硬编码 switch 无法区分。改成 DT 后一块屏改DTS 就能调偏移，
> 不必重编内核。数值来自原厂 1.14" 偏移 patch。

⚠️ **1.49 寸（172×320）没有偏移数据** —— 原厂只给了 1.9" 与 1.14" 两份。
若实机显示位置不对，在其 DTS 的 panel 节点加 `x-offset` / `y-offset` 即可。

---

## 二、风扇

### 覆盖情况

| 机型 | 风扇 PWM | 温控 cooling-maps | 状态 |
|---|---|---|---|
| **H69K / H69K-mini** | **pwm0 → pwm-fan** | ✅✅ 4 档 | ✅ **已移植**（见下） |
| H89K | `pwm3`（febf0020）| — | ⚠️ 只有 PWM，无 pwm-fan 节点 |
| H88K v2/v3 | — | — | ✅ 无风扇（厂商无） |
| H66K / H68K 系列 | — | — | ✅ 无风扇（厂商无） |
| H28K / H29K / HT2 | pwm1/pwm2 作 **vdd_cpu/vdd_logic 调压** | — | ✅ 非风扇用途 |

### H69K / H69K-mini 的风扇配置（已移植）

参数来自 iStoreOS 官方 `rk3568-opc-h69k.dts`，并由「h69k-fan」LuCI 插件的
`DEVELOPMENT.md` 反向验证：

```dts
fan: pwm-fan {
    compatible = "pwm-fan";
    cooling-levels = <0 0x55 0x66 0x77 0x88 0x99 0xbb 0xcc 0xff>;
    #cooling-cells = <2>;
    fan-supply = <&vcc5v0_sys>;
    pwms = <&pwm0 0 50000 0>;
};
&pwm0 { status = "okay"; };
```

**9 档转速**（与插件的 `pct_to_state` 映射表**逐值一致**，改动会让插件档位错位）：

| 档 | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|---|
| 占空比 | 0% | 33% | 40% | 47% | 53% | 60% | 73% | 80% | 100% |
| 值 | 0 | 0x55 | 0x66 | 0x77 | 0x88 | 0x99 | 0xbb | 0xcc | 0xff |

**温控曲线**（`&cpu_thermal` 的 cooling-maps 绑到 fan）：

| 温度 | 类型 | 风扇档位 |
|---|---|---|
| 20℃ | passive | 最低档常转（`THERMAL_NO_LIMIT`~2） |
| 65℃ | active | 2 ~ 4 |
| 85℃ | active | 4 ~ 6 |
| 95℃ | active | 6 ~ 满档 |
| — | critical | 115℃（内核默认，本仓库未改） |

⚠️ 内核 `rk356x-base.dtsi` 原本的 `cpu_thermal` 只有 passive 的
`cpu_alert0(70℃)` / `cpu_alert1(75℃)` + `critical(95℃)`，且 cooling-map0
绑的是 **CPU**（CPU_FREQ_INCREASE）不是风扇。本仓库覆盖为风扇曲线 ——
**这意味着放弃了内核的 CPU 降频策略**。若要两者兼得，需把两组
cooling-maps 合并（CPU 降频 + 风扇调速）。

⚠️ **设备树无 tach 引脚** → 没有 RPM 反馈，界面只能显示占空比。

### 可选：iStoreOS「h69k-fan」LuCI 插件

用户提供的 `iStoreOS_H69K风扇插件编译 已冻结.zip` 是**纯用户态**方案
（`/usr/libexec/h69k-fan` 是 POSIX shell 脚本，23849 B），**不需要任何内核 patch**。

它的工作方式：

1. **接管**：把 `cpu_thermal` 的 `mode` 写成 `disabled`，
   并把绑定风扇的 trip 温度抬到 `min(105, critical-10)`，
   阻止内核 thermal governor 跟用户态守护争抢 PWM
2. **探测**：遍历 `/sys/class/hwmon/hwmon*/pwm1`（pwm-fan 驱动）
   或 `/sys/class/thermal/cooling_device*/cur_state`（内核 thermal 框架）
3. **调速**：5 档曲线（40/50/60/70/80℃ → 25/35/50/75/100%）+ 迟滞 2℃
   + 低温踢转（0% → 100% 持续 1 秒防停转）
4. **释放**：`release` 时先满速交接，再还原 mode 与 trips

本仓库的 DTS 提供了它所需的 `pwm-fan` 节点，
所以**装上这个插件即可用**，无需改动内核。

配置项在 `/etc/config/h69k-fan`：`enabled` / `mode`(auto|manual) /
`t1..t5` / `s1..s5` / `hysteresis` / `kickstart` / `interval` / `zone`。

⚠️ 插件默认 `enabled '0'`，需在 LuCI「系统 → 风扇控制」里启用并保存。

### H69K / H69K-mini 的风扇：已移植（2026-10-09 起）

上面的 `fan: pwm-fan` + `&cpu_thermal cooling-maps` 已经写进
`rk3568-hinlink-opc.dtsi`（H69K / H69K-mini 共用），**不再是缺口**。
参数取自 iStoreOS 官方 `rk3568-opc-h69k.dts`，并由用户提供的
「iStoreOS_H69K风扇插件编译 已冻结.zip」里 `DEVELOPMENT.md` 的
`pct_to_state` 映射表**逐值反验**（9 档 duty 完全一致）。

固件侧自 2026-10-10 起默认预置：

| 包 | 作用 |
|---|---|
| `kmod-hwmon-pwmfan` | 提供 `/sys/class/hwmon/hwmonX/pwm1`（用户态可读写） |
| `kmod-thermal` / `kmod-hwmon-core` | 内核 thermal 框架与 hwmon 基类 |
| `fancontrol` | 通用 PWM 风扇守护脚本 |
| `luci-app-fancontrol` + `luci-i18n-fancontrol-zh-cn` | LuCI「系统 → 风扇控制」界面 |

⚠️ 若改用 iStoreOS 的「h69k-fan」插件，它会**接管** `cpu_thermal`
（把 mode 写成 disabled、抬 trip 温度），与内核 thermal governor 互斥 ——
两者选一个即可。

### H89K 的 pwm3 只接了 PWM 未接风扇

厂商 dtb 里 `pwm@febf0020` 是 `okay`，本仓库照抄了，但**没有 `pwm-fan` 节点**，
所以风扇不会自动调速（需用户态控制）。厂商 dtb 里也没有 pwm-fan / cooling-maps，
说明厂商固件同样只把它当普通 PWM 用。

---

## 三、WiFi

### 覆盖情况

| 机型 | WiFi 模组 | 控制器 | pwrseq | enable | host-wake | 驱动包 |
|---|---|---|---|---|---|---|
| **H28K** | **无** | — | — | — | — | — |
| H29K v1.3 | AIC8800 | `sdio0` | ✅ | ✅ | ✅ | `kmod-aic8800-sdio` |
| H29K v5 (1.14") | AIC8800 | `sdio0` | ✅ | ✅ | ✅ | `kmod-aic8800-sdio` |
| H29K v5 (1.49") | AIC8800 | `sdio0` | ✅ | ✅ | ✅ | `kmod-aic8800-sdio` |
| HT2 | AIC8800 | `sdio0` | ✅ | ✅ | ✅ | `kmod-aic8800-sdio` |
| H68K a / a-usb | **AP6256** | `sdio0`? | ✅ | ✅ | — | 见下 |
| H68K new | **AIC8800** | `sdio0` | ✅ | ✅ | — | `kmod-aic8800-sdio` |
| H69K / H69K-mini | AIC8800 | `sdio0` | ✅ | ✅ | — | `kmod-aic8800-sdio` |
| **H68K c-d-f / c-d-f-usb** | M.2 位 | — | ❌ | ❌ | ❌ | 无 |
| H66K | — | — | ❌ | ❌ | ❌ | 无 |
| H88K v2/v3 | M.2 位 | — | ❌ | ❌ | ❌ | 无 |

> ⚠️ 表里「M.2 位 / 驱动包 = 无」指的是**板上没有焊死的 WiFi 芯片**
> （走 M.2 / PCIe 扩展位，由用户自行插卡）。**固件里的驱动是全的**（见 §0）：
> M.2/PCIe 位的 `mt7921e` / `mt7925e` / **`mt7915e`（一个驱动同时支持
> MT7915 与 MT7916）** / `mt7615e` / rtw88 / rtw89 全部带上，插卡即可用。
>
> ★ **MT7915 / MT7916 还要额外两个固件包**（`kmod-mt7915-firmware` +
> `kmod-mt7916-firmware`）—— 因为 `kmod-mt7915e` 的 DEPENDS 里**不含固件**。
> 2026-10-12 之前漏装这两个，插 MT7916 会报：
> ```
> Direct firmware load for mediatek/mt7916_wm.bin failed
> ```
> 现在固件里已含 `mt7915_{wa,wm,rom_patch}.bin` 与 `mt7916_{wa,wm,rom_patch}.bin`
> 六个文件（约 3.8 MB 未压缩）。**H69K / H88K / H89K 插 MT7916 就靠这一组。**

### ★ H28K 无WiFi 的厂商证据

厂商 2024 固件 dtb（`vendor-h28x.dtb`）里 `/mmc@ffbf0000` 带 **`no-sdio`** 属性 ——
明确禁用 SDIO。RK3528 的 WiFi 走 sdio0，所以这是厂商自己声明「本机无 WiFi」。
上游 unifreq `rk3528-hlink-h28k.dts` 同样无任何 sdio/wifi 节点，两侧一致。

### ★ H68K c/d 系列无 WiFi

这4 个变体（c / c-usb3 / d / d-usb）的 DTS 里**完全没有 sdio 节点**。
README 的机型表把它们记为「M.2」—— 意思是 WiFi 走 M.2 扩展位，需要用户
自行插模组。**2026-10-10 起改为全系预置**所有可能的无线网卡驱动（M.2/PCIe + SDIO + USB 一起带上），
（AP6256 用 `kmod-brcmfmac`，AIC8800 用 `kmod-aic8800-sdio`）。**2026-10-10 起这些驱动已全部预置在固件里，无需再补。**

### AP6256 vs AIC8800 的代际差异

| | 老机器（2022–2023） | 新机器（2023末–2024） |
|---|---|---|
| 模组 | **AP6256**（Broadcom） | **AIC8800** |
| 驱动 | `kmod-brcmfmac` + 43455 固件/nvram | `kmod-aic8800-sdio`（自带固件） |
| 型号 | a / a-usb | c 系列外的新板、new、h69k 系 |

⚠️ AP6256 用 brcmfmac 驱动，AIC8800 用 aic8800-sdio 驱动，**驱动不通用**。
但自 2026-10-10 起两种驱动（以及 mt76 / rtw88 / rtw89 全家）都预置在固件里，
所以**刷同一块固件即可**，不必先确认自己机器是哪一代。

---

## 四、5G / 4G 模组：供电、复位与**软复位**

本节说明「iStoreOS 同款的启动 5G pin 流程」以及本仓库新增的**软复位**能力。
2026-10-12 两次重写：先修掉三个会让模组完全不工作的 bug，
再把复位脚从 regulator 改为 `rfkill-gpio` —— 这是能软复位的前提。

### 4.1 结构：供电走 regulator，复位走 rfkill-gpio

```
        vcc5v0_sys / vcc_3v3_s3              板级常电
                │
                ▼
        vcc3v3_modem   regulator-fixed, always-on   ← 供电（内核保证上电）
                │                                    ※ H69K 没有这一级（单路）
                ▼
        rfkill-modem   rfkill-gpio                  ← 复位（用户态可控）
                           │
                           └─ /sys/class/rfkill/rfkillN/state    ★ 可写
```

**为什么复位必须交给 `rfkill-gpio`（而不是 regulator）**

`regulator-fixed` 和 `rfkill-gpio` **都会占用**这个 GPIO ——
用户态 `echo N > /sys/class/gpio/export` 必然 `EBUSY`。区别在别处：

| | `regulator-fixed` | `rfkill-gpio` |
|---|---|---|
| 占用 GPIO | ✅ | ✅ |
| 用户态能否控制 | ❌ 无任何接口（`always-on` 还拒绝 disable） | ✅ `/sys/class/rfkill/rfkillN/state` 是 `DEVICE_ATTR_RW` |
| 开机动作 | 内核 `late_initcall_sync` 释放复位一次 | probe（`device_initcall`）时定电平 |
| **软复位** | ❌ | ✅ `echo 0` → `echo 1` |

6.18 `net/rfkill/core.c` 里就是 `static DEVICE_ATTR_RW(state)`；
`state_store()` → `rfkill_set_block()` → `rfkill_gpio_set_power()` →
`gpiod_set_value(reset_gpio, …)`。**不需要装 `rfkill` 命令**（纯 sysfs）。

⇒ 结论：**凡是想要软复位的复位脚，就必须归 `rfkill-gpio`。** 详见 §4.8。

### 4.2 ★★ 极性铁律：`regulator-fixed` 只看 `enable-active-high` ★★

**这一条只对 regulator 适用，对 `rfkill-gpio` 不适用**（见本节末尾对照）。

6.18 的 `drivers/gpio/gpiolib-of.c` 里有一张极性映射表，注释原文：

```
The regulator GPIO handles are specified such that the presence
or absence of "enable-active-high" solely controls the polarity of
the GPIO line. Any phandle flags must be actively ignored.
```

⇒ 对 `regulator-fixed` / `reg-fixed-voltage` / `regulator-gpio` 的
`gpio` / `gpios` 属性：

| 节点里有没有 `enable-active-high` | 实际极性 | 使能时物理电平 |
|---|---|---|
| **有** | 高电平使能 | 高（3.3 V） |
| **无** | 低电平使能 | 低（0 V） |

⚠️ **`gpios = <&gpio4 RK_PC6 GPIO_ACTIVE_HIGH>` 里的 flag 只是装饰**，
内核不读它。H69K 那个 bug 就是这么来的（见 §4.4）。

**对照（重要）**：

* `rfkill-gpio` 的 `reset-gpios` —— 走**常规 gpiod 路径，flag 有效**；
* `gpio-hog` —— flag 也有效；
* 只有上面那三类 regulator compatible 有「忽略 flag」的特殊规则。

### 4.3 逐机型明细（厂商 dtb 逐字段核对）

| 机型 | 供电脚 | 复位脚 | 复位脚极性 | DTS 归属 | 软复位 |
|---|---|---|---|---|---|
| **H29K 全系**<br>(v1.3 / v5-1.14 / v5-1.49) | GPIO4_B5 | GPIO4_B4 | `GPIO_ACTIVE_LOW` | `vcc3v3_modem`(regulator)<br>+ `rfkill-gpio` | ✅ |
| **H69K / H69K-mini** | —（只有一路） | GPIO0_C0 | `GPIO_ACTIVE_LOW` | `rfkill-gpio` 独占 | ✅（= 断电重启） |
| **H88K v2 / v3 / H89K** | GPIO4_A3 | GPIO4_C6 | `GPIO_ACTIVE_HIGH` | `vcc3v3_modem`(regulator)<br>+ `rfkill-gpio` | ✅ |

三组极性**互不相同**：H29K / H69K 低有效，H88K / H89K 高有效。
抄错任意一组，结果都是**模组不上电**。

H69K 只有一路 GPIO，它同时担当「模组供电使能」与「复位释放」——
交给 rfkill 后，`block` 等效于**真正的断电**，这是它独有的好处。

### 4.4 演进记录（三轮改动，每轮都有实证）

| 轮次 | 改什么 | 为什么 |
|---|---|---|
| ① 2026-10-12 上午 | 修**三个 bug**（见下表） | 模组根本不工作 |
| ② 同日 | 统一为「两级 regulator + `vin-supply` 依赖链」 | 保证「先上电、后释放复位」 |
| ③ 同日（当前） | **复位脚从 regulator 改回 `rfkill-gpio`** | regulator 没有任何用户态接口，**无法软复位** |

**① 的三个 bug**：

| # | 机型 | 原状 | 后果 | 现在 |
|---|---|---|---|---|
| 1 | H69K / H69K-mini | `modem_enable` 多写 `enable-active-high` | 按 §4.2 变高电平使能，内核把 GPIO0_C0 拉**高** ⇒ **模组从没被上电过** | 已删该属性 |
| 2 | H29K v5 ×2 | `&gpio4 { modem_reset_en { gpio-hog; output-high; } }` | 与 rfkill 抢同一个脚；语义与厂商相反；写法本身也错（`gpios = <4 RK_PB4 …>` 的 `4` 被当 phandle） | 整块删除 |
| 3 | H29K 全系 | 只有 `rfkill-gpio`（`reset-gpios` + `power-gpios`） | 6.18 的 `rfkill-gpio.c` **只 request `reset` / `shutdown`，没有 `power`** ⇒ 供电脚 GPIO4_B5 从未被驱动 | 供电另交给 `vcc3v3_modem` regulator |

另外两个「`rfkill-gpio` 的属性名」坑（这一轮才知道）：

* 6.18 对 DT 节点读的是 **`label`** / **`radio-type`**，
  厂商 dtb 写的 `name` / `type` **会被忽略**（type 退化成 `RFKILL_TYPE_ALL`，
  按 type 就找不到设备）；
* 厂商 dtb 里的 `power-gpios` 在 6.18 无实现，别照抄。

**③ 的取舍**：放弃了「内核用 `vin-supply` 串死时序」的确定性。
现在复位脚在 `device_initcall`（rfkill probe）就定好工作态，
供电在更晚的 `late_initcall_sync` 才 enable —— 看似「复位先于上电」，
但**模组上电时看到的已经是"不复位"，而且上电自身有 POR 复位**，
所以开机路径依然正确。换来的是**运行时软复位**。

### 4.5 内核侧执行时序

```
内核启动
  ├─ device_initcall      rfkill-gpio probe
  │     → gpiod_direction_output(reset_gpio, true)
  │     → 复位脚进入"工作态"（此后不会把模组保持在复位）
  ├─ ...
  └─ late_initcall_sync   regulator_late_init()
        → 使能 vcc3v3_modem（有这一级的机型）→ 模组上电 → POR 复位
```

以 H29K 为例（复位脚 `GPIO_ACTIVE_LOW`，unblock 时物理低）：

```
                    正常      软复位(手动 block)      正常
复位 GPIO4_B4       低   →        高（保持 300ms）      →   低
                         ↑                          ↑
                  平时一直低              echo 0 / echo 1
```

**实机验证命令**：

```sh
# 1. rfkill 设备在不在（关键）
for d in /sys/class/rfkill/rfkill*; do
  echo "$d: name=$(cat $d/name) type=$(cat $d/type) state=$(cat $d/state)"
done
#    期望：name=rfkill-modem  type=wwan  state=1

# 2. 供电 regulator（H29K / H88K / H89K）
cat /sys/kernel/debug/regulator/regulator_summary | grep -i modem

# 3. 模组是否枚举（正式判据 = 接口结构，见 README「模组识别」一节；
#    下面这条 lsusb 过滤只是人工速查 —— 靠厂名字符串 + 常见 VID，会漏）
lsusb | grep -iE "quectel|fibocom|2cb7|2dee|0e8d"
ls /dev/ttyUSB* /dev/cdc-wdm* 2>/dev/null

# 4. 一键看全部
/etc/init.d/hinlink-modem-hardreset status
```

### 4.6 5G 模组 UART

H29K v5 有 `&uart2`（5G 串口），v1.3 没有。这是 v1.3/v5 的重要区别之一，
详见 README §4.6。

### 4.7 关于那 2 秒延时

原 regulator 版带 `startup-delay-us = 2000000`（上电后等模组稳定）。
改用 `rfkill-gpio` 后**内核侧没有**这个延时（rfkill 无延时机制），
改由 `/etc/init.d/hinlink-modem-hardreset` 在复位后等待
（`HINLINK_MODEM_BOOT_WAIT`，默认 2 s）。
开机路径不依赖它 —— 网络层（modemmanager / proto）本来就有超时重试。

### 4.8 ★ 软复位（2026-10-12 新增）

**底层入口**：`/sys/class/rfkill/rfkillN/state`（可写，需 root / CAP_NET_ADMIN）

```sh
echo 0 > /sys/class/rfkill/rfkill0/state   # 拉复位 / 断电
sleep 0.3
echo 1 > /sys/class/rfkill/rfkill0/state   # 释放 / 上电
```

**① LuCI 页面**：**网络 → 5G复位**
状态（每 5 秒轮询）+ 四个动作按钮（**按操作顺序排**：断电 → 上电 → 软复位 →
仅 USB 重新枚举；「软复位」是「断电 + 等 hold_ms + 上电」的合成）
+ 开机行为配置（`enabled` / `auto_reset` / `hold_ms` / `boot_wait` / `usb_all`）。
后端是 rpcd 插件 `hinlink-modem-hardreset` → `/usr/libexec/hinlink-modem-hardreset`。

**② CLI**（`/etc/init.d/hinlink-modem-hardreset`）—— 注意命令名用**下划线**：
rc.common 会把 `EXTRA_COMMANDS` 的条目当函数名调用，而函数名不能含 `-`。

```sh
/etc/init.d/hinlink-modem-hardreset status        # 人类可读状态
/etc/init.d/hinlink-modem-hardreset reset         # 软复位（拉 hold_ms → 释放 → 等 boot_wait）
/etc/init.d/hinlink-modem-hardreset power_off     # 只拉复位（保持）
/etc/init.d/hinlink-modem-hardreset power_on      # 只释放
/etc/init.d/hinlink-modem-hardreset usb_reset     # 只在 USB 层重新枚举（不碰 pin）
```

**③ 直接调核心脚本**（连字符 / 下划线都接受）：

```sh
/usr/libexec/hinlink-modem-hardreset status-json  # JSON，给脚本 / rpcd 消费
/usr/libexec/hinlink-modem-hardreset reset
/usr/libexec/hinlink-modem-hardreset power-off
/usr/libexec/hinlink-modem-hardreset usb-reset
```

**④ USB 层复位**：`usbreset <vid>:<pid>`（usbutils 自带），
或 `hinlink-modem-hardreset usb-reset`（按**接口结构判据**自动找模组 ——
导出了 ttyUSB*/cdc-wdm*，或有 USB 网卡 + 0xff 接口；不再依赖 VID 白名单）。
与 pin 复位互补 —— 模组固件卡死时 pin 复位更彻底；
只是枚举丢了，USB 重枚举就够。

时序优先级：**环境变量 > UCI > 内置默认值**：
`HINLINK_MODEM_HOLD_MS`（默认 300 ms）、
`HINLINK_MODEM_BOOT_WAIT`（默认 2 s）。

**开机自动复位一次**（可选）：在 `/etc/rc.local` 的 `exit 0` 之前加一行
`/etc/init.d/hinlink-modem-hardreset reset`。

**原理**：`state_store()` → `rfkill_set_block()` → `rfkill_gpio_set_power()`
→ `gpiod_set_value(reset_gpio, 0/1)`。
`0` = soft blocked = 拉复位；`1` = unblocked = 释放。

⚠️ **副作用**：`block` 期间上层（modemmanager / netifd）会看到 wwan 被
block 并停掉相关接口 —— 这正是「复位」应有的语义，`unblock` 后需重新拨号。

⚠️ 排错：
* 写 `state` 报权限错 → 确认是 root；
* 找不到 `type=wwan` 的设备 → 检查 DTS 的 `rfkill-modem` 节点（`label`
  与 `radio-type` 是否写对）以及内核 `CONFIG_RFKILL_GPIO=y`；
* 复位后模组不回来 → 极性可能反了（三个机型族极性不同，见 §4.3），
  用万用表量一下 `block` 前后该脚电平。

#### 日志（2026-10-14 新增，同日改名到 `hinlink-modem-hardreset`）

手动操作、开机检查、以及 **USB / 串口 / 网卡三个层级的上下线**都会被自动捕获，
写进 `/etc/hinlink-modem-hardreset.log`，同一份内容也进 syslog：

```sh
hinlink-modem-hardreset log            # 最近 100 行
hinlink-modem-hardreset log 500        # 最近 500 行
hinlink-modem-hardreset log-clear      # 清空（会追加一条「已清空」记录）
logread | grep hinlink       # syslog 视图
```

**三个层级的 hotplug 各记各的**（时间上也不同步）：

| 子系统 | 目录 | 记录 |
|---|---|---|
| `usb` | `/etc/hotplug.d/usb/` | `模组上线 / 模组下线`（**设备级**，含 vid:pid、总线设备号） |
| `tty` | `/etc/hotplug.d/tty/` | `串口上线 / 串口下线`（**逐口**，`/dev/ttyUSB0…3`） |
| `net` | `/etc/hotplug.d/net/` | `网卡上线 / 网卡下线`（`usb0` / `wwan0`） |

⇒ 一次复位能看到**完整过程**：串口逐个消失 → 网卡消失 → 模组消失
→（约 20 s）→ 模组回来 → 串口逐个回来 → 网卡回来。
**「哪个口没回来」一眼可见** —— 只看设备级事件是做不到这一点的。

★ tty 侧**必须**用 `[ -n "$DEVNAME" ]` 过滤：一次插拔会发 3 类事件
（`ttyUSB0` 的 remove/add、接口级 `DEVNAME=`、`bind`/`unbind`），
只有带 `DEVNAME` 的才是真正的字符设备节点，否则一个口记 3 遍。

LuCI「网络 → 5G复位」页面里也有对应日志区（倒序显示，操作后自动刷新）。
写日志而不是只靠 dmesg 的理由、以及 hotplug 环境变量与 udev 的差异，
见 README §4.20。

⚠️ 日志时间戳直接取系统时钟 —— 实机若没配 NTP / 时区（`date` 一看便知），
记录里的时间会失真。那属于系统层，脚本不做纠正。

### 4.9 时序问答：rfkill 设备会不会「加载太晚、看不到」？

**不会。** 三条依据（都对着 6.18 源码逐条核过）：

1. **`rfkill-gpio` 是内建（`CONFIG_RFKILL_GPIO=y`），不是模块。**
   `module_platform_driver()` → `module_driver()` → `module_init()`；
   内建时 `module_init(x)` 展开成 `__initcall(x)`
   （`include/linux/module.h:89`）→ **`device_initcall`（级别 6）**。

2. **所有 initcall 都在用户态之前跑完。**
   `init/main.c` 的 `kernel_init()` → `kernel_init_freeable()`
   （内含 `do_basic_setup()` → `do_initcalls()`，一路到
   `late_initcall_sync` 级别 7s），之后才 `run_init_process("/sbin/init")`。

3. **OpenWrt 的 preinit / rcS 全在用户态。**
   ⇒ `/etc/init.d/*`、`/etc/rc.local`、以及你 SSH 进去敲的任何命令，
   执行时 `/sys/class/rfkill/rfkillN/` 早就建好了。

**唯一会让它真的"看不到"的情况**：内核把 `CONFIG_RFKILL_GPIO` 改成 `=m`。
那就得等 `kmods` 服务加载，而 OpenWrt 的 kmods 时机可能晚于 `START=95`。

⇒ **本仓库把这个依赖写死在内核 config 里**：
`target/linux/rockchip/hinlink-config.append` 里有
`CONFIG_RFKILL=y` + `CONFIG_RFKILL_GPIO=y`，不依赖上游 rockchip
`config-6.18` 那两行（那两行虽然也是 `=y`，但属上游、可能被改）。

**双保险**：`hinlink-modem-hardreset` 的 `start()` 里有 **5 秒重试窗口**
（`sleep 0.5` × 10）；仍然等不到就往 syslog 打警告，并附上
`dmesg | grep -i rfkill` 的尾部 —— 一眼能区分「DTS 写错」还是「驱动没编」。

**排查过的其它「看不到」可能**（都不成立）：

| 场景 | 结论 |
|---|---|
| probe defer（gpio controller 未就绪） | 不会 —— rockchip gpio 在 `postcore/subsys_initcall` 就绪，早于 rfkill 的 `device_initcall` |
| rfkill 编号不是 0（可能被别的设备占号） | 不影响 —— `hinlink-modem-hardreset` 按 `type=wwan` 查找，**不写死** `rfkillN` |
| 系统里有多个 wwan rfkill | 不会 —— 各机型 DTS 只定义 1 个 |
| `/sys` 未挂载 | 不会 —— preinit 阶段已 mount |

⚠️ **顺带一个真实的风险（不是时序问题）**：
H69K 只有**一路** GPIO，现在它是 `rfkill-gpio` 管的 —— 也就是说
**模组的「供电使能」也依赖这个驱动成功 probe**。若 DT 写错或驱动缺失，
模组会连电都没有（原来 regulator `always-on` 是内核保证的）。
所以 H69K 刷机后第一件事建议先跑
`/etc/init.d/hinlink-modem-hardreset status` 确认 `name=rfkill-modem` 在。

---

## 五、SARADC（电池电压）

| 机型 | SARADC | 用途 | 依赖 |
|---|---|---|---|
| **H29K v5** | ch1 (`adc-battery@0`) | 电池电压检测 | ⚠️ **依赖 patch** |
| H29K v1.3 | 无 | — | — |
| 其他机型 | 见各 DTS | — | — |

✅ **不需要 patch** —— Linux 6.18 上游已原生支持 rk3528 SARADC：

```
# drivers/iio/adc/rockchip_saradc.c（6.18 原生）
static const struct iio_chan_spec rockchip_rk3528_saradc_iio_channels[] = {
	SARADC_CHANNEL(0, "adc0", 10), ... SARADC_CHANNEL(3, "adc3", 10),
};
static const struct rockchip_saradc_data rk3528_saradc_data = { ... };
/* of_match_table 里 */ { .compatible = "rockchip,rk3528-saradc", .data = &rk3528_saradc_data, },

# arch/arm64/boot/dts/rockchip/rk3528.dtsi（6.18 原生）
saradc: saradc@ff300000 { compatible = "rockchip,rk3528-saradc"; ... }
```

本仓库早期带的 `9527-rockchip-rk3528-iio-add-adc.patch` 已**删除**（上游已合入）。
只需装 `kmod-iio-adc-rk3528` 让用户态能读。

---

## 六、其他

### LED

各机型 LED 定义见 `target/linux/rockchip/armv8/base-files/etc/board.d/01_leds`。
DTS 里的 `leds` 节点给出引脚，`01_leds` 补netdev / heartbeat 触发规则。

### 按键

- H28K：`adc-keys` on SARADC ch0（KEY_SETUP = BOOT）
- H68K 系列：`gpio-keys` on GPIO0_A0（factory / KEY_RESTART）

### 内核 patch 清单

| patch | 用途 | 必需性 |
|---|---|---|
| `9999-fbtft-read-display-offset-from-dt.patch` | 从 DT 读显示偏移 | H29K 1.14" / H89K 必需 |
| ~~`9527-...-iio-add-adc.patch`~~ | ~~加 rk3528 SARADC 驱动~~ | ❌ **已删除** —— 6.18 上游已原生支持 |
| `9528-linux-delfbcon-cursor.patch` | 禁 framebuffer 硬件光标 | 建议（SPI 小屏上光标会显示异常） |
| `9530-fbtft-add-gc9307-driver.patch` | **新增 GC9307 fbtft 驱动**（主线没有）+ Kconfig/Makefile 条目 | H29K v5 1.49" 必需 |

---

## 七、汇总：待确认清单

| # | 项目 | 机型 | 说明 |
|---|---|---|---|
| 1 | **风扇配置** | H89K | pwm3 已使能但无 `pwm-fan` 节点，风扇不会自动调速 |
| 2 | **1.49" 屏偏移** | H29K v5 1.49" | 原厂未提供偏移 patch，172×320 的偏移量未知 |
| 3 | **H89K 屏偏移** | H89K | 40/52 是从 H29K 1.14" 推断的，需实机确认画面完整 |
| 4 | **H89K 背光** | H89K | 厂商 dtb 里无背光节点（屏可能常亮），未配置 |
| 5 | **rfkill** | H69K / H89K | 无软关机节点，是否需要待定 |
| 6 | ~~**WiFi 代际**~~ | ~~H68K a 系列~~ | ✅ **已解决**：2026-10-10 起固件全系预置 brcmfmac + aic8800 + mt76/rtw88/rtw89 所有驱动 |
| 7 | ~~**M.2 WiFi**~~ | ~~H68K c/d / H88K~~ | ✅ **已解决**：同上，M.2/PCIe 侧 mt7921e/mt7925e/mt7915e/mt7615e/rtw88/rtw89 全部预置 |
| 8 | **CPU 降频** | H69K / H69K-mini | 风扇 cooling-maps 覆盖了内核原有的 CPU_FREQ 映射，需合并才能兼得 |
| 9 | **风扇实测** | H69K / H69K-mini | 9 档 duty 与 4 档温度曲线均取自 iStoreOS，未上机验证转速与噪音 |
| 10 | **AXS5106 触控** | H29K v5 1.49" | 主线无 `chipone,axs5106` 驱动（连 fbtft 的 gc9307 都是本仓库新加的），触控暂不可用 |
| 11 | **GC9307 初始化** | H29K v5 1.49" | `fb_gc9307` 由 `fb_st7789v.c` 派生、init 序列沿用 ST7789V，172×320 实际显示需实机确认 |
