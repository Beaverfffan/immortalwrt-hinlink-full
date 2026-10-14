# H68K A/B 板（USB3.0 版）（RK3568）

> 本文对应 `configs/h68k-a-b-usb.config`。通用编译 / 刷机步骤见仓库根
> [README](../../README.md)；底层硬件机理见 [docs/HARDWARE.md](../HARDWARE.md)。

## 编译

```sh
git clone https://github.com/Beaverfffan/immortalwrt-hinlink-full.git
cd immortalwrt-hinlink-full
./scripts/feeds update -a && ./scripts/feeds install -a
cp configs/h68k-a-b-usb.config .config
make defconfig
make -j$(nproc) download && make -j$(nproc)
```

产物在 `bin/targets/rockchip/armv8/`：`*squashfs-sysupgrade.img.gz`（日常系统升级）、
`*ext4-sysupgrade.img.gz`（ext4 版）。

## 硬件

| 项 | 值 |
|---|---|
| SoC | RK3568 |
| 网口 | 2 个 —— 2×GMAC（板载千兆） |
| 板载 WiFi | **AP6256**（Broadcom，SDIO） |
| 存储 | USB3.0 |
| 屏幕 | 无 |
| 5G 模组复位 | 不支持（无 5G 接口） |

## 网口映射（DTS 里写死，不做运行时探测）

| 接口 | 角色 |
|---|---|
| `eth0` | **WAN** |
| `eth1` | LAN |

> WAN 口的判据是「WAN 焊在哪颗 GMAC 上」，不是「机器有几个口」——
> 具体到本机型的依据见下面注意事项。

## 5G 模组

本机型 DTS 未定义 `rfkill-gpio`，也没有 5G 接口 ⇒
5G 面板会显示「未找到 type=wwan 的 rfkill 设备」，这是**正常的**，
不是故障。要外接 5G 模组的话，供电与复位需要改 DTS 加上对应节点。


## 注意事项

- 与 `h68k-a-b` 的唯一差别：本机型关闭 `sata0`、放开 USB3.0。
