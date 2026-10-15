#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从**标准** `configs/` 生成**发行版专用**配置（`configs-release/`）。

为什么单独一个脚本、而不是改 gen_configs.py
--------------------------------------------
用户 2026-10-14 明确：

> 「不要更新 configs，这个只是编译发行版用的」

即「分区放大到 128/1024 + 打包 passwall/openclash/ttyd/upnp」这组改动
**只服务于发行版固件**，仓库里的标准 `configs/` 必须保持原样
（16/160、不带四件套）。所以职责拆开：

  · `tools/gen_configs.py`     -> 生成**标准** configs（仓库里那一份，不变）
  · `tools/gen_release_cfg.py` -> 在标准 configs 基础上**注入**发行版改动

注入内容
--------
1. 分区：
     CONFIG_TARGET_KERNEL_PARTSIZE=128
     CONFIG_TARGET_ROOTFS_PARTSIZE=1024
   ★ 这两个值**只影响镜像生成**（分区表 + padding），不参与任何 C 编译，
     所以改了不会引起重编。放大原因：passwall/openclash 的依赖
     （xray-core / sing-box / ruby）在 160 MB rootfs 里放不下。
2. 四个应用（**全部机型**）：luci-app-passwall / -openclash / -ttyd / -upnp
   + passwall 的 8 个 `INCLUDE_*` 子选项（默认值各版本不一，必须显式钉住，
     否则可能得到不带 xray/sing-box 的残缺包）。
   openclash 需要的 kmod（kmod-tun / kmod-inet-diag / kmod-nft-tproxy /
   kmod-nft-socket）由 defconfig 自动 select。

用法（在内核树根目录执行）
--------------------------
    python3 tools/gen_release_cfg.py             # 只生成，不跑 defconfig
    python3 tools/gen_release_cfg.py --check     # 逐份 make defconfig 验证
    python3 tools/gen_release_cfg.py --out DIR   # 指定输出目录
    python3 tools/gen_release_cfg.py --nas --check   # 叠加 NAS/Docker 套件
                                                     # -> configs-release-nas/

生成的 `configs-release/<机型>.config` 供 `tools/build_single.sh` 使用：
    CFGDIR=configs-release sh tools/build_single.sh
"""
import os
import re
import shutil
import subprocess
import sys

TREE = os.getcwd()
SRC_DIR = os.path.join(TREE, "configs")
PREFIX = "CONFIG_TARGET_DEVICE_rockchip_armv8_DEVICE_"

KERNEL_PARTSIZE = 128
ROOTFS_PARTSIZE = 1024

INJECT = """
# ---- 发行版注入（由 tools/gen_release_cfg.py 追加；**不进仓库 configs**）----
# 分区：只影响镜像生成（分区表 + padding），不参与 C 编译
CONFIG_TARGET_KERNEL_PARTSIZE=%(kp)d
CONFIG_TARGET_ROOTFS_PARTSIZE=%(rp)d
# 四件套（全部机型）
CONFIG_PACKAGE_luci-app-passwall=y
CONFIG_PACKAGE_luci-app-openclash=y
CONFIG_PACKAGE_luci-app-ttyd=y
CONFIG_PACKAGE_luci-app-upnp=y
# passwall 功能子选项：显式钉住（默认值各版本不一）
CONFIG_PACKAGE_luci-app-passwall_INCLUDE_Haproxy=y
CONFIG_PACKAGE_luci-app-passwall_INCLUDE_Shadowsocks_Rust_Client=y
CONFIG_PACKAGE_luci-app-passwall_INCLUDE_Shadowsocks_Rust_Server=y
CONFIG_PACKAGE_luci-app-passwall_INCLUDE_Simple_Obfs=y
CONFIG_PACKAGE_luci-app-passwall_INCLUDE_SingBox=y
CONFIG_PACKAGE_luci-app-passwall_INCLUDE_V2ray_Geoview=y
CONFIG_PACKAGE_luci-app-passwall_INCLUDE_V2ray_Plugin=y
CONFIG_PACKAGE_luci-app-passwall_INCLUDE_Xray=y
""" % {"kp": KERNEL_PARTSIZE, "rp": ROOTFS_PARTSIZE}

# ── 可选的额外包集合（--nas）──────────────────────────────────────────
# 用户 2026-10-15：「再出一个带 luci-app-diskman / luci-app-samba4 /
# luci-app-dockerman / docker 的固件，放在另外一个 release」。
# 经确认：**叠加**在现有发行版之上（四件套保留）、rootfs 仍 1024 MB、16 机型全编。
#
# 四个包都在官方 feeds 里：
#   feeds/luci/applications/{luci-app-diskman,luci-app-samba4,luci-app-dockerman}
#   feeds/packages/utils/{docker,dockerd,docker-compose}
# docker 的依赖（kmod-veth / kmod-br-netfilter / kmod-ip6tables …）由 defconfig
# 自动 select。内核侧 CGROUPS / NAMESPACES / OVERLAY_FS 已具备，只有 **VETH 需要
# 新开** ⇒ 会触发一次内核重编（这是加入 docker 的主要代价）。
NAS_EXTRA = """
# ---- NAS / Docker 套件（--nas 时追加）----
CONFIG_PACKAGE_luci-app-diskman=y
CONFIG_PACKAGE_luci-app-samba4=y
CONFIG_PACKAGE_luci-app-dockerman=y
CONFIG_PACKAGE_docker=y
"""

# defconfig 之后必须仍然存在（丢了 = 包名错 / 依赖不满足，会被静默丢弃）
MUST_KEEP = [
    "luci-app-passwall", "luci-app-openclash",
    "luci-app-ttyd", "luci-app-upnp",
]
NAS_MUST_KEEP = [
    "luci-app-diskman", "luci-app-samba4",
    "luci-app-dockerman", "docker",
]
MUST_KEEP_LINES = [
    "CONFIG_TARGET_KERNEL_PARTSIZE=%d" % KERNEL_PARTSIZE,
    "CONFIG_TARGET_ROOTFS_PARTSIZE=%d" % ROOTFS_PARTSIZE,
]


def inject(txt, extra=""):
    """去掉标准 config 里已有的分区行，再追加发行版注入段（+ 可选额外段）。"""
    out = []
    for ln in txt.splitlines():
        if ln.startswith("CONFIG_TARGET_KERNEL_PARTSIZE=") or \
                ln.startswith("CONFIG_TARGET_ROOTFS_PARTSIZE="):
            continue
        out.append(ln)
    return "\n".join(out) + "\n" + INJECT + extra


def main():
    argv = sys.argv[1:]
    do_check = "--check" in argv
    nas = "--nas" in argv
    extra = NAS_EXTRA if nas else ""
    # 默认输出目录：普通发行版 -> configs-release/；NAS 版 -> configs-release-nas/
    out_dir = os.path.join(TREE, "configs-release-nas" if nas else "configs-release")
    if "--out" in argv:
        out_dir = argv[argv.index("--out") + 1]

    if not os.path.isdir(SRC_DIR):
        sys.exit("找不到 %s" % SRC_DIR)
    os.makedirs(out_dir, exist_ok=True)

    cfgs = sorted(f for f in os.listdir(SRC_DIR) if f.endswith(".config"))
    if not cfgs:
        sys.exit("%s 下没有 *.config" % SRC_DIR)

    defconfig = os.path.join(TREE, ".config")
    ok = fail = 0
    for name in cfgs:
        src = os.path.join(SRC_DIR, name)
        dst = os.path.join(out_dir, name)
        txt = open(src, encoding="utf-8").read()
        open(dst, "w", encoding="utf-8", newline="\n").write(inject(txt, extra))

        dev = re.search(re.escape(PREFIX) + r'([^\s=]+)=y', txt)
        tag = "生成"
        if do_check:
            shutil.copy(dst, defconfig)
            r = subprocess.run(["make", "defconfig"], cwd=TREE,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               universal_newlines=True)
            if r.returncode != 0:
                print("!! %-16s defconfig 失败" % name)
                print((r.stdout or "")[-1200:])
                fail += 1
                continue
            shutil.copy(defconfig, dst)
            after = open(dst, encoding="utf-8").read()
            want = MUST_KEEP + (NAS_MUST_KEEP if nas else [])
            miss = [k for k in want if ("CONFIG_PACKAGE_%s=y" % k) not in after]
            miss += [k for k in MUST_KEEP_LINES if k not in after]
            tag = "OK" if not miss else "缺(%d)" % len(miss)
            if miss:
                fail += 1
                print("   %-16s 缺失: %s" % (name, " ".join(miss)))
            else:
                ok += 1
        else:
            ok += 1

        print("%-24s %-8s device=%s" % (name, tag, dev.group(1) if dev else "?"))

    print("\n输出目录：%s" % out_dir)
    print("完成：%d 份%s" % (ok, ("，%d 份有问题" % fail) if fail else ""))
    print("编译：CFGDIR=%s sh tools/build_single.sh" % os.path.basename(out_dir))


if __name__ == "__main__":
    main()
