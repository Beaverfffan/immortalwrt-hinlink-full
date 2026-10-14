'use strict';
/* SPDX-License-Identifier: Apache-2.0 */
/*
 * HinLink 5G 模组 —— 状态 / 手动软复位 / 日志 / 开机行为
 *
 * 机理
 * ----
 * 5G 的「复位 / 使能」脚在 DTS 里归 rfkill-gpio，
 * /sys/class/rfkill/rfkillN/state 是 DEVICE_ATTR_RW（可写）：
 *     echo 0  -> 拉复位（H69K 上同时就是断电）    echo 1  -> 释放
 * 所以「0 -> 等一会儿 -> 1」就是一次硬复位脉冲。
 *
 * 后端 = /usr/libexec/hinlink-modem-hardreset；rpcd 插件
 * （/usr/libexec/rpcd/hinlink-modem-hardreset）把它转发成 ubus 方法：
 *     status / reset / power_off / power_on / usb_reset / log / log_clear
 *
 * 日志由三处写入，都汇总到 /etc/hinlink-modem-hardreset.log：
 *   · 手动操作（本页面的按钮、或 CLI）
 *   · 开机检查（/etc/init.d/hinlink-modem-hardreset）
 *   · 模组 USB 插拔（/etc/hotplug.d/usb/50-hinlink-modem-hardreset）
 *
 * 详见 docs/HARDWARE.md §四。
 */

'require view';
'require form';
'require poll';
'require rpc';
'require ui';
'require uci';

var LOG_LINES = 200;

/*
 * 页面版本标记 —— 印在「状态」区说明末尾。
 * 存在的唯一理由是**当缓存探针**：uhttpd 对 /luci-static/ 下的静态文件
 * 只发 ETag + Last-Modified、**不发 Cache-Control**，浏览器一旦按启发式
 * 缓存住旧 JS，改多少代码都看不见。页面上直接印版本号，
 * 「看不到 v2」≈「浏览器还在用旧文件」，省得来回猜。
 */
var PAGE_VERSION = '前端 v3 · 2026-10-14';

var callStatus = rpc.declare({
	object: 'hinlink-modem-hardreset',
	method: 'status',
	expect: {}
});

var callReset    = rpc.declare({ object: 'hinlink-modem-hardreset', method: 'reset',     expect: {} });
var callPowerOff = rpc.declare({ object: 'hinlink-modem-hardreset', method: 'power_off', expect: {} });
var callPowerOn  = rpc.declare({ object: 'hinlink-modem-hardreset', method: 'power_on',  expect: {} });
var callUsbReset = rpc.declare({ object: 'hinlink-modem-hardreset', method: 'usb_reset', expect: {} });

/*
 * ★ 这里**不能**写 `expect: { entries: [] }`。
 *
 *   LuCI 的 rpc.js（handleCallReply）对 expect 的处理是：
 *       for (const key in req.expect) {
 *           if (ret != null && key != '')  ret = ret[key];
 *           if (ret == null || type.call(ret) != type.call(req.expect[key]))
 *               ret = req.expect[key];
 *           break;
 *       }
 *   即「把**整个返回值替换成 expect 里的第一个字段**」—— 它不是类型校验，
 *   而是"只取这个字段"。副作用有两个：
 *     ① total / max_lines / file 全被丢掉（页面上的行数统计永远是 0）；
 *     ② 一旦类型判断把 entries 换成 req.expect[key]（一个非数组值），
 *        前端再调 `r.entries.slice()` 就直接 TypeError、整页打白。
 *        实测用户就是这样报的：(r.entries || []).slice is not a function
 *
 *   ⇒ 不写 expect，拿完整对象，字段自己兜底（见 logEntries）。
 */
var callLog = rpc.declare({
	object: 'hinlink-modem-hardreset',
	method: 'log',
	params: [ 'lines' ]
});

var callLogClear = rpc.declare({ object: 'hinlink-modem-hardreset', method: 'log_clear', expect: {} });

/* 轮询时就地更新的节点 */
var nodes = {};

/* 日志刷新函数：render 时赋值，操作按钮完成后复用 */
var refreshLog = null;

function num(v, unit) {
	return (v === 0 || v) ? (String(v) + (unit || '')) : '—';
}

function applyState(st) {
	st = st || {};

	if (nodes.rfkill) {
		if (st.rfkill_found) {
			var working = (String(st.state) === '1');
			nodes.rfkill.textContent = (st.rfkill_name || st.rfkill_dev || 'wwan') +
				'  ·  ' + (working ? '工作（state=1）' : '复位中（state=0）');
			nodes.rfkill.className = working ? 'label success' : 'label warning';
		}
		else {
			nodes.rfkill.textContent = '未找到 type=wwan 的 rfkill 设备（该机型 DTS 未定义 rfkill-gpio？）';
			nodes.rfkill.className = 'label danger';
		}
	}

	if (nodes.reg)
		nodes.reg.textContent = st.regulator ? st.regulator
			: '（该机型无独立供电级 —— H69K 只有一路，属正常）';

	if (nodes.usb)
		nodes.usb.textContent = st.usb_dev
			? (st.usb_dev + '   ' + (st.usb_vid || '') + ':' + (st.usb_pid || '')
				+ (st.usb_driver ? '   · ' + st.usb_driver : ''))
			: '未发现通信模组（已按接口结构判据扫描）';

	/*
	 * 识别依据 —— 让「为什么判成模组 / 为什么判不出来」直接可见。
	 * 2026-10-14 之前这里写死的是「VID 白名单」，换别家模组只会得到一句
	 * 「未匹配到常见模组 USB」，看不出到底是没插、还是判据不适用。
	 * 现在后端回的是「匹配来源 + 结构摘要」（结构判据 / 已知 VID / 通配）。
	 */
	if (nodes.umatch)
		nodes.umatch.textContent = st.usb_match
			? (st.usb_match + (st.usb_reason ? '   ·   ' + st.usb_reason : ''))
			: (String(st.usb_all) === '1'
				? '通配模式已开（任何 USB 设备插拔都会记录）'
				: '未命中 —— 判据：导出了 ttyUSB/cdc-wdm，或有 USB 网卡 + 0xff 接口');

	if (nodes.tty)
		nodes.tty.textContent = st.usb_tty ? st.usb_tty
			: '无 /dev/ttyUSB* · /dev/cdc-wdm* · /dev/ttyACM*';

	if (nodes.timing)
		nodes.timing.textContent = '拉复位 ' + num(st.hold_ms) + ' ms，释放后等 ' + num(st.boot_wait) + ' s';
}

/*
 * 容忍后端 / 传输层可能给出的几种形态，避免一行 TypeError 把整页打白：
 *   · { total, showing, max_lines, file, entries: [...] }   正常
 *   · [...]                        —— 只剩 entries（旧 expect 写法的后果）
 *   · { entries: { "0": "...", "1": "..." } }   下标对象（被序列化转过）
 *   · 其它                          —— 当作空
 */
function logEntries(r) {
	if (Array.isArray(r))
		return r;

	if (r && typeof r === 'object') {
		var e = r.entries;

		if (Array.isArray(e))
			return e;

		if (e && typeof e === 'object')
			/* 整数键会被 JS 按升序枚举，顺序能对上 */
			return Object.keys(e).map(function(k) { return e[k]; });

		/* 极少数情况：传进来的本身就是下标对象（数组被序列化转过） */
		var ks = Object.keys(r);
		if (ks.length && ks.every(function(k) { return /^\d+$/.test(k); }))
			return ks.map(function(k) { return r[k]; });
	}

	return [];
}

function renderLog(r) {
	var meta = (r && typeof r === 'object' && !Array.isArray(r)) ? r : {};

	/* 文件是追加写的，最新的在最后 —— 显示时倒过来，最新在最上面 */
	var e = logEntries(r).slice().reverse();

	if (nodes.log)
		nodes.log.textContent = e.length
			? e.join('\n')
			: '（暂无记录）\n点上面的按钮做一次软复位，或等模组 USB 插拔事件。';

	if (nodes.logmeta)
		nodes.logmeta.textContent = '共 ' + (meta.total | 0) + ' 行'
			+ '（上限 ' + (meta.max_lines || 300) + ' 行，超出自动轮转）'
			+ (meta.file ? ' · ' + meta.file : '');
}

function row(label, key) {
	nodes[key] = E('em', {}, '—');
	return E('tr', { 'class': 'tr' }, [
		E('td', { 'class': 'td left', 'width': '22%' }, label),
		E('td', { 'class': 'td left' }, [ nodes[key] ])
	]);
}

function actionButton(label, fn, kind, hint) {
	/* hint 只作 hover 提示（<button title=>），按钮文字保持短 —— 四个按钮
	 * 要能排在一行里，长标签（「断电（拉复位）」那种）会换行、显得散。
	 *
	 * style 里那两个声明是**必须**的，机理见下面 actions 处的长注释：
	 * 主题 cascade.css 会给 .cbi-page-actions 的一部分子元素加 float，
	 * 内联 float:none 用来把这层干扰压掉（内联优先级高于任何类选择器）。
	 * margin-right:0 则是压掉那条规则自带的 margin-right:.4em，
	 * 让间距统一交给容器的 gap 管，四个按钮才是等距的。 */
	return E('button', {
		'class': 'btn cbi-button ' + (kind || 'cbi-button-action'),
		'style': 'float:none;margin-right:0',
		'title': hint || label,
		'click': function(ev) {
			ev.preventDefault();

			ui.showModal(hint || label, [
				E('p', { 'class': 'spinner' }, '执行中，请勿关闭页面…')
			]);

			return fn()
				.then(function() { return ui.hideModal(); })
				.then(function() { return callStatus(); })
				.then(function(st) {
					applyState(st);
					ui.addNotification(null, E('p', {}, label + '：已下发'), 'info');
				})
				.then(function() { return refreshLog ? refreshLog() : null; })
				.catch(function(e) {
					ui.hideModal();
					ui.addNotification(null, E('p', {}, String((e && e.message) || e)), 'error');
					return refreshLog ? refreshLog() : null;
				});
		}
	}, label);
}

return view.extend({
	load: function() {
		return Promise.all([
			callStatus(),
			callLog(LOG_LINES),
			uci.load('hinlink-modem-hardreset')
		]);
	},

	render: function(data) {
		var st = (data && data[0]) || {};
		var lg = (data && data[1]) || {};

		/* ---------- ① 状态 ---------- */
		var statusTable = E('table', { 'class': 'table' }, [
			row('复位控制（rfkill-gpio）', 'rfkill'),
			row('供电 regulator', 'reg'),
			row('模组 USB 设备', 'usb'),
			row('识别依据', 'umatch'),
			row('串口 / QMI 节点', 'tty'),
			row('复位时序', 'timing')
		]);

		/*
		 * 四个手动动作，**按操作逻辑排**：
		 *
		 *     断电 → 上电 → 软复位 → 仅 USB 重新枚举
		 *
		 * 理由：「软复位」本质就是「断电 + 等 hold_ms + 上电」，
		 * 是前两个动作的**合成**，放在它们后面才符合直觉；
		 * 旧顺序把「软复位」放最前，读起来像是和后面三个并列的
		 * 第四种操作，容易误解。
		 *
		 * ★★ 为什么必须写 style="display:flex …"（2026-10-14 实证，别再删）★
		 *
		 * 上一版只调了 DOM 顺序，用户两次反馈「还是左两个右两个 / 排序没成功」。
		 * 真正原因是主题 /www/luci-static/bootstrap/cascade.css 里这一条：
		 *
		 *   .cbi-page-actions > :not([method="post"]):not(.cbi-button-apply):
		 *     not(.cbi-button-negative):not(.cbi-button-save):not(.cbi-button-reset)
		 *       { float: left; margin-right: .4em }
		 *
		 * 读法：**除 apply / negative / save / reset 之外的直接子元素，一律
		 * float:left**。我们的四个按钮正好被劈成两半 ——
		 *   · 「断电」(cbi-button-reset)  「软复位」(cbi-button-apply)
		 *        → 被 :not() 排除 ⇒ 不受这条规则管，留在行内流里；
		 *   · 「上电」(cbi-button-action)「仅 USB」(cbi-button-neutral)
		 *        → 命中规则 ⇒ 被 float:left 抽到行首。
		 * 于是浮动的两个占住左边、留在流里的两个被挤到右边，
		 * **DOM 顺序怎么改都还是「左两个右两个」** —— 与 CSS 是否居中/右对齐无关。
		 *
		 * 解法：让这个 div 成为 flex 容器。CSS 规范里 float 对 flex item 的
		 * 计算值恒为 none（float 只影响 in-flow 块级盒子），这一条规则被整条废掉；
		 * 子项随即严格按 DOM 顺序从左边依次排列，间距改由 gap 统一给。
		 * 按钮上的内联 float:none 是双保险（万一某主题把容器的 display 也覆盖掉）。
		 */
		var actions = E('div', {
			'class': 'cbi-page-actions',
			'style': 'display:flex;flex-wrap:wrap;align-items:center;'
				+ 'justify-content:flex-start;gap:.5em'
		}, [
			actionButton('断电', callPowerOff, 'cbi-button-reset',
				'断电：只拉复位脚，并保持该状态'),
			actionButton('上电', callPowerOn, 'cbi-button-action',
				'上电：只释放复位脚'),
			actionButton('软复位', callReset, 'cbi-button-apply',
				'软复位：断电 → 等 hold_ms 毫秒 → 上电'),
			actionButton('仅 USB 重新枚举', callUsbReset, 'cbi-button-neutral',
				'仅 USB 重新枚举：不碰复位脚，只让 USB 层重新枚举模组')
		]);

		var statusSection = E('div', { 'class': 'cbi-section' }, [
			E('h3', {}, '状态'),
			statusTable,
			E('div', { 'class': 'cbi-section-descr' }, [
				'手动操作（四个按钮是一组，按操作顺序从左到右）：',
				E('code', {}, '断电'), ' → ', E('code', {}, '上电'), ' 两步即一次硬复位；',
				E('code', {}, '软复位'), ' 把这两步合成一步（断电 → 等 hold_ms → 上电）。',
				E('br'),
				'底层等价于：echo 0 > /sys/class/rfkill/rfkillN/state，等一会儿，再 echo 1。',
				E('br'),
				E('em', {}, PAGE_VERSION)
			]),
			actions
		]);

		applyState(st);

		/* ---------- ② 日志 ---------- */
		nodes.log = E('pre', {
			'style': 'margin:0;padding:.6em .8em;max-height:24em;overflow:auto;'
				+ 'background:rgba(127,127,127,.10);'
				+ 'border:1px solid rgba(127,127,127,.35);border-radius:3px;'
				+ 'font-family:monospace;font-size:92%;line-height:1.45;'
				+ 'white-space:pre-wrap;word-break:break-word;'
		}, '（载入中…）');

		nodes.logmeta = E('em', {}, '');

		refreshLog = function() {
			return callLog(LOG_LINES).then(renderLog).catch(function(e) {
				if (nodes.log)
					nodes.log.textContent = '读取失败：' + String((e && e.message) || e);
			});
		};

		try { renderLog(lg); }
		catch (e) {
			/* 兜底：日志区出任何意外都不该把整页打白（render 抛异常 = 白屏） */
			if (nodes.log)
				nodes.log.textContent = '日志渲染失败：' + String((e && e.message) || e);
		}

		/* 与上面四个动作按钮同样的处理：容器 flex + 子项 float:none ——
		 * 否则主题那条 `.cbi-page-actions > :not(apply/save/reset/negative)
		 * {float:left}` 会把「刷新日志」抽到左边、「清空日志」挤到右边。
		 * 机理与样式说明见状态区 actions 处的长注释。 */
		var logButtons = E('div', {
			'class': 'cbi-page-actions',
			'style': 'display:flex;flex-wrap:wrap;align-items:center;'
				+ 'justify-content:flex-start;gap:.5em'
		}, [
			E('button', {
				'class': 'btn cbi-button cbi-button-action',
				'style': 'float:none;margin-right:0',
				'click': function(ev) { ev.preventDefault(); return refreshLog(); }
			}, '刷新日志'),
			E('button', {
				'class': 'btn cbi-button cbi-button-reset',
				'style': 'float:none;margin-right:0',
				'click': function(ev) {
					ev.preventDefault();
					if (!confirm('确定清空 5G 模组日志？此操作不可撤销。'))
						return;

					return callLogClear().then(function() {
						ui.addNotification(null, E('p', {}, '日志已清空'), 'info');
						return refreshLog();
					}).catch(function(e) {
						ui.addNotification(null, E('p', {},
							'清空失败：' + String((e && e.message) || e)), 'error');
					});
				}
			}, '清空日志')
		]);

		var logSection = E('div', { 'class': 'cbi-section' }, [
			E('h3', {}, '日志'),
			E('div', { 'class': 'cbi-section-descr' }, [
				'记录手动操作、开机检查与模组 USB 插拔事件（最新在最上面）。',
				E('br'),
				'同一份内容也写进 syslog，可用 ',
				E('code', {}, 'logread | grep hinlink'),
				' 看；模组掉线后重新枚举的耗时可以从这里对上时间轴。'
			]),
			nodes.log,
			E('div', { 'class': 'cbi-section-descr' }, [ nodes.logmeta ]),
			logButtons
		]);

		/* ---------- ③ 配置 ---------- */
		var m = new form.Map('hinlink-modem-hardreset', '开机行为',
			'这些选项在 /etc/init.d/hinlink-modem-hardreset 的 start() 时生效。');

		var s = m.section(form.NamedSection, 'modem', 'hinlink-modem-hardreset', '模组');
		s.anonymous = true;
		s.addremove = false;

		var o = s.option(form.Flag, 'enabled', '启用本服务',
			'关闭后开机不碰模组，只保留手动命令。');
		o.default = '1';
		o.rmempty = false;

		o = s.option(form.Flag, 'auto_reset', '开机自动软复位一次',
			'模组冷启动不认卡 / 注不上网时可以打开。');
		o.default = '0';
		o.rmempty = false;

		o = s.option(form.Value, 'hold_ms', '复位保持时长（毫秒）',
			'模组手册一般要求 RESET 脉宽 ≥ 100 µs；默认 300 ms 留足余量。');
		o.datatype = 'uinteger';
		o.placeholder = '300';
		o.default = '300';

		o = s.option(form.Value, 'boot_wait', '释放后等启动（秒）',
			'原内核 regulator 的 startup-delay-us = 2 s 就是等这个。FM160 实际约需 20 s，'
			+ '但这里不宜设太大（会拖慢开机），靠日志里的 hotplug 记录确认模组何时回来。');
		o.datatype = 'uinteger';
		o.placeholder = '2';
		o.default = '2';

		o = s.option(form.Value, 'log_max_lines', '日志保留行数',
			'超过后自动轮转（只留最近一半）。日志在 /etc/hinlink-modem-hardreset.log。');
		o.datatype = 'uinteger';
		o.placeholder = '300';
		o.default = '300';

		o = s.option(form.Flag, 'usb_all', '记录所有 USB 设备（不做模组识别）',
			'默认关闭。关闭时按**接口结构**判断模组 —— 导出了 ttyUSB / ttyACM / '
			+ 'cdc-wdm，或者有 USB 网卡 + vendor-specific(0xff) 接口，就算模组；'
			+ '任何厂家的 4G/5G 模组都会命中，U 盘 / 键鼠 / HUB / 普通 USB 网卡不会。'
			+ '打开后 U 盘、HUB、键鼠的插拔也会记进日志，只在「明明插着模组却判不出来」'
			+ '时用来排查。');
		o.default = '0';
		o.rmempty = false;

		return m.render().then(function(formNode) {
			poll.add(function() {
				return callStatus().then(applyState);
			}, 5);

			return E('div', {}, [ statusSection, logSection, formNode ]);
		});
	},

	handleSave: null,
	handleSaveApply: null,
	handleReset: null
});
