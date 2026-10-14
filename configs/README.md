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

## 自带驱动

每份 config 都默认编入：MT7921 / MT7922 / **MT7925** / MT7915 / **MT7916** /
**NFA765（ath11k / WCN6855）** / AIC8800 的驱动与固件，以及
`package/beaverfffan` 下的风扇温控、5G 复位、SSD1306 OLED 三个 LuCI 应用。

> ⚠️ **驱动 ≠ 固件**：`kmod-mt7915e` 一个驱动同时支持 MT7915 与 MT7916，
> 但固件是两个独立包且**不在驱动的 DEPENDS 里**；MT7925 同理（光有
> `-common` 不够，必须有 `-firmware`）。这些 config 里都已经带上了。
