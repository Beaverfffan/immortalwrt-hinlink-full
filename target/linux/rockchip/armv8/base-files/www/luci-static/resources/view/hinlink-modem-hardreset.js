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
			? (st.usb_dev + '   ' + (st.usb_vid || '') + ':' + (st.usb_pid || ''))
			: '未匹配到常见模组 USB（VID 白名单）';

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
	 * 要能排在一行里，长标签（「断电（拉复位）」那种）会换行、显得散。 */
	return E('button', {
		'class': 'btn cbi-button ' + (kind || 'cbi-button-action'),
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
			row('串口 / QMI 节点', 'tty'),
			row('复位时序', 'timing')
		]);

		/*
		 * 四个手动动作，**按操作逻辑排**（用户 2026-10-14 反馈「排布有点怪」）：
		 *
		 *     断电 → 上电 → 软复位 → 仅 USB 重新枚举
		 *
		 * 理由：「软复位」本质就是「断电 + 等 hold_ms + 上电」，
		 * 是前两个动作的**合成**，放在它们后面才符合直觉；
		 * 旧顺序把「软复位模组」放最前，读起来像是和后面三个并列的
		 * 第四种操作，容易误解。
		 *
		 * 标签也收短了（原来「断电（拉复位）」「软复位模组」「仅 USB 重枚举」），
		 * 长标签会换行、把这一组撑散；详细说明移到 hover 的 title 上。
		 */
		var actions = E('div', { 'class': 'cbi-page-actions' }, [
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
				'手动操作（四个按钮是一组）：',
				E('code', {}, '断电'), ' → ', E('code', {}, '上电'), ' 两步即一次硬复位；',
				E('code', {}, '软复位'), ' 把这两步合成一步（断电 → 等 hold_ms → 上电）。',
				E('br'),
				'底层等价于：echo 0 > /sys/class/rfkill/rfkillN/state，等一会儿，再 echo 1。'
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

		var logButtons = E('div', { 'class': 'cbi-page-actions' }, [
			E('button', {
				'class': 'btn cbi-button cbi-button-action',
				'click': function(ev) { ev.preventDefault(); return refreshLog(); }
			}, '刷新日志'),
			E('button', {
				'class': 'btn cbi-button cbi-button-reset',
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
