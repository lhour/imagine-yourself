import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import AdminNav from '../components/AdminNav';
import { tracesApi, TraceSummary } from '../api/client';
import { useGameStore } from '../store/gameStore';
import './RequestLogPage.css';

interface SpanNode {
  id: string;
  name: string;
  type: string;
  status: string;
  start_ms: number;
  end_ms: number | null;
  duration_ms: number | null;
  thread_id: number;
  data: Record<string, unknown>;
  children: SpanNode[];
  token_usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    cache_hit_tokens: number;
    cache_miss_tokens: number;
    direct_prompt_tokens: number;
    direct_completion_tokens: number;
    direct_total_tokens: number;
    direct_cache_hit_tokens: number;
    direct_cache_miss_tokens: number;
    child_prompt_tokens: number;
    child_completion_tokens: number;
    child_total_tokens: number;
    child_cache_hit_tokens: number;
    child_cache_miss_tokens: number;
  };
}

const TYPE_COLORS: Record<string, string> = {
  request: '#8a5a2a',
  step: '#2f6f9f',
  skill_call: '#3d8a4a',
  model_call: '#9a4a6a',
  tool_call: '#b08a2a',
};

const TYPE_LABELS: Record<string, string> = {
  request: '请求',
  step: '步骤',
  skill_call: 'Skill',
  model_call: '模型调用',
  tool_call: '工具调用',
};

const ALL_TYPES = ['request', 'step', 'skill_call', 'model_call', 'tool_call'] as const;

function flattenAll(roots: SpanNode[]): SpanNode[] {
  const out: SpanNode[] = [];
  const walk = (n: SpanNode) => {
    out.push(n);
    for (const c of n.children) walk(c);
  };
  for (const r of roots) walk(r);
  return out;
}

function fmtTime(ms: number | null | undefined): string {
  if (ms == null) return '—';
  if (ms < 1000) return `${ms.toFixed(1)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function fmtTokens(tokens: number | undefined): string {
  if (!tokens) return '0';
  if (tokens >= 1000) return `${(tokens / 1000).toFixed(1)}k`;
  return String(tokens);
}

function calcTotalTokens(node: SpanNode): number {
  if (node.token_usage?.total_tokens) return node.token_usage.total_tokens;
  let sum = 0;
  for (const c of node.children) sum += calcTotalTokens(c);
  return sum;
}

function calcDirectTokens(node: SpanNode): number {
  if (node.token_usage?.direct_total_tokens) return node.token_usage.direct_total_tokens;
  if (node.token_usage?.direct_total_tokens === 0) return 0;
  if (node.type === 'model_call' && node.data?.usage) {
    const u = node.data.usage as Record<string, number>;
    return u.total_tokens || (u.prompt_tokens || 0) + (u.completion_tokens || 0);
  }
  return 0;
}

function TextBlock({ label, value }: { label: string; value: unknown }) {
  if (value === undefined || value === null || value === '') return null;
  let text: string;
  if (typeof value === 'string') text = value;
  else if (typeof value === 'object') text = JSON.stringify(value, null, 2);
  else text = String(value);
  return (
    <div className="tl-block">
      <div className="tl-block-label">{label}</div>
      <pre className="tl-block-pre">{text}</pre>
    </div>
  );
}

function TokenBadge({ tokens, label }: { tokens: number; label?: string }) {
  if (!tokens) return null;
  return (
    <span className="tl-token-badge" title={label || `${tokens} tokens`}>
      {fmtTokens(tokens)}t
    </span>
  );
}

function SpanDetail({ span }: { span: SpanNode }) {
  const d = span.data || {};
  const tu = span.token_usage;
  const directTokens = calcDirectTokens(span);
  const totalTokens = tu?.total_tokens ?? calcTotalTokens(span);
  const hasChildren = span.children.length > 0;
  const childTokens = tu?.child_total_tokens ?? (totalTokens - directTokens);

  const tuCacheHit = tu?.cache_hit_tokens ?? 0;
  const tuCacheMiss = tu?.cache_miss_tokens ?? 0;
  const u = d.usage as Record<string, number> | undefined;
  const directCacheHit = u?.prompt_cache_hit_tokens ?? 0;
  const directCacheMiss = u?.prompt_cache_miss_tokens ?? 0;
  const cacheHit = tuCacheHit > 0 ? tuCacheHit : directCacheHit;
  const cacheMiss = tuCacheMiss > 0 ? tuCacheMiss : directCacheMiss;
  const cacheTotal = cacheHit + cacheMiss;
  const cacheRate = cacheTotal > 0 ? (cacheHit / cacheTotal * 100) : 0;

  return (
    <div className="tl-detail">
      <div className="tl-detail-head">
        <span className={`tl-badge tl-badge-${span.type}`}>
          {TYPE_LABELS[span.type] || span.type}
        </span>
        <span className="tl-detail-name">{span.name}</span>
        <span className="tl-detail-meta">
          {fmtTime(span.duration_ms)} · 线程 {span.thread_id} · {span.status}
        </span>
      </div>

      {(totalTokens > 0 || directTokens > 0) && (
        <div className="tl-token-section">
          <div className="tl-token-section-title">Token 消耗</div>
          <div className="tl-token-grid">
            <div className="tl-token-cell">
              <span className="tl-token-cell-label">总计</span>
              <span className="tl-token-cell-value tl-token-total">{fmtTokens(totalTokens)}</span>
            </div>
            {tu && (
              <>
                <div className="tl-token-cell">
                  <span className="tl-token-cell-label">输入</span>
                  <span className="tl-token-cell-value">{fmtTokens(tu.prompt_tokens)}</span>
                </div>
                <div className="tl-token-cell">
                  <span className="tl-token-cell-label">输出</span>
                  <span className="tl-token-cell-value">{fmtTokens(tu.completion_tokens)}</span>
                </div>
              </>
            )}
            {directTokens > 0 && (
              <div className="tl-token-cell" title="本节点直接消耗">
                <span className="tl-token-cell-label">本节点</span>
                <span className="tl-token-cell-value">{fmtTokens(directTokens)}</span>
              </div>
            )}
            {hasChildren && childTokens > 0 && (
              <div className="tl-token-cell" title="子节点累计">
                <span className="tl-token-cell-label">子节点</span>
                <span className="tl-token-cell-value">{fmtTokens(childTokens)}</span>
              </div>
            )}
            {cacheTotal > 0 && (
              <div className="tl-token-cell tl-token-cache">
                <span className="tl-token-cell-label">缓存命中</span>
                <span className="tl-token-cell-value">
                  {fmtTokens(cacheHit)}
                  <span className="tl-token-cache-rate" title={`命中率 ${cacheRate.toFixed(1)}%`}>
                    {cacheRate > 0 ? ` · ${cacheRate.toFixed(0)}%` : ''}
                  </span>
                </span>
              </div>
            )}
          </div>
          {cacheTotal > 0 && (
            <div className="tl-cache-bar-container" title={`命中率 ${cacheRate.toFixed(1)}%`}>
              {cacheHit > 0 && (
                <div
                  className="tl-cache-bar tl-cache-bar-hit"
                  style={{ width: `${(cacheHit / cacheTotal) * 100}%` }}
                />
              )}
              {cacheMiss > 0 && (
                <div
                  className="tl-cache-bar tl-cache-bar-miss"
                  style={{ width: `${(cacheMiss / cacheTotal) * 100}%` }}
                />
              )}
              <span className="tl-cache-bar-label">
                命中率 {cacheRate.toFixed(1)}% · 命中 {fmtTokens(cacheHit)} · 未命中 {fmtTokens(cacheMiss)}
              </span>
            </div>
          )}
          {totalTokens > 0 && (
            <div className="tl-token-bar-container">
              {directTokens > 0 && (
                <div
                  className="tl-token-bar tl-token-bar-direct"
                  style={{ width: `${(directTokens / totalTokens) * 100}%` }}
                  title={`本节点 ${fmtTokens(directTokens)}`}
                />
              )}
              {childTokens > 0 && (
                <div
                  className="tl-token-bar tl-token-bar-child"
                  style={{ width: `${(childTokens / totalTokens) * 100}%` }}
                  title={`子节点 ${fmtTokens(childTokens)}`}
                />
              )}
            </div>
          )}
        </div>
      )}

      {span.type === 'model_call' && (
        <>
          <TextBlock label="System Prompt" value={d.system_prompt} />
          <TextBlock label="User Prompt" value={d.user_prompt} />
          <TextBlock label="Think（思考）" value={d.think} />
          <TextBlock label="Output（输出）" value={d.output} />
          <TextBlock label="请求的工具参数" value={d.tool_calls_requested} />
          <TextBlock label="Usage" value={d.usage} />
          <TextBlock label="模型参数" value={{ model: d.model, temperature: d.temperature, max_tokens: d.max_tokens }} />
        </>
      )}
      {span.type === 'tool_call' && (
        <>
          <TextBlock label="工具名" value={span.name.replace(/^tool:/, '') || d.name} />
          <TextBlock label="输入参数" value={d.arguments} />
          <TextBlock label="返回结果" value={d.result} />
        </>
      )}
      {span.type === 'skill_call' && (
        <>
          <TextBlock label="Skill 名" value={d.skill_name} />
          <TextBlock label="轮次 / mock" value={{ rounds: d.rounds, mock: d.mock }} />
          <TextBlock label="Usage" value={d.usage} />
        </>
      )}
      {span.type === 'step' && (
        <TextBlock label="步骤数据" value={{ step: d.step, ...Object.fromEntries(Object.entries(d).filter(([k]) => !['step'].includes(k))) }} />
      )}
      {span.type === 'request' && (
        <TextBlock label="请求元信息" value={d} />
      )}
    </div>
  );
}

function TreeView({
  node,
  depth = 0,
  selectedId,
  onSelect,
}: {
  node: SpanNode;
  depth?: number;
  selectedId: string | null;
  onSelect: (n: SpanNode) => void;
}) {
  const [open, setOpen] = useState(depth < 2);
  const hasChildren = node.children.length > 0;
  const isSelected = selectedId === node.id;
  const totalTokens = node.token_usage?.total_tokens ?? calcTotalTokens(node);

  return (
    <div className="tl-tree-node">
      <div
        className={`tl-tree-row${hasChildren ? ' has-children' : ''}${isSelected ? ' selected' : ''}`}
        style={{ paddingLeft: depth * 16 }}
        onClick={() => {
          onSelect(node);
          if (hasChildren) setOpen((o) => !o);
        }}
      >
        <span className="tl-tree-caret">{hasChildren ? (open ? '▾' : '▸') : ''}</span>
        <span className={`tl-badge tl-badge-${node.type}`}>{TYPE_LABELS[node.type] || node.type}</span>
        <span className="tl-tree-name">{node.name}</span>
        {totalTokens > 0 && <TokenBadge tokens={totalTokens} />}
        {(node.token_usage?.cache_hit_tokens ?? 0) > 0 && (
          <span className="tl-tree-cache" title={`缓存命中 ${fmtTokens(node.token_usage!.cache_hit_tokens!)}t`}>
            ⚡{fmtTokens(node.token_usage!.cache_hit_tokens!)}t
          </span>
        )}
        <span className="tl-tree-dur">{fmtTime(node.duration_ms)}</span>
      </div>
      {open &&
        node.children.map((c) => (
          <TreeView
            key={c.id}
            node={c}
            depth={depth + 1}
            selectedId={selectedId}
            onSelect={onSelect}
          />
        ))}
    </div>
  );
}

/* ============================================================
 * 甘特图布局：真实时间 X 轴 + 全局并发泳道 Y 轴
 * 每个 span 独占一行，时间区间重叠的 span 分配到不同行。
 * ============================================================ */
const ROW_HEIGHT = 26;

interface LayoutBox {
  top: number; // 顶部行号
  height: number; // 占据行数（甘特图恒为 1）
}

/** 按类型过滤树：当父节点类型未启用时，提升其子节点替代自身位置。 */
function filterTree(node: SpanNode, enabled: Set<string>): SpanNode[] {
  const children: SpanNode[] = [];
  for (const c of node.children) {
    children.push(...filterTree(c, enabled));
  }

  if (!enabled.has(node.type)) {
    return children;
  }

  return [{ ...node, children }];
}

/** 全局并发泳道布局：展平所有 span，按 start 排序、贪心分配到互不重叠的行。 */
function computeLayout(roots: SpanNode[]): { map: Map<string, LayoutBox>; totalRows: number } {
  const map = new Map<string, LayoutBox>();
  const flat = flattenAll(roots).sort((a, b) => a.start_ms - b.start_ms);
  const rowEnds: number[] = [];
  for (const n of flat) {
    const start = n.start_ms;
    const end = n.end_ms ?? start;
    let row = rowEnds.findIndex((re) => re <= start);
    if (row === -1) { row = rowEnds.length; rowEnds.push(-Infinity); }
    rowEnds[row] = Math.max(rowEnds[row], end);
    map.set(n.id, { top: row, height: 1 });
  }
  return { map, totalRows: Math.max(rowEnds.length, 1) };
}

/** 展平所有节点（带布局行号）。 */
function collectRects(roots: SpanNode[], layoutMap: Map<string, LayoutBox>): { node: SpanNode; box: LayoutBox }[] {
  return flattenAll(roots)
    .filter((n) => layoutMap.has(n.id))
    .map((n) => ({ node: n, box: layoutMap.get(n.id)! }));
}

/** 计算好看的刻度间隔。 */
function niceStep(targetMs: number): number {
  const pow = Math.pow(10, Math.floor(Math.log10(Math.max(targetMs, 1))));
  const d = targetMs / pow;
  let f = 1;
  if (d >= 5) f = 5;
  else if (d >= 2) f = 2;
  return f * pow;
}

function getAncestorPath(roots: SpanNode[], id: string): SpanNode[] {
  const path: SpanNode[] = [];
  const walk = (n: SpanNode): boolean => {
    path.push(n);
    if (n.id === id) return true;
    for (const c of n.children) if (walk(c)) return true;
    path.pop();
    return false;
  };
  for (const r of roots) if (walk(r)) return path;
  return [];
}

/* ============================================================
 * GanttChart：真实时间甘特图（缩放 / 平移 / minimap / 过滤 / 高亮）
 * ============================================================ */
function GanttChart({
  trace,
  selectedSpan,
  onSelect,
}: {
  trace: SpanNode;
  selectedSpan: SpanNode | null;
  onSelect: (n: SpanNode) => void;
}) {
  const totalMs = trace.end_ms != null && trace.start_ms != null
    ? Math.max(trace.end_ms - trace.start_ms, 1)
    : (trace.duration_ms ?? 1);

  // 时间窗口（占全量百分比）
  const [winStart, setWinStart] = useState(0);
  const [winEnd, setWinEnd] = useState(100);
  const [filters, setFilters] = useState<Set<string>>(new Set(ALL_TYPES));
  const [scrollTop, setScrollTop] = useState(0);
  const [viewH, setViewH] = useState(300);
  const [dragging, setDragging] = useState<{ startX: number; winStart: number; winEnd: number } | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<HTMLDivElement>(null);

  // 布局
  const enabled = useMemo(() => filters, [filters]);
  const filteredRoots = useMemo(() => {
    const result = filterTree(trace, enabled);
    if (result.length === 0) return [trace];
    return result;
  }, [trace, enabled]);
  const { map: layoutMap, totalRows } = useMemo(() => computeLayout(filteredRoots), [filteredRoots]);
  const rects = useMemo(() => collectRects(filteredRoots, layoutMap), [filteredRoots, layoutMap]);

  const winDur = winEnd - winStart;
  const winDurMs = (winDur / 100) * totalMs;

  // 慢调用阈值：窗口总时长的 10%，至少 800ms
  const slowThreshold = Math.max(800, winDurMs * 0.1);

  // 错误 / 最慢节点（用于统计与跳转）
  const errorNodes = useMemo(() => rects.filter((r) => r.node.status === 'error'), [rects]);
  const slowestNode = useMemo(
    () => rects.reduce<{ node: SpanNode; dur: number } | null>((acc, r) => {
      const d = r.node.duration_ms ?? 0;
      if (!acc || d > acc.dur) return { node: r.node, dur: d };
      return acc;
    }, null),
    [rects],
  );

  // 面包屑
  const breadcrumb = useMemo(
    () => (selectedSpan ? getAncestorPath(filteredRoots, selectedSpan.id) : []),
    [filteredRoots, selectedSpan],
  );

  // 视口内节点裁剪（Y 方向虚拟化）
  const visibleRects = useMemo(() => {
    const topPx = scrollTop - ROW_HEIGHT * 2;
    const bottomPx = scrollTop + viewH + ROW_HEIGHT * 2;
    return rects.filter((r) => {
      const yTop = r.box.top * ROW_HEIGHT;
      const yBottom = (r.box.top + r.box.height) * ROW_HEIGHT;
      return yBottom > topPx && yTop < bottomPx;
    });
  }, [rects, scrollTop, viewH]);

  // X 映射（相对请求起点，窗口内归一化到 0-100%）
  const mapX = (ms: number) =>
    ((ms - trace.start_ms - (winStart / 100) * totalMs) / winDurMs) * 100;

  // 原生 wheel 监听（非 passive 才能 preventDefault）→ 滚轮缩放
  useEffect(() => {
    const el = chartRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const px = e.clientX - rect.left;
      const pct = (px / rect.width) * 100; // 指针在窗口内的百分比
      const anchorVal = winStart + (pct / 100) * winDur;
      const factor = e.deltaY > 0 ? 1.2 : 1 / 1.2; // 向下缩小，向上放大
      let newDur = winDur * factor;
      newDur = Math.min(Math.max(newDur, 0.5), 100);
      let ns = anchorVal - (pct / 100) * newDur;
      let ne = ns + newDur;
      if (ns < 0) { ns = 0; ne = newDur; }
      if (ne > 100) { ne = 100; ns = 100 - newDur; }
      setWinStart(ns);
      setWinEnd(ne);
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, [winStart, winDur, winEnd]);

  // 测量视口高度
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const measure = () => setViewH(el.clientHeight);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // 键盘快捷键：E=跳到错误，S=跳到最慢，Esc=清除选中
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      if (e.key === 'e' || e.key === 'E') { jumpTo(errorNodes[0]?.node); }
      else if (e.key === 's' || e.key === 'S') { jumpTo(slowestNode?.node); }
      else if (e.key === 'Escape') { setNoSelection(); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [errorNodes, slowestNode, selectedSpan]);

  const setNoSelection = useCallback(() => {
    onSelect({} as SpanNode);
  }, [onSelect]);

  function jumpTo(node: SpanNode | null | undefined) {
    if (!node) return;
    const s = node.start_ms - trace.start_ms;
    const e = (node.end_ms ?? node.start_ms) - trace.start_ms;
    const dur = e - s || totalMs * 0.05;
    const pad = dur * 0.3;
    const ws = Math.max(0, ((s - pad) / totalMs) * 100);
    const we = Math.min(100, ((e + pad) / totalMs) * 100);
    // 保证最小窗口宽度
    if (we - ws < 2) {
      const c = (ws + we) / 2;
      setWinStart(Math.max(0, c - 1));
      setWinEnd(Math.min(100, c + 1));
    } else {
      setWinStart(ws);
      setWinEnd(we);
    }
    onSelect(node);
  }

  const resetZoom = () => { setWinStart(0); setWinEnd(100); };

  // 平移
  const onMouseDown = (e: React.MouseEvent) => {
    const target = e.target as HTMLElement;
    if (target.closest('.tl-gantt-bar')) return; // 点中节点 → 交给节点点击
    setDragging({ startX: e.clientX, winStart, winEnd });
  };
  const onMouseMove = (e: React.MouseEvent) => {
    if (!dragging) return;
    const dx = e.clientX - dragging.startX;
    const el = chartRef.current;
    if (!el) return;
    const pct = (dx / el.clientWidth) * 100 * (winDur / 100);
    let ns = dragging.winStart - pct;
    let ne = dragging.winEnd - pct;
    if (ns < 0) { ne -= ns; ns = 0; }
    if (ne > 100) { ns -= (ne - 100); ne = 100; }
    setWinStart(ns);
    setWinEnd(ne);
  };
  const onMouseUp = () => setDragging(null);

  // minimap 点击/拖动跳转
  const miniRef = useRef<HTMLDivElement>(null);
  const onMiniDown = (e: React.MouseEvent) => {
    const el = miniRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const cx = ((e.clientX - rect.left) / rect.width) * 100;
    const half = (winEnd - winStart) / 2;
    let ns = cx - half;
    let ne = cx + half;
    if (ns < 0) { ns = 0; ne = half * 2; }
    if (ne > 100) { ne = 100; ns = 100 - half * 2; }
    setWinStart(ns);
    setWinEnd(ne);
  };

  const toggleType = (t: string) => {
    setFilters((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t); else next.add(t);
      return next;
    });
  };

  // 刻度
  const stepMs = niceStep(winDurMs / 8);
  const ticks: { ms: number; pct: number }[] = [];
  {
    const startMs = (winStart / 100) * totalMs;
    const firstTick = Math.ceil(startMs / stepMs) * stepMs;
    for (let t = firstTick; t <= (winEnd / 100) * totalMs; t += stepMs) {
      ticks.push({ ms: t, pct: mapX(t) });
    }
  }

  const barClass = (node: SpanNode) => {
    const cls = ['tl-gantt-bar'];
    if (selectedSpan?.id === node.id) cls.push('active');
    if (node.status === 'error') cls.push('err');
    const dur = node.duration_ms ?? 0;
    if (dur >= slowThreshold) cls.push('slow');
    return cls.join(' ');
  };

  return (
    <div className="tl-gantt">
      {/* 顶部：概览条 + 类型图例 + 统计 + 跳转 */}
      <div className="tl-gantt-top">
        <div className="tl-gantt-stats">
          <span>总耗时 <b>{fmtTime(totalMs)}</b></span>
          <span className="tl-gantt-zoom">缩放 {winDur.toFixed(0)}%</span>
          {errorNodes.length > 0 && <span className="tl-gantt-stat-err">⚠ {errorNodes.length} 错误</span>}
          {slowestNode && (
            <span className="tl-gantt-stat-slow">🐢 最慢 {slowestNode.node.name} · {fmtTime(slowestNode.dur)}</span>
          )}
        </div>
        <div className="tl-gantt-actions">
          <button className="btn-secondary btn-sm" onClick={() => jumpTo(slowestNode?.node)}>跳到最慢 (S)</button>
          <button className="btn-secondary btn-sm" onClick={() => jumpTo(errorNodes[0]?.node)} disabled={errorNodes.length === 0}>跳到错误 (E)</button>
          <button className="btn-secondary btn-sm" onClick={resetZoom}>复位</button>
        </div>
      </div>

      <div className="tl-gantt-legend">
        {ALL_TYPES.map((t) => (
          <label key={t} className="tl-legend-item">
            <input
              type="checkbox"
              checked={filters.has(t)}
              onChange={() => toggleType(t)}
            />
            <span className="tl-legend-color" style={{ background: TYPE_COLORS[t] }} />
            {TYPE_LABELS[t]}
          </label>
        ))}
        <span className="tl-gantt-hint">滚轮缩放 · 拖拽平移 · 双击复位</span>
      </div>

      {/* minimap 概览条 */}
      <div className="tl-gantt-minimap" ref={miniRef} onMouseDown={onMiniDown}>
        {rects.map((r) => {
          const x = ((r.node.start_ms - trace.start_ms) / totalMs) * 100;
          const w = Math.max(((r.node.duration_ms ?? 0) / totalMs) * 100, 0.4);
          return (
            <div
              key={r.node.id}
              className="tl-mini-bar"
              style={{ left: `${x}%`, width: `${w}%`, background: TYPE_COLORS[r.node.type] || '#666' }}
              title={r.node.name}
            />
          );
        })}
        <div className="tl-mini-window" style={{ left: `${winStart}%`, width: `${winDur}%` }} />
      </div>

      {/* 时间刻度尺 */}
      <div className="tl-gantt-ruler">
        {ticks.map((t, i) => (
          <div key={i} className="tl-ruler-tick" style={{ left: `${t.pct}%` }}>
            <span>{fmtTime(t.ms)}</span>
          </div>
        ))}
      </div>

      {/* 面包屑 */}
      {breadcrumb.length > 0 && (
        <div className="tl-gantt-breadcrumb">
          {breadcrumb.map((n, i) => (
            <span key={n.id} className="tl-breadcrumb-item">
              {i > 0 && <span className="tl-breadcrumb-sep">›</span>}
              <button
                className={`tl-breadcrumb-btn${selectedSpan?.id === n.id ? ' current' : ''}`}
                onClick={() => { onSelect(n); if (n.duration_ms) jumpTo(n); }}
              >
                <span className={`tl-badge tl-badge-${n.type}`}>{TYPE_LABELS[n.type] || n.type}</span>
                {n.name}
              </button>
            </span>
          ))}
        </div>
      )}

      {/* 主体画布（可滚动） */}
      <div
        ref={scrollRef}
        className="tl-gantt-scroll"
        onScroll={(e) => setScrollTop((e.target as HTMLDivElement).scrollTop)}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
        onDoubleClick={resetZoom}
      >
        <div ref={chartRef} className="tl-gantt-inner" style={{ height: Math.max(totalRows * ROW_HEIGHT, viewH) }}>
          {visibleRects.map(({ node, box }) => {
            const x = mapX(node.start_ms);
            const w = Math.max(((node.duration_ms ?? 0) / totalMs) * 100 * (100 / winDur), 0.2);
            if (x > 100 || x + w < 0) return null;
            const y = box.top * ROW_HEIGHT;
            const h = box.height * ROW_HEIGHT;
            const totalTokens = node.token_usage?.total_tokens ?? 0;
            return (
              <div
                key={node.id}
                className={barClass(node)}
                style={{
                  left: `${x}%`,
                  width: `${w}%`,
                  top: y,
                  height: h,
                  background: TYPE_COLORS[node.type] || '#666',
                }}
                title={`${node.name} · ${fmtTime(node.duration_ms)}${totalTokens ? ` · ${fmtTokens(totalTokens)}t` : ''}${node.status === 'error' ? ' · ERROR' : ''}`}
                onClick={(e) => { e.stopPropagation(); onSelect(node); }}
              >
                <span className="tl-gantt-label">
                  {node.name} · {fmtTime(node.duration_ms)}
                  {totalTokens > 0 && <TokenBadge tokens={totalTokens} />}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default function RequestLogPage() {
  const setError = useGameStore((s) => s.setError);
  const setNotification = useGameStore((s) => s.setNotification);

  const [items, setItems] = useState<TraceSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [trace, setTrace] = useState<SpanNode | null>(null);
  const [selectedSpan, setSelectedSpan] = useState<SpanNode | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionFilter, setActionFilter] = useState('');
  const [viewMode, setViewMode] = useState<'gantt' | 'tree'>('gantt');

  const refreshList = useCallback(async () => {
    setLoading(true);
    try {
      const r = await tracesApi.list(200, actionFilter || undefined);
      setItems(r.items);
    } catch (e: unknown) {
      setError(`加载请求日志失败：${e instanceof Error ? e.message : e}`);
    } finally {
      setLoading(false);
    }
  }, [actionFilter, setError]);

  useEffect(() => {
    refreshList();
  }, [refreshList]);

  const openTrace = async (id: string) => {
    setSelectedId(id);
    setSelectedSpan(null);
    try {
      const d = await tracesApi.get<SpanNode>(id);
      setTrace(d);
      setSelectedSpan(d);
    } catch (e: unknown) {
      setError(`加载 trace 失败：${e instanceof Error ? e.message : e}`);
    }
  };

  const actions = useMemo(
    () => Array.from(new Set(items.map((i) => i.action).filter(Boolean))) as string[],
    [items],
  );

  const totalMs = trace && trace.end_ms != null ? trace.end_ms - trace.start_ms : trace?.duration_ms || 1;
  const rootTokens = trace?.token_usage?.total_tokens ?? (trace ? calcTotalTokens(trace) : 0);
  const rootPromptTokens = trace?.token_usage?.prompt_tokens ?? 0;
  const rootCompletionTokens = trace?.token_usage?.completion_tokens ?? 0;
  const rootCacheHit = trace?.token_usage?.cache_hit_tokens ?? 0;
  const rootCacheMiss = trace?.token_usage?.cache_miss_tokens ?? 0;

  const clearAll = async () => {
    if (!window.confirm('确定清空所有请求日志？')) return;
    try {
      const r = await tracesApi.clear();
      setItems([]);
      setTrace(null);
      setSelectedId(null);
      setSelectedSpan(null);
      setNotification(`已清空 ${r.cleared} 条请求日志`);
    } catch (e: unknown) {
      setError(`清空失败：${e instanceof Error ? e.message : e}`);
    }
  };

  return (
    <div className="admin-page">
      <AdminNav />
      <div className="admin-content tl-page">
        <div className="admin-header">
          <h2>请求日志 · 调用链追踪</h2>
          <div className="tl-toolbar">
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="tl-select"
            >
              <option value="">全部动作</option>
              {actions.map((a) => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
            <button className="btn-secondary" onClick={refreshList}>刷新</button>
            <button className="btn-danger" onClick={clearAll}>清空</button>
          </div>
        </div>

        <div className="tl-layout">
          {/* 左侧：请求列表 */}
          <div className="tl-list">
            {loading && <div className="tl-hint">加载中…</div>}
            {!loading && items.length === 0 && (
              <div className="tl-hint">暂无请求日志。执行一次「下一 Tick」或时间推进后，这里会展示每次请求的完整调用链。</div>
            )}
            {items.map((it) => (
              <div
                key={it.id}
                className={`tl-item${selectedId === it.id ? ' active' : ''}`}
                onClick={() => openTrace(it.id)}
              >
                <div className="tl-item-top">
                  <span className="tl-item-name">{it.name || it.action} <small>{it.action}</small></span>
                  <span className="tl-item-dur">{fmtTime(it.duration_ms)}</span>
                </div>
                <div className="tl-item-sub">
                  <span>{it.ts}</span>
                  <span>{it.save}</span>
                </div>
                <div className="tl-item-stats">
                  <span className="tl-stat" title="span 节点数">{it.span_count} 节点</span>
                  <span className="tl-stat tl-stat-model" title="模型调用轮数">{it.model_rounds} 模型</span>
                  <span className="tl-stat tl-stat-skill" title="skill 调用数">{it.skills} skill</span>
                  <span className="tl-stat tl-stat-tool" title="工具调用数">{it.tool_calls} 工具</span>
                  {(it.total_tokens ?? 0) > 0 ? (
                    <span className="tl-stat tl-stat-tokens" title="总 token 数">
                      {fmtTokens(it.total_tokens!)}
                      {(it.cache_hit_tokens ?? 0) > 0 && (
                        <span className="tl-stat-cache-hit" title={`缓存命中 ${fmtTokens(it.cache_hit_tokens!)}t`}>
                          {' '}· {fmtTokens(it.cache_hit_tokens!)}t 缓存
                        </span>
                      )}
                    </span>
                  ) : null}
                  <span className={`tl-status ${it.status}`}>{it.status}</span>
                </div>
              </div>
            ))}
          </div>

          {/* 右侧：主面板 */}
          <div className="tl-detail-panel">
            {!trace ? (
              <div className="tl-hint tl-empty">点击左侧某条请求查看调用链</div>
            ) : (
              <>
                <div className="tl-detail-controller">
                  <div className="tl-viewtabs">
                    <button className={viewMode === 'gantt' ? 'active' : ''} onClick={() => setViewMode('gantt')}>甘特图</button>
                    <button className={viewMode === 'tree' ? 'active' : ''} onClick={() => setViewMode('tree')}>树形</button>
                  </div>
                  <div className="tl-summary-stats">
                    <span className="tl-total">总耗时 {fmtTime(totalMs)}</span>
                    {rootTokens > 0 && (
                      <span className="tl-tokens-summary">
                        Tokens: {fmtTokens(rootTokens)}
                        {rootPromptTokens > 0 && <span className="tl-tokens-sub"> ({fmtTokens(rootPromptTokens)}↑ / {fmtTokens(rootCompletionTokens)}↓)</span>}
                        {(rootCacheHit > 0 || rootCacheMiss > 0) && (
                          <span className="tl-tokens-sub tl-tokens-cache">
                            {' '}· 缓存 {fmtTokens(rootCacheHit)} 命中 / {fmtTokens(rootCacheMiss)} 未命中
                          </span>
                        )}
                      </span>
                    )}
                  </div>
                </div>

                <div className="tl-split">
                  {/* 子左：图形 */}
                  <div className="tl-split-left">
                    <div className="tl-pane-title">
                      {viewMode === 'gantt' ? '甘特图（真实时间）' : '调用树'}
                    </div>

                    {viewMode === 'gantt' && (
                      <GanttChart
                        trace={trace}
                        selectedSpan={selectedSpan}
                        onSelect={setSelectedSpan}
                      />
                    )}

                    {viewMode === 'tree' && (
                      <div className="tl-tree">
                        <TreeView
                          node={trace}
                          selectedId={selectedSpan?.id ?? null}
                          onSelect={setSelectedSpan}
                        />
                      </div>
                    )}
                  </div>

                  {/* 子右：详情 */}
                  <div className="tl-split-right">
                    <div className="tl-pane-title">输入 / 输出详情</div>
                    {selectedSpan && selectedSpan.id ? (
                      <SpanDetail span={selectedSpan} />
                    ) : (
                      <div className="tl-hint">
                        {viewMode === 'tree'
                          ? '点击树中节点查看详情'
                          : '点击甘特图中的某个节点查看详情'}
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
