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
  };
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

  const [saves, setSaves] = useState<SaveRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedSave, setSelectedSave] = useState<string | null>(null);
  const [snapshots, setSnapshots] = useState<SnapshotInfo[]>([]);
  const [showSnapshots, setShowSnapshots] = useState(false);

  const refresh = async () => {
    setLoading(true);
    try {
      const list = await savesApi.list();
      const rows: SaveRow[] = [];
      for (const name of list) {
        try {
          await savesApi.switch(name);
          const meta = await savesApi.getMeta();
          rows.push({ name, meta });
        } catch {
          rows.push({ name });
        }
      }
      // 切回第一个存档（如果有）
      if (rows.length > 0) {
        await savesApi.switch(rows[0].name);
      }
      setSaves(rows);
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
      setNotification(`已创建空存档 ${newName}（复制数据功能待 v3.1 接入）`);
      refresh();
    } catch (e: unknown) {
      setError(`复制失败：${e instanceof Error ? e.message : e}`);
    }
  };

  const handleDelete = async (name: string) => {
    if (!window.confirm(`确定删除存档 "${name}"？此操作不可恢复。`)) return;
    try {
      await savesApi.delete(name);
      setNotification(`已删除存档 ${name}`);
      refresh();
    } catch (e: unknown) {
      setError(`删除失败：${e instanceof Error ? e.message : e}`);
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
      setNotification('快照已创建');
      const r = await savesApi.listSnapshots();
      setSnapshots(r.snapshots || []);
    } catch (e: unknown) {
      setError(`创建快照失败：${e instanceof Error ? e.message : e}`);
    }
  };

  const handleRestore = async (snap: string) => {
    if (!window.confirm(`确定回滚到快照 "${snap}"？当前未保存的进度将丢失。`)) return;
    try {
      await savesApi.restoreSnapshot(snap);
      setNotification(`已回滚到 ${snap}`);
      setShowSnapshots(false);
    } catch (e: unknown) {
      setError(`回滚失败：${e instanceof Error ? e.message : e}`);
    }
  };

  const handleDeleteSnap = async (snap: string) => {
    if (!window.confirm(`删除快照 "${snap}"？`)) return;
    try {
      await savesApi.deleteSnapshot(snap);
      setNotification(`已删除快照 ${snap}`);
      const r = await savesApi.listSnapshots();
      setSnapshots(r.snapshots || []);
    } catch (e: unknown) {
      setError(`删除失败：${e instanceof Error ? e.message : e}`);
    }
  };

  return (
    <div className="admin-page">
      <AdminNav />
      <div className="admin-content">
        <div className="admin-header">
          <h1>📂 读取存档</h1>
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
          <table className="data-table">
            <thead>
              <tr>
                <th>存档名</th>
                <th>剧本</th>
                <th>tick</th>
                <th>游戏时间</th>
                <th>主角 ID</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {saves.map((s) => (
                <tr key={s.name}>
                  <td><strong>{s.name}</strong></td>
                  <td>{s.meta?.script_name || '—'}</td>
                  <td>{s.meta?.tick_num ?? '—'}</td>
                  <td>{s.meta?.game_time || '—'}</td>
                  <td>{s.meta?.protagonist_id ?? '—'}</td>
                  <td className="actions">
                    <button onClick={() => handleEnter(s.name)} className="btn-icon" title="进入">▶</button>
                    <button onClick={() => handleCopy(s.name)} className="btn-icon" title="复制">📋</button>
                    <button onClick={() => handleShowSnapshots(s.name)} className="btn-icon" title="快照">🕒</button>
                    <button onClick={() => handleDelete(s.name)} className="btn-icon btn-danger" title="删除">🗑</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
