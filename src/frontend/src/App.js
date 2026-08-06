import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useGameStore } from './store/gameStore';
import StartPage from './pages/StartPage';
import GamePage from './pages/GamePage';
import SavesPage from './pages/SavesPage';
import DramasPage from './pages/DramasPage';
import ModelPage from './pages/ModelPage';
import SettingsPage from './pages/SettingsPage';
import './App.css';
function App() {
    const error = useGameStore((s) => s.error);
    const notification = useGameStore((s) => s.notification);
    const setError = useGameStore((s) => s.setError);
    const setNotification = useGameStore((s) => s.setNotification);
    const refreshSaves = useGameStore((s) => s.refreshSaves);
    useEffect(() => {
        refreshSaves();
    }, [refreshSaves]);
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
    return (_jsx(BrowserRouter, { children: _jsxs("div", { className: "app", children: [_jsxs(Routes, { children: [_jsx(Route, { path: "/", element: _jsx(StartPage, {}) }), _jsx(Route, { path: "/saves", element: _jsx(SavesPage, {}) }), _jsx(Route, { path: "/dramas", element: _jsx(DramasPage, {}) }), _jsx(Route, { path: "/model", element: _jsx(ModelPage, {}) }), _jsx(Route, { path: "/settings", element: _jsx(SettingsPage, {}) }), _jsx(Route, { path: "/play", element: _jsx(GamePage, {}) }), _jsx(Route, { path: "*", element: _jsx(Navigate, { to: "/", replace: true }) })] }), error && (_jsxs("div", { className: "toast toast-error", onClick: () => setError(null), children: [_jsx("span", { className: "toast-icon", children: "\u26A0" }), _jsx("span", { className: "toast-msg", children: error })] })), notification && (_jsxs("div", { className: "toast toast-info", onClick: () => setNotification(null), children: [_jsx("span", { className: "toast-icon", children: "\u2713" }), _jsx("span", { className: "toast-msg", children: notification })] }))] }) }));
}
export default App;
