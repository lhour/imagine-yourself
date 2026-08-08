import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useGameStore } from './store/gameStore';
import StartPage from './pages/StartPage';
import GamePage from './pages/GamePage';
import SavesPage from './pages/SavesPage';
import DramasPage from './pages/DramasPage';
import ModelPage from './pages/ModelPage';
import SettingsPage from './pages/SettingsPage';
import RequestLogPage from './pages/RequestLogPage';
import GameplayOptionsPage from './pages/GameplayOptionsPage';
import OperationLogPage from './pages/OperationLogPage';
import KnowledgePage from './pages/KnowledgePage';
import WorldSchedulePage from './pages/WorldSchedulePage';
import './App.css';
import './pages/GameplayOptionsPage.css';
import './pages/OperationLogPage.css';
import './pages/KnowledgePage.css';

function App() {
  const error = useGameStore((s) => s.error);
  const notification = useGameStore((s) => s.notification);
  const setError = useGameStore((s) => s.setError);
  const setNotification = useGameStore((s) => s.setNotification);
  const refreshSaves = useGameStore((s) => s.refreshSaves);
  const checkActiveSave = useGameStore((s) => s.checkActiveSave);

  useEffect(() => {
    refreshSaves();
    // 后端重启后会自动恢复活跃存档，前端启动时同步状态
    void checkActiveSave();
  }, [refreshSaves, checkActiveSave]);

  useEffect(() => {
    if (error) {
      const t = setTimeout(() => setError(null), 5000);
      return () => clearTimeout(t);
    }
  }, [error, setError]);

  useEffect(() => {
    if (notification) {
      const t = setTimeout(() => setNotification(null), 3000);
      return () => clearTimeout(t);
    }
  }, [notification, setNotification]);

  return (
    <BrowserRouter>
      <div className="app">
        <Routes>
          <Route path="/" element={<StartPage />} />
          <Route path="/saves" element={<SavesPage />} />
          <Route path="/dramas" element={<DramasPage />} />
          <Route path="/model" element={<ModelPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/traces" element={<RequestLogPage />} />
          <Route path="/trace" element={<Navigate to="/traces" replace />} />
          <Route path="/gameplay" element={<GameplayOptionsPage />} />
          <Route path="/world-schedule" element={<WorldSchedulePage />} />
          <Route path="/operations" element={<OperationLogPage />} />
          <Route path="/knowledge" element={<KnowledgePage />} />
          <Route path="/play" element={<GamePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>

        {error && (
          <div className="toast toast-error" onClick={() => setError(null)}>
            <span className="toast-icon">⚠</span>
            <span className="toast-msg">{error}</span>
          </div>
        )}
        {notification && (
          <div className="toast toast-info" onClick={() => setNotification(null)}>
            <span className="toast-icon">✓</span>
            <span className="toast-msg">{notification}</span>
          </div>
        )}
      </div>
    </BrowserRouter>
  );
}

export default App;
