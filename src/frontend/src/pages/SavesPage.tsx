import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AdminNav from '../components/AdminNav';
import { savesApi } from '../api/client';
import { useGameStore } from '../store/gameStore';

interface SaveRow {
  name: string;
  meta?: {
    tick_num?: number;
    game_time?: string;
    script_name?: string;
    protagonist_id?: number | null;
    era_name?: string;
  };
  protagonist_name?: string;
  mtime?: string;
  size?: number;
}

interface SnapshotInfo {
  name: string;
  size_bytes?: number;
  mtime?: string;
}

export default function SavesPage() {
  const navigate = useNavigate();
  const setNotification = useGameStore((s) => s.setNotification);
  const setError = useGameStore((s) => s.setError);
  const switchSave = useGameStore((s) => s.switchSave);
  const refreshSaves = useGameStore((s) => s.refreshSaves);
  const clearActiveSave = useGameStore((s) => s.clearActiveSave);
  const activeSave = useGameStore((s) => s.activeSave);

  const [saves, setSaves] = useState<SaveRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedSave, setSelectedSave] = useState<string | null>(null);
  const [snapshots, setSnapshots] = useState<SnapshotInfo[]>([]);
  const [showSnapshots, setShowSnapshots] = useState(false);

  const refresh = async () => {
    setLoading(true);
    try {
      // 并行获取存档列表和所有存档的元信息
      const [list, metas] = await Promise.all([
        savesApi.list(),
        savesApi.batchMeta(),
      ]);

      const metaMap = new Map<string, any>();
      for (const m of metas) {
        if (m.save) {
          metaMap.set(m.save as string, m);
        }
      }

      const rows: SaveRow[] = list.map((name) => {
        const meta = metaMap.get(name);
        if (!meta) return { name };

        const row: SaveRow = {
          name,
          meta: {
            tick_num: meta.tick_num,
            game_time: meta.game_time,
            script_name: meta.script_name,
            protagonist_id: meta.protagonist_id,
            era_name: meta.era_name,
          },
        };

        // 使用批量接口返回的主角名
        if (meta.protagonist_name) {
          row.protagonist_name = meta.protagonist_name as string;
        } else if (meta.protagonist_id) {
          row.protagonist_name = `#${meta.protagonist_id}`;
        }

        return row;
      });

      setSaves(rows);

      // 切回第一个存档（如果有），用 try-catch 防止超时影响列表显示
      if (rows.length > 0) {
        try {
          await savesApi.switch(rows[0].name);
        } catch {
          // 忽略超时错误，列表已经显示
        }
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(`加载存档列表失败：${msg}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleEnter = async (name: string) => {
    try {
      await switchSave(name);
      navigate('/play');
    } catch (e: unknown) {
      setError(`进入存档失败：${e instanceof Error ? e.message : e}`);
    }
  };

  const handleCopy = async (name: string) => {
    const newName = window.prompt(`复制存档 "${name}" 为：`, `${name}_copy`);
    if (!newName) return;
    try {
      await savesApi.create(newName);
      await refresh();
      setNotification(`已创建空存档 ${newName}（复制数据功能待 v3.1 接入）`);
    } catch (e: unknown) {
      setError(`复制失败：${e instanceof Error ? e.message : e}`);
    }
  };

  const handleDelete = async (name: string) => {
    if (!window.confirm(`确定删除存档 "${name}"？此操作不可恢复。`)) return;
    try {
      await savesApi.delete(name);
      if (activeSave === name) {
        clearActiveSave();
        await refreshSaves();
      }
      await refresh();
      setNotification(`存档「${name}」已删除`);
    } catch (e) {
      setError(`删除存档失败：${(e as Error).message}`);
    }
  };

  const handleShowSnapshots = async (name: string) => {
    try {
      await savesApi.switch(name);
      const r = await savesApi.listSnapshots();
      setSnapshots(r.snapshots || []);
      setSelectedSave(name);
      setShowSnapshots(true);
    } catch (e: unknown) {
      setError(`加载快照失败：${e instanceof Error ? e.message : e}`);
    }
  };

  const handleCreateSnapshot = async () => {
    try {
      await savesApi.createSnapshot();
      const r = await savesApi.listSnapshots();
      setSnapshots(r.snapshots || []);
      setNotification('快照已创建');
    } catch (e: unknown) {
      setError(`创建快照失败：${e instanceof Error ? e.message : e}`);
    }
  };

  const handleRestore = async (snap: string) => {
    if (!window.confirm(`确定回滚到快照 "${snap}"？当前未保存的进度将丢失。`)) return;
    try {
      await savesApi.restoreSnapshot(snap);
      setShowSnapshots(false);
      setNotification(`已回滚到 ${snap}`);
    } catch (e: unknown) {
      setError(`回滚失败：${e instanceof Error ? e.message : e}`);
    }
  };

  const handleDeleteSnap = async (snap: string) => {
    if (!window.confirm(`删除快照 "${snap}"？`)) return;
    try {
      await savesApi.deleteSnapshot(snap);
      const r = await savesApi.listSnapshots();
      setSnapshots(r.snapshots || []);
      setNotification(`已删除快照 ${snap}`);
    } catch (e: unknown) {
      setError(`删除失败：${e instanceof Error ? e.message : e}`);
    }
  };

  return (
    <div className="admin-page">
      <AdminNav />
      <div className="admin-content">
        <div className="admin-header">
          <h1>📂 Recall 回忆</h1>
          <button onClick={refresh} disabled={loading} className="btn-secondary">
            {loading ? '加载中...' : '🔄 刷新'}
          </button>
        </div>

        {saves.length === 0 && !loading ? (
          <div className="empty-state">
            <p>暂无存档。请先到「剧本」页导入一个剧本生成存档。</p>
            <button onClick={() => navigate('/dramas')} className="btn-primary">
              📜 去剧本管理
            </button>
          </div>
        ) : (
          <div className="saves-grid">
            {saves.map((s) => (
              <div key={s.name} className="save-detail-card">
                <div className="save-detail-header">
                  <div className="save-detail-icon">🎮</div>
                  <div className="save-detail-name">{s.name}</div>
                </div>
                <div className="save-detail-info">
                  <div className="save-detail-row">
                    <span className="label">剧本</span>
                    <span className="value">{s.meta?.script_name || '—'}</span>
                  </div>
                  <div className="save-detail-row">
                    <span className="label">Tick</span>
                    <span className="value">{s.meta?.tick_num ?? '—'}</span>
                  </div>
                  <div className="save-detail-row">
                    <span className="label">游戏时间</span>
                    <span className="value">{s.meta?.game_time || '—'}</span>
                  </div>
                  <div className="save-detail-row">
                    <span className="label">主角</span>
                    <span className="value highlight">
                      {s.protagonist_name || (s.meta?.protagonist_id ? `#${s.meta.protagonist_id}` : '—')}
                    </span>
                  </div>
                </div>
                <div className="save-detail-actions">
                  <button onClick={() => handleEnter(s.name)} className="btn-primary small">▶ 进入</button>
                  <button onClick={() => handleShowSnapshots(s.name)} className="btn-secondary small">🕒 快照</button>
                  <button onClick={() => handleCopy(s.name)} className="btn-secondary small">📋 复制</button>
                  <button onClick={() => handleDelete(s.name)} className="btn-icon btn-danger" title="删除">🗑</button>
                </div>
              </div>
            ))}
          </div>
        )}

        {showSnapshots && (
          <div className="modal-overlay" onClick={() => setShowSnapshots(false)}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h2>🕒 存档 "{selectedSave}" 的快照</h2>
                <button onClick={() => setShowSnapshots(false)} className="btn-icon">✕</button>
              </div>
              <div className="modal-actions">
                <button onClick={handleCreateSnapshot} className="btn-primary">+ 创建快照</button>
              </div>
              {snapshots.length === 0 ? (
                <p className="empty-hint">暂无快照</p>
              ) : (
                <ul className="snapshot-list">
                  {snapshots.map((snap) => {
                    const name = typeof snap === 'string' ? snap : snap.name;
                    return (
                      <li key={name}>
                        <span className="snap-name">{name}</span>
                        <button onClick={() => handleRestore(name)} className="btn-icon" title="回滚">↩</button>
                        <button onClick={() => handleDeleteSnap(name)} className="btn-icon btn-danger" title="删除">🗑</button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
