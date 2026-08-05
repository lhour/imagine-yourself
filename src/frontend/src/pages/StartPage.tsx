import { useState } from 'react';
import { useGameStore } from '../store/gameStore';

export default function StartPage() {
  const saves = useGameStore((s) => s.saves);
  const createSave = useGameStore((s) => s.createSave);
  const switchSave = useGameStore((s) => s.switchSave);
  const deleteSave = useGameStore((s) => s.deleteSave);
  const [newName, setNewName] = useState('');

  const handleCreate = async () => {
    const name = newName.trim();
    if (!name) return;
    if (!/^[a-zA-Z0-9_-]+$/.test(name)) {
      alert('存档名只能包含字母、数字、下划线、连字符');
      return;
    }
    await createSave(name);
    setNewName('');
  };

  return (
    <div className="start-page">
      <div>
        <h1>设身处地</h1>
        <div className="subtitle">v3 · 客观/主观双轨制叙事引擎</div>
      </div>

      <div className="start-card">
        <h2>新建存档</h2>
        <div className="form-row">
          <input
            type="text"
            placeholder="存档名（字母/数字/_/-）"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
          />
          <button className="primary" onClick={handleCreate} disabled={!newName.trim()}>
            创建
          </button>
        </div>
      </div>

      {saves.length > 0 && (
        <div className="start-card">
          <h2>已有存档（{saves.length}）</h2>
          <div className="saves-list">
            {saves.map((name) => (
              <div key={name} className="save-item">
                <span className="save-name">{name}</span>
                <div className="save-actions">
                  <button className="primary" onClick={() => switchSave(name)}>
                    进入
                  </button>
                  <button
                    className="danger"
                    onClick={() => {
                      if (confirm(`确定删除存档「${name}」？此操作不可逆。`)) {
                        deleteSave(name);
                      }
                    }}
                  >
                    删除
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
