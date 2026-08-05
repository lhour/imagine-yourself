// 地图浏览器 — 全屏浮层
// 组合：面包屑 + 地图选择 + PixiMapRenderer + tooltip
// 数据流：当前 mapId → 加载 features + heatmaps → 传给渲染器
import { useCallback, useEffect, useState } from 'react';
import { useGameStore } from '../../store/gameStore';
import { mapsApi } from '../../api/client';
import { MapRecord, MapFeature, HeatmapGrid } from '../../api/types';
import PixiMapRenderer, { HeatmapInput } from './PixiMapRenderer';

interface HeatmapItem {
  group_name?: string;
  grid?: HeatmapGrid;
}

export default function MapBrowser() {
  const open = useGameStore((s) => s.mapBrowserOpen);
  const initialMapId = useGameStore((s) => s.mapBrowserMapId);
  const maps = useGameStore((s) => s.maps);
  const close = useGameStore((s) => s.closeMapBrowser);

  const [currentMapId, setCurrentMapId] = useState<number | null>(null);
  const [currentMap, setCurrentMap] = useState<MapRecord | null>(null);
  const [features, setFeatures] = useState<MapFeature[]>([]);
  const [heatmaps, setHeatmaps] = useState<HeatmapItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [tooltip, setTooltip] = useState<{ text: string; x: number; y: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 打开时初始化 mapId
  useEffect(() => {
    if (!open) return;
    const target =
      initialMapId ??
      maps.find((m) => m.parent_map_id == null)?.id ??
      maps[0]?.id ??
      null;
    setCurrentMapId(target);
  }, [open, initialMapId, maps]);

  // 加载当前地图的数据
  const loadMap = useCallback(async (mapId: number | null) => {
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
    } catch (e) {
      setError(`加载地图失败：${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, [maps]);

  useEffect(() => {
    if (open) loadMap(currentMapId);
  }, [open, currentMapId, loadMap]);

  // 进入子地图
  const enterChildMap = (childId: number) => {
    setCurrentMapId(childId);
  };

  const handleHover = (feature: MapFeature | null, screenX?: number, screenY?: number) => {
    if (!feature) {
      setTooltip(null);
      return;
    }
    const lines = [
      `${feature.name || feature.feature_type}`,
      `类型 ${feature.feature_type} · shape ${feature.shape} · z ${feature.layer_z}`,
    ];
    if (feature.child_map_id != null) lines.push('▸ 双击进入子地图');
    setTooltip({ text: lines.join('\n'), x: screenX ?? 0, y: screenY ?? 0 });
  };

  if (!open) return null;

  // 面包屑：祖先链
  const breadcrumb: MapRecord[] = [];
  let cur = currentMap;
  while (cur) {
    breadcrumb.unshift(cur);
    const pid = cur.parent_map_id;
    cur = pid != null ? maps.find((m) => m.id === pid) ?? null : null;
  }

  const heatmapInputs: HeatmapInput[] = heatmaps.map((h) => ({
    group_name: h.group_name,
    grid: h.grid ?? undefined,
  }));

  return (
    <div className="map-browser-overlay">
      <div className="map-browser-header">
        <div className="map-breadcrumb">
          {breadcrumb.length === 0 ? (
            <span className="muted">未选择地图</span>
          ) : (
            breadcrumb.map((m, i) => (
              <span key={m.id} className="crumb">
                {i > 0 && <span className="crumb-sep">›</span>}
                <button className="crumb-btn" onClick={() => setCurrentMapId(m.id)}>
                  {m.name}
                </button>
              </span>
            ))
          )}
        </div>

        <select
          className="map-select"
          value={currentMapId ?? ''}
          onChange={(e) => setCurrentMapId(Number(e.target.value))}
        >
          {maps.length === 0 && <option value="">（无地图）</option>}
          {maps.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}（{m.map_type}）
            </option>
          ))}
        </select>

        <button className="small" onClick={() => loadMap(currentMapId)} disabled={loading}>
          ⟳ 刷新
        </button>
        <button className="small" onClick={close}>✕ 关闭</button>
      </div>

      <div className="map-browser-body">
        {error && <div className="map-error">{error}</div>}
        {loading && <div className="map-loading"><span className="spinner" /> 加载地图数据…</div>}
        {!loading && currentMap && (
          <PixiMapRenderer
            map={currentMap}
            features={features}
            heatmaps={heatmapInputs}
            onEnterChildMap={enterChildMap}
            onHoverFeature={handleHover}
          />
        )}
        {!loading && !currentMap && (
          <div className="map-empty">请选择一张地图，或先在右面板「地图」tab 中创建。</div>
        )}
      </div>

      {tooltip && (
        <div
          className="map-tooltip"
          style={{ left: tooltip.x + 14, top: tooltip.y + 14 }}
        >
          {tooltip.text.split('\n').map((l, i) => (
            <div key={i} className={i === 0 ? 'tt-title' : 'tt-line'}>{l}</div>
          ))}
        </div>
      )}
    </div>
  );
}
