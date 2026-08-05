import { useState } from 'react';
import TopBar from '../components/TopBar';
import LeftPanel from '../components/LeftPanel';
import EventStreamPanel from '../components/EventStreamPanel';
import RightPanel from '../components/RightPanel';
import BottomBar from '../components/BottomBar';
import QuestAgendaPanel from '../components/QuestAgendaPanel';
import MapBrowser from '../components/map/MapBrowser';
import '../styles/GamePage.css';

type BottomSubTab = 'player' | 'quest';

export default function GamePage() {
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const [bottomSub, setBottomSub] = useState<BottomSubTab>('player');

  return (
    <div className="game-page">
      <div className="gp-topbar">
        <TopBar />
      </div>

      <button
        className={`gp-collapse gp-collapse-l ${leftOpen ? 'open' : 'closed'}`}
        onClick={() => setLeftOpen((v) => !v)}
        title={leftOpen ? '收起左栏' : '展开左栏'}
      >{leftOpen ? '◀' : '▶'}</button>

      <div className={`gp-left ${leftOpen ? '' : 'gp-collapsed'}`}>
        <LeftPanel />
      </div>

      <div className="gp-main">
        <EventStreamPanel />
      </div>

      <button
        className={`gp-collapse gp-collapse-r ${rightOpen ? 'open' : 'closed'}`}
        onClick={() => setRightOpen((v) => !v)}
        title={rightOpen ? '收起右栏' : '展开右栏'}
      >{rightOpen ? '▶' : '◀'}</button>

      <div className={`gp-right ${rightOpen ? '' : 'gp-collapsed'}`}>
        <RightPanel />
      </div>

      <div className="gp-bottom">
        <div className="gp-bottom-tabs">
          <button
            className={`gp-tab ${bottomSub === 'player' ? 'on' : ''}`}
            onClick={() => setBottomSub('player')}
          >🕹 玩家动作</button>
          <button
            className={`gp-tab ${bottomSub === 'quest' ? 'on' : ''}`}
            onClick={() => setBottomSub('quest')}
          >📋 任务 / 纲领</button>
        </div>
        <div className="gp-bottom-body">
          {bottomSub === 'player' ? (
            <div className="gp-bottom-player"><BottomBar /></div>
          ) : (
            <QuestAgendaPanel />
          )}
        </div>
      </div>

      <MapBrowser />
    </div>
  );
}
