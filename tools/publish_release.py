#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 ~/hinlink-out 下的固件产物发布为 GitHub Release。

用法（在构建机执行，需要 GH_TOKEN 环境变量）：
    GH_TOKEN=ghp_xxx python3 tools/publish_release.py
    TAG=v2026.10.14-hinlink-16dev GH_TOKEN=... python3 tools/publish_release.py

特性
----
· release 已存在时**复用**（不报错），已上传的同名 asset 会跳过（断点续传）
· asset 上传走 uploads.github.com，逐个重试 3 次
· 自动生成并上传 sha256sums.txt
"""
import glob
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("FM160_TOKEN")
if not TOKEN:
    sys.exit("需要 GH_TOKEN 环境变量")

REPO = os.environ.get("REPO", "Beaverfffan/immortalwrt-hinlink-full")
TAG = os.environ.get("TAG", "v2026.10.15-hinlink-16dev")
OUT = os.environ.get("HINLINK_OUT", os.path.expanduser("~/hinlink-out"))

BODY = """\
## HinLink H 系列全设备固件（16 机型）

基于 **immortalwrt master**（内核 6.18.55）+ HinLink 全系适配。
本页为编译产物；对应源码与每机型 config 见仓库 `configs/` 与 `docs/devices/`。

### 本版修正了什么

上一版把「有风扇」与「有 5G 复位脚」当成了**一个交集条件**，结果 H29K 全系
（**有 5G 复位脚、但没有风扇**）被漏掉。两者其实是**独立的**：

> **机器有风扇 → 就编风扇插件；有 5G 复位脚 → 就编复位面板。**

| 插件 | 本版 | 上一版 |
|---|---|---|
| 风扇温控 `luci-app-fancontrol` | **只给有风扇的 5 个机型** | 16 个机型全编（多编了） |
| 5G 复位面板 `luci-app-hinlink-modem-hardreset` | **给有 5G 复位脚的 8 个机型** | 只有 5 个（漏了 H29K 全系） |
| passwall / openclash / ttyd / upnp | 16 个机型全带 | 同 |
| 内核 / rootfs 分区 | 128 MB / 1024 MB | 同 |

### 机型 × 插件对照

| 机型 | 风扇插件 | 5G 复位面板 |
|---|---|---|
| h69k、h69k-mini | ✅ | ✅ |
| h88k-v2、h88k-v3、h89k | ✅ | ✅ |
| h29k-v1.3-1.14、h29k-v5-1.14、h29k-v5-1.49 | — | ✅ |
| h28k、ht2、h66k、h68k-a-b、h68k-a-b-usb、h68k-c-d-f、h68k-c-d-f-usb、h68k-new | — | — |

> 依据是 DTS 里的**真实节点**（`pwm-fan` / `compatible = "rfkill-gpio"`），
> 逐个 grep 核实过。注意区分「节点」与「注释」：ht2 的 dts 里有一行注释就写着
> 「无 4G/5G LED 与 rfkill」，H89K 的 dts 里也有注释提到风扇（实际节点在 dtsi）。

### 已内置的驱动

MT7921 / MT7922 / MT7925 / MT7915 / MT7916 / AIC8800（PCIe+SDIO+USB）/ NFA765（QCNFA765 = WCN6855，ath11k + 固件）

### 机型（16）

```
RK3568  h66k  h68k-a-b  h68k-a-b-usb  h68k-c-d-f  h68k-c-d-f-usb  h68k-new  h69k  h69k-mini
RK3528  h28k  h29k-v1.3-1.14  h29k-v5-1.14  h29k-v5-1.49  ht2
RK3588  h88k-v2  h88k-v3  h89k
```

每个机型两种镜像：

* `*-squashfs-sysupgrade.img.gz` —— 常规刷机（推荐）
* `*-ext4-sysupgrade.img.gz` —— 需要可写大分区时用

### 5G 复位面板 与 风扇插件（两个独立判据）

- `luci-app-hinlink-modem-hardreset`（菜单：**网络 → 5G复位**）
  → **有 5G 复位脚的 8 个机型**：`h29k-v1.3-1.14`、`h29k-v5-1.14`、
  `h29k-v5-1.49`、`h69k`、`h69k-mini`、`h88k-v2`、`h88k-v3`、`h89k`
- 风扇温控（`luci-app-fancontrol` + `fancontrol`，默认开启温控）
  → **有风扇的 5 个机型**：`h69k`、`h69k-mini`、`h88k-v2`、`h88k-v3`、`h89k`

### 板载屏幕提示

H29K 全系（1.14″/1.49″）、H88K-v3、H89K 有 SPI 小屏。DTS + 内核 fbtft 已就位，屏会点亮并出现 `/dev/fbX`，
**但固件里没有用户态程序往屏上画内容**（不显示 IP / 温度）—— 这不是故障。
仓库里的 `luci-app-oled` 是给**外接 I2C SSD1306（0.91″）** 用的，与板载 SPI 屏无关。

### 刷写

```sh
# 常规升级（保留配置）
sysupgrade -v immortalwrt-rockchip-armv8-<机型>-squashfs-sysupgrade.img.gz

# 从其他固件首次刷入（不保留配置）
sysupgrade -n immortalwrt-rockchip-armv8-<机型>-squashfs-sysupgrade.img.gz
```

校验：`sha256sum -c sha256sums.txt`
"""


def api(method, url, data=None, ctype="application/json"):
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", "token " + TOKEN)
    req.add_header("Accept", "application/vnd.github+json")
    if data is not None:
        if isinstance(data, str):
            data = data.encode()
        req.add_header("Content-Type", ctype)
        req.data = data
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}


def curl_upload(rid, path, name):
    """大文件走 curl（内存友好、有 --retry）。"""
    url = ("https://uploads.github.com/repos/%s/releases/%d/assets?name=%s"
           % (REPO, rid, name))
    cmd = ["curl", "-sS", "--retry", "3", "--retry-delay", "5",
           "-X", "POST",
           "-H", "Authorization: token " + TOKEN,
           "-H", "Content-Type: application/octet-stream",
           "--data-binary", "@" + path,
           url]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       universal_newlines=True)
    try:
        j = json.loads(r.stdout or "{}")
    except Exception:
        j = {"raw": r.stdout[:300]}
    return r.returncode, j


def main():
    # ---- 1) 创建（或复用）release ----
    # BODY_FILE 环境变量可覆盖默认说明（比如 NAS/Docker 版另写一份）
    body = BODY
    bf = os.environ.get("BODY_FILE")
    if bf and os.path.isfile(bf):
        body = open(bf, encoding="utf-8").read()
        print("使用自定义说明：%s（%d 字节）" % (bf, len(body)))
    payload = json.dumps({"tag_name": TAG, "name": TAG, "body": body,
                          "draft": False})
    st, r = api("POST", "https://api.github.com/repos/%s/releases" % REPO, payload)
    if st == 422:      # already_exists
        st, r = api("GET", "https://api.github.com/repos/%s/releases/tags/%s"
                    % (REPO, TAG))
    if st not in (200, 201):
        sys.exit("创建 release 失败: HTTP %s %s" % (st, r))
    rid = r["id"]
    rel_url = r.get("html_url")
    print("release id=%s  %s" % (rid, rel_url))

    # ---- 2) 已上传的 asset 名 ----
    st, r = api("GET", "https://api.github.com/repos/%s/releases/%d/assets"
                % (REPO, rid))
    have = {a["name"] for a in r} if st == 200 and isinstance(r, list) else set()

    # ---- 3) 生成 sha256sums ----
    files = sorted(glob.glob(os.path.join(OUT, "*", "*.img.gz")))
    if not files:
        sys.exit("在 %s 下没找到 *.img.gz" % OUT)
    sums = os.path.join(OUT, "sha256sums.txt")
    with open(sums, "w", encoding="utf-8") as fh:
        for f in files:
            h = hashlib.sha256()
            with open(f, "rb") as g:
                for b in iter(lambda: g.read(1 << 20), b""):
                    h.update(b)
            fh.write("%s  %s\n" % (h.hexdigest(), os.path.basename(f)))
    files.append(sums)

    # ★ 只上传「名字唯一」的文件。
    #   manifest / config.buildinfo / feeds.buildinfo 在**每个机型目录里都同名**
    #   （如 immortalwrt-rockchip-armv8.manifest），一起上传会在 GitHub 侧撞名
    #   报 422 —— 所以这里只收 img.gz + sha256sums.txt，manifest 留在源码树里。
    files = [f for f in files if f.endswith(".img.gz") or f == sums]

    # ---- 4) 逐个上传 ----
    ok = skip = bad = 0
    for f in files:
        name = os.path.basename(f)
        if name in have:
            print("  跳过（已存在） %s" % name)
            skip += 1
            continue
        sz = os.path.getsize(f)
        print("  上传 %-72s %8.1f MB" % (name, sz / 1048576.0))
        rc, j = curl_upload(rid, f, name)
        if rc == 0 and j.get("name"):
            ok += 1
        else:
            bad += 1
            print("    !! 失败 rc=%s %s" % (rc, str(j)[:200]))
        time.sleep(0.5)

    print("\n完成：上传 %d / 跳过 %d / 失败 %d" % (ok, skip, bad))
    print("地址：%s" % rel_url)


if __name__ == "__main__":
    main()
