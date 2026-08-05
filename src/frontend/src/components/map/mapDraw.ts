// 地图绘制辅助函数 — 解析要素 geometry 并用 PixiJS v8 Graphics API 绘制
// 5 层架构（spec 5.6 地图浏览器渲染规范）：
//   static(0) / feature(1) / dynamic(2) / effect(3) / heatmap(4)
import { Container, Graphics, Text, TextStyle } from 'pixi.js';
import { MapFeature } from '../../api/types';

// 按 feature_type 的默认色（spec 规定）
export const DEFAULT_FEATURE_COLORS: Record<string, number> = {
  building: 0x8a7a6a,
  mountain: 0xc8a878,
  river: 0x3a7ad8,
  forest: 0x2a6a3a,
  star: 0xffd700,
  starship: 0xa0a0b0,
  road: 0x6a5a4a,
  wall: 0x5a5a5a,
  lake: 0x2a5ad8,
  sea: 0x1a3aa8,
  grassland: 0x4a6a3a,
  desert: 0xd8c878,
  snow: 0xe8e8e8,
};

// 解析十六进制颜色（支持 "#rrggbb" / "0xrrggbb" / "rgb(...)"）
export function parseColor(hint: string | null | undefined, fallback: number): number {
  if (!hint) return fallback;
  const s = hint.trim();
  if (s.startsWith('0x') || s.startsWith('0X')) {
    const n = parseInt(s, 16);
    return Number.isNaN(n) ? fallback : n;
  }
  if (s.startsWith('#')) {
    const n = parseInt(s.slice(1), 16);
    return Number.isNaN(n) ? fallback : n;
  }
  const m = s.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
  if (m) {
    return (parseInt(m[1]) << 16) | (parseInt(m[2]) << 8) | parseInt(m[3]);
  }
  return fallback;
}

function asNum(v: unknown, d = 0): number {
  const n = typeof v === 'number' ? v : typeof v === 'string' ? parseFloat(v) : NaN;
  return Number.isFinite(n) ? n : d;
}

function asPoints(v: unknown): number[][] {
  if (Array.isArray(v)) {
    return v
      .map((p) => (Array.isArray(p) ? p.map((x) => asNum(x, 0)) : []))
      .filter((p) => p.length >= 2);
  }
  return [];
}

// ============================================================
// 静态层：bbox 边界 + 网格 + 比例尺
// ============================================================
export function drawStaticLayer(
  layer: Container,
  map: { bbox_w: number; bbox_h: number; scale_unit?: string; scale_per_unit?: number },
) {
  layer.removeChildren();
  const w = Math.max(1, map.bbox_w);
  const h = Math.max(1, map.bbox_h);

  // 边界
  const border = new Graphics();
  border.rect(0, 0, w, h).stroke({ width: 2, color: 0x3a3a3a, alpha: 0.8 });
  border.rect(0, 0, w, h).fill({ color: 0x121212, alpha: 0.3 });
  layer.addChild(border);

  // 网格（每 100 单位一条，或自适应）
  const step = chooseGridStep(Math.max(w, h));
  const grid = new Graphics();
  for (let x = step; x < w; x += step) {
    grid.moveTo(x, 0).lineTo(x, h).stroke({ width: 1, color: 0x2a2a2a, alpha: 0.5 });
  }
  for (let y = step; y < h; y += step) {
    grid.moveTo(0, y).lineTo(w, y).stroke({ width: 1, color: 0x2a2a2a, alpha: 0.5 });
  }
  layer.addChild(grid);

  // 比例尺文本
  const style = new TextStyle({ fill: 0x6a6a6a, fontSize: 11, fontFamily: 'Consolas, monospace' });
  const scaleText = new Text({
    text: `bbox ${w}×${h} · grid ${step} · ${map.scale_unit ?? 'unit'}`,
    style,
  });
  scaleText.x = 6;
  scaleText.y = 4;
  layer.addChild(scaleText);
}

function chooseGridStep(maxDim: number): number {
  const targets = [10, 20, 50, 100, 200, 500, 1000, 2000, 5000];
  for (const t of targets) {
    if (maxDim / t <= 30) return t;
  }
  return 10000;
}

// ============================================================
// 要素层：按 shape 绘制单个要素
// ============================================================
export function drawFeature(feature: MapFeature): { g: Graphics; label?: Text; cx: number; cy: number } {
  const fallback = DEFAULT_FEATURE_COLORS[feature.feature_type] ?? 0x8a8a8a;
  const color = parseColor(feature.color_hint, fallback);
  const g = new Graphics();
  g.label = `feature-${feature.id}`;
  let cx = 0;
  let cy = 0;

  const geom = feature.geometry ?? {};
  const alpha = feature.is_obstacle ? 0.45 : 0.35;

  switch (feature.shape) {
    case 'point': {
      cx = asNum(geom.x, 0);
      cy = asNum(geom.y, 0);
      const r = asNum(geom.r, 5);
      g.circle(cx, cy, r).fill({ color, alpha: 0.9 });
      g.circle(cx, cy, r).stroke({ width: 1, color, alpha: 1 });
      break;
    }
    case 'circle': {
      cx = asNum(geom.cx, asNum(geom.x, 0));
      cy = asNum(geom.cy, asNum(geom.y, 0));
      const r = Math.max(1, asNum(geom.r, 10));
      g.circle(cx, cy, r).fill({ color, alpha });
      g.circle(cx, cy, r).stroke({ width: 1.5, color, alpha: 0.9 });
      break;
    }
    case 'line': {
      const pts = asPoints(geom.points);
      if (pts.length >= 2) {
        const width = Math.max(1, asNum(geom.width, 2));
        g.moveTo(pts[0][0], pts[0][1]);
        for (let i = 1; i < pts.length; i++) g.lineTo(pts[i][0], pts[i][1]);
        g.stroke({ width, color, alpha: 0.85 });
        cx = pts.reduce((s, p) => s + p[0], 0) / pts.length;
        cy = pts.reduce((s, p) => s + p[1], 0) / pts.length;
      }
      break;
    }
    case 'polygon': {
      const pts = asPoints(geom.points);
      if (pts.length >= 3) {
        const flat = pts.flat();
        g.poly(flat).fill({ color, alpha });
        g.poly(flat).stroke({ width: 1.5, color, alpha: 0.9 });
        cx = pts.reduce((s, p) => s + p[0], 0) / pts.length;
        cy = pts.reduce((s, p) => s + p[1], 0) / pts.length;
      }
      break;
    }
    case 'volume': {
      // 假 3D：底面 polygon + 顶部偏移 polygon + 侧面
      const pts = asPoints(geom.points);
      const zMax = asNum(geom.z_max, 20);
      if (pts.length >= 3) {
        const flat = pts.flat();
        // 底面
        g.poly(flat).fill({ color, alpha: 0.3 });
        // 顶面（y 向上偏移 zMax）
        const topFlat = pts.flatMap((p) => [p[0], p[1] - zMax]);
        g.poly(topFlat).fill({ color: lighten(color, 30), alpha: 0.5 });
        // 侧面（每条边一个四边形）
        for (let i = 0; i < pts.length; i++) {
          const a = pts[i];
          const b = pts[(i + 1) % pts.length];
          g.moveTo(a[0], a[1]).lineTo(b[0], b[1]).lineTo(b[0], b[1] - zMax).lineTo(a[0], a[1] - zMax).closePath().fill({ color: darken(color, 20), alpha: 0.4 });
        }
        cx = pts.reduce((s, p) => s + p[0], 0) / pts.length;
        cy = pts.reduce((s, p) => s + p[1], 0) / pts.length - zMax / 2;
      }
      break;
    }
    default: {
      // 未知 shape：画一个占位方块
      cx = asNum(geom.x, 0);
      cy = asNum(geom.y, 0);
      g.rect(cx - 4, cy - 4, 8, 8).fill({ color, alpha: 0.6 });
    }
  }

  // 标注名（默认显示，可由上层隐藏）
  let label: Text | undefined;
  if (feature.name) {
    const style = new TextStyle({ fill: 0xc8c8c8, fontSize: 10, fontFamily: 'sans-serif' });
    label = new Text({ text: feature.name, style });
    label.x = cx + 6;
    label.y = cy - 6;
    label.resolution = 2;
  }

  return { g, label, cx, cy };
}

// 颜色明暗辅助
function clamp(n: number): number {
  return Math.max(0, Math.min(255, Math.round(n)));
}
function lighten(color: number, amt: number): number {
  const r = clamp(((color >> 16) & 0xff) + amt);
  const g = clamp(((color >> 8) & 0xff) + amt);
  const b = clamp((color & 0xff) + amt);
  return (r << 16) | (g << 8) | b;
}
function darken(color: number, amt: number): number {
  return lighten(color, -amt);
}

// ============================================================
// 热力图层（简化版：逐格 Graphics fillRect，后续可换 WebGL shader）
// ============================================================
export function drawHeatmapLayer(
  layer: Container,
  heatmaps: Array<{
    group_name?: string;
    grid?: { cells: number[][]; resolution: number; bbox?: { x: number; y: number; w: number; h: number }; min_density?: number; max_density?: number };
  }>,
  mapBbox: { w: number; h: number },
) {
  layer.removeChildren();
  for (const hm of heatmaps) {
    const grid = hm.grid;
    if (!grid || !grid.cells?.length) continue;
    const res = grid.resolution || grid.cells.length;
    const bbox = grid.bbox ?? { x: 0, y: 0, w: mapBbox.w, h: mapBbox.h };
    const cellW = bbox.w / res;
    const cellH = bbox.h / res;
    const max = grid.max_density ?? 1;
    const min = grid.min_density ?? 0;
    const range = Math.max(1e-6, max - min);

    const g = new Graphics();
    for (let r = 0; r < grid.cells.length; r++) {
      const row = grid.cells[r];
      for (let c = 0; c < row.length; c++) {
        const d = (row[c] - min) / range;
        if (d <= 0.01) continue;
        const color = densityColor(d);
        const x = bbox.x + c * cellW;
        const y = bbox.y + r * cellH;
        g.rect(x, y, cellW + 0.5, cellH + 0.5).fill({ color, alpha: 0.6 * d + 0.1 });
      }
    }
    layer.addChild(g);
  }
}

// 密度 → 颜色（蓝→绿→黄→红 5 色阶，对应 spec 的 shader 色阶）
function densityColor(d: number): number {
  const stops = [0x1a3aa8, 0x2a8ad8, 0x4ad86a, 0xd8c84a, 0xd86a4a];
  const t = Math.max(0, Math.min(1, d));
  const seg = t * (stops.length - 1);
  const i = Math.floor(seg);
  const f = seg - i;
  if (i >= stops.length - 1) return stops[stops.length - 1];
  return blend(stops[i], stops[i + 1], f);
}
function blend(a: number, b: number, t: number): number {
  const ar = (a >> 16) & 0xff, ag = (a >> 8) & 0xff, ab = a & 0xff;
  const br = (b >> 16) & 0xff, bg = (b >> 8) & 0xff, bb = b & 0xff;
  const r = Math.round(ar + (br - ar) * t);
  const g = Math.round(ag + (bg - ag) * t);
  const bl = Math.round(ab + (bb - ab) * t);
  return (r << 16) | (g << 8) | bl;
}
