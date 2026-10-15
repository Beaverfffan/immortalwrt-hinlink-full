# configs/ —— 每个机型一份 defconfig

选一个机型，拷成 `.config`，然后 `make defconfig && make -j$(nproc)`。
**不要**手改这些文件里的 `CONFIG_TARGET_DEVICE_*`，那会让 profile 与
机型不匹配。

| config | 机型 | SoC | 网口 | 板载 WiFi | 5G 复位 | 说明 |
|---|---|---|---|---|---|---|
| `h66k.config` | H66K | RK3568 | 2 | 无板载 WiFi | — | [H66K](../docs/devices/h66k.md) |
| `h68k-a-b.config` | H68K A/B 板 | RK3568 | 2 | AP6256 | — | [H68K A/B 板](../docs/devices/h68k-a-b.md) |
| `h68k-a-b-usb.config` | H68K A/B 板（USB3.0 版） | RK3568 | 2 | AP6256 | — | [H68K A/B 板（USB3.0 版）](../docs/devices/h68k-a-b-usb.md) |
| `h68k-c-d-f.config` | H68K C/D/F 板 | RK3568 | 4 | 无板载 WiFi | — | [H68K C/D/F 板](../docs/devices/h68k-c-d-f.md) |
| `h68k-c-d-f-usb.config` | H68K C/D/F 板（USB3.0 版） | RK3568 | 4 | 无板载 WiFi | — | [H68K C/D/F 板（USB3.0 版）](../docs/devices/h68k-c-d-f-usb.md) |
| `h68k-new.config` | H68K（新板） | RK3568 | 4 | AIC8800 | — | [H68K（新板）](../docs/devices/h68k-new.md) |
| `h69k.config` | H69K | RK3568 | 3 | AIC8800 | ✅ | [H69K](../docs/devices/h69k.md) |
| `h69k-mini.config` | H69K mini（= H68K max） | RK3568 | 4 | AIC8800 | ✅ | [H69K mini（= H68K max）](../docs/devices/h69k-mini.md) |
| `h28k.config` | H28K | RK3528 | 2 | 无板载 WiFi —— 厂商 dtb 里 `/mmc@ffbf0000` 带 `no-sdio` 属性，明确禁用 SDIO | — | [H28K](../docs/devices/h28k.md) |
| `h29k-v1.3-1.14.config` | H29K v1.3（1.14″ 屏） | RK3528 | 1 | SDIO WiFi | ✅ | [H29K v1.3（1.14″ 屏）](../docs/devices/h29k-v1.3-1.14.md) |
| `h29k-v5-1.14.config` | H29K v5（1.14″ 屏） | RK3528 | 1 | SDIO WiFi | ✅ | [H29K v5（1.14″ 屏）](../docs/devices/h29k-v5-1.14.md) |
| `h29k-v5-1.49.config` | H29K v5（1.49″ 触屏） | RK3528 | 1 | SDIO WiFi | ✅ | [H29K v5（1.49″ 触屏）](../docs/devices/h29k-v5-1.49.md) |
| `ht2.config` | HT2 | RK3528 | 1 | SDIO WiFi | — | [HT2](../docs/devices/ht2.md) |
| `h88k-v2.config` | H88K v2 | RK3588 | 2 | 无板载 WiFi | ✅ | [H88K v2](../docs/devices/h88k-v2.md) |
| `h88k-v3.config` | H88K v3 | RK3588 | 3 | 无板载 WiFi | ✅ | [H88K v3](../docs/devices/h88k-v3.md) |
| `h89k.config` | H89K | RK3588 | 3 | 无板载 WiFi | ✅ | [H89K](../docs/devices/h89k.md) |

## 关于「一机型一 config」

这些 config 是**完整可用**的 defconfig：从一份已编过固件的全机型配置收敛而
来，并且每一份都跑过 `make defconfig` 验证 —— 追加的驱动与插件在收敛后
仍然存在（`tools/gen_configs.py` 会逐个检查这一点）。所以拿到手选一个就行，
不会因为缺项在非交互构建里直接失败。

**想一次编全部 16 个机型**：不要用这些单机型 config，直接用多机型 profile ——
在 `make menuconfig` 里把 `Target Profile` 切到 `Multi Profile`，
再勾选全部 `HinLink` 机型即可（`CONFIG_TARGET_MULTI_PROFILE=y` +
一串 `CONFIG_TARGET_DEVICE_rockchip_armv8_DEVICE_*=y`）。

## 自带驱动与插件

每份 config 都默认编入：MT7921 / MT7922 / **MT7925** / MT7915 / **MT7916** /
**NFA765（ath11k / WCN6855）** / AIC8800 的驱动与固件，以及 SSD1306 OLED 面板
（`luci-app-oled`，外接 I2C 屏，任何机型都能接）。

另外两个是**按硬件选装**的（不是所有机型都有）：

| 插件 | 选装条件 | 机型 |
|---|---|---|
| **风扇温控** `luci-app-fancontrol` + `fancontrol` | **有风扇**（DTS 里有 `pwm-fan` 节点） | h69k、h69k-mini、h88k-v2、h88k-v3、h89k |
| **5G 复位面板** `luci-app-hinlink-modem-hardreset` | **有 5G 复位脚**（DTS 里有 `rfkill-gpio` 节点） | 上面 5 个 **+ h29k-v1.3-1.14、h29k-v5-1.14、h29k-v5-1.49** |

> 两个条件**互相独立**：有风扇就编风扇，有复位脚就编面板。
> H29K 全系有复位脚但没有风扇，所以只有 5G 面板、没有风扇插件。

> ⚠️ **驱动 ≠ 固件**：`kmod-mt7915e` 一个驱动同时支持 MT7915 与 MT7916，
> 但固件是两个独立包且**不在驱动的 DEPENDS 里**；MT7925 同理（光有
> `-common` 不够，必须有 `-firmware`）。这些 config 里都已经带上了。

## 与 Release 固件的差异

本目录是**标准配置**：分区 **16 / 160**，**不含** passwall / openclash / ttyd / upnp。

[Releases](../../releases) 里的固件额外注入了 **128 MB / 1024 MB 分区**和
上面四个应用（全部 16 个机型都有）。想编出与 Release 相同的固件：

```sh
python3 tools/gen_release_cfg.py                        # 生成 configs-release/
CFGDIR=configs-release sh tools/build_single.sh         # 用它编译
```
