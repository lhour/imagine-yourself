import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AdminNav from '../components/AdminNav';
import { savesApi } from '../api/client';
import { useGameStore } from '../store/gameStore';
export default function SavesPage() {
    const navigate = useNavigate();
    const setNotification = useGameStore((s) => s.setNotification);
    const setError = useGameStore((s) => s.setError);
    const switchSave = useGameStore((s) => s.switchSave);
    const [saves, setSaves] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedSave, setSelectedSave] = useState(null);
    const [snapshots, setSnapshots] = useState([]);
    const [showSnapshots, setShowSnapshots] = useState(false);
    const refresh = async () => {
        setLoading(true);
        try {
            const list = await savesApi.list();
            const rows = [];
            for (const name of list) {
                try {
                    await savesApi.switch(name);
                    const meta = await savesApi.getMeta();
                    rows.push({ name, meta });
                }
                catch {
                    rows.push({ name });
                }
            }
            // 切回第一个存档（如果有）
            if (rows.length > 0) {
                await savesApi.switch(rows[0].name);
            }
            setSaves(rows);
        }
        catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            setError(`加载存档列表失败：${msg}`);
        }
        finally {
            setLoading(false);
        }
    };
    useEffect(() => {
        refresh();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
    const handleEnter = async (name) => {
        try {
            await switchSave(name);
            navigate('/play');
        }
        catch (e) {
            setError(`进入存档失败：${e instanceof Error ? e.message : e}`);
        }
    };
    const handleCopy = async (name) => {
        const newName = window.prompt(`复制存档 "${name}" 为：`, `${name}_copy`);
        if (!newName)
            return;
        try {
            await savesApi.create(newName);
            setNotification(`已创建空存档 ${newName}（复制数据功能待 v3.1 接入）`);
            refresh();
        }
        catch (e) {
            setError(`复制失败：${e instanceof Error ? e.message : e}`);
        }
    };
    const handleDelete = async (name) => {
        if (!window.confirm(`确定删除存档 "${name}"？此操作不可恢复。`))
            return;
        try {
            await savesApi.delete(name);
            setNotification(`已删除存档 ${name}`);
            refresh();
        }
        catch (e) {
            setError(`删除失败：${e instanceof Error ? e.message : e}`);
        }
    };
    const handleShowSnapshots = async (name) => {
        try {
            await savesApi.switch(name);
            const r = await savesApi.listSnapshots();
            setSnapshots(r.snapshots || []);
            setSelectedSave(name);
            setShowSnapshots(true);
        }
        catch (e) {
            setError(`加载快照失败：${e instanceof Error ? e.message : e}`);
        }
    };
    const handleCreateSnapshot = async () => {
        try {
            await savesApi.createSnapshot();
            setNotification('快照已创建');
            const r = await savesApi.listSnapshots();
            setSnapshots(r.snapshots || []);
        }
        catch (e) {
            setError(`创建快照失败：${e instanceof Error ? e.message : e}`);
        }
    };
    const handleRestore = async (snap) => {
        if (!window.confirm(`确定回滚到快照 "${snap}"？当前未保存的进度将丢失。`))
            return;
        try {
            await savesApi.restoreSnapshot(snap);
            setNotification(`已回滚到 ${snap}`);
            setShowSnapshots(false);
        }
        catch (e) {
            setError(`回滚失败：${e instanceof Error ? e.message : e}`);
        }
    };
    const handleDeleteSnap = async (snap) => {
        if (!window.confirm(`删除快照 "${snap}"？`))
            return;
        try {
            await savesApi.deleteSnapshot(snap);
            setNotification(`已删除快照 ${snap}`);
            const r = await savesApi.listSnapshots();
            setSnapshots(r.snapshots || []);
        }
        catch (e) {
            setError(`删除失败：${e instanceof Error ? e.message : e}`);
        }
    };
    return (_jsxs("div", { className: "admin-page", children: [_jsx(AdminNav, {}), _jsxs("div", { className: "admin-content", children: [_jsxs("div", { className: "admin-header", children: [_jsx("h1", { children: "\uD83D\uDCC2 \u8BFB\u53D6\u5B58\u6863" }), _jsx("button", { onClick: refresh, disabled: loading, className: "btn-secondary", children: loading ? '加载中...' : '🔄 刷新' })] }), saves.length === 0 && !loading ? (_jsxs("div", { className: "empty-state", children: [_jsx("p", { children: "\u6682\u65E0\u5B58\u6863\u3002\u8BF7\u5148\u5230\u300C\u5267\u672C\u300D\u9875\u5BFC\u5165\u4E00\u4E2A\u5267\u672C\u751F\u6210\u5B58\u6863\u3002" }), _jsx("button", { onClick: () => navigate('/dramas'), className: "btn-primary", children: "\uD83D\uDCDC \u53BB\u5267\u672C\u7BA1\u7406" })] })) : (_jsxs("table", { className: "data-table", children: [_jsx("thead", { children: _jsxs("tr", { children: [_jsx("th", { children: "\u5B58\u6863\u540D" }), _jsx("th", { children: "\u5267\u672C" }), _jsx("th", { children: "tick" }), _jsx("th", { children: "\u6E38\u620F\u65F6\u95F4" }), _jsx("th", { children: "\u4E3B\u89D2 ID" }), _jsx("th", { children: "\u64CD\u4F5C" })] }) }), _jsx("tbody", { children: saves.map((s) => (_jsxs("tr", { children: [_jsx("td", { children: _jsx("strong", { children: s.name }) }), _jsx("td", { children: s.meta?.script_name || '—' }), _jsx("td", { children: s.meta?.tick_num ?? '—' }), _jsx("td", { children: s.meta?.game_time || '—' }), _jsx("td", { children: s.meta?.protagonist_id ?? '—' }), _jsxs("td", { className: "actions", children: [_jsx("button", { onClick: () => handleEnter(s.name), className: "btn-icon", title: "\u8FDB\u5165", children: "\u25B6" }), _jsx("button", { onClick: () => handleCopy(s.name), className: "btn-icon", title: "\u590D\u5236", children: "\uD83D\uDCCB" }), _jsx("button", { onClick: () => handleShowSnapshots(s.name), className: "btn-icon", title: "\u5FEB\u7167", children: "\uD83D\uDD52" }), _jsx("button", { onClick: () => handleDelete(s.name), className: "btn-icon btn-danger", title: "\u5220\u9664", children: "\uD83D\uDDD1" })] })] }, s.name))) })] })), showSnapshots && (_jsx("div", { className: "modal-overlay", onClick: () => setShowSnapshots(false), children: _jsxs("div", { className: "modal", onClick: (e) => e.stopPropagation(), children: [_jsxs("div", { className: "modal-header", children: [_jsxs("h2", { children: ["\uD83D\uDD52 \u5B58\u6863 \"", selectedSave, "\" \u7684\u5FEB\u7167"] }), _jsx("button", { onClick: () => setShowSnapshots(false), className: "btn-icon", children: "\u2715" })] }), _jsx("div", { className: "modal-actions", children: _jsx("button", { onClick: handleCreateSnapshot, className: "btn-primary", children: "+ \u521B\u5EFA\u5FEB\u7167" }) }), snapshots.length === 0 ? (_jsx("p", { className: "empty-hint", children: "\u6682\u65E0\u5FEB\u7167" })) : (_jsx("ul", { className: "snapshot-list", children: snapshots.map((snap) => {
                                        const name = typeof snap === 'string' ? snap : snap.name;
                                        return (_jsxs("li", { children: [_jsx("span", { className: "snap-name", children: name }), _jsx("button", { onClick: () => handleRestore(name), className: "btn-icon", title: "\u56DE\u6EDA", children: "\u21A9" }), _jsx("button", { onClick: () => handleDeleteSnap(name), className: "btn-icon btn-danger", title: "\u5220\u9664", children: "\uD83D\uDDD1" })] }, name));
                                    }) }))] }) }))] })] }));
}
