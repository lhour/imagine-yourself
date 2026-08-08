import { useEffect, useState } from 'react';
import { useGameStore } from '../store/gameStore';
import { savesApi, configApi, v5Api } from '../api/client';

interface SnapshotItem {
  name: string;
}

interface GameplayOptions {
  player_sexuality: string;
  death_likelihood: number;
  favorability_bias: number;
  luck_bias: number;
  challenge_bias: number;
  writing_style: string;
  world_modify_allowed: boolean;
}

function snapshotName(s: unknown): string {
  if (typeof s === 'string') return s;
  return ((s as SnapshotItem | null)?.name) ?? String(s ?? '');
}

const POLISH_MODE_OPTS = [
  { v: 'none', label: '无润色' },
  { v: 'short', label: '短润色' },
  { v: 'long', label: '长润色' },
] as const;

const DEFAULT_GAMEPLAY: GameplayOptions = {
  player_sexuality: '异主角',
  death_likelihood: 3,
  favorability_bias: 0,
  luck_bias: 0,
  challenge_bias: 0,
  writing_style: '直白',
  world_modify_allowed: false,
};

const SEXUALITY_OPTS = ['男', '女', '同主角', '异主角'];
const WRITING_STYLE_OPTS = ['直白', '隐晦', '写意', '克制'];
const BIAS_OPTS = [
  { v: -5, label: '极端(-5)' },
  { v: -3, label: '较低(-3)' },
  { v: -1, label: '略低(-1)' },
  { v: 0, label: '中性(0)' },
  { v: 1, label: '略高(1)' },
  { v: 3, label: '较高(3)' },
  { v: 5, label: '极端(5)' },
];
const DEATH_OPTS = [
  { v: 0, label: '几乎不会死' },
  { v: 1, label: '很少死亡' },
  { v: 2, label: '偶发死亡' },
  { v: 3, label: '正常概率' },
  { v: 4, label: '较频繁' },
  { v: 5, label: '频繁且残酷' },
];

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
    polish_mode?: string;
  }>({});

  const [gameplayOpen, setGameplayOpen] = useState(false);
  const [gameplay, setGameplay] = useState<GameplayOptions>(DEFAULT_GAMEPLAY);
  const [gameplayLoading, setGameplayLoading] = useState(false);

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
        polish_mode: c.simulation?.polish_mode ?? 'none',
      });
    } catch { /* ignore */ }
  };

  const loadGameplay = async () => {
    if (!activeSave) return;
    setGameplayLoading(true);
    try {
      const r = await v5Api.getGameplayOptions();
      const opts = { ...DEFAULT_GAMEPLAY, ...r.gameplay_options } as GameplayOptions;
      setGameplay(opts);
    } catch { /* ignore */ }
    finally {
      setGameplayLoading(false);
    }
  };

  useEffect(() => {
    if (activeSave) {
      loadSnapshots();
      loadGameplay();
    } else {
      setSnapshots([]);
    }
  }, [activeSave]);
  useEffect(() => { void loadCfg(); }, []);

  const patchCfg = async (patch: Record<string, unknown>) => {
    try {
      const simulation = {
        polish_mode: cfg.polish_mode,
        ...patch,
      };
      await configApi.patch({ simulation });
      setCfg((prev) => ({ ...prev, ...patch }));
      setNotification('设置已更新');
    } catch (e) {
      setError(`保存设置失败：${(e as Error).message}`);
    }
  };

  const patchGameplay = async (patch: Partial<GameplayOptions>) => {
    try {
      const full = { ...gameplay, ...patch };
      const result = await v5Api.setGameplayOptions(full);
      if (result.gameplay_options) {
        setGameplay(result.gameplay_options as GameplayOptions);
      }
      setNotification('玩法配置已更新');
    } catch (e) {
      setError(`保存玩法配置失败：${(e as Error).message}`);
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
      await loadSnapshots();
      setNotification(`快照已创建：${(r as { created?: string }).created ?? ''}`);
    } catch (e) {
      setError(`快照失败：${(e as Error).message}`);
    }
  };

  const restoreSnapshot = async (name: string) => {
    if (!confirm(`确认回滚到快照「${name}」？当前进度将被覆盖。`)) return;
    try {
      await savesApi.restoreSnapshot(name);
      await refreshAll();
      await loadSnapshots();
      setNotification('快照已回滚');
    } catch (e) {
      setError(`回滚失败：${(e as Error).message}`);
    }
  };

  const deleteSnapshot = async (name: string) => {
    if (!confirm(`确认删除快照「${name}」？`)) return;
    try {
      await savesApi.deleteSnapshot(name);
      await loadSnapshots();
      setNotification('快照已删除');
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
          <label>润色</label>
          <select
            value={cfg.polish_mode ?? 'none'}
            onChange={(e) => void patchCfg({ polish_mode: e.target.value })}
          >
            {POLISH_MODE_OPTS.map((o) => (
              <option key={o.v} value={o.v}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="panel-section">
        <div className="panel-title" style={{ cursor: 'pointer', userSelect: 'none' }} onClick={() => setGameplayOpen(!gameplayOpen)}>
          <span>🎮 玩法配置</span>
          <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{gameplayOpen ? '▼' : '▶'}</span>
        </div>
        {gameplayOpen && (
          gameplayLoading ? (
            <div className="panel-empty">加载中...</div>
          ) : (
            <>
              <div className="field-row field-col">
                <label>主角性取向</label>
                <select
                  value={gameplay.player_sexuality}
                  onChange={(e) => void patchGameplay({ player_sexuality: e.target.value })}
                  disabled={!activeSave}
                >
                  {SEXUALITY_OPTS.map((v) => (
                    <option key={v} value={v}>{v}</option>
                  ))}
                </select>
              </div>
              <div className="field-row field-col">
                <label>叙事笔法</label>
                <select
                  value={gameplay.writing_style}
                  onChange={(e) => void patchGameplay({ writing_style: e.target.value })}
                  disabled={!activeSave}
                >
                  {WRITING_STYLE_OPTS.map((v) => (
                    <option key={v} value={v}>{v}</option>
                  ))}
                </select>
              </div>
              <div className="field-row field-col">
                <label>死亡概率</label>
                <select
                  value={gameplay.death_likelihood}
                  onChange={(e) => void patchGameplay({ death_likelihood: Number(e.target.value) })}
                  disabled={!activeSave}
                >
                  {DEATH_OPTS.map((o) => (
                    <option key={o.v} value={o.v}>{o.label}</option>
                  ))}
                </select>
              </div>
              <div className="field-row field-col">
                <label>好感度倾向</label>
                <select
                  value={gameplay.favorability_bias}
                  onChange={(e) => void patchGameplay({ favorability_bias: Number(e.target.value) })}
                  disabled={!activeSave}
                >
                  {BIAS_OPTS.map((o) => (
                    <option key={o.v} value={o.v}>{o.label}</option>
                  ))}
                </select>
              </div>
              <div className="field-row field-col">
                <label>运气倾向</label>
                <select
                  value={gameplay.luck_bias}
                  onChange={(e) => void patchGameplay({ luck_bias: Number(e.target.value) })}
                  disabled={!activeSave}
                >
                  {BIAS_OPTS.map((o) => (
                    <option key={o.v} value={o.v}>{o.label}</option>
                  ))}
                </select>
              </div>
              <div className="field-row field-col">
                <label>挑战倾向</label>
                <select
                  value={gameplay.challenge_bias}
                  onChange={(e) => void patchGameplay({ challenge_bias: Number(e.target.value) })}
                  disabled={!activeSave}
                >
                  {BIAS_OPTS.map((o) => (
                    <option key={o.v} value={o.v}>{o.label}</option>
                  ))}
                </select>
              </div>
              <div className="field-row field-col">
                <label>允许模型追加设定</label>
                <select
                  value={gameplay.world_modify_allowed ? 'true' : 'false'}
                  onChange={(e) => void patchGameplay({ world_modify_allowed: e.target.value === 'true' })}
                  disabled={!activeSave}
                >
                  <option value="false">禁止（只读）</option>
                  <option value="true">允许追加</option>
                </select>
              </div>
              {!activeSave && (
                <div className="panel-empty" style={{ marginTop: 8, fontSize: 12 }}>
                  请先激活存档
                </div>
              )}
            </>
          )
        )}
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