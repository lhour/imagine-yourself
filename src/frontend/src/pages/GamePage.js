import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import TopBar from '../components/TopBar';
import LeftPanel from '../components/LeftPanel';
import EventStreamPanel from '../components/EventStreamPanel';
import RightPanel from '../components/RightPanel';
import BottomBar from '../components/BottomBar';
import QuestAgendaPanel from '../components/QuestAgendaPanel';
import MapBrowser from '../components/map/MapBrowser';
import '../styles/GamePage.css';
export default function GamePage() {
    const [bottomSub, setBottomSub] = useState('player');
    return (_jsxs("div", { className: "game-page", children: [_jsx("div", { className: "topbar", children: _jsx(TopBar, {}) }), _jsx("div", { className: "left", children: _jsx(LeftPanel, {}) }), _jsx("div", { className: "main", children: _jsx(EventStreamPanel, {}) }), _jsx("div", { className: "right", children: _jsx(RightPanel, {}) }), _jsxs("div", { className: "bottom", children: [_jsxs("div", { className: "gp-bottom-tabs", children: [_jsx("button", { className: `gp-tab ${bottomSub === 'player' ? 'on' : ''}`, onClick: () => setBottomSub('player'), children: "\uD83D\uDD79 \u73A9\u5BB6\u52A8\u4F5C" }), _jsx("button", { className: `gp-tab ${bottomSub === 'quest' ? 'on' : ''}`, onClick: () => setBottomSub('quest'), children: "\uD83D\uDCCB \u4EFB\u52A1 / \u7EB2\u9886" })] }), _jsx("div", { className: "gp-bottom-body", children: bottomSub === 'player' ? (_jsx("div", { className: "gp-bottom-player", children: _jsx(BottomBar, {}) })) : (_jsx(QuestAgendaPanel, {})) })] }), _jsx(MapBrowser, {})] }));
}
