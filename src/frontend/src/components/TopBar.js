import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from 'react';
import { useGameStore } from '../store/gameStore';
import MenuDrawer from './MenuDrawer';
export default function TopBar() {
    const meta = useGameStore((s) => s.meta);
    const activeSave = useGameStore((s) => s.activeSave);
    const protagonist = useGameStore((s) => s.protagonist);
    const refreshAll = useGameStore((s) => s.refreshAll);
    const [menuOpen, setMenuOpen] = useState(false);
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "topbar-section", children: [_jsx("span", { className: "topbar-title", children: "\u8BBE\u8EAB\u5904\u5730 v3" }), activeSave && (_jsxs("span", { className: "meta-chip", children: ["\u5B58\u6863 ", _jsx("strong", { children: activeSave })] }))] }), meta && (_jsx(_Fragment, { children: _jsxs("div", { className: "topbar-section", children: [_jsxs("span", { className: "meta-chip", children: ["Tick ", _jsx("strong", { children: meta.tick_num })] }), _jsxs("span", { className: "meta-chip", children: ["\u65F6\u95F4 ", _jsx("strong", { children: meta.game_time || '—' })] }), meta.era_name && (_jsxs("span", { className: "meta-chip", children: ["\u7EAA\u5143 ", _jsx("strong", { children: meta.era_name })] })), protagonist && (_jsxs("span", { className: "meta-chip", children: ["\u4E3B\u89D2 ", _jsx("strong", { children: protagonist.name })] }))] }) })), _jsx("div", { className: "topbar-spacer" }), _jsxs("div", { className: "topbar-section", children: [_jsx("button", { onClick: () => refreshAll(), title: "\u5237\u65B0\u6240\u6709\u6570\u636E", children: "\u27F3 \u5237\u65B0" }), _jsx("button", { className: "menu-btn", onClick: () => setMenuOpen(true), children: "\u2630 \u83DC\u5355" })] }), menuOpen && _jsx(MenuDrawer, { onClose: () => setMenuOpen(false) })] }));
}
