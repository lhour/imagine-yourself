import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AdminNav from '../components/AdminNav';
import { useGameStore } from '../store/gameStore';
import { dramasApi, configApi } from '../api/client';

interface DramaItem {
  name: string;
  title: string;
  summary: string;
  protagonist_default?: string;
  start_game_time?: string;
  era_name?: string;
  files: string[];
}

export default function StartPage() {
  const navigate = useNavigate();
  const saves = useGameStore((s) => s.saves);
  const refreshSaves = useGameStore((s) => s.refreshSaves);
  const switchSave = useGameStore((s) => s.switchSave);
  const setNotification = useGameStore((s) => s.setNotification);
  const setError = useGameStore((s) => s.setError);

  const [dramas, setDramas] = useState<DramaItem[]>([]);
  const [initDrama, setInitDrama] = useState<string | null>(null);
  const [saveName, setSaveName] = useState('');
  const [initializing, setInitializing] = useState(false);

  useEffect(() => {
    refreshSaves();
    dramasApi.list().then(setDramas).catch(() => {});
  }, [refreshSaves]);

  const handleEnter = async (name: string) => {
    await switchSave(name);
    navigate('/play');
  };

  const handleInit = async () => {
    if (!initDrama || !saveName.trim()) {
      setError('请填写存档名');
      return;
    }
    setInitializing(true);
    try {
      const r = await dramasApi.init(initDrama, saveName.trim(), false);
      const stats = r.stats || {};
      setNotification(
        `剧本已导入！角色 ${stats.characters ?? 0} / 群体 ${stats.groups ?? 0} / 事件 ${stats.events ?? 0}`
      );
      await switchSave(saveName.trim());
      navigate('/play');
    } catch (e: unknown) {
      setError(`导入失败：${e instanceof Error ? e.message : e}`);
    } finally {
      setInitializing(false);
    }
  };

  return (
    <div className="admin-page">
      <AdminNav />
      <div className="admin-content">
        <div className="hero">
          <h1>设身处地</h1>
          <div className="hero-subtitle">v3 · 客观/主观双轨制叙事引擎</div>
          <div className="hero-actions">
            <button onClick={() => navigate('/dramas')} className="btn-primary">📜 浏览剧本</button>
            <button onClick={() => navigate('/saves')} className="btn-secondary">📂 读取存档</button>
          </div>
        </div>

        {/* 最近存档 */}
        {saves.length > 0 && (
          <section className="home-section">
            <h2>📂 最近存档</h2>
            <div className="save-tiles">
              {saves.slice(0, 5).map((name) => (
                <div key={name} className="save-tile" onClick={() => handleEnter(name)}>
                  <span className="save-tile-icon">🎮</span>
                  <span className="save-tile-name">{name}</span>
                  <span className="save-tile-hint">点击进入 →</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* 剧本卡片区 */}
        <section className="home-section">
          <h2>📜 可用剧本（点击导入新存档）</h2>
          {dramas.length === 0 ? (
            <div className="empty-hint">暂无剧本，<a href="#/dramas">前往剧本管理</a></div>
          ) : (
            <div className="drama-grid">
              {dramas.map((d) => (
                <div key={d.name} className="drama-card">
                  <div className="drama-card-cover">
                    <span className="drama-cover-icon">📖</span>
                    <span className="drama-cover-files">{d.files.length} 文件</span>
                  </div>
                  <div className="drama-card-body">
                    <h3>{d.title}</h3>
                    <div className="drama-meta">
                      <span>👤 {d.protagonist_default || '未指定'}</span>
                      <span>⏰ {d.start_game_time || '—'}</span>
                    </div>
                    <p className="drama-summary">{d.summary}</p>
                    <button
                      className="btn-primary"
                      onClick={() => { setInitDrama(d.name); setSaveName(`${d.name}_run`); }}
                    >
                      ▶ 导入并开始
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* 导入存档 Modal */}
        {initDrama && (
          <div className="modal-overlay" onClick={() => setInitDrama(null)}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h2>▶ 导入剧本 "{initDrama}" 为新存档</h2>
                <button onClick={() => setInitDrama(null)} className="btn-icon">✕</button>
              </div>
              <div className="form-group">
                <label>新存档名</label>
                <input
                  value={saveName}
                  onChange={(e) => setSaveName(e.target.value)}
                  placeholder="my_save"
                />
              </div>
              <div className="modal-actions">
                <button onClick={() => setInitDrama(null)} className="btn-secondary">取消</button>
                <button onClick={handleInit} disabled={initializing} className="btn-primary">
                  {initializing ? '⏳ 导入中...' : '🚀 开始游戏'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
