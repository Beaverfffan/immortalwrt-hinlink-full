# HT2（RK3528）

> 本文对应 `configs/ht2.config`。通用编译 / 刷机步骤见仓库根
> [README](../../README.md)；底层硬件机理见 [docs/HARDWARE.md](../HARDWARE.md)。

## 编译

```sh
git clone https://github.com/Beaverfffan/immortalwrt-hinlink-full.git
cd immortalwrt-hinlink-full
./scripts/feeds update -a && ./scripts/feeds install -a
cp configs/ht2.config .config
make defconfig
make -j$(nproc) download && make -j$(nproc)
```

产物在 `bin/targets/rockchip/armv8/`：`*squashfs-sysupgrade.img.gz`（日常系统升级）、
`*ext4-sysupgrade.img.gz`（ext4 版）。

## 硬件

| 项 | 值 |
|---|---|
| SoC | RK3528 |
| 网口 | 1 个 —— 板载 RGMII（单口） |
| 板载 WiFi | SDIO WiFi（**SDR50**，比 H29K 的 SDR104 慢一档） |
| 存储 | — |
| 屏幕 | 无 |
| 5G 模组复位 | **不支持** —— DTS 注释明写「无 4G/5G LED 与 rfkill（H29K 才有）」 |

## 网口映射（DTS 里写死，不做运行时探测）

| 接口 | 角色 |
|---|---|
| `eth0` | **WAN / LAN（单网口）** |

> WAN 口的判据是「WAN 焊在哪颗 GMAC 上」，不是「机器有几个口」——
> 具体到本机型的依据见下面注意事项。

## 5G 模组

本机型 DTS 未定义 `rfkill-gpio`，也没有 5G 接口 ⇒
5G 面板会显示「未找到 type=wwan 的 rfkill 设备」，这是**正常的**，
不是故障。要外接 5G 模组的话，供电与复位需要改 DTS 加上对应节点。


## 注意事项

- 与 H29K 同源但精简：单网口、无屏、SDIO 最高只到 SDR50，也没有 5G 相关的 LED 与复位脚。
