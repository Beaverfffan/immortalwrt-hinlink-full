#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rebuild_commits.py —— 把 HinLink 适配按「基础设施 + 每机型一个提交」重放进 git。

背景
----
一开始需要一个 commit 把整批适配塞进去（单提交快照），但那样看不出「哪个改动
属于哪个机型」，也没法逐机型回溯。本脚本把同一份最终内容**重放**成一串提交：

    base(官方 immortalwrt 完整历史)
      └─ 基础设施：U-Boot / 内核 patch / 公共 dtsi / 5G 复位应用 / beaverfffan 包 / 文档骨架
      └─ 机型 h66k        DTS + config + 机型文档 + armv8.mk.hinlink 段 + 02_network/01_leds 分支
      └─ 机型 h68k-a-b    同上
      └─ ...（按 armv8.mk.hinlink 里 Define Device 的出现顺序）

用法（在目标树里、HEAD 已 reset 到官方提交之后跑）
    python3 rebuild_commits.py ~/hinlink-snap ~/iwrt-hinlink-full

保证
----
结束时逐文件比对 TREE 与 SNAP（跳过 .git 与 gitignore 覆盖的路径），
有任何一处不一致就 **不** 提交最后一步并报错退出 —— 宁可失败也不留错树。
"""
import io
import os
import re
import subprocess
import sys

SNAP = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/hinlink-snap")
TREE = os.path.expanduser(sys.argv[2] if len(sys.argv) > 2 else "~/iwrt-hinlink-full")

MK = "target/linux/rockchip/image/armv8.mk.hinlink"
AMK = "target/linux/rockchip/image/armv8.mk"
DTS_DIR = "target/linux/rockchip/files/arch/arm64/boot/dts/rockchip"
NET = "target/linux/rockchip/armv8/base-files/etc/board.d/02_network"
LED = "target/linux/rockchip/armv8/base-files/etc/board.d/01_leds"

# DTS 文件 → 机型（None = 归基础设施，如 lede 的 h29k 参考存档）
DTS_MAP = {
    "rk3528-hinlink-h28k.dts": "h28k",
    "rk3528-hinlink-h29k-v1.3-1.14.dts": "h29k-v1.3-1.14",
    "rk3528-hinlink-h29k-v5-1.14.dts": "h29k-v5-1.14",
    "rk3528-hinlink-h29k-v5-1.49.dts": "h29k-v5-1.49",
    "rk3528-hinlink-ht2.dts": "ht2",
    "rk3528-hinlink-h29k.dts": None,          # lede 参考存档，不参与编译
    "rk3568-hinlink-h66k.dts": "h66k",
    "rk3568-hinlink-h68k-a-b-usb.dts": "h68k-a-b-usb",
    "rk3568-hinlink-h68k-a-b.dts": "h68k-a-b",
    "rk3568-hinlink-h68k-c-d-f-usb.dts": "h68k-c-d-f-usb",
    "rk3568-hinlink-h68k-c-d-f.dts": "h68k-c-d-f",
    "rk3568-hinlink-h68k-new.dts": "h68k-new",
    "rk3568-hinlink-h69k-3eth.dts": "h69k",
    "rk3568-hinlink-h69k-mini.dts": "h69k-mini",
    "rk3588-hinlink-h88k-v2.dts": "h88k-v2",
    "rk3588-hinlink-h88k-v3.dts": "h88k-v3",
    "rk3588-hinlink-h89k.dts": "h89k",
}

# board.d 分支的关键词 → 机型。顺序即"命中多个时选谁"的优先级无关紧要，
# 真正的归属由 ORDER（下面按 mk 段顺序算出来）决定。
KEYS = [
    ("h66k", "opc-h66k"),
    ("h68k-a-b-usb", "opc-h68k-a-b-usb"),
    ("h68k-a-b", "opc-h68k-a-b"),
    ("h68k-c-d-f-usb", "opc-h68k-c-d-f-usb"),
    ("h68k-c-d-f", "opc-h68k-c-d-f"),
    ("h68k-new", "opc-h68k-new"),
    ("h69k-mini", "opc-h69k-mini"),
    ("h69k", "h69k"),
    ("h28k", "h28k"),
    ("h29k-v1.3-1.14", "h29k"),      # H29K 全系共用一个分支块
    ("ht2", "ht2"),
    ("h88k-v2", "h88k-v2"),
    ("h88k-v3", "h88k-v3"),
    ("h89k", "h89k"),
]


def rd(p):
    return io.open(p, encoding="utf-8").read()


def wr(p, t):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)


def git(*a):
    r = subprocess.run(["git"] + list(a), cwd=TREE, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, universal_newlines=True)
    if r.returncode != 0:
        sys.exit("git %s 失败：\n%s" % (" ".join(a), r.stdout))
    return r.stdout


def commit(msg, paths):
    paths = [p for p in paths if os.path.exists(os.path.join(TREE, p))]
    if not paths:
        print("  （无文件可提交，跳过）")
        return
    git("add", "-A", "--", *paths)
    st = git("diff", "--cached", "--name-only").strip()
    if not st:
        print("  （无变化，跳过）")
        return
    git("-c", "user.name=Beaverfffan",
        "-c", "user.email=beaverfffan@users.noreply.github.com",
        "commit", "-q", "-m", msg)
    print("  ✔ %-22s %d 个文件" % (msg.split("\n")[0][:22], len(st.splitlines())))


# ---------------------------------------------------------------- 分片解析

def split_mk(txt):
    """按 define Device/ 切段 → (文件头, [(段名, 段文本)])"""
    pos = [m.start() for m in re.finditer(r'^define Device/', txt, re.M)]
    if not pos:
        return txt, []
    head = txt[:pos[0]]
    segs = []
    for i, a in enumerate(pos):
        b = pos[i + 1] if i + 1 < len(pos) else len(txt)
        seg = txt[a:b]
        segs.append((re.match(r'define Device/(\S+)', seg).group(1), seg))
    return head, segs


def case_regions(txt):
    """找所有 case ... in ... esac 的 body 区域 → [(body_start, body_end)]"""
    out = []
    for m in re.finditer(r'^(\t*)case\s+[^\n]*\bin[ \t]*\n', txt, re.M):
        indent = m.group(1)
        bs = m.end()
        e = re.search(r'^%sesac[ \t]*\n' % re.escape(indent), txt[bs:], re.M)
        if e:
            out.append((bs, bs + e.start()))
    return out


def split_branches(body):
    """把 case body 切成分支（以 ';;' 结尾）→ [(文本, 是否我方)]"""
    parts, cur = [], []
    for ln in body.splitlines(True):
        cur.append(ln)
        if ln.strip() == ";;":
            parts.append("".join(cur))
            cur = []
    if cur:
        parts.append("".join(cur))
    out = []
    for t in parts:
        ours = ("hinlink," in t or "linkstar," in t or "hlink," in t)
        out.append((t, ours))
    return out


def owner_of(text, order):
    hits = [s for s, k in KEYS if k in text]
    if not hits:
        return None
    hits.sort(key=lambda s: order.index(s) if s in order else 999)
    return hits[0]


def main():
    if not os.path.isdir(os.path.join(SNAP, ".git")):
        sys.exit("SNAP 里没有 .git：%s" % SNAP)

    # 1) 改动清单（SNAP 相对其 git HEAD）
    changed = [l[3:] for l in
               subprocess.run(["git", "status", "--porcelain"], cwd=SNAP,
                              stdout=subprocess.PIPE, universal_newlines=True)
               .stdout.splitlines()]
    # 改名/目录折叠的情况：把目录展开成文件
    files = []
    for c in changed:
        p = os.path.join(SNAP, c)
        if os.path.isdir(p):
            for root, _, fs in os.walk(p):
                files += [os.path.relpath(os.path.join(root, f), SNAP) for f in fs]
        else:
            files.append(c)
    files = sorted(set(files))

    # 2) 分类：infra / 机型
    dev_files = {}          # short -> [rel...]
    infra = []
    for rel in files:
        b = os.path.basename(rel)
        s = None
        if rel.startswith("configs/") and b.endswith(".config"):
            s = b[:-len(".config")]
        elif rel.startswith("docs/devices/") and b.endswith(".md"):
            s = b[:-3]
        elif rel.startswith(DTS_DIR + "/") and b in DTS_MAP:
            s = DTS_MAP[b]
        if s:
            dev_files.setdefault(s, []).append(rel)
        else:
            infra.append(rel)

    # 3) armv8.mk.hinlink 的段顺序 = 机型提交顺序
    mk_head, mk_segs = split_mk(rd(os.path.join(SNAP, MK)))
    COMMON_MK = [n for n, _ in mk_segs if n.startswith("hinlink_common")
                 or n.startswith("hinlink_h6xk")]
    ORDER = [s for s, _ in KEYS if s in dev_files or True]
    order_seq = []
    seg_by_short = {}
    for name, seg in mk_segs:
        key = None
        for s, k in KEYS:
            if s.replace("-", "-") and k in name.replace("_", "-"):
                key = s
                break
        if key is None:
            continue
        if key not in order_seq:
            order_seq.append(key)
        seg_by_short.setdefault(key, []).append(seg)

    print("机型提交顺序（按 armv8.mk.hinlink 的段顺序）：")
    print("  " + " ".join(order_seq))
    missing = set(dev_files) - set(order_seq)
    if missing:
        print("  ⚠ 有文件但没找到 mk 段的机型：%s" % " ".join(sorted(missing)))

    # 4) board.d 的分支分片
    net_txt, led_txt = rd(os.path.join(SNAP, NET)), rd(os.path.join(SNAP, LED))
    net_regions, led_regions = case_regions(net_txt), case_regions(led_txt)
    base_net, base_led = rd(os.path.join(TREE, NET)), rd(os.path.join(TREE, LED))

    def collect(txt, regions, order):
        """→ {case_idx: [(seq, owner, branch_text)]}"""
        res = {}
        for ci, (bs, be) in enumerate(regions):
            res[ci] = []
            for t, ours in split_branches(txt[bs:be]):
                if not ours or t.strip().startswith("#"):
                    continue
                o = owner_of(t, order)
                if o:
                    res[ci].append((order.index(o), o, t))
            res[ci].sort(key=lambda x: x[0])
        return res

    net_own = collect(net_txt, net_regions, order_seq)
    led_own = collect(led_txt, led_regions, order_seq)

    def rebuild(base_txt, regions, own, upto):
        """把 base_txt 的每个 case 区域重建为：base 分支 + 已启用的我方分支（插在 *) 之前）"""
        segs = split_branches_caseregion(base_txt, regions)
        out = []
        for ci, (pos, body) in enumerate(segs):
            parts = split_branches(body)
            newparts = []
            for t, ours in parts:
                if ours:
                    continue                       # 官方侧不该有我方分支
                if re.match(r'^\s*\*\)', t):       # 兜底分支：先插我方
                    for seq, o, bt in own.get(ci, []):
                        if seq <= upto:
                            newparts.append(bt)
                newparts.append(t)
            out.append((pos, "".join(newparts)))
        return apply_regions(base_txt, regions, out)

    def split_branches_caseregion(txt, regions):
        return [(i, txt[bs:be]) for i, (bs, be) in enumerate(regions)]

    def apply_regions(txt, regions, newbodies):
        """从后往前替换（避免偏移）"""
        res = txt
        for (ci, body), (bs, be) in reversed(list(zip(newbodies, regions))):
            res = res[:bs] + body + res[be:]
        return res

    # 5) 基础设施
    print("\n[0] 基础设施")
    for rel in infra:
        wr(os.path.join(TREE, rel), rd(os.path.join(SNAP, rel)))
    # armv8.mk.hinlink 先只放公共段（无机型段）
    wr(os.path.join(TREE, MK), mk_head + "".join(
        seg for n, seg in mk_segs
        if n.startswith("hinlink_common") or n.startswith("hinlink_h6xk")))
    commit("rockchip: HinLink 适配基础设施（U-Boot / 内核 patch / 公共 dtsi / 5G 复位应用 / beaverfffan 包 / 文档）",
           infra + [MK])

    # 6) 逐机型
    for seq, short in enumerate(order_seq):
        print("\n[%d/%d] %s" % (seq + 1, len(order_seq), short))
        paths = list(dev_files.get(short, []))
        for rel in paths:
            wr(os.path.join(TREE, rel), rd(os.path.join(SNAP, rel)))
        # mk 段：追加（顺序 = 段顺序）
        cur_mk = rd(os.path.join(TREE, MK))
        for seg in seg_by_short.get(short, []):
            cur_mk = cur_mk.rstrip("\n") + "\n" + seg
            paths.append(MK)
        wr(os.path.join(TREE, MK), cur_mk if cur_mk.endswith("\n") else cur_mk + "\n")
        # board.d 分支
        wr(os.path.join(TREE, NET), rebuild(base_net, net_regions, net_own, seq))
        wr(os.path.join(TREE, LED), rebuild(base_led, led_regions, led_own, seq))
        paths += [NET, LED]
        commit("rockchip: 新增机型 %s（DTS / defconfig / 机型文档 / 板级映射）" % short,
               paths)

    # 7) 校验
    print("\n=== 校验 TREE 与 SNAP ===")
    bad = 0
    for rel in files:
        a = os.path.join(SNAP, rel)
        b = os.path.join(TREE, rel)
        if not os.path.exists(b) or rd(a) != rd(b):
            print("  ✗ 不一致：%s" % rel)
            bad += 1
    if bad:
        sys.exit("有 %d 个文件不一致，请检查（未推送）" % bad)
    print("  ✔ 全部 %d 个文件一致" % len(files))
    print("\n提交历史：")
    print(git("log", "--oneline", "-20"))


if __name__ == "__main__":
    main()
