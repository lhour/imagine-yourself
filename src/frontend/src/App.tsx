import { useEffect } from 'react';
import { useGameStore } from './store/gameStore';
import StartPage from './pages/StartPage';
import GamePage from './pages/GamePage';
import './App.css';

export default function App() {
  const activeSave = useGameStore((s) => s.activeSave);
  const error = useGameStore((s) => s.error);
  const notification = useGameStore((s) => s.notification);
  const setError = useGameStore((s) => s.setError);
  const setNotification = useGameStore((s) => s.setNotification);
  const refreshSaves = useGameStore((s) => s.refreshSaves);

  useEffect(() => {
    refreshSaves();
  }, [refreshSaves]);

  // 错误/通知自动消失
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
    <div className="app">
      {activeSave ? <GamePage /> : <StartPage />}

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
  );
}
