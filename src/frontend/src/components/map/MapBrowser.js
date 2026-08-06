import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// 地图浏览器 — 全屏浮层
// 组合：面包屑 + 地图选择 + PixiMapRenderer + tooltip
// 数据流：当前 mapId → 加载 features + heatmaps → 传给渲染器
import { useCallback, useEffect, useState } from 'react';
import { useGameStore } from '../../store/gameStore';
import { mapsApi } from '../../api/client';
import PixiMapRenderer from './PixiMapRenderer';
export default function MapBrowser() {
    const open = useGameStore((s) => s.mapBrowserOpen);
    const initialMapId = useGameStore((s) => s.mapBrowserMapId);
    const maps = useGameStore((s) => s.maps);
    const close = useGameStore((s) => s.closeMapBrowser);
    const [currentMapId, setCurrentMapId] = useState(null);
    const [currentMap, setCurrentMap] = useState(null);
    const [features, setFeatures] = useState([]);
    const [heatmaps, setHeatmaps] = useState([]);
    const [loading, setLoading] = useState(false);
    const [tooltip, setTooltip] = useState(null);
    const [error, setError] = useState(null);
    // 打开时初始化 mapId
    useEffect(() => {
        if (!open)
            return;
        const target = initialMapId ??
            maps.find((m) => m.parent_map_id == null)?.id ??
            maps[0]?.id ??
            null;
        setCurrentMapId(target);
    }, [open, initialMapId, maps]);
    // 加载当前地图的数据
    const loadMap = useCallback(async (mapId) => {
        if (mapId == null) {
            setCurrentMap(null);
            setFeatures([]);
            setHeatmaps([]);
            return;
        }
        setLoading(true);
        setError(null);
        try {
            const mapRec = maps.find((m) => m.id === mapId) ?? null;
            setCurrentMap(mapRec);
            const [featRes, heatRes] = await Promise.all([
                mapsApi.features(mapId),
                mapsApi.heatmaps(mapId).catch(() => ({ items: [] })),
            ]);
            setFeatures(featRes.items ?? []);
            setHeatmaps(heatRes.items ?? []);
        }
        catch (e) {
            setError(`加载地图失败：${e.message}`);
        }
        finally {
            setLoading(false);
        }
    }, [maps]);
    useEffect(() => {
        if (open)
            loadMap(currentMapId);
    }, [open, currentMapId, loadMap]);
    // 进入子地图
    const enterChildMap = (childId) => {
        setCurrentMapId(childId);
    };
    const handleHover = (feature, screenX, screenY) => {
        if (!feature) {
            setTooltip(null);
            return;
        }
        const lines = [
            `${feature.name || feature.feature_type}`,
            `类型 ${feature.feature_type} · shape ${feature.shape} · z ${feature.layer_z}`,
        ];
        if (feature.child_map_id != null)
            lines.push('▸ 双击进入子地图');
        setTooltip({ text: lines.join('\n'), x: screenX ?? 0, y: screenY ?? 0 });
    };
    if (!open)
        return null;
    // 面包屑：祖先链
    const breadcrumb = [];
    let cur = currentMap;
    while (cur) {
        breadcrumb.unshift(cur);
        const pid = cur.parent_map_id;
        cur = pid != null ? maps.find((m) => m.id === pid) ?? null : null;
    }
    const heatmapInputs = heatmaps.map((h) => ({
        group_name: h.group_name,
        grid: h.grid ?? undefined,
    }));
    return (_jsxs("div", { className: "map-browser-overlay", children: [_jsxs("div", { className: "map-browser-header", children: [_jsx("div", { className: "map-breadcrumb", children: breadcrumb.length === 0 ? (_jsx("span", { className: "muted", children: "\u672A\u9009\u62E9\u5730\u56FE" })) : (breadcrumb.map((m, i) => (_jsxs("span", { className: "crumb", children: [i > 0 && _jsx("span", { className: "crumb-sep", children: "\u203A" }), _jsx("button", { className: "crumb-btn", onClick: () => setCurrentMapId(m.id), children: m.name })] }, m.id)))) }), _jsxs("select", { className: "map-select", value: currentMapId ?? '', onChange: (e) => setCurrentMapId(Number(e.target.value)), children: [maps.length === 0 && _jsx("option", { value: "", children: "\uFF08\u65E0\u5730\u56FE\uFF09" }), maps.map((m) => (_jsxs("option", { value: m.id, children: [m.name, "\uFF08", m.map_type, "\uFF09"] }, m.id)))] }), _jsx("button", { className: "small", onClick: () => loadMap(currentMapId), disabled: loading, children: "\u27F3 \u5237\u65B0" }), _jsx("button", { className: "small", onClick: close, children: "\u2715 \u5173\u95ED" })] }), _jsxs("div", { className: "map-browser-body", children: [error && _jsx("div", { className: "map-error", children: error }), loading && _jsxs("div", { className: "map-loading", children: [_jsx("span", { className: "spinner" }), " \u52A0\u8F7D\u5730\u56FE\u6570\u636E\u2026"] }), !loading && currentMap && (_jsx(PixiMapRenderer, { map: currentMap, features: features, heatmaps: heatmapInputs, onEnterChildMap: enterChildMap, onHoverFeature: handleHover })), !loading && !currentMap && (_jsx("div", { className: "map-empty", children: "\u8BF7\u9009\u62E9\u4E00\u5F20\u5730\u56FE\uFF0C\u6216\u5148\u5728\u53F3\u9762\u677F\u300C\u5730\u56FE\u300Dtab \u4E2D\u521B\u5EFA\u3002" }))] }), tooltip && (_jsx("div", { className: "map-tooltip", style: { left: tooltip.x + 14, top: tooltip.y + 14 }, children: tooltip.text.split('\n').map((l, i) => (_jsx("div", { className: i === 0 ? 'tt-title' : 'tt-line', children: l }, i))) }))] }));
}
