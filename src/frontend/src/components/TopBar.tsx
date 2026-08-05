import { useState } from 'react';
import { useGameStore } from '../store/gameStore';
import MenuDrawer from './MenuDrawer';

export default function TopBar() {
  const meta = useGameStore((s) => s.meta);
  const activeSave = useGameStore((s) => s.activeSave);
  const protagonist = useGameStore((s) => s.protagonist);
  const refreshAll = useGameStore((s) => s.refreshAll);
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <>
      <div className="topbar-section">
        <span className="topbar-title">设身处地 v3</span>
        {activeSave && (
          <span className="meta-chip">
            存档 <strong>{activeSave}</strong>
          </span>
        )}
      </div>

      {meta && (
        <>
          <div className="topbar-section">
            <span className="meta-chip">
              Tick <strong>{meta.tick_num}</strong>
            </span>
            <span className="meta-chip">
              时间 <strong>{meta.game_time || '—'}</strong>
            </span>
            {meta.era_name && (
              <span className="meta-chip">
                纪元 <strong>{meta.era_name}</strong>
              </span>
            )}
            {protagonist && (
              <span className="meta-chip">
                主角 <strong>{protagonist.name}</strong>
              </span>
            )}
          </div>
        </>
      )}

      <div className="topbar-spacer" />

      <div className="topbar-section">
        <button onClick={() => refreshAll()} title="刷新所有数据">
          ⟳ 刷新
        </button>
        <button className="menu-btn" onClick={() => setMenuOpen(true)}>
          ☰ 菜单
        </button>
      </div>

      {menuOpen && <MenuDrawer onClose={() => setMenuOpen(false)} />}
    </>
  );
}
