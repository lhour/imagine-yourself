import TopBar from '../components/TopBar';
import LeftPanel from '../components/LeftPanel';
import EventStreamPanel from '../components/EventStreamPanel';
import RightPanel from '../components/RightPanel';
import BottomBar from '../components/BottomBar';
import MapBrowser from '../components/map/MapBrowser';

export default function GamePage() {
  return (
    <div className="game-page">
      <div className="topbar"><TopBar /></div>
      <div className="left"><LeftPanel /></div>
      <div className="main"><EventStreamPanel /></div>
      <div className="right"><RightPanel /></div>
      <div className="bottom"><BottomBar /></div>
      <MapBrowser />
    </div>
  );
}
