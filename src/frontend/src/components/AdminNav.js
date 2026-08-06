import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Link, useLocation, useNavigate } from 'react-router-dom';
const NAV_ITEMS = [
    { path: '/', label: '首页', icon: '🏠' },
    { path: '/saves', label: '存档', icon: '📂' },
    { path: '/dramas', label: '剧本', icon: '📜' },
    { path: '/model', label: '模型', icon: '🤖' },
    { path: '/settings', label: '设置', icon: '⚙' },
    { path: '/play', label: '游戏', icon: '🎮' },
];
export default function AdminNav() {
    const location = useLocation();
    const navigate = useNavigate();
    const current = location.pathname;
    return (_jsx("nav", { className: "admin-nav", children: _jsxs("div", { className: "admin-nav-inner", children: [_jsxs("div", { className: "admin-nav-brand", onClick: () => navigate('/'), children: [_jsx("span", { className: "brand-icon", children: "\u2726" }), _jsx("span", { className: "brand-text", children: "\u8BBE\u8EAB\u5904\u5730 v3" })] }), _jsx("ul", { className: "admin-nav-list", children: NAV_ITEMS.map((item) => {
                        const active = current === item.path || (item.path !== '/' && current.startsWith(item.path));
                        return (_jsx("li", { className: active ? 'active' : '', children: _jsxs(Link, { to: item.path, children: [_jsx("span", { className: "nav-icon", children: item.icon }), _jsx("span", { className: "nav-label", children: item.label })] }) }, item.path));
                    }) })] }) }));
}
