import { useCallback, useEffect, useMemo, useState } from 'react';
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

function flattenAll(roots: SpanNode[]): SpanNode[] {
  const out: SpanNode[] = [];
  const walk = (n: SpanNode) => {
    out.push(n);
    for (const c of n.children) walk(c);
  };
  for (const r of roots) walk(r);
  return out;
}

/** 按时间区间做行打包（贪心），重叠的 span 排到不同行 → 直观展示并发。 */
function packRows(spans: SpanNode[]) {
  const flat = flattenAll(spans);
  const entries = flat.map((n) => ({
    node: n,
    start: n.start_ms,
    end: n.end_ms ?? n.start_ms,
  }));
  entries.sort((a, b) => a.start - b.start);
  const rowEnds: number[] = [];
  const assigned: { node: SpanNode; row: number }[] = [];
  for (const e of entries) {
    let row = rowEnds.findIndex((end) => end <= e.start);
    if (row === -1) {
      row = rowEnds.length;
      rowEnds.push(-Infinity);
    }
    rowEnds[row] = Math.max(rowEnds[row], e.end);
    assigned.push({ node: e.node, row });
  }
  return assigned;
}

function fmtTime(ms: number | null | undefined): string {
  if (ms == null) return '—';
  if (ms < 1000) return `${ms.toFixed(1)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
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

function SpanDetail({ span }: { span: SpanNode }) {
  const d = span.data || {};
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

function TreeView({ node, depth = 0 }: { node: SpanNode; depth?: number }) {
  const [open, setOpen] = useState(depth < 2);
  const hasChildren = node.children.length > 0;
  return (
    <div className="tl-tree-node">
      <div
        className={`tl-tree-row${hasChildren ? ' has-children' : ''}`}
        style={{ paddingLeft: depth * 16 }}
        onClick={() => hasChildren && setOpen((o) => !o)}
      >
        <span className="tl-tree-caret">{hasChildren ? (open ? '▾' : '▸') : ''}</span>
        <span className={`tl-badge tl-badge-${node.type}`}>{TYPE_LABELS[node.type] || node.type}</span>
        <span className="tl-tree-name">{node.name}</span>
        <span className="tl-tree-dur">{fmtTime(node.duration_ms)}</span>
      </div>
      {open &&
        node.children.map((c) => <TreeView key={c.id} node={c} depth={depth + 1} />)}
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
  const [viewMode, setViewMode] = useState<'timeline' | 'tree'>('timeline');

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

  const rows = useMemo(() => (trace ? packRows([trace]) : []), [trace]);
  const totalMs = trace && trace.end_ms != null ? trace.end_ms - trace.start_ms : trace?.duration_ms || 1;

  const clearAll = async () => {
    if (!window.confirm('确定清空所有请求日志？')) return;
    try {
      const r = await tracesApi.clear();
      setItems([]);
      setTrace(null);
      setSelectedId(null);
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
                  <span className={`tl-status ${it.status}`}>{it.status}</span>
                </div>
              </div>
            ))}
          </div>

          {/* 右侧：详情 */}
          <div className="tl-detail-panel">
            {!trace ? (
              <div className="tl-hint tl-empty">点击左侧某条请求查看调用链</div>
            ) : (
              <>
                <div className="tl-detail-controller">
                  <div className="tl-viewtabs">
                    <button className={viewMode === 'timeline' ? 'active' : ''} onClick={() => setViewMode('timeline')}>时间轴</button>
                    <button className={viewMode === 'tree' ? 'active' : ''} onClick={() => setViewMode('tree')}>树形</button>
                  </div>
                  <span className="tl-total">总耗时 {fmtTime(totalMs)}</span>
                </div>

                {viewMode === 'timeline' && (
                  <div className="tl-timeline">
                    <div className="tl-timeline-head">
                      <div className="tl-legend">
                        {Object.entries(TYPE_LABELS).map(([k, v]) => (
                          <span key={k} className="tl-legend-item">
                            <span className="tl-legend-dot" style={{ background: TYPE_COLORS[k] }} />
                            {v}
                          </span>
                        ))}
                      </div>
                      <span className="tl-hint2">重叠的条 = 并发执行；点击条查看详情</span>
                    </div>
                    <div className="tl-chart" style={{ height: Math.max(120, rows.length * 26) }}>
                      {rows.map(({ node, row }) => {
                        const left = ((node.start_ms - trace.start_ms) / (totalMs || 1)) * 100;
                        const width = ((node.end_ms ?? node.start_ms) - node.start_ms) / (totalMs || 1) * 100;
                        const active = selectedSpan?.id === node.id;
                        return (
                          <div
                            key={node.id}
                            className={`tl-bar${active ? ' active' : ''}`}
                            style={{
                              left: `${Math.max(0, left)}%`,
                              width: `${Math.max(0.4, width)}%`,
                              top: row * 26,
                              background: TYPE_COLORS[node.type] || '#666',
                            }}
                            title={`${node.name} · ${fmtTime(node.duration_ms)}`}
                            onClick={(e) => { e.stopPropagation(); setSelectedSpan(node); }}
                          >
                            <span className="tl-bar-label">
                              {node.name} · {fmtTime(node.duration_ms)}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                    {selectedSpan && <SpanDetail span={selectedSpan} />}
                  </div>
                )}

                {viewMode === 'tree' && (
                  <div className="tl-tree">
                    <TreeView node={trace} />
                    {selectedSpan && <SpanDetail span={selectedSpan} />}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}