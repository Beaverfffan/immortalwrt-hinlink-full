#!/bin/sh
# ============================================================================
# 逐机型编译 16 个 HinLink 固件（**单机型 config 模式**）
#
#   sh tools/build_single.sh                # 编全部 16 个
#   sh tools/build_single.sh h69k h28k      # 只编指定机型
#   JOBS=8 sh tools/build_single.sh h69k    # 指定并发
#
# 为什么用单机型模式、而不用 build_all.sh 的多机型模式
# ----------------------------------------------------
# 多机型模式下所有机型**共用一份 rootfs**（PER_DEVICE_ROOTFS=n），于是
# .config 里 =y 的包会出现在**每一个**机型上 —— 5G 复位面板会落到全部 16 个，
# 而用户要求它只出现在「有风扇 且有 5G 复位脚」的 5 个机型（见 gen_configs.py）。
# 单机型模式下每个机型有自己的 rootfs，产物与 configs/<机型>.config 一一对应，
# 用户 clone 后 cp 同一份 config 就能复现同一份固件。
#
# 代价：每个机型都要重跑一次 make。但除首次外，包只编一次，
# 后续机型主要是 rootfs 打包 + 镜像生成（每机型数分钟）。
#
# 断点续跑：产物已存在的机型自动跳过。想重编某机型就删掉
# ~/hinlink-out/<机型>/ 再跑。
# ============================================================================
set -u

TREE=$(cd "$(dirname "$0")/.." && pwd)
OUT=${HINLINK_OUT:-$HOME/hinlink-out}
JOBS=${JOBS:-$(nproc)}
LOGDIR="$OUT/_logs"
# 配置来源目录。默认 configs/ = **标准**配置（仓库里那一份）。
# 编「发行版」时用 CFGDIR=configs-release（由 tools/gen_release_cfg.py 生成，
# 含分区 128/1024 与四件套）—— 用户 2026-10-14 明确「不要更新 configs，
# 这个只是编译发行版用的」，所以两份配置必须分开。
CFGDIR=${CFGDIR:-configs}
mkdir -p "$OUT" "$LOGDIR"

[ -f "$TREE/include/image.mk" ] || { echo "请在 immortalwrt 树根执行"; exit 1; }
[ -d "$TREE/$CFGDIR" ] || { echo "找不到配置目录 $TREE/$CFGDIR"; exit 1; }

if [ $# -gt 0 ]; then
	LIST="$*"
else
	LIST=""
	for f in "$TREE/$CFGDIR"/*.config; do
		LIST="$LIST $(basename "$f" .config)"
	done
fi
echo "配置目录:$CFGDIR"
echo "机型:$LIST"
echo "产物:$OUT   并发:-j$JOBS"

echo "=== [0] 预下载全部源码（passwall/openclash 会拉 v2ray/xray/sing-box 等）==="
( cd "$TREE" && make -j"$JOBS" download ) >"$LOGDIR/_download.log" 2>&1 \
	|| echo "!! download 有失败项（非致命，编译到时会重试），见 $LOGDIR/_download.log"

fail=""
for short in $LIST; do
	cfg="$TREE/$CFGDIR/$short.config"
	if [ ! -f "$cfg" ]; then echo "!! 缺 $cfg"; fail="$fail $short"; continue; fi

	if [ -n "$(ls "$OUT/$short"/*.img.gz 2>/dev/null)" ]; then
		echo "=== [$short] 已有产物，跳过"
		continue
	fi

	echo "=== [$short] 开始 $(date '+%H:%M:%S')"
	rm -rf "$TREE/bin/targets/rockchip/armv8"
	cp "$cfg" "$TREE/.config"
	log="$LOGDIR/$short.log"
	( cd "$TREE" && make defconfig && make -j"$JOBS" ) >"$log" 2>&1
	if [ $? -ne 0 ]; then
		echo "!! [$short] 编译失败，日志尾部："
		tail -20 "$log"
		fail="$fail $short"
		continue
	fi

	mkdir -p "$OUT/$short"
	cp -a "$TREE"/bin/targets/rockchip/armv8/*.img.gz "$OUT/$short/" 2>/dev/null
	cp -a "$TREE"/bin/targets/rockchip/armv8/*.manifest "$OUT/$short/" 2>/dev/null
	cp -a "$TREE"/bin/targets/rockchip/armv8/*.buildinfo "$OUT/$short/" 2>/dev/null
	echo "=== [$short] 完成 $(date '+%H:%M:%S')，$(ls "$OUT/$short"/*.img.gz 2>/dev/null | wc -l) 个镜像"
done

echo
echo "================ 汇总 ================"
for d in "$OUT"/*/; do
	[ "$(basename "$d")" = "_logs" ] && continue
	echo "  $(basename "$d"): $(ls "$d"*.img.gz 2>/dev/null | wc -l) 镜像"
done
echo "失败机型:${fail:-无}"
