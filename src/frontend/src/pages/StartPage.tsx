import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AdminNav from '../components/AdminNav';
import { useGameStore } from '../store/gameStore';
import { dramasApi } from '../api/client';

interface DramaItem {
  name: string;
  title: string;
  summary: string;
  protagonist_default?: string;
  start_game_time?: string;
  era_name?: string;
  files: string[];
}

type HomeCardKey = 'roleplay' | 'saves' | 'dramas' | 'knowledge' | 'model' | 'traces' | 'settings';

export default function StartPage() {
  const navigate = useNavigate();
  const saves = useGameStore((s) => s.saves);
  const refreshSaves = useGameStore((s) => s.refreshSaves);
  const switchSave = useGameStore((s) => s.switchSave);
  const setNotification = useGameStore((s) => s.setNotification);
  const setError = useGameStore((s) => s.setError);

  const [dramas, setDramas] = useState<DramaItem[]>([]);
  const [showDramaPicker, setShowDramaPicker] = useState(false);
  const [initDrama, setInitDrama] = useState<string | null>(null);
  const [saveName, setSaveName] = useState('');
  const [initializing, setInitializing] = useState(false);

  useEffect(() => {
    refreshSaves();
    dramasApi.list().then(setDramas).catch(() => {});
  }, [refreshSaves]);

  const handleCardClick = (key: HomeCardKey) => {
    switch (key) {
      case 'roleplay':
        setShowDramaPicker(true);
        break;
      case 'saves':
        navigate('/saves');
        break;
      case 'dramas':
        navigate('/dramas');
        break;
      case 'knowledge':
        navigate('/knowledge');
        break;
      case 'model':
        navigate('/model');
        break;
      case 'traces':
        navigate('/traces');
        break;
      case 'settings':
        navigate('/settings');
        break;
    }
  };

  const handleStartInit = async () => {
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
      setShowDramaPicker(false);
      setInitDrama(null);
      setSaveName('');
      navigate('/play');
    } catch (e: unknown) {
      setError(`导入失败：${e instanceof Error ? e.message : e}`);
    } finally {
      setInitializing(false);
    }
  };

  const cards: { key: HomeCardKey; icon: string; title: string; desc: string; count?: string }[] = [
    { key: 'roleplay', icon: '🎭', title: 'Roleplay 扮演', desc: '选择剧本，创建新存档，从第一幕开始你的故事' },
    { key: 'saves', icon: '📂', title: 'Recall 回忆', desc: '读取所有存档，继续未完的叙事', count: `${saves.length} 个存档` },
    { key: 'dramas', icon: '📜', title: 'Script 剧本', desc: '生成、编辑、管理剧本文件', count: `${dramas.length} 个剧本` },
    { key: 'knowledge', icon: '📚', title: 'Knowledge 知识库', desc: '管理世界观设定、角色外貌、武功等创作素材' },
    { key: 'model', icon: '🤖', title: 'Model 模型', desc: '查看与配置 Prompt、Skill、工具链' },
    { key: 'traces', icon: '📊', title: 'Traces 日志', desc: '查看所有请求的完整调用链记录' },
    { key: 'settings', icon: '⚙', title: 'Settings 设置', desc: '全局参数、LLM 管线、润色策略等' },
  ];

  return (
    <div className="admin-page">
      <AdminNav />
      <div className="admin-content start-page-content">
        <div className="start-hero">
          <h1>Aether Story Engine</h1>
          <div className="start-hero-subtitle">An AI-driven narrative engine · v3</div>
        </div>

        <div className="start-cards-grid">
          {cards.map((card) => (
            <div
              key={card.key}
              className="start-feature-card"
              onClick={() => handleCardClick(card.key)}
            >
              <div className="start-card-icon">{card.icon}</div>
              <div className="start-card-body">
                <h3>{card.title}</h3>
                <p>{card.desc}</p>
              </div>
              {card.count && <div className="start-card-count">{card.count}</div>}
              <div className="start-card-arrow">→</div>
            </div>
          ))}
        </div>

        {/* 选择剧本弹窗 */}
        {showDramaPicker && (
          <div className="modal-overlay" onClick={() => { setShowDramaPicker(false); setInitDrama(null); }}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h2>🎭 选择剧本开始扮演</h2>
                <button onClick={() => { setShowDramaPicker(false); setInitDrama(null); }} className="btn-icon">✕</button>
              </div>
              {dramas.length === 0 ? (
                <div className="empty-hint">
                  暂无剧本，请先到「剧本」页创建或导入剧本。
                  <div style={{ marginTop: 12 }}>
                    <button onClick={() => { setShowDramaPicker(false); navigate('/dramas'); }} className="btn-primary">
                      前往剧本管理
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="drama-picker-list">
                    {dramas.map((d) => (
                      <div
                        key={d.name}
                        className={`drama-picker-item${initDrama === d.name ? ' active' : ''}`}
                        onClick={() => { setInitDrama(d.name); setSaveName(`${d.name}_run`); }}
                      >
                        <div className="drama-picker-icon">📖</div>
                        <div className="drama-picker-info">
                          <div className="drama-picker-title">{d.title}</div>
                          <div className="drama-picker-meta">
                            <span>👤 {d.protagonist_default || '未指定'}</span>
                            <span>⏰ {d.start_game_time || '—'}</span>
                            <span>📁 {d.files.length} 文件</span>
                          </div>
                        </div>
                        {initDrama === d.name && <div className="drama-picker-check">✓</div>}
                      </div>
                    ))}
                  </div>
                  {initDrama && (
                    <div className="form-group" style={{ marginTop: 16 }}>
                      <label>存档名</label>
                      <input
                        value={saveName}
                        onChange={(e) => setSaveName(e.target.value)}
                        placeholder="my_save"
                      />
                    </div>
                  )}
                  <div className="modal-actions">
                    <button onClick={() => { setShowDramaPicker(false); setInitDrama(null); }} className="btn-secondary">取消</button>
                    <button
                      onClick={handleStartInit}
                      disabled={!initDrama || initializing}
                      className="btn-primary"
                    >
                      {initializing ? '⏳ 导入中...' : '🚀 从头开始'}
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
