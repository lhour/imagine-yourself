import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// 菜单栏抽屉（右上角弹出）— 对应 spec 5.6
// 菜单项：角色 / 群体 / 地图 / 物品 / 设定 / 记忆宫殿 / 管理员模式
import { useGameStore } from '../store/gameStore';
export default function MenuDrawer({ onClose }) {
    const setRightTab = useGameStore((s) => s.setRightTab);
    const openMapBrowser = useGameStore((s) => s.openMapBrowser);
    const maps = useGameStore((s) => s.maps);
    const goTab = (tab) => {
        setRightTab(tab);
        onClose();
    };
    const openMap = () => {
        // 默认打开第一张根地图（无 parent_map_id），否则第一张
        const root = maps.find((m) => m.parent_map_id == null) ?? maps[0] ?? null;
        openMapBrowser(root?.id ?? null);
        onClose();
    };
    const items = [
        { icon: '🧍', label: '角色', desc: '全部角色卡 · 属性/位置/任务', action: () => goTab('characters') },
        { icon: '👥', label: '群体', desc: '群体树 + 热力图预览', action: () => goTab('groups') },
        { icon: '🗺', label: '地图', desc: '地图浏览器（地形 + 热力图 + 测距）', action: openMap },
        { icon: '🎒', label: '物品', desc: '按类型/稀有度筛选', action: () => goTab('items') },
        { icon: '📜', label: '设定', desc: '世界/时代/文化/超自然', action: () => onClose() },
        { icon: '🧠', label: '记忆宫殿', desc: '主角视角记忆分层树', action: () => goTab('memory') },
        { icon: '⚙', label: '管理员模式', desc: '全局配置临时修改', action: () => onClose() },
    ];
    return (_jsx("div", { className: "drawer-overlay", onClick: onClose, children: _jsxs("div", { className: "drawer-card", onClick: (e) => e.stopPropagation(), children: [_jsxs("div", { className: "drawer-header", children: [_jsx("span", { children: "\u83DC\u5355" }), _jsx("button", { className: "drawer-close", onClick: onClose, children: "\u2715" })] }), _jsx("div", { className: "drawer-list", children: items.map((it) => (_jsxs("button", { className: "drawer-item", onClick: it.action, children: [_jsx("span", { className: "drawer-icon", children: it.icon }), _jsxs("span", { className: "drawer-text", children: [_jsx("span", { className: "drawer-label", children: it.label }), _jsx("span", { className: "drawer-desc", children: it.desc })] }), _jsx("span", { className: "drawer-arrow", children: "\u203A" })] }, it.label))) })] }) }));
}
