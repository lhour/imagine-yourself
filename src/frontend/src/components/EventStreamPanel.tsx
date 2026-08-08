import { useEffect, useMemo, useRef, useState } from 'react';
import { useGameStore } from '../store/gameStore';
import { EventRecord, EventParticipant, Character } from '../api/types';
import { worldApi, entitiesApi } from '../api/client';
import '../styles/EventStreamPanel.css';

const EVENT_TYPE_LABELS: Record<string, string> = {
  discovery: '发现',
  appearance: '登场',
  perception: '感知',
  action: '行动',
  encounter: '遭遇',
  dialogue: '对话',
  combat: '战斗',
  quest: '任务',
  player_action: '玩家行动',
  narrative: '叙事',
  environment: '环境',
  objective: '客观',
  system: '系统',
  milestone: '里程碑',
};

function typeLabel(t: string): string { return EVENT_TYPE_LABELS[t] ?? t; }
function groupByTick(events: EventRecord[]): Record<number, EventRecord[]> {
  const groups: Record<number, EventRecord[]> = {};
  for (const e of events) {
    const t = e.tick_num;
    if (!groups[t]) groups[t] = [];
    groups[t].push(e);
  }
  return groups;
}
function clsx(...xs: (string | false | null | undefined)[]): string {
  return xs.filter(Boolean).join(' ');
}

// ===== Event detail modal =====
function EventDetailModal({ eventId, onClose }: { eventId: number; onClose: () => void }) {
  const [detail, setDetail] = useState<EventRecord | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    worldApi.getEvent(eventId).then((r) => { if (active) setDetail(r as EventRecord); })
      .catch((e: unknown) => { if (active) setErr((e as { message?: string }).message ?? '加载失败'); });
    return () => { active = false; };
  }, [eventId]);
  if (err) {
    return (
      <div className="modal-mask" onClick={onClose}>
        <div className="modal-body" onClick={(e) => e.stopPropagation()}>
          <h3>事件详情加载失败</h3>
          <p style={{ color: '#b91c1c' }}>{err}</p>
          <div className="modal-actions"><button onClick={onClose}>关闭</button></div>
        </div>
      </div>
    );
  }
  if (!detail) {
    return (
      <div className="modal-mask" onClick={onClose}>
        <div className="modal-body" onClick={(e) => e.stopPropagation()}>
          <span className="spinner" /> 加载中…
        </div>
      </div>
    );
  }
  return (
    <div className="modal-mask" onClick={onClose}>
      <div className="modal-body ev-detail" onClick={(e) => e.stopPropagation()}>
        <div className="ev-detail-header">
          <div>
            <span className="event-type">{typeLabel(detail.event_type)}</span>
            <span className="event-stars" title={`重要性 ${detail.importance}/5`}>
              {'★'.repeat(Math.max(0, Math.min(5, detail.importance)))}
            </span>
            <span className="ev-title">#{detail.id} · Tick {detail.tick_num}</span>
          </div>
          <button className="close-x" onClick={onClose}>✕</button>
        </div>
        <div className="ev-meta">
          <span>🕒 {detail.game_time}</span>
          {detail.location_detail_raw && <span>📍 {detail.location_detail_raw}</span>}
          {detail.location_map_id != null && <span>🗺️ Map #{detail.location_map_id}</span>}
        </div>
        <div className="ev-body">
          <div className="ev-polished">{detail.content_polished || detail.content_raw}</div>
          {detail.content_polished && detail.content_raw && detail.content_raw !== detail.content_polished && (
            <details className="ev-raw-det">
              <summary>查看结构化原文</summary>
              <pre>{detail.content_raw}</pre>
            </details>
          )}
        </div>
        <div className="ev-section">
          <h4>参与人 ({detail.participants?.length ?? 0})</h4>
          {!detail.participants?.length ? <div className="empty-sub">无参与人</div> : (
            <div className="ev-chips">
              {detail.participants.map((p: EventParticipant) => (
                <span key={p.id} className={`chip chip-${p.participant_type}`} title={p.perception_raw ?? p.role_raw}>
                  <b>{p.name}</b> · {p.role_raw || p.participant_type}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="ev-2col">
          <div className="ev-section">
            <h4>被谁记得 ({detail.remembered_by?.length ?? 0})</h4>
            {!detail.remembered_by?.length ? <div className="empty-sub">—</div> : (
              <ul className="ev-ul">
                {detail.remembered_by.map((m, i) => (
                  <li key={i} title={`深度 ${m.depth} · 正确率 ${m.correctness.toFixed(2)}`}>
                    <b>{m.char_name}</b>
                    <span className="ev-sub">depth {m.depth} · corr {(m.correctness * 100).toFixed(0)}%</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="ev-section">
            <h4>已遗忘 ({detail.forgotten_by?.length ?? 0})</h4>
            {!detail.forgotten_by?.length ? <div className="empty-sub">—</div> : (
              <ul className="ev-ul">
                {detail.forgotten_by.map((m, i) => (
                  <li key={i} className="forgotten" title={`遗忘概率 ${(m.forget_prob * 100).toFixed(0)}%`}>
                    <b>{m.char_name}</b>
                    <span className="ev-sub">forget {(m.forget_prob * 100).toFixed(0)}%</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
        {detail.linked_memories?.length ? (
          <div className="ev-section">
            <h4>关联记忆 ({detail.linked_memories.length})</h4>
            <div className="ev-memories">
              {detail.linked_memories.map((m) => (
                <div key={m.id} className="ev-memory">
                  <div className="ev-memory-head">
                    <span className="mem-char">{m.char_name}</span>
                    <span className="mem-depth">深度 {m.depth}</span>
                    <span className={m.is_false ? 'mem-false' : 'mem-true'}>
                      {m.is_false ? '虚假' : '真实'}
                    </span>
                  </div>
                  <div className="ev-memory-body">
                    {m.memory_polished || m.memory_raw}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

// ===== Event card =====
function EventCard({
  event,
  showRaw,
  highlightChars,
  onOpen,
}: {
  event: EventRecord;
  showRaw: boolean;
  highlightChars: Set<number>;
  onOpen: (id: number) => void;
}) {
  const importance = Math.max(0, Math.min(5, event.importance ?? 3));
  const charParticipants = (event.participants ?? []).filter((p) => p.participant_type === 'character');
  const highlighted = charParticipants.length === 0
    ? false
    : highlightChars.size === 0
      ? false
      : charParticipants.some((p) => highlightChars.has(p.participant_id));
  const anyParticipants = (event.participants ?? []).length > 0;
  const rememberedTooltip = useMemo(() => {
    const r = (event.remembered_by ?? []).slice(0, 8).map((m) => `✓ ${m.char_name}`).join('\n');
    const f = (event.forgotten_by ?? []).slice(0, 8).map((m) => `✗ ${m.char_name}`).join('\n');
    if (!r && !f) return '';
    return ['【记得】', r, '【遗忘】', f].filter(Boolean).join('\n');
  }, [event]);
  const isNarrative = event.event_type === 'narrative';
  return (
    <div
      className={clsx(
        `event-card importance-${importance}`,
        highlighted && 'ev-highlighted',
        isNarrative && 'event-card-narrative',
      )}
      onClick={() => onOpen(event.id)}
      title={rememberedTooltip || undefined}
    >
      <div className="event-header">
        <span className="event-type">{isNarrative ? '📖 剧情' : typeLabel(event.event_type)}</span>
        <span className="event-meta">
          {event.location_detail_raw && <span className="event-location">📍 {event.location_detail_raw}</span>}
          <span className="event-stars" title={`重要性 ${importance}/5`}>
            {'★'.repeat(importance)}
            {'☆'.repeat(5 - importance)}
          </span>
          <span className="event-time">#{event.id}</span>
        </span>
      </div>
      <div className={clsx('event-content', isNarrative && 'narrative-content')}>
        {event.content_polished || event.content_raw || '（空事件）'}
      </div>
      {showRaw && event.content_raw && (
        <div className="event-raw">原文：{event.content_raw}</div>
      )}
      {/* narrative 事件隐藏参与者 chips，突出剧情文本 */}
      {!isNarrative && anyParticipants && (
        <div className="event-chips-row">
          {(event.participants ?? []).slice(0, 10).map((p) => (
            <span
              key={p.id}
              className={clsx(
                'chip chip-mini',
                `chip-${p.participant_type}`,
                p.participant_type === 'character' && highlightChars.has(p.participant_id) && 'chip-focus'
              )}
              title={p.perception_raw || p.role_raw || ''}
            >
              {p.name}
            </span>
          ))}
          {(event.participants ?? []).length > 10 && (
            <span className="chip chip-mini chip-more">+{(event.participants ?? []).length - 10}</span>
          )}
          {(event.remembered_by?.length ?? 0) + (event.forgotten_by?.length ?? 0) > 0 && (
            <span
              className="chip chip-mini chip-memory"
              title={rememberedTooltip || undefined}
            >
              记 {event.remembered_by?.length ?? 0} / 忘 {event.forgotten_by?.length ?? 0}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

// ===== Main panel =====
export default function EventStreamPanel() {
  const events = useGameStore((s) => s.events);
  const loading = useGameStore((s) => s.eventsLoading);
  const loadingOlder = useGameStore((s) => s.loadingOlder);
  const hasMoreEvents = useGameStore((s) => s.hasMoreEvents);
  const filter = useGameStore((s) => s.eventsFilter);
  const setFilter = useGameStore((s) => s.setEventsFilter);
  const meta = useGameStore((s) => s.meta);
  const [chars, setChars] = useState<Character[]>([]);
  const [openEventId, setOpenEventId] = useState<number | null>(null);
  const refresh = useGameStore((s) => s.refreshEvents);
  const loadOlder = useGameStore((s) => s.loadOlderEvents);

  const streamRef = useRef<HTMLDivElement>(null);
  const pinnedBottomRef = useRef(true);   // 用户是否贴底（贴底时新事件自动滚到底）
  const prevEventsLenRef = useRef(0);

  useEffect(() => {
    (async () => {
      try {
        const list = await entitiesApi.list<Character>('character');
        setChars(Array.isArray(list) ? list : []);
      } catch { /* ignore */ }
    })();
  }, []);

  const allChars = useMemo(() => chars.sort((a, b) => b.importance - a.importance), [chars]);
  // char focus → multi-select chips
  const selectedCharIds = useMemo<Set<number>>(() => {
    const ids = filter.charIds ?? [];
    return new Set(typeof ids === 'string' ? ids.split(',').map(Number).filter((n) => !isNaN(n)) : ids);
  }, [filter.charIds]);

  const toggleChar = (id: number) => {
    const next = new Set(selectedCharIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    const idsStr = Array.from(next).sort((a, b) => a - b).join(',');
    setFilter({ charIds: idsStr || null });
  };

  const filtered = useMemo(() => {
    let arr = events;
    if (selectedCharIds.size > 0) {
      arr = arr.filter((e) =>
        (e.participants ?? []).some(
          (p) => p.participant_type === 'character' && selectedCharIds.has(p.participant_id)
        )
      );
    }
    return arr;
  }, [events, selectedCharIds]);

  const tickGroups = useMemo(() => groupByTick(filtered), [filtered]);
  // 聊天式：旧 tick 在上、新 tick 在下（正序）
  const tickKeys = Object.keys(tickGroups).map(Number).sort((a, b) => a - b);
  const hasFilter = selectedCharIds.size > 0;

  const clearFilter = () => setFilter({ charIds: null });

  // 滚动事件：触顶加载更早历史；记录是否贴底
  const onStreamScroll = () => {
    const el = streamRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    pinnedBottomRef.current = distanceFromBottom < 40;
    // 触顶且非筛选模式（筛选下不分页）时加载更早
    if (el.scrollTop < 30 && !hasFilter && hasMoreEvents && !loadingOlder) {
      const prevHeight = el.scrollHeight;
      void loadOlder().then(() => {
        // 保持视觉位置：加载后把 scrollTop 恢复到新增内容之下
        requestAnimationFrame(() => {
          if (streamRef.current) {
            streamRef.current.scrollTop = streamRef.current.scrollHeight - prevHeight;
          }
        });
      });
    }
  };

  // 新事件到达且用户贴底时，自动滚到底部
  useEffect(() => {
    const el = streamRef.current;
    if (!el) return;
    if (pinnedBottomRef.current && events.length > prevEventsLenRef.current) {
      el.scrollTop = el.scrollHeight;
    }
    prevEventsLenRef.current = events.length;
  }, [events.length]);

  return (
    <div className="event-panel">
      <div className="event-filter-bar">
        <span className="filter-label">筛选</span>

        <label className="filter-field check">
          <input
            type="checkbox"
            checked={filter.showRaw}
            onChange={(e) => setFilter({ showRaw: e.target.checked })}
          />
          原文
        </label>

        {hasFilter && (
          <button className="filter-reset" onClick={clearFilter}>✕ 重置</button>
        )}

        <div className="filter-summary">
          <span>{filtered.length} / {events.length} 条</span>
          <span className="tick-now">当前 Tick <b>{meta?.tick_num ?? '—'}</b></span>
        </div>
        <button className="btn-ghost" onClick={() => void refresh()}>⟳ 刷新</button>
      </div>

      {allChars.length > 0 && (
        <div className="ev-char-focus">
          <span className="filter-sub">角色聚焦（高亮并过滤）</span>
          <div className="filter-chips">
            <button
              className={clsx('chip chip-btn chip-character', selectedCharIds.size === 0 && 'chip-btn-on')}
              onClick={() => setFilter({ charIds: null })}
            >全部</button>
            {allChars.slice(0, 24).map((c) => (
              <button
                key={c.id}
                className={clsx('chip chip-btn chip-character', selectedCharIds.has(c.id) && 'chip-btn-on')}
                onClick={() => toggleChar(c.id)}
                title={`${c.name} · 重要性 ${c.importance}`}
              >
                {c.name}
              </button>
            ))}
            {allChars.length > 24 && <span className="chip chip-more">+{allChars.length - 24}</span>}
          </div>
        </div>
      )}

      <div className="event-stream" ref={streamRef} onScroll={onStreamScroll}>
        {loading && events.length === 0 ? (
          <div className="event-stream-empty">
            <span className="spinner" /> 正在加载事件…
          </div>
        ) : events.length === 0 ? (
          <div className="event-stream-empty">
            <div className="empty-icon">📜</div>
            <p>尚无事件</p>
            <p className="empty-hint">点击底部「⏭ 下一 Tick」开始推进剧情。</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="event-stream-empty">
            <p>没有符合筛选条件的事件</p>
            <button className="btn-secondary" onClick={clearFilter}>清除筛选</button>
          </div>
        ) : (
          <>
            {loadingOlder && (
              <div className="load-more-hint"><span className="spinner" /> 加载更早历史…</div>
            )}
            {tickKeys.map((tick) => {
              // tick 内事件按 id 升序（旧在上、新在下，匹配聊天式阅读顺序）
              const tickEvents = [...tickGroups[tick]].sort((a, b) => a.id - b.id);
              return (
                <div key={tick} className="tick-group">
                  <div className="tick-group-header">
                    <span className={`tick-badge ${tick <= 0 ? 'prologue' : ''}`}>
                      {tick <= 0 ? '序幕' : `Tick ${tick}`}
                    </span>
                    {tick <= 0 && <span className="tick-prologue-tag">开场铺垫</span>}
                    <span className="tick-time">{tickEvents[0]?.game_time ?? ''}</span>
                    <span className="tick-count">{tickEvents.length} 个事件</span>
                  </div>
                  {tickEvents.map((e) => (
                    <EventCard
                      key={e.id}
                      event={e}
                      showRaw={filter.showRaw}
                      highlightChars={selectedCharIds}
                      onOpen={(id) => setOpenEventId(id)}
                    />
                  ))}
                </div>
              );
            })}
          </>
        )}
      </div>

      {openEventId != null && (
        <EventDetailModal eventId={openEventId} onClose={() => setOpenEventId(null)} />
      )}
    </div>
  );
}
