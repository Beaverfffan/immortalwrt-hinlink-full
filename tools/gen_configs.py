#!/usr/bin/env python3
"""从全机型 .config 生成 16 份**单机型** config。

思路
----
不使用「手写一份最小 .config 再让 OpenWrt 补」的路子：那样 target 默认值
里没有 luci、也没有一堆无线驱动，补出来是残的。

这里反过来：拿**已经在用、且编过固件**的全机型 .config 当底稿 —— 它已经
包含 luci、所有无线 kmod/firmware、以及全部功能包选择 —— 然后

  1. 把 `CONFIG_TARGET_DEVICE_rockchip_armv8_DEVICE_*` 收敛成只留一个；
  2. 追加本固件要求「自带」的驱动与 beaverfffan 插件；
  3. 交给 `make defconfig` 去收敛/补依赖，再把结果写回 configs/<机型>.config。

第 3 步是关键：defconfig 之后的 .config 才是 OpenWrt 真正认可的完整配置，
用户 clone 下来 `cp configs/x.config .config && make defconfig && make -j`
不会因为缺项而弹交互提问（非交互构建会直接失败）。

同时脚本会检查追加的包在 defconfig 后**是否还在** —— 包名写错、依赖不满足
或包不存在时 defconfig 会静默丢弃那一行，这是最容易漏的坑。

用法（在内核树根目录跑）：
    python3 tools/gen_configs.py [内核树路径]
"""
import os
import re
import shutil
import subprocess
import sys

TREE = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/iwrt-hinlink-full")
SRC = os.path.join(TREE, ".config")
OUT = os.path.join(TREE, "configs")

PREFIX = "CONFIG_TARGET_DEVICE_rockchip_armv8_DEVICE_"

# (configs/ 里的文件名, OpenWrt DEVICE 名)
DEVICES = [
    ("h28k",           "hinlink_h28k_rk3528"),
    ("h29k-v1.3-1.14", "hinlink_h29k-v1.3-1.14_rk3528"),
    ("h29k-v5-1.14",   "hinlink_h29k-v5-1.14_rk3528"),
    ("h29k-v5-1.49",   "hinlink_h29k-v5-1.49_rk3528"),
    ("ht2",            "hinlink_opc-ht2_rk3528"),
    ("h66k",           "hinlink_opc-h66k"),
    ("h68k-a-b",       "hinlink_opc-h68k-a-b"),
    ("h68k-a-b-usb",   "hinlink_opc-h68k-a-b-usb"),
    ("h68k-c-d-f",     "hinlink_opc-h68k-c-d-f"),
    ("h68k-c-d-f-usb", "hinlink_opc-h68k-c-d-f-usb"),
    ("h68k-new",       "hinlink_opc-h68k-new"),
    ("h69k",           "hinlink_opc-h69k"),
    ("h69k-mini",      "hinlink_opc-h69k-mini"),
    ("h88k-v2",        "hinlink_h88k_v2"),
    ("h88k-v3",        "hinlink_h88k_v3"),
    ("h89k",           "hinlink_opc-h89k_rk3588"),
]

# 本固件要求「自带」的无线驱动（用户 2026-10-14 指定）
#   7921 -> kmod-mt7921e/s/u + kmod-mt7921-firmware     （底稿里已有）
#   7922 -> kmod-mt7922-firmware（共用 mt7921e 驱动）    （底稿里已有）
#   7916 -> kmod-mt7915e + kmod-mt7916-firmware          （底稿里已有）
#   aic8800 -> kmod-aic8800-{pcie,sdio,usb}              （底稿里已有）
#   7925 / nfa765 底稿里是缺的，必须在这里补：
#     7925 只有 -common，firmware 没选 → 会 "Direct firmware load failed"
#     nfa765 = QCNFA765/WCN6855，走 ath11k，底稿里 ath11k 整个是 not set
EXTRA_COMMON = """
# ---- HinLink 固件自带驱动/插件（由 tools/gen_configs.py 追加）----
CONFIG_PACKAGE_kmod-mt7925e=y
CONFIG_PACKAGE_kmod-mt7925-firmware=y
CONFIG_PACKAGE_kmod-ath11k=y
CONFIG_PACKAGE_kmod-ath11k-pci=y
CONFIG_PACKAGE_ath11k-firmware-wcn6855=y
CONFIG_PACKAGE_luci-app-fancontrol=y
CONFIG_PACKAGE_fancontrol=y
CONFIG_PACKAGE_luci-app-oled=y
"""

# ★ 5G 复位面板只编进「**有风扇 且 有 5G 复位脚**」的机型（用户 2026-10-14 指定）。
#
# 硬件能力表是 2026-10-14 从 DTS 里逐个 grep 出来的，别再凭印象改：
#   有风扇（pwm-fan 节点）：
#     h69k / h69k-mini      —— 各自 dts 里的 pwm-fan（PWM0 绑 cpu_thermal）
#     h88k-v2 / h88k-v3 / h89k —— 三者都 #include "rk3588-hinlink.dtsi"，
#                                风扇节点在 dtsi 里（pwm14，5 档 cooling-levels）
#   有 5G 复位脚（rfkill-gpio）：
#     h29k 全系 3 个         —— GPIO4_B4 复位（低有效）+ GPIO4_B5 供电
#     h69k / h69k-mini      —— GPIO0_C0（单路，低有效）
#     h88k-v2 / h88k-v3 / h89k —— GPIO4_C6 复位（高有效），定义在 rk3588-hinlink.dtsi
#   交集 = 下面 5 个。
#
# ⚠️ h29k 全系**有 5G 复位脚但没有风扇**，按该条件被排除 —— 如果也要给它们编，
#    把 short 名加进 MODEM_APP 即可（DTS 里确实定义了 rfkill-gpio）。
HAS_FAN = {"h69k", "h69k-mini", "h88k-v2", "h88k-v3", "h89k"}
HAS_MODEM = {"h29k-v1.3-1.14", "h29k-v5-1.14", "h29k-v5-1.49",
             "h69k", "h69k-mini", "h88k-v2", "h88k-v3", "h89k"}
MODEM_APP = sorted(HAS_FAN & HAS_MODEM)

MODEM_APP_ON = "CONFIG_PACKAGE_luci-app-hinlink-modem-hardreset=y\n"
MODEM_APP_OFF = "# CONFIG_PACKAGE_luci-app-hinlink-modem-hardreset is not set\n"

# defconfig 之后必须仍然存在的包（丢了就是包名错/依赖不满足）
MUST_KEEP_COMMON = [
    "kmod-mt7921e", "kmod-mt7921-firmware",
    "kmod-mt7922-firmware",
    "kmod-mt7915e", "kmod-mt7916-firmware",
    "kmod-mt7925e", "kmod-mt7925-firmware",
    "kmod-ath11k", "kmod-ath11k-pci", "ath11k-firmware-wcn6855",
    "kmod-aic8800-pcie", "kmod-aic8800-sdio", "kmod-aic8800-usb",
    "luci-app-fancontrol", "fancontrol", "luci-app-oled",
]


def make_single(base, dev, short):
    """把全机型 .config 收敛成 dev 单机型（short 用于决定选哪些插件）。"""
    out = []
    for ln in base.splitlines():
        if PREFIX in ln:
            m = re.search(re.escape(PREFIX) + r'([^\s=]+)', ln)
            if not m:
                continue
            name = m.group(1)
            if name == dev:
                out.append("%s%s=y" % (PREFIX, name))
            else:
                out.append("# %s%s is not set" % (PREFIX, name))
        elif ln.startswith("CONFIG_TARGET_PROFILE="):
            continue                      # 统一在末尾重设
        else:
            out.append(ln)

    # 单机型：显式钉住 profile（defconfig 会据此校正 MULTI_PROFILE 等派生项）
    out.append('CONFIG_TARGET_PROFILE="DEVICE_%s"' % dev)
    out.append("# CONFIG_TARGET_PER_DEVICE_ROOTFS is not set")
    out.append(EXTRA_COMMON)
    # 5G 复位面板：只有「有风扇 且 有 5G 复位脚」的机型才编
    out.append(MODEM_APP_ON if short in MODEM_APP else MODEM_APP_OFF)
    return "\n".join(out) + "\n"


def main():
    if not os.path.isfile(SRC):
        sys.exit("找不到底稿 %s" % SRC)
    base = open(SRC, encoding="utf-8").read()
    os.makedirs(OUT, exist_ok=True)

    defconfig = os.path.join(TREE, ".config")
    ok = fail = 0
    print("5G 复位面板只编入（有风扇 且 有 5G 复位脚）：%s\n" % " ".join(MODEM_APP))
    for short, dev in DEVICES:
        p = os.path.join(OUT, short + ".config")
        open(p, "w", encoding="utf-8", newline="\n").write(
            make_single(base, dev, short))
        shutil.copy(p, defconfig)

        r = subprocess.run(["make", "defconfig"], cwd=TREE,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           universal_newlines=True)
        if r.returncode != 0:
            print("!! %-16s defconfig 失败" % short)
            print((r.stdout or "")[-1500:])
            fail += 1
            continue

        shutil.copy(defconfig, p)
        after = open(p, encoding="utf-8").read()

        must = list(MUST_KEEP_COMMON)
        if short in MODEM_APP:
            must.append("luci-app-hinlink-modem-hardreset")
        miss = [k for k in must if ("CONFIG_PACKAGE_%s=y" % k) not in after]
        # 反向检查：不该选的机型别被别处（比如底稿）带进来
        if short not in MODEM_APP and \
                "CONFIG_PACKAGE_luci-app-hinlink-modem-hardreset=y" in after:
            miss.append("!(误选)5G复位面板")

        got = re.search(re.escape(PREFIX) + r'([^\s=]+)=y', after)
        profile = re.search(r'^CONFIG_TARGET_PROFILE="?([^"\n]+)"?', after, re.M)

        apps = "5G复位" if short in MODEM_APP else "-"
        tag = "OK"
        if miss:
            tag = "缺包(%d)" % len(miss)
        if not got or got.group(1) != dev:
            tag = "机型不符!"
            fail += 1
        elif miss:
            fail += 1
        else:
            ok += 1

        print("%-16s %-11s 5G面板=%-7s lines=%-5d device=%s"
              % (short, tag, apps, len(after.splitlines()),
                 got.group(1) if got else "?"))
        if miss:
            print("                 缺失: %s" % " ".join(miss))

    print("\n完成：%d 成功 / %d 有问题" % (ok, fail))


if __name__ == "__main__":
    main()
