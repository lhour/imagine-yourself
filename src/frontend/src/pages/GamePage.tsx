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
  const [bottomSub, setBottomSub] = useState<BottomSubTab>('player');

  return (
    <div className="game-page">
      <div className="topbar">
        <TopBar />
      </div>

      <div className="left">
        <LeftPanel />
      </div>

      <div className="main">
        <EventStreamPanel />
      </div>

      <div className="right">
        <RightPanel />
      </div>

      <div className="bottom">
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
