import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// 底部时间控制条
//   第 1 行：快速推进预设（10秒/1分/5分/10分/30分/1小时）
//   第 2 行：自定义跨度（年/月/日/时/分/秒）
//   第 3 行：瞬间动作输入 + 发送
import { useState } from 'react';
import { useGameStore } from '../store/gameStore';
const FAST_PRESETS = [
    { label: '10秒', seconds: 10 },
    { label: '1分', seconds: 60 },
    { label: '5分', seconds: 300 },
    { label: '10分', seconds: 600 },
    { label: '30分', seconds: 1800 },
    { label: '1小时', seconds: 3600 },
];
const SPAN_FIELDS = [
    { key: 'y', label: '年', unit: 365 * 86400 },
    { key: 'mo', label: '月', unit: 30 * 86400 },
    { key: 'd', label: '日', unit: 86400 },
    { key: 'h', label: '时', unit: 3600 },
    { key: 'mi', label: '分', unit: 60 },
    { key: 's', label: '秒', unit: 1 },
];
export default function BottomBar() {
    const isProcessing = useGameStore((s) => s.isProcessing);
    const runAdvance = useGameStore((s) => s.runAdvance);
    const setError = useGameStore((s) => s.setError);
    // 自定义跨度
    const [span, setSpan] = useState({ y: 0, mo: 0, d: 0, h: 0, mi: 0, s: 0 });
    // 瞬间动作
    const [actionText, setActionText] = useState('');
    const spanSeconds = SPAN_FIELDS.reduce((acc, f) => acc + (span[f.key] || 0) * f.unit, 0);
    const doAdvance = (seconds) => {
        if (seconds <= 0) {
            setError('推进秒数必须大于 0');
            return;
        }
        runAdvance(seconds);
    };
    const submitAction = () => {
        const text = actionText.trim();
        if (!text)
            return;
        // 由模型判断动作的最短执行时长作为推进跨度
        runAdvance(0, { player_action: text });
        setActionText('');
    };
    return (_jsxs("div", { className: "bottom-bar", children: [_jsxs("div", { className: "ctl-row", children: [_jsx("span", { className: "bar-label", children: "\u63A8\u8FDB" }), _jsx("div", { className: "unit-group", children: FAST_PRESETS.map((p) => (_jsx("button", { className: "unit-btn", disabled: isProcessing, onClick: () => doAdvance(p.seconds), children: p.label }, p.label))) })] }), _jsxs("div", { className: "ctl-row", children: [_jsx("span", { className: "bar-label", children: "\u8DE8\u5EA6" }), _jsx("div", { className: "span-fields", children: SPAN_FIELDS.map((f) => (_jsxs("label", { className: "span-field", children: [_jsx("input", { type: "number", min: 0, value: span[f.key] ?? 0, onChange: (e) => setSpan({ ...span, [f.key]: Math.max(0, Number(e.target.value) || 0) }), disabled: isProcessing }), _jsx("span", { children: f.label })] }, f.key))) }), _jsxs("button", { className: "submit-btn", disabled: isProcessing || spanSeconds <= 0, onClick: () => doAdvance(spanSeconds), children: ["\u63A8\u8FDB ", spanSeconds, " \u79D2"] })] }), _jsxs("div", { className: "ctl-row", children: [_jsx("span", { className: "bar-label", children: "\u52A8\u4F5C" }), _jsx("input", { className: "action-input", placeholder: "\u8F93\u5165\u77AC\u95F4\u52A8\u4F5C\uFF08\u7531\u6A21\u578B\u5224\u65AD\u6267\u884C\u65F6\u957F\u5E76\u63A8\u6F14\uFF09\u2026", value: actionText, onChange: (e) => setActionText(e.target.value), onKeyDown: (e) => {
                            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                                e.preventDefault();
                                submitAction();
                            }
                        }, disabled: isProcessing }), _jsx("button", { className: "submit-btn", onClick: submitAction, disabled: isProcessing || !actionText.trim(), children: isProcessing ? _jsx("span", { className: "spinner" }) : '发送' })] })] }));
}
