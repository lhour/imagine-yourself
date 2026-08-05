import { useMemo } from 'react';
import { useGameStore } from '../store/gameStore';
import { EventRecord } from '../api/types';

// 把事件按 tick 分组
function groupByTick(events: EventRecord[]): Record<number, EventRecord[]> {
  const groups: Record<number, EventRecord[]> = {};
  for (const e of events) {
    const t = e.tick_num;
    if (!groups[t]) groups[t] = [];
    groups[t].push(e);
  }
  return groups;
}

export default function EventStreamPanel() {
  const events = useGameStore((s) => s.events);
  const loading = useGameStore((s) => s.eventsLoading);
  const filter = useGameStore((s) => s.eventsFilter);
  const setFilter = useGameStore((s) => s.setEventsFilter);
  const meta = useGameStore((s) => s.meta);

  const tickGroups = useMemo(() => {
    let filtered = events;
    if (filter.eventType) {
      filtered = filtered.filter((e) => e.event_type === filter.eventType);
    }
    if (filter.importanceMin > 0) {
      filtered = filtered.filter((e) => e.importance >= filter.importanceMin);
    }
    return groupByTick(filtered);
  }, [events, filter]);

  const tickKeys = Object.keys(tickGroups)
    .map(Number)
    .sort((a, b) => b - a); // 新 tick 在上

  return (
    <div className="main">
      <div className="event-filter-bar">
        <select
          value={filter.eventType}
          onChange={(e) => setFilter({ eventType: e.target.value })}
        >
          <option value="">全部类型</option>
          <option value="narrative">叙事</option>
          <option value="player_action">玩家行动</option>
          <option value="environment">环境</option>
          <option value="objective">客观</option>
          <option value="system">系统</option>
        </select>
        <label className="muted small">
          重要性 ≥
          <input
            type="number"
            min={0}
            max={5}
            value={filter.importanceMin}
            onChange={(e) => setFilter({ importanceMin: Number(e.target.value) })}
            style={{ width: 50, marginLeft: 4 }}
          />
        </label>
        <label className="muted small">
          <input
            type="checkbox"
            checked={filter.showRaw}
            onChange={(e) => setFilter({ showRaw: e.target.checked })}
          />
          显示 raw
        </label>
        <span className="muted small" style={{ marginLeft: 'auto' }}>
          {events.length} 条事件 · 当前 Tick {meta?.tick_num ?? '—'}
        </span>
      </div>

      <div className="event-stream">
        {loading && events.length === 0 ? (
          <div className="event-stream-empty">加载中…</div>
        ) : events.length === 0 ? (
          <div className="event-stream-empty">
            尚无事件。点击底部「下一 Tick」开始推进剧情。
          </div>
        ) : (
          tickKeys.map((tick) => (
            <div key={tick} className="tick-group">
              <div className="tick-group-header">
                <span className="tick-badge">Tick {tick}</span>
                <span className="tick-time">{tickGroups[tick][0]?.game_time ?? ''}</span>
              </div>
              {tickGroups[tick].map((e) => (
                <EventCard key={e.id} event={e} showRaw={filter.showRaw} />
              ))}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function EventCard({ event, showRaw }: { event: EventRecord; showRaw: boolean }) {
  const importance = Math.max(0, Math.min(5, event.importance ?? 3));
  return (
    <div className={`event-card importance-${importance}`}>
      <div className="event-header">
        <span className="event-type">{event.event_type}</span>
        <span className="event-time">#{event.id}</span>
      </div>
      <div className="event-content">
        {event.content_polished || event.content_raw || '（空事件）'}
      </div>
      {showRaw && event.content_raw && (
        <div className="event-raw">raw: {event.content_raw}</div>
      )}
    </div>
  );
}
