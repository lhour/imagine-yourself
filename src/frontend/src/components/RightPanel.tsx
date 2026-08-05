// 右侧信息面板 — 5 个 tab：角色 / 群体 / 物品 / 地图 / 记忆
import type React from 'react';
import { useGameStore } from '../store/gameStore';
import { Character, Group, Item, MapRecord } from '../api/types';

const TABS: { key: 'characters' | 'groups' | 'items' | 'maps' | 'memory'; label: string; icon: string }[] = [
  { key: 'characters', label: '角色', icon: '🧍' },
  { key: 'groups', label: '群体', icon: '👥' },
  { key: 'items', label: '物品', icon: '🎒' },
  { key: 'maps', label: '地图', icon: '🗺' },
  { key: 'memory', label: '记忆', icon: '🧠' },
];

function importanceDots(n: number): string {
  const v = Math.max(0, Math.min(5, n));
  return '★'.repeat(v) + '☆'.repeat(5 - v);
}

export default function RightPanel() {
  const rightTab = useGameStore((s) => s.rightTab);
  const setRightTab = useGameStore((s) => s.setRightTab);
  const characters = useGameStore((s) => s.characters);
  const groups = useGameStore((s) => s.groups);
  const items = useGameStore((s) => s.items);
  const maps = useGameStore((s) => s.maps);
  const openMapBrowser = useGameStore((s) => s.openMapBrowser);
  const refreshCharacters = useGameStore((s) => s.refreshCharacters);
  const refreshGroups = useGameStore((s) => s.refreshGroups);
  const refreshItems = useGameStore((s) => s.refreshItems);
  const refreshMaps = useGameStore((s) => s.refreshMaps);

  return (
    <div className="right-panel">
      <div className="tab-bar">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`tab-btn ${rightTab === t.key ? 'active' : ''}`}
            onClick={() => setRightTab(t.key)}
          >
            <span>{t.icon}</span>
            <span>{t.label}</span>
          </button>
        ))}
      </div>

      <div className="tab-content">
        {rightTab === 'characters' && (
          <CharacterTab chars={characters} onRefresh={refreshCharacters} />
        )}
        {rightTab === 'groups' && (
          <GroupTab groups={groups} onRefresh={refreshGroups} />
        )}
        {rightTab === 'items' && <ItemTab items={items} onRefresh={refreshItems} />}
        {rightTab === 'maps' && (
          <MapTab maps={maps} onRefresh={refreshMaps} onOpen={openMapBrowser} />
        )}
        {rightTab === 'memory' && <MemoryTab />}
      </div>
    </div>
  );
}

// ============================================================
// 角色
// ============================================================
function CharacterTab({ chars, onRefresh }: { chars: Character[]; onRefresh: () => void }) {
  if (chars.length === 0) {
    return <EmptyHint text="尚无角色" onRefresh={onRefresh} />;
  }
  return (
    <>
      {chars.map((c) => (
        <div key={c.id} className="entity-card">
          <div className="entity-name">
            {c.name}
            <span className="importance-dots small">{importanceDots(c.importance)}</span>
          </div>
          <div className="entity-desc">
            {c.gender ?? '—'} · {c.age != null ? `${c.age}岁` : '—'}
            {c.status ? ` · ${c.status}` : ''}
          </div>
          {c.appearance_polished && (
            <div className="entity-desc">{c.appearance_polished.slice(0, 40)}…</div>
          )}
        </div>
      ))}
    </>
  );
}

// ============================================================
// 群体
// ============================================================
function GroupTab({ groups, onRefresh }: { groups: Group[]; onRefresh: () => void }) {
  if (groups.length === 0) {
    return <EmptyHint text="尚无群体" onRefresh={onRefresh} />;
  }
  return (
    <>
      {groups.map((g) => (
        <div key={g.id} className="entity-card">
          <div className="entity-name">
            {g.name}
            <span className="importance-dots small">{importanceDots(g.importance)}</span>
          </div>
          <div className="entity-desc">
            {g.group_type}
            {g.heatmap_grid ? ' · 有热力图' : ' · 点状分布'}
          </div>
          {g.desc_polished && (
            <div className="entity-desc">{g.desc_polished.slice(0, 40)}…</div>
          )}
        </div>
      ))}
    </>
  );
}

// ============================================================
// 物品
// ============================================================
function ItemTab({ items, onRefresh }: { items: Item[]; onRefresh: () => void }) {
  if (items.length === 0) {
    return <EmptyHint text="尚无物品" onRefresh={onRefresh} />;
  }
  return (
    <>
      {items.map((it) => (
        <div key={it.id} className="entity-card">
          <div className="entity-name">
            {it.name}
            <span className="importance-dots small">{importanceDots(it.importance)}</span>
          </div>
          <div className="entity-desc">
            {it.item_type} · 稀有度 {it.rarity}
            {it.is_stackable ? ` · 堆叠×${it.stack_size}` : ''}
          </div>
        </div>
      ))}
    </>
  );
}

// ============================================================
// 地图
// ============================================================
function MapTab({
  maps,
  onRefresh,
  onOpen,
}: {
  maps: MapRecord[];
  onRefresh: () => void;
  onOpen: (mapId?: number | null) => void;
}) {
  if (maps.length === 0) {
    return <EmptyHint text="尚无地图" onRefresh={onRefresh} />;
  }
  // 按 parent_map_id 组织成树
  const roots = maps.filter((m) => m.parent_map_id == null);
  const childrenOf = (pid: number) => maps.filter((m) => m.parent_map_id === pid);
  const renderNode = (m: MapRecord, depth: number): React.ReactNode => {
    const kids = childrenOf(m.id);
    return (
      <div key={m.id} style={{ marginLeft: depth * 12 }}>
        <div className="entity-card" onClick={() => onOpen(m.id)}>
          <div className="entity-name">
            {m.name}
            {m.is_mobile ? <span className="small muted"> (移动)</span> : null}
          </div>
          <div className="entity-desc">
            {m.map_type} · {m.coord_system}
            {kids.length ? ` · ${kids.length} 子地图` : ''}
          </div>
        </div>
        {kids.map((k) => renderNode(k, depth + 1))}
      </div>
    );
  };
  return <>{roots.map((r) => renderNode(r, 0))}</>;
}

// ============================================================
// 记忆（主角视角）
// ============================================================
function MemoryTab() {
  const protagonist = useGameStore((s) => s.protagonist);
  if (!protagonist) {
    return <div className="entity-card entity-desc">尚未设定主角，无法查看记忆。</div>;
  }
  return (
    <div className="entity-card entity-desc">
      主角 <strong>{protagonist.name}</strong> 的记忆宫殿
      <br />
      <span className="muted small">（记忆检索入口开发中）</span>
    </div>
  );
}

// ============================================================
// 空状态提示
// ============================================================
function EmptyHint({ text, onRefresh }: { text: string; onRefresh: () => void }) {
  return (
    <div className="event-stream-empty" style={{ height: 'auto', padding: '24px 8px' }}>
      <div style={{ marginBottom: 8 }}>{text}</div>
      <button className="small" onClick={onRefresh}>⟳ 刷新</button>
    </div>
  );
}

