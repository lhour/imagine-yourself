import { useEffect, useState } from 'react';
import { useGameStore } from '../store/gameStore';
import { savesApi, configApi } from '../api/client';

interface SnapshotItem {
  name: string;
}

function snapshotName(s: unknown): string {
  if (typeof s === 'string') return s;
  return ((s as SnapshotItem | null)?.name) ?? String(s ?? '');
}

const POLISH_LEN_OPTS = [
  { v: 'short', label: '短（1句）' },
  { v: 'medium', label: '中（3~5句）' },
  { v: 'long', label: '长（段落）' },
  { v: 'epic', label: '史诗（多段）' },
] as const;

export default function LeftPanel() {
  const meta = useGameStore((s) => s.meta);
  const activeSave = useGameStore((s) => s.activeSave);
  const refreshMeta = useGameStore((s) => s.refreshMeta);
  const refreshAll = useGameStore((s) => s.refreshAll);
  const protagonist = useGameStore((s) => s.protagonist);
  const setNotification = useGameStore((s) => s.setNotification);
  const setError = useGameStore((s) => s.setError);

  const [editingMeta, setEditingMeta] = useState(false);
  const [metaDraft, setMetaDraft] = useState({ tick_num: 0, game_time: '', era_name: '' });
  const [snapshots, setSnapshots] = useState<string[]>([]);
  const [cfg, setCfg] = useState<{
    polish_length?: string;
    gore_enabled?: boolean;
    adult_content?: boolean;
    violence_level?: number;
  }>({});

  const loadSnapshots = async () => {
    try {
      const data = await savesApi.listSnapshots();
      const items: unknown[] = data?.snapshots ?? [];
      setSnapshots(items.map(snapshotName));
    } catch {
      setSnapshots([]);
    }
  };

  const loadCfg = async () => {
    try {
      const c = await configApi.get();
      setCfg({
        polish_length: c.ui?.default_polish_length ?? c.simulation?.polish_length ?? 'medium',
        gore_enabled: c.simulation?.gore_enabled ?? false,
        adult_content: c.simulation?.adult_content ?? false,
        violence_level: c.simulation?.violence_level ?? 2,
      });
    } catch { /* ignore */ }
  };

  useEffect(() => {
    if (activeSave) {
      loadSnapshots();
    } else {
      setSnapshots([]);
    }
  }, [activeSave]);
  useEffect(() => { void loadCfg(); }, []);

  const patchCfg = async (patch: Record<string, unknown>) => {
    try {
      const simulation = {
        gore_enabled: cfg.gore_enabled,
        adult_content: cfg.adult_content,
        violence_level: cfg.violence_level,
        polish_length: cfg.polish_length,
        ...patch,
      };
      await configApi.patch({ simulation });
      setCfg((prev) => ({ ...prev, ...patch }));
      setNotification('设置已更新');
    } catch (e) {
      setError(`保存设置失败：${(e as Error).message}`);
    }
  };

  const startEditMeta = () => {
    if (meta) {
      setMetaDraft({
        tick_num: meta.tick_num,
        game_time: meta.game_time,
        era_name: meta.era_name ?? '',
      });
      setEditingMeta(true);
    }
  };

  const saveMeta = async () => {
    try {
      await savesApi.updateMeta({
        tick_num: metaDraft.tick_num,
        game_time: metaDraft.game_time,
        era_name: metaDraft.era_name,
      });
      await refreshMeta();
      setEditingMeta(false);
      setNotification('元信息已保存');
    } catch (e) {
      setError(`保存失败：${(e as Error).message}`);
    }
  };

  const createSnapshot = async () => {
    try {
      const r = await savesApi.createSnapshot();
      setNotification(`快照已创建：${(r as { created?: string }).created ?? ''}`);
      await loadSnapshots();
    } catch (e) {
      setError(`快照失败：${(e as Error).message}`);
    }
  };

  const restoreSnapshot = async (name: string) => {
    if (!confirm(`确认回滚到快照「${name}」？当前进度将被覆盖。`)) return;
    try {
      await savesApi.restoreSnapshot(name);
      setNotification('快照已回滚');
      await refreshAll();
      await loadSnapshots();
    } catch (e) {
      setError(`回滚失败：${(e as Error).message}`);
    }
  };

  const deleteSnapshot = async (name: string) => {
    if (!confirm(`确认删除快照「${name}」？`)) return;
    try {
      await savesApi.deleteSnapshot(name);
      setNotification('快照已删除');
      await loadSnapshots();
    } catch (e) {
      setError(`删除失败：${(e as Error).message}`);
    }
  };

  return (
    <div className="left-panel">
      <div className="panel-section">
        <div className="panel-title">
          <span>当前存档</span>
          <span className="panel-badge">{activeSave ?? '未激活'}</span>
        </div>
        <div className="field-row">
          <label>Tick</label>
          <span className="value">{meta?.tick_num ?? '—'}</span>
        </div>
        <div className="field-row">
          <label>游戏时间</label>
          <span className="value small">{meta?.game_time ?? '—'}</span>
        </div>
        <div className="field-row">
          <label>纪元</label>
          <span className="value">{meta?.era_name ?? '—'}</span>
        </div>
        <div className="field-row">
          <label>主角</label>
          <span className="value">{protagonist?.name ?? '—'}</span>
        </div>
        <div className="panel-actions">
          <button className="small" onClick={startEditMeta} disabled={!meta}>
            编辑
          </button>
          <button className="small" onClick={createSnapshot} disabled={!activeSave}>
            快照
          </button>
          <button className="small" onClick={refreshMeta}>
            刷新
          </button>
        </div>
      </div>

      <div className="panel-section">
        <div className="panel-title">
          <span>内容偏好</span>
        </div>
        <div className="field-row field-col">
          <label>润色长度</label>
          <select
            value={cfg.polish_length ?? 'medium'}
            onChange={(e) => void patchCfg({ polish_length: e.target.value })}
          >
            {POLISH_LEN_OPTS.map((o) => (
              <option key={o.v} value={o.v}>{o.label}</option>
            ))}
          </select>
        </div>
        <div className="field-row">
          <label>血腥描写</label>
          <label className="switch">
            <input
              type="checkbox"
              checked={!!cfg.gore_enabled}
              onChange={(e) => void patchCfg({ gore_enabled: e.target.checked })}
            />
            <span className="slider" />
          </label>
        </div>
        <div className="field-row">
          <label>成人内容</label>
          <label className="switch">
            <input
              type="checkbox"
              checked={!!cfg.adult_content}
              onChange={(e) => void patchCfg({ adult_content: e.target.checked })}
            />
            <span className="slider" />
          </label>
        </div>
        <div className="field-row field-col">
          <label>暴力等级 {cfg.violence_level ?? 2}/5</label>
          <input
            type="range"
            min={0} max={5} step={1}
            value={cfg.violence_level ?? 2}
            onChange={(e) => void patchCfg({ violence_level: Number(e.target.value) })}
          />
        </div>
      </div>

      <div className="panel-section">
        <div className="panel-title">
          <span>快照</span>
          <span className="panel-badge">{snapshots.length}</span>
        </div>
        {snapshots.length === 0 ? (
          <div className="panel-empty">暂无快照。点击上方「快照」保存当前进度。</div>
        ) : (
          <ul className="snapshot-mini-list">
            {snapshots.map((s) => (
              <li key={s}>
                <span className="snap-mini-name" title={s}>
                  {s}
                </span>
                <button className="snap-mini-btn" title="回滚" onClick={() => restoreSnapshot(s)}>
                  ↩
                </button>
                <button
                  className="snap-mini-btn danger"
                  title="删除"
                  onClick={() => deleteSnapshot(s)}
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {editingMeta && (
        <div className="modal-overlay" onClick={() => setEditingMeta(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h3>编辑元信息</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label>
                Tick
                <input
                  type="number"
                  value={metaDraft.tick_num}
                  onChange={(e) => setMetaDraft({ ...metaDraft, tick_num: Number(e.target.value) })}
                />
              </label>
              <label>
                游戏时间
                <input
                  type="text"
                  value={metaDraft.game_time}
                  onChange={(e) => setMetaDraft({ ...metaDraft, game_time: e.target.value })}
                />
              </label>
              <label>
                纪元
                <input
                  type="text"
                  value={metaDraft.era_name}
                  onChange={(e) => setMetaDraft({ ...metaDraft, era_name: e.target.value })}
                />
              </label>
            </div>
            <div className="modal-actions">
              <button onClick={() => setEditingMeta(false)}>取消</button>
              <button className="primary" onClick={saveMeta}>
                保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}