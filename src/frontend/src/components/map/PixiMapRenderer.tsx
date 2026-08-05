// PixiJS 地图渲染器（5 层 Container 架构）
// 对应 spec 5.6「PixiJS 五层 Container 设计」
//   static(0) / feature(1) / dynamic(2) / effect(3) / heatmap(4)
// 使用原生 pixi.js v8（非 @pixi/react，避免 React 协调开销）
import { useEffect, useRef, useState } from 'react';
import { Application, Container, FederatedPointerEvent, Text } from 'pixi.js';
import { MapRecord, MapFeature } from '../../api/types';
import { drawStaticLayer, drawFeature, drawHeatmapLayer } from './mapDraw';

export interface HeatmapInput {
  group_name?: string;
  grid?: {
    cells: number[][];
    resolution: number;
    bbox?: { x: number; y: number; w: number; h: number };
    min_density?: number;
    max_density?: number;
  };
}

interface Props {
  map: MapRecord;
  features: MapFeature[];
  heatmaps: HeatmapInput[];
  onEnterChildMap?: (mapId: number) => void;
  onHoverFeature?: (feature: MapFeature | null, screenX?: number, screenY?: number) => void;
}

export default function PixiMapRenderer({ map, features, heatmaps, onEnterChildMap, onHoverFeature }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const appRef = useRef<Application | null>(null);
  const [showLabels, setShowLabels] = useState(true);
  const [zoom, setZoom] = useState(1);

  // 缩放/平移状态（DOM 控制 → 传给 PixiJS）
  const viewportRef = useRef<Container | null>(null);
  const panState = useRef<{ dragging: boolean; lastX: number; lastY: number }>({ dragging: false, lastX: 0, lastY: 0 });

  useEffect(() => {
    let destroyed = false;
    const host = hostRef.current;
    if (!host) return;

    const app = new Application();
    appRef.current = app;

    (async () => {
      const w = host.clientWidth || 800;
      const h = host.clientHeight || 600;
      await app.init({
        width: w,
        height: h,
        background: 0x0a0a0a,
        antialias: true,
        eventMode: 'auto',
      });
      if (destroyed) {
        app.destroy(true);
        return;
      }
      host.appendChild(app.canvas);

      // viewport：所有图层挂在其下，通过 transform 实现平移/缩放
      const viewport = new Container();
      viewport.sortableChildren = true;
      viewport.eventMode = 'static';
      app.stage.addChild(viewport);
      viewportRef.current = viewport;

      // 5 个图层 Container
      const staticLayer = new Container(); staticLayer.zIndex = 0;
      const featureLayer = new Container(); featureLayer.zIndex = 1;
      const dynamicLayer = new Container(); dynamicLayer.zIndex = 2;
      const effectLayer = new Container(); effectLayer.zIndex = 3;
      const heatmapLayer = new Container(); heatmapLayer.zIndex = 4;
      viewport.addChild(staticLayer, featureLayer, dynamicLayer, effectLayer, heatmapLayer);

      // 初始：把地图 bbox 居中适配到视口
      const mapW = Math.max(1, map.bbox_w);
      const mapH = Math.max(1, map.bbox_h);
      const fitScale = Math.min(w / mapW, h / mapH) * 0.9;
      viewport.scale.set(fitScale);
      viewport.x = (w - mapW * fitScale) / 2;
      viewport.y = (h - mapH * fitScale) / 2;
      setZoom(fitScale);

      // 1. 静态层
      drawStaticLayer(staticLayer, map);

      // 2. 要素层（按 layer_z 升序）
      const sorted = [...features].sort((a, b) => a.layer_z - b.layer_z);
      for (const f of sorted) {
        const { g, label } = drawFeature(f);
        g.eventMode = 'static';
        g.cursor = 'pointer';
        // 悬停 → tooltip
        g.on('pointermove', (e: FederatedPointerEvent) => {
          const pos = e.client;
          onHoverFeature?.(f, pos.x, pos.y);
        });
        g.on('pointerout', () => onHoverFeature?.(null));
        // 点击：若有子地图 → 进入；否则也回调
        g.on('pointertap', () => {
          if (f.child_map_id != null) {
            onEnterChildMap?.(f.child_map_id);
          }
        });
        featureLayer.addChild(g);
        if (label) {
          label.visible = showLabels;
          featureLayer.addChild(label);
        }
      }

      // 4. 热力图层
      drawHeatmapLayer(heatmapLayer, heatmaps, { w: mapW, h: mapH });

      // 交互：滚轮缩放
      const onWheel = (e: WheelEvent) => {
        e.preventDefault();
        const factor = e.deltaY > 0 ? 0.9 : 1.1;
        const newScale = Math.max(0.1, Math.min(20, viewport.scale.x * factor));
        // 以鼠标位置为缩放中心
        const rect = app.canvas.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        const localX = (mx - viewport.x) / viewport.scale.x;
        const localY = (my - viewport.y) / viewport.scale.y;
        viewport.scale.set(newScale);
        viewport.x = mx - localX * newScale;
        viewport.y = my - localY * newScale;
        setZoom(newScale);
      };
      app.canvas.addEventListener('wheel', onWheel, { passive: false });

      // 交互：拖拽平移
      const onPointerDown = (e: FederatedPointerEvent) => {
        panState.current = { dragging: true, lastX: e.clientX, lastY: e.clientY };
      };
      const onPointerMove = (e: FederatedPointerEvent) => {
        if (!panState.current.dragging) return;
        const dx = e.clientX - panState.current.lastX;
        const dy = e.clientY - panState.current.lastY;
        panState.current.lastX = e.clientX;
        panState.current.lastY = e.clientY;
        viewport.x += dx;
        viewport.y += dy;
      };
      const onPointerUp = () => {
        panState.current.dragging = false;
      };
      viewport.on('pointerdown', onPointerDown);
      viewport.on('globalpointermove', onPointerMove);
      viewport.on('pointerup', onPointerUp);
      viewport.on('pointerupoutside', onPointerUp);
    })();

    return () => {
      destroyed = true;
      if (appRef.current) {
        appRef.current.destroy(true);
        appRef.current = null;
      }
      viewportRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, features, heatmaps]);

  // 切换标注显示
  useEffect(() => {
    const vp = viewportRef.current;
    if (!vp) return;
    const featureLayer = vp.children.find((c) => c.zIndex === 1) as Container | undefined;
    if (!featureLayer) return;
    featureLayer.children.forEach((child) => {
      // Text 类型才切换可见性（Graphics 跳过）
      if (child instanceof Text) {
        child.visible = showLabels;
      }
    });
  }, [showLabels]);

  // 重置视图按钮
  const resetView = () => {
    const vp = viewportRef.current;
    const app = appRef.current;
    if (!vp || !app) return;
    const w = app.canvas.width;
    const h = app.canvas.height;
    const mapW = Math.max(1, map.bbox_w);
    const mapH = Math.max(1, map.bbox_h);
    const fitScale = Math.min(w / mapW, h / mapH) * 0.9;
    vp.scale.set(fitScale);
    vp.x = (w - mapW * fitScale) / 2;
    vp.y = (h - mapH * fitScale) / 2;
    setZoom(fitScale);
  };

  return (
    <div className="pixi-renderer-wrap">
      <div className="pixi-canvas-host" ref={hostRef} />
      <div className="pixi-toolbar">
        <button className="small" onClick={() => setShowLabels((v) => !v)}>
          {showLabels ? '🏷 隐藏标注' : '🏷 显示标注'}
        </button>
        <button className="small" onClick={resetView}>⊕ 重置视图</button>
        <span className="muted small">缩放 {(zoom * 100).toFixed(0)}%</span>
      </div>
    </div>
  );
}
