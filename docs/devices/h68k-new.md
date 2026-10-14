# H68K（新板）（RK3568）

> 本文对应 `configs/h68k-new.config`。通用编译 / 刷机步骤见仓库根
> [README](../../README.md)；底层硬件机理见 [docs/HARDWARE.md](../HARDWARE.md)。

## 编译

```sh
git clone https://github.com/Beaverfffan/immortalwrt-hinlink-full.git
cd immortalwrt-hinlink-full
./scripts/feeds update -a && ./scripts/feeds install -a
cp configs/h68k-new.config .config
make defconfig
make -j$(nproc) download && make -j$(nproc)
```

产物在 `bin/targets/rockchip/armv8/`：`*squashfs-sysupgrade.img.gz`（日常系统升级）、
`*ext4-sysupgrade.img.gz`（ext4 版）。

## 硬件

| 项 | 值 |
|---|---|
| SoC | RK3568 |
| 网口 | 4 个 —— 2×GMAC + 2×RTL8125（PCIe） |
| 板载 WiFi | **AIC8800**（SDIO） |
| 存储 | USB3.0 + SATA |
| 屏幕 | 无 |
| 5G 模组复位 | 不支持（无 5G 接口） |

## 网口映射（DTS 里写死，不做运行时探测）

| 接口 | 角色 |
|---|---|
| `eth0` | LAN |
| `eth1` | **WAN** |
| `eth2` | LAN |
| `eth3` | LAN |

> WAN 口的判据是「WAN 焊在哪颗 GMAC 上」，不是「机器有几个口」——
> 具体到本机型的依据见下面注意事项。

## 5G 模组

本机型 DTS 未定义 `rfkill-gpio`，也没有 5G 接口 ⇒
5G 面板会显示「未找到 type=wwan 的 rfkill 设备」，这是**正常的**，
不是故障。要外接 5G 模组的话，供电与复位需要改 DTS 加上对应节点。


## 注意事项

- 2023 年末~2024 的新一代：板载 WiFi 从 AP6256 换成 **AIC8800**，并且 **WAN 从 gmac0 挪到了 gmac1** —— 所以 WAN 是 `eth1` 而不是 `eth0`（老一代正好相反）。
- 同一个 H68K 名字下这两代的 WAN 口不同，刷机前务必看清机型。
