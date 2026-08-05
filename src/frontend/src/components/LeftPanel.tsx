import { useState } from 'react';
import { useGameStore } from '../store/gameStore';
import { savesApi } from '../api/client';

export default function LeftPanel() {
  const meta = useGameStore((s) => s.meta);
  const activeSave = useGameStore((s) => s.activeSave);
  const refreshMeta = useGameStore((s) => s.refreshMeta);
  const refreshSaves = useGameStore((s) => s.refreshSaves);
  const protagonist = useGameStore((s) => s.protagonist);

  const [editingMeta, setEditingMeta] = useState(false);
  const [metaDraft, setMetaDraft] = useState({ tick_num: 0, game_time: '', era_name: '' });
  const [snapshotName, setSnapshotName] = useState('');

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
    } catch (e) {
      alert(`保存失败：${(e as Error).message}`);
    }
  };

  const createSnapshot = async () => {
    try {
      const r = await fetch('/api/saves/snapshot', { method: 'POST' });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || '快照失败');
      alert(`快照已创建：${data.created ?? ''}`);
    } catch (e) {
      alert(`快照失败：${(e as Error).message}`);
    }
  };

  const saveGame = async () => {
    // 元信息已经在后端持久化，这里只是触发一次快照
    await createSnapshot();
  };

  return (
    <div className="left-panel">
      <div className="panel-section">
        <h4>当前存档</h4>
        <div className="field-row">
          <label>存档名</label>
          <span className="value">{activeSave ?? '—'}</span>
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
        <div style={{ display: 'flex', gap: 4, marginTop: 8 }}>
          <button className="small" onClick={startEditMeta}>编辑</button>
          <button className="small" onClick={saveGame}>保存</button>
          <button className="small" onClick={() => { refreshSaves(); refreshMeta(); }}>刷新</button>
        </div>
      </div>

      <div className="panel-section">
        <h4>全局配置</h4>
        <div className="toggle-row">
          <label>
            <input type="checkbox" defaultChecked={false} /> 血腥
          </label>
        </div>
        <div className="toggle-row">
          <label>
            <input type="checkbox" defaultChecked={false} /> 成人内容
          </label>
        </div>
        <div className="field-row">
          <label>润色长度</label>
          <select className="small" defaultValue="medium">
            <option value="short">短</option>
            <option value="medium">中</option>
            <option value="long">长</option>
            <option value="epic">史诗</option>
          </select>
        </div>
        <div className="field-row">
          <label>风格</label>
          <select className="small" defaultValue="narrative">
            <option value="narrative">叙事</option>
            <option value="ancient">古风</option>
            <option value="scifi">科幻</option>
            <option value="realistic">写实</option>
          </select>
        </div>
      </div>

      <div className="panel-section">
        <h4>快照</h4>
        <div className="form-row">
          <input
            className="small"
            placeholder="（自动命名）"
            value={snapshotName}
            onChange={(e) => setSnapshotName(e.target.value)}
            disabled
          />
        </div>
        <button className="small" style={{ width: '100%' }} onClick={createSnapshot}>
          创建快照
        </button>
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
              <button className="primary" onClick={saveMeta}>保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
