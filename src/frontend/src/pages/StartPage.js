import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AdminNav from '../components/AdminNav';
import { useGameStore } from '../store/gameStore';
import { dramasApi } from '../api/client';
export default function StartPage() {
    const navigate = useNavigate();
    const saves = useGameStore((s) => s.saves);
    const refreshSaves = useGameStore((s) => s.refreshSaves);
    const switchSave = useGameStore((s) => s.switchSave);
    const setNotification = useGameStore((s) => s.setNotification);
    const setError = useGameStore((s) => s.setError);
    const [dramas, setDramas] = useState([]);
    const [initDrama, setInitDrama] = useState(null);
    const [saveName, setSaveName] = useState('');
    const [initializing, setInitializing] = useState(false);
    useEffect(() => {
        refreshSaves();
        dramasApi.list().then(setDramas).catch(() => { });
    }, [refreshSaves]);
    const handleEnter = async (name) => {
        await switchSave(name);
        navigate('/play');
    };
    const handleInit = async () => {
        if (!initDrama || !saveName.trim()) {
            setError('请填写存档名');
            return;
        }
        setInitializing(true);
        try {
            const r = await dramasApi.init(initDrama, saveName.trim(), false);
            const stats = r.stats || {};
            setNotification(`剧本已导入！角色 ${stats.characters ?? 0} / 群体 ${stats.groups ?? 0} / 事件 ${stats.events ?? 0}`);
            await switchSave(saveName.trim());
            navigate('/play');
        }
        catch (e) {
            setError(`导入失败：${e instanceof Error ? e.message : e}`);
        }
        finally {
            setInitializing(false);
        }
    };
    return (_jsxs("div", { className: "admin-page", children: [_jsx(AdminNav, {}), _jsxs("div", { className: "admin-content", children: [_jsxs("div", { className: "hero", children: [_jsx("h1", { children: "\u8BBE\u8EAB\u5904\u5730" }), _jsx("div", { className: "hero-subtitle", children: "v3 \u00B7 \u5BA2\u89C2/\u4E3B\u89C2\u53CC\u8F68\u5236\u53D9\u4E8B\u5F15\u64CE" }), _jsxs("div", { className: "hero-actions", children: [_jsx("button", { onClick: () => navigate('/dramas'), className: "btn-primary", children: "\uD83D\uDCDC \u6D4F\u89C8\u5267\u672C" }), _jsx("button", { onClick: () => navigate('/saves'), className: "btn-secondary", children: "\uD83D\uDCC2 \u8BFB\u53D6\u5B58\u6863" })] })] }), saves.length > 0 && (_jsxs("section", { className: "home-section", children: [_jsx("h2", { children: "\uD83D\uDCC2 \u6700\u8FD1\u5B58\u6863" }), _jsx("div", { className: "save-tiles", children: saves.slice(0, 5).map((name) => (_jsxs("div", { className: "save-tile", onClick: () => handleEnter(name), children: [_jsx("span", { className: "save-tile-icon", children: "\uD83C\uDFAE" }), _jsx("span", { className: "save-tile-name", children: name }), _jsx("span", { className: "save-tile-hint", children: "\u70B9\u51FB\u8FDB\u5165 \u2192" })] }, name))) })] })), _jsxs("section", { className: "home-section", children: [_jsx("h2", { children: "\uD83D\uDCDC \u53EF\u7528\u5267\u672C\uFF08\u70B9\u51FB\u5BFC\u5165\u65B0\u5B58\u6863\uFF09" }), dramas.length === 0 ? (_jsxs("div", { className: "empty-hint", children: ["\u6682\u65E0\u5267\u672C\uFF0C", _jsx("a", { href: "#/dramas", children: "\u524D\u5F80\u5267\u672C\u7BA1\u7406" })] })) : (_jsx("div", { className: "drama-grid", children: dramas.map((d) => (_jsxs("div", { className: "drama-card", children: [_jsxs("div", { className: "drama-card-cover", children: [_jsx("span", { className: "drama-cover-icon", children: "\uD83D\uDCD6" }), _jsxs("span", { className: "drama-cover-files", children: [d.files.length, " \u6587\u4EF6"] })] }), _jsxs("div", { className: "drama-card-body", children: [_jsx("h3", { children: d.title }), _jsxs("div", { className: "drama-meta", children: [_jsxs("span", { children: ["\uD83D\uDC64 ", d.protagonist_default || '未指定'] }), _jsxs("span", { children: ["\u23F0 ", d.start_game_time || '—'] })] }), _jsx("p", { className: "drama-summary", children: d.summary }), _jsx("button", { className: "btn-primary", onClick: () => { setInitDrama(d.name); setSaveName(`${d.name}_run`); }, children: "\u25B6 \u5BFC\u5165\u5E76\u5F00\u59CB" })] })] }, d.name))) }))] }), initDrama && (_jsx("div", { className: "modal-overlay", onClick: () => setInitDrama(null), children: _jsxs("div", { className: "modal", onClick: (e) => e.stopPropagation(), children: [_jsxs("div", { className: "modal-header", children: [_jsxs("h2", { children: ["\u25B6 \u5BFC\u5165\u5267\u672C \"", initDrama, "\" \u4E3A\u65B0\u5B58\u6863"] }), _jsx("button", { onClick: () => setInitDrama(null), className: "btn-icon", children: "\u2715" })] }), _jsxs("div", { className: "form-group", children: [_jsx("label", { children: "\u65B0\u5B58\u6863\u540D" }), _jsx("input", { value: saveName, onChange: (e) => setSaveName(e.target.value), placeholder: "my_save" })] }), _jsxs("div", { className: "modal-actions", children: [_jsx("button", { onClick: () => setInitDrama(null), className: "btn-secondary", children: "\u53D6\u6D88" }), _jsx("button", { onClick: handleInit, disabled: initializing, className: "btn-primary", children: initializing ? '⏳ 导入中...' : '🚀 开始游戏' })] })] }) }))] })] }));
}
