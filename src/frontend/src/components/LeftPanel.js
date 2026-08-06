import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import { useGameStore } from '../store/gameStore';
import { savesApi, configApi } from '../api/client';
function snapshotName(s) {
    if (typeof s === 'string')
        return s;
    return (s?.name) ?? String(s ?? '');
}
const POLISH_MODE_OPTS = [
    { v: 'none', label: '无润色' },
    { v: 'short', label: '短润色' },
    { v: 'long', label: '长润色' },
];
export default function LeftPanel() {
    const meta = useGameStore((s) => s.meta);
    const activeSave = useGameStore((s) => s.activeSave);
    const refreshMeta = useGameStore((s) => s.refreshMeta);
    const refreshAll = useGameStore((s) => s.refreshAll);
    const protagonist = useGameStore((s) => s.protagonist);
    const setNotification = useGameStore((s) => s.setNotification);
    const setError = useGameStore((s) => s.setError);
    const [editingMeta, setEditingMeta] = useState(false);
    const [metaDraft, setMetaDraft] = useState({ tick_num: 0, game_time: '', era_name: '' });
    const [snapshots, setSnapshots] = useState([]);
    const [cfg, setCfg] = useState({});
    const loadSnapshots = async () => {
        try {
            const data = await savesApi.listSnapshots();
            const items = data?.snapshots ?? [];
            setSnapshots(items.map(snapshotName));
        }
        catch {
            setSnapshots([]);
        }
    };
    const loadCfg = async () => {
        try {
            const c = await configApi.get();
            setCfg({
                polish_mode: c.simulation?.polish_mode ?? 'none',
            });
        }
        catch { /* ignore */ }
    };
    useEffect(() => {
        if (activeSave) {
            loadSnapshots();
        }
        else {
            setSnapshots([]);
        }
    }, [activeSave]);
    useEffect(() => { void loadCfg(); }, []);
    const patchCfg = async (patch) => {
        try {
            const simulation = {
                polish_mode: cfg.polish_mode,
                ...patch,
            };
            await configApi.patch({ simulation });
            setCfg((prev) => ({ ...prev, ...patch }));
            setNotification('设置已更新');
        }
        catch (e) {
            setError(`保存设置失败：${e.message}`);
        }
    };
    const startEditMeta = () => {
        if (meta) {
            setMetaDraft({
                tick_num: meta.tick_num,
                game_time: meta.game_time,
                era_name: meta.era_name ?? '',
            });
            setEditingMeta(true);
        }
    };
    const saveMeta = async () => {
        try {
            await savesApi.updateMeta({
                tick_num: metaDraft.tick_num,
                game_time: metaDraft.game_time,
                era_name: metaDraft.era_name,
            });
            await refreshMeta();
            setEditingMeta(false);
            setNotification('元信息已保存');
        }
        catch (e) {
            setError(`保存失败：${e.message}`);
        }
    };
    const createSnapshot = async () => {
        try {
            const r = await savesApi.createSnapshot();
            setNotification(`快照已创建：${r.created ?? ''}`);
            await loadSnapshots();
        }
        catch (e) {
            setError(`快照失败：${e.message}`);
        }
    };
    const restoreSnapshot = async (name) => {
        if (!confirm(`确认回滚到快照「${name}」？当前进度将被覆盖。`))
            return;
        try {
            await savesApi.restoreSnapshot(name);
            setNotification('快照已回滚');
            await refreshAll();
            await loadSnapshots();
        }
        catch (e) {
            setError(`回滚失败：${e.message}`);
        }
    };
    const deleteSnapshot = async (name) => {
        if (!confirm(`确认删除快照「${name}」？`))
            return;
        try {
            await savesApi.deleteSnapshot(name);
            setNotification('快照已删除');
            await loadSnapshots();
        }
        catch (e) {
            setError(`删除失败：${e.message}`);
        }
    };
    return (_jsxs("div", { className: "left-panel", children: [_jsxs("div", { className: "panel-section", children: [_jsxs("div", { className: "panel-title", children: [_jsx("span", { children: "\u5F53\u524D\u5B58\u6863" }), _jsx("span", { className: "panel-badge", children: activeSave ?? '未激活' })] }), _jsxs("div", { className: "field-row", children: [_jsx("label", { children: "Tick" }), _jsx("span", { className: "value", children: meta?.tick_num ?? '—' })] }), _jsxs("div", { className: "field-row", children: [_jsx("label", { children: "\u6E38\u620F\u65F6\u95F4" }), _jsx("span", { className: "value small", children: meta?.game_time ?? '—' })] }), _jsxs("div", { className: "field-row", children: [_jsx("label", { children: "\u7EAA\u5143" }), _jsx("span", { className: "value", children: meta?.era_name ?? '—' })] }), _jsxs("div", { className: "field-row", children: [_jsx("label", { children: "\u4E3B\u89D2" }), _jsx("span", { className: "value", children: protagonist?.name ?? '—' })] }), _jsxs("div", { className: "panel-actions", children: [_jsx("button", { className: "small", onClick: startEditMeta, disabled: !meta, children: "\u7F16\u8F91" }), _jsx("button", { className: "small", onClick: createSnapshot, disabled: !activeSave, children: "\u5FEB\u7167" }), _jsx("button", { className: "small", onClick: refreshMeta, children: "\u5237\u65B0" })] })] }), _jsxs("div", { className: "panel-section", children: [_jsx("div", { className: "panel-title", children: _jsx("span", { children: "\u5185\u5BB9\u504F\u597D" }) }), _jsxs("div", { className: "field-row field-col", children: [_jsx("label", { children: "\u6DA6\u8272" }), _jsx("select", { value: cfg.polish_mode ?? 'none', onChange: (e) => void patchCfg({ polish_mode: e.target.value }), children: POLISH_MODE_OPTS.map((o) => (_jsx("option", { value: o.v, children: o.label }, o.v))) })] })] }), _jsxs("div", { className: "panel-section", children: [_jsxs("div", { className: "panel-title", children: [_jsx("span", { children: "\u5FEB\u7167" }), _jsx("span", { className: "panel-badge", children: snapshots.length })] }), snapshots.length === 0 ? (_jsx("div", { className: "panel-empty", children: "\u6682\u65E0\u5FEB\u7167\u3002\u70B9\u51FB\u4E0A\u65B9\u300C\u5FEB\u7167\u300D\u4FDD\u5B58\u5F53\u524D\u8FDB\u5EA6\u3002" })) : (_jsx("ul", { className: "snapshot-mini-list", children: snapshots.map((s) => (_jsxs("li", { children: [_jsx("span", { className: "snap-mini-name", title: s, children: s }), _jsx("button", { className: "snap-mini-btn", title: "\u56DE\u6EDA", onClick: () => restoreSnapshot(s), children: "\u21A9" }), _jsx("button", { className: "snap-mini-btn danger", title: "\u5220\u9664", onClick: () => deleteSnapshot(s), children: "\u2715" })] }, s))) }))] }), editingMeta && (_jsx("div", { className: "modal-overlay", onClick: () => setEditingMeta(false), children: _jsxs("div", { className: "modal-card", onClick: (e) => e.stopPropagation(), children: [_jsx("h3", { children: "\u7F16\u8F91\u5143\u4FE1\u606F" }), _jsxs("div", { style: { display: 'flex', flexDirection: 'column', gap: 8 }, children: [_jsxs("label", { children: ["Tick", _jsx("input", { type: "number", value: metaDraft.tick_num, onChange: (e) => setMetaDraft({ ...metaDraft, tick_num: Number(e.target.value) }) })] }), _jsxs("label", { children: ["\u6E38\u620F\u65F6\u95F4", _jsx("input", { type: "text", value: metaDraft.game_time, onChange: (e) => setMetaDraft({ ...metaDraft, game_time: e.target.value }) })] }), _jsxs("label", { children: ["\u7EAA\u5143", _jsx("input", { type: "text", value: metaDraft.era_name, onChange: (e) => setMetaDraft({ ...metaDraft, era_name: e.target.value }) })] })] }), _jsxs("div", { className: "modal-actions", children: [_jsx("button", { onClick: () => setEditingMeta(false), children: "\u53D6\u6D88" }), _jsx("button", { className: "primary", onClick: saveMeta, children: "\u4FDD\u5B58" })] })] }) }))] }));
}
