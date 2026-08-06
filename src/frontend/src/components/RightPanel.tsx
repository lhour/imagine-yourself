// 右侧信息面板 — 5 个 tab：角色 / 群体 / 物品 / 地图 / 记忆
import type React from 'react';
import { useEffect, useState } from 'react';
import { useGameStore } from '../store/gameStore';
import { Character, Group, Item, MapRecord } from '../api/types';
import { memoryApi, entitiesApi } from '../api/client';

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

  const [profileCharId, setProfileCharId] = useState<number | null>(null);

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
          <CharacterTab chars={characters} onRefresh={refreshCharacters} onOpen={setProfileCharId} />
        )}
        {rightTab === 'groups' && (
          <GroupTab groups={groups} onRefresh={refreshGroups} />
        )}
        {rightTab === 'items' && <ItemTab items={items} onRefresh={refreshItems} />}
        {rightTab === 'maps' && (
          <MapTab maps={maps} onRefresh={refreshMaps} onOpen={openMapBrowser} />
        )}
        {rightTab === 'memory' && <MemoryTab onOpen={setProfileCharId} />}
      </div>

      {profileCharId != null && (
        <CharacterProfileModal charId={profileCharId} onClose={() => setProfileCharId(null)} />
      )}
    </div>
  );
}

// ============================================================
// 角色
// ============================================================
function CharacterTab({ chars, onRefresh, onOpen }: { chars: Character[]; onRefresh: () => void; onOpen: (id: number) => void }) {
  if (!Array.isArray(chars) || chars.length === 0) {
    return <EmptyHint text="尚无角色" onRefresh={onRefresh} />;
  }
  return (
    <>
      {chars.map((c) => (
        <div key={c.id} className="entity-card clickable" onClick={() => onOpen(c.id)}>
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
  if (!Array.isArray(groups) || groups.length === 0) {
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
  if (!Array.isArray(items) || items.length === 0) {
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
  if (!Array.isArray(maps) || maps.length === 0) {
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
interface MemoryCard {
  id: number;
  depth: number;
  correctness: number;
  is_false: boolean | number;
  remember_tick?: number;
  mood?: string;
  memory_polished?: string;
  memory_raw?: string;
}
interface ImpressionCard {
  target_char_id: number;
  target_name: string;
  impression_polished?: string;
  favorability?: number;
  trust?: number;
  fear?: number;
}

function MemoryTab({ onOpen }: { onOpen: (id: number) => void }) {
  const protagonist = useGameStore((s) => s.protagonist);
  const [memories, setMemories] = useState<MemoryCard[]>([]);
  const [impressions, setImpressions] = useState<ImpressionCard[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    if (!protagonist) return;
    setLoading(true);
    try {
      const r = await memoryApi.retrieve(protagonist.id, { max_count: 30, expand_palace: true });
      setMemories(Array.isArray(r?.memories) ? r.memories : []);
      setImpressions(Array.isArray(r?.outline) ? r.outline : []);
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [protagonist?.id]);

  if (!protagonist) {
    return <div className="entity-card entity-desc">尚未设定主角，无法查看记忆。</div>;
  }
  return (
    <div className="memory-panel">
      <div className="entity-card entity-desc">
        主角 <strong>{protagonist.name}</strong> 的记忆
        <button className="small" style={{ marginLeft: 8 }} onClick={() => void load()}>⟳ 刷新</button>
      </div>

      {loading && <div className="entity-desc">加载中…</div>}

      {impressions.length > 0 && (
        <div className="mem-section">
          <div className="mem-title">角色印象（{impressions.length}）</div>
          {impressions.map((im, i) => (
            <div key={i} className="entity-card clickable" onClick={() => onOpen(im.target_char_id)}>
              <div className="entity-name">{im.target_name || `#${im.target_char_id}`}</div>
              <div className="entity-desc">{im.impression_polished || '—'}</div>
              <div className="entity-desc small muted">
                好感 {im.favorability ?? '—'} · 信任 {im.trust ?? '—'} · 恐惧 {im.fear ?? '—'}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="mem-section">
        <div className="mem-title">记忆（{memories.length}）</div>
        {memories.length === 0 ? (
          <div className="entity-desc">暂无记忆。推进 tick 后角色会累积记忆。</div>
        ) : (
          memories.map((m) => (
            <div key={m.id} className="entity-card">
              <div className="entity-name">
                {m.is_false ? '⚠ 虚假记忆' : '记忆'}
                <span className="importance-dots small">深度 {m.depth}</span>
              </div>
              <div className="entity-desc">{m.memory_polished || m.memory_raw}</div>
              <div className="entity-desc small muted">
                正确率 {m.correctness ?? '—'}%{m.remember_tick != null ? ` · Tick ${m.remember_tick}` : ''}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ============================================================
// 角色档案抽屉
// ============================================================
interface CharProfile {
  character: Record<string, unknown>;
  impressions: ImpressionCard[];
  memories: MemoryCard[];
  quests: { id: number; title: string; status: string; desc_polished?: string }[];
  agendas: { id: number; title: string; status: string; principle_polished?: string }[];
  groups: { group_id: number; group_name: string; role_raw?: string; importance_in_group?: number }[];
  recent_events: { event_id: number; tick_num: number; event_type: string; content_polished?: string }[];
}

function CharacterProfileModal({ charId, onClose }: { charId: number; onClose: () => void }) {
  const [profile, setProfile] = useState<CharProfile | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    entitiesApi.characterProfile(charId)
      .then((r) => { if (active) setProfile(r as CharProfile); })
      .catch((e: unknown) => { if (active) setErr((e as { message?: string }).message ?? '加载失败'); });
    return () => { active = false; };
  }, [charId]);

  const ch = profile?.character as (Character & { personality_polished?: string; appearance_polished?: string }) | undefined;

  return (
    <div className="modal-mask" onClick={onClose}>
      <div className="modal-body profile-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="profile-head">
          <div>
            <h3>{ch?.name || `角色 #${charId}`}</h3>
            <div className="entity-desc">
              {ch?.gender ?? '—'} · {ch?.age != null ? `${ch.age}岁` : '—'}
              {ch?.status ? ` · ${ch.status}` : ''}
            </div>
          </div>
          <button className="close-x" onClick={onClose}>✕</button>
        </div>

        {err && <p style={{ color: '#b91c1c' }}>{err}</p>}
        {!profile && !err && <div className="entity-desc"><span className="spinner" /> 加载中…</div>}

        {profile && (
          <div className="profile-body">
            {ch?.appearance_polished && (
              <div className="profile-sec">
                <div className="prof-sec-title">外貌</div>
                <div className="entity-desc">{ch.appearance_polished}</div>
              </div>
            )}
            {ch?.personality_polished && (
              <div className="profile-sec">
                <div className="prof-sec-title">性格</div>
                <div className="entity-desc">{ch.personality_polished}</div>
              </div>
            )}

            <div className="profile-sec">
              <div className="prof-sec-title">角色印象（{profile.impressions.length}）</div>
              {profile.impressions.length === 0 ? <div className="entity-desc muted">—</div> :
                profile.impressions.map((im, i) => (
                  <div key={i} className="entity-card">
                    <div className="entity-name">{im.target_name || `#${im.target_char_id}`}</div>
                    <div className="entity-desc">{im.impression_polished || '—'}</div>
                  </div>
                ))}
            </div>

            <div className="profile-sec">
              <div className="prof-sec-title">记忆（{profile.memories.length}）</div>
              {profile.memories.length === 0 ? <div className="entity-desc muted">—</div> :
                profile.memories.slice(0, 20).map((m) => (
                  <div key={m.id} className="entity-card">
                    <div className="entity-desc">{m.memory_polished || m.memory_raw}</div>
                    <div className="entity-desc small muted">深度 {m.depth} · 正确率 {m.correctness}%</div>
                  </div>
                ))}
            </div>

            <div className="profile-sec">
              <div className="prof-sec-title">任务（{profile.quests.length}）</div>
              {profile.quests.length === 0 ? <div className="entity-desc muted">—</div> :
                profile.quests.map((q) => (
                  <div key={q.id} className="entity-card">
                    <div className="entity-name">{q.title} <span className="small muted">[{q.status}]</span></div>
                    <div className="entity-desc">{q.desc_polished || '—'}</div>
                  </div>
                ))}
            </div>

            <div className="profile-sec">
              <div className="prof-sec-title">纲领（{profile.agendas.length}）</div>
              {profile.agendas.length === 0 ? <div className="entity-desc muted">—</div> :
                profile.agendas.map((a) => (
                  <div key={a.id} className="entity-card">
                    <div className="entity-name">{a.title} <span className="small muted">[{a.status}]</span></div>
                    <div className="entity-desc">{a.principle_polished || '—'}</div>
                  </div>
                ))}
            </div>

            <div className="profile-sec">
              <div className="prof-sec-title">群体关系（{profile.groups.length}）</div>
              {profile.groups.length === 0 ? <div className="entity-desc muted">—</div> :
                profile.groups.map((g, i) => (
                  <div key={i} className="entity-card">
                    <div className="entity-name">{g.group_name || `#${g.group_id}`}</div>
                    <div className="entity-desc">身份 {g.role_raw || '—'} · 重要性 {g.importance_in_group ?? '—'}</div>
                  </div>
                ))}
            </div>

            <div className="profile-sec">
              <div className="prof-sec-title">最近参与事件（{profile.recent_events.length}）</div>
              {profile.recent_events.length === 0 ? <div className="entity-desc muted">—</div> :
                profile.recent_events.slice(0, 15).map((e) => (
                  <div key={e.event_id} className="entity-card">
                    <div className="entity-desc">Tick {e.tick_num} · {e.event_type}</div>
                    <div className="entity-desc">{e.content_polished || '—'}</div>
                  </div>
                ))}
            </div>
          </div>
        )}
      </div>
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

