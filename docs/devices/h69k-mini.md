# H69K mini（= H68K max）（RK3568）

> 本文对应 `configs/h69k-mini.config`。通用编译 / 刷机步骤见仓库根
> [README](../../README.md)；底层硬件机理见 [docs/HARDWARE.md](../HARDWARE.md)。

## 编译

```sh
git clone https://github.com/Beaverfffan/immortalwrt-hinlink-full.git
cd immortalwrt-hinlink-full
./scripts/feeds update -a && ./scripts/feeds install -a
cp configs/h69k-mini.config .config
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
| 5G 模组复位 | **支持** —— 复位脚 `GPIO0_C0`（低有效，单路） |

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

本机型有 5G 复位能力，控制面板在 **网络 → 5G复位**：

| 动作 | 实际行为 |
|---|---|
| 断电 | 只拉复位脚并保持（H69K 系单路机型的 `rfkill` 同时管使能，等于真断电） |
| 上电 | 只释放复位脚 |
| 软复位 | 断电 → 等 `hold_ms`（默认 300 ms）→ 上电 |
| 仅 USB 重新枚举 | 不碰复位脚，只让 USB 层重新枚举模组 |

底层等价于 `echo 0 > /sys/class/rfkill/rfkillN/state`，等一会儿，再 `echo 1`。
模组识别按**接口结构判据**（不看 VID），换别家模组不需要改代码。


## 注意事项

- 名字叫 H69K mini，实际是四网口的 H68K max；WAN 与 `h68k-new` 一样在 `gmac1`（=`eth1`）。
