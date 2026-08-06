import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useMemo, useState } from 'react';
import { useGameStore } from '../store/gameStore';
import { worldApi, entitiesApi } from '../api/client';
import '../styles/EventStreamPanel.css';
const EVENT_TYPE_LABELS = {
    discovery: '发现',
    appearance: '登场',
    perception: '感知',
    action: '行动',
    encounter: '遭遇',
    dialogue: '对话',
    combat: '战斗',
    quest: '任务',
    player_action: '玩家行动',
    narrative: '叙事',
    environment: '环境',
    objective: '客观',
    system: '系统',
    milestone: '里程碑',
};
function typeLabel(t) { return EVENT_TYPE_LABELS[t] ?? t; }
function groupByTick(events) {
    const groups = {};
    for (const e of events) {
        const t = e.tick_num;
        if (!groups[t])
            groups[t] = [];
        groups[t].push(e);
    }
    return groups;
}
function clsx(...xs) {
    return xs.filter(Boolean).join(' ');
}
// ===== Event detail modal =====
function EventDetailModal({ eventId, onClose }) {
    const [detail, setDetail] = useState(null);
    const [err, setErr] = useState(null);
    useEffect(() => {
        let active = true;
        worldApi.getEvent(eventId).then((r) => { if (active)
            setDetail(r); })
            .catch((e) => { if (active)
            setErr(e.message ?? '加载失败'); });
        return () => { active = false; };
    }, [eventId]);
    if (err) {
        return (_jsx("div", { className: "modal-mask", onClick: onClose, children: _jsxs("div", { className: "modal-body", onClick: (e) => e.stopPropagation(), children: [_jsx("h3", { children: "\u4E8B\u4EF6\u8BE6\u60C5\u52A0\u8F7D\u5931\u8D25" }), _jsx("p", { style: { color: '#b91c1c' }, children: err }), _jsx("div", { className: "modal-actions", children: _jsx("button", { onClick: onClose, children: "\u5173\u95ED" }) })] }) }));
    }
    if (!detail) {
        return (_jsx("div", { className: "modal-mask", onClick: onClose, children: _jsxs("div", { className: "modal-body", onClick: (e) => e.stopPropagation(), children: [_jsx("span", { className: "spinner" }), " \u52A0\u8F7D\u4E2D\u2026"] }) }));
    }
    return (_jsx("div", { className: "modal-mask", onClick: onClose, children: _jsxs("div", { className: "modal-body ev-detail", onClick: (e) => e.stopPropagation(), children: [_jsxs("div", { className: "ev-detail-header", children: [_jsxs("div", { children: [_jsx("span", { className: "event-type", children: typeLabel(detail.event_type) }), _jsx("span", { className: "event-stars", title: `重要性 ${detail.importance}/5`, children: '★'.repeat(Math.max(0, Math.min(5, detail.importance))) }), _jsxs("span", { className: "ev-title", children: ["#", detail.id, " \u00B7 Tick ", detail.tick_num] })] }), _jsx("button", { className: "close-x", onClick: onClose, children: "\u2715" })] }), _jsxs("div", { className: "ev-meta", children: [_jsxs("span", { children: ["\uD83D\uDD52 ", detail.game_time] }), detail.location_detail_raw && _jsxs("span", { children: ["\uD83D\uDCCD ", detail.location_detail_raw] }), detail.location_map_id != null && _jsxs("span", { children: ["\uD83D\uDDFA\uFE0F Map #", detail.location_map_id] })] }), _jsxs("div", { className: "ev-body", children: [_jsx("div", { className: "ev-polished", children: detail.content_polished || detail.content_raw }), detail.content_polished && detail.content_raw && detail.content_raw !== detail.content_polished && (_jsxs("details", { className: "ev-raw-det", children: [_jsx("summary", { children: "\u67E5\u770B\u7ED3\u6784\u5316\u539F\u6587" }), _jsx("pre", { children: detail.content_raw })] }))] }), _jsxs("div", { className: "ev-section", children: [_jsxs("h4", { children: ["\u53C2\u4E0E\u4EBA (", detail.participants?.length ?? 0, ")"] }), !detail.participants?.length ? _jsx("div", { className: "empty-sub", children: "\u65E0\u53C2\u4E0E\u4EBA" }) : (_jsx("div", { className: "ev-chips", children: detail.participants.map((p) => (_jsxs("span", { className: `chip chip-${p.participant_type}`, title: p.perception_raw ?? p.role_raw, children: [_jsx("b", { children: p.name }), " \u00B7 ", p.role_raw || p.participant_type] }, p.id))) }))] }), _jsxs("div", { className: "ev-2col", children: [_jsxs("div", { className: "ev-section", children: [_jsxs("h4", { children: ["\u88AB\u8C01\u8BB0\u5F97 (", detail.remembered_by?.length ?? 0, ")"] }), !detail.remembered_by?.length ? _jsx("div", { className: "empty-sub", children: "\u2014" }) : (_jsx("ul", { className: "ev-ul", children: detail.remembered_by.map((m, i) => (_jsxs("li", { title: `深度 ${m.depth} · 正确率 ${m.correctness.toFixed(2)}`, children: [_jsx("b", { children: m.char_name }), _jsxs("span", { className: "ev-sub", children: ["depth ", m.depth, " \u00B7 corr ", (m.correctness * 100).toFixed(0), "%"] })] }, i))) }))] }), _jsxs("div", { className: "ev-section", children: [_jsxs("h4", { children: ["\u5DF2\u9057\u5FD8 (", detail.forgotten_by?.length ?? 0, ")"] }), !detail.forgotten_by?.length ? _jsx("div", { className: "empty-sub", children: "\u2014" }) : (_jsx("ul", { className: "ev-ul", children: detail.forgotten_by.map((m, i) => (_jsxs("li", { className: "forgotten", title: `遗忘概率 ${(m.forget_prob * 100).toFixed(0)}%`, children: [_jsx("b", { children: m.char_name }), _jsxs("span", { className: "ev-sub", children: ["forget ", (m.forget_prob * 100).toFixed(0), "%"] })] }, i))) }))] })] }), detail.linked_memories?.length ? (_jsxs("div", { className: "ev-section", children: [_jsxs("h4", { children: ["\u5173\u8054\u8BB0\u5FC6 (", detail.linked_memories.length, ")"] }), _jsx("div", { className: "ev-memories", children: detail.linked_memories.map((m) => (_jsxs("div", { className: "ev-memory", children: [_jsxs("div", { className: "ev-memory-head", children: [_jsx("span", { className: "mem-char", children: m.char_name }), _jsxs("span", { className: "mem-depth", children: ["\u6DF1\u5EA6 ", m.depth] }), _jsx("span", { className: m.is_false ? 'mem-false' : 'mem-true', children: m.is_false ? '虚假' : '真实' })] }), _jsx("div", { className: "ev-memory-body", children: m.memory_polished || m.memory_raw })] }, m.id))) })] })) : null] }) }));
}
// ===== Event card =====
function EventCard({ event, showRaw, highlightChars, onOpen, }) {
    const importance = Math.max(0, Math.min(5, event.importance ?? 3));
    const charParticipants = (event.participants ?? []).filter((p) => p.participant_type === 'character');
    const highlighted = charParticipants.length === 0
        ? false
        : highlightChars.size === 0
            ? false
            : charParticipants.some((p) => highlightChars.has(p.participant_id));
    const anyParticipants = (event.participants ?? []).length > 0;
    const rememberedTooltip = useMemo(() => {
        const r = (event.remembered_by ?? []).slice(0, 8).map((m) => `✓ ${m.char_name}`).join('\n');
        const f = (event.forgotten_by ?? []).slice(0, 8).map((m) => `✗ ${m.char_name}`).join('\n');
        if (!r && !f)
            return '';
        return ['【记得】', r, '【遗忘】', f].filter(Boolean).join('\n');
    }, [event]);
    return (_jsxs("div", { className: clsx(`event-card importance-${importance}`, highlighted && 'ev-highlighted'), onClick: () => onOpen(event.id), title: rememberedTooltip || undefined, children: [_jsxs("div", { className: "event-header", children: [_jsx("span", { className: "event-type", children: typeLabel(event.event_type) }), _jsxs("span", { className: "event-meta", children: [event.location_detail_raw && _jsxs("span", { className: "event-location", children: ["\uD83D\uDCCD ", event.location_detail_raw] }), _jsxs("span", { className: "event-stars", title: `重要性 ${importance}/5`, children: ['★'.repeat(importance), '☆'.repeat(5 - importance)] }), _jsxs("span", { className: "event-time", children: ["#", event.id] })] })] }), _jsx("div", { className: "event-content", children: event.content_polished || event.content_raw || '（空事件）' }), showRaw && event.content_raw && (_jsxs("div", { className: "event-raw", children: ["\u539F\u6587\uFF1A", event.content_raw] })), anyParticipants && (_jsxs("div", { className: "event-chips-row", children: [(event.participants ?? []).slice(0, 10).map((p) => (_jsx("span", { className: clsx('chip chip-mini', `chip-${p.participant_type}`, p.participant_type === 'character' && highlightChars.has(p.participant_id) && 'chip-focus'), title: p.perception_raw || p.role_raw || '', children: p.name }, p.id))), (event.participants ?? []).length > 10 && (_jsxs("span", { className: "chip chip-mini chip-more", children: ["+", (event.participants ?? []).length - 10] })), (event.remembered_by?.length ?? 0) + (event.forgotten_by?.length ?? 0) > 0 && (_jsxs("span", { className: "chip chip-mini chip-memory", title: rememberedTooltip || undefined, children: ["\u8BB0 ", event.remembered_by?.length ?? 0, " / \u5FD8 ", event.forgotten_by?.length ?? 0] }))] }))] }));
}
// ===== Main panel =====
export default function EventStreamPanel() {
    const events = useGameStore((s) => s.events);
    const loading = useGameStore((s) => s.eventsLoading);
    const filter = useGameStore((s) => s.eventsFilter);
    const setFilter = useGameStore((s) => s.setEventsFilter);
    const meta = useGameStore((s) => s.meta);
    const [chars, setChars] = useState([]);
    const [openEventId, setOpenEventId] = useState(null);
    const refresh = useGameStore((s) => s.refreshEvents);
    useEffect(() => {
        (async () => {
            try {
                const list = await entitiesApi.list('character');
                setChars(Array.isArray(list) ? list : []);
            }
            catch { /* ignore */ }
        })();
    }, []);
    const allChars = useMemo(() => chars.sort((a, b) => b.importance - a.importance), [chars]);
    // char focus → multi-select chips
    const selectedCharIds = useMemo(() => {
        const ids = filter.charIds ?? [];
        return new Set(typeof ids === 'string' ? ids.split(',').map(Number).filter((n) => !isNaN(n)) : ids);
    }, [filter.charIds]);
    const toggleChar = (id) => {
        const next = new Set(selectedCharIds);
        if (next.has(id))
            next.delete(id);
        else
            next.add(id);
        const idsStr = Array.from(next).sort((a, b) => a - b).join(',');
        setFilter({ charIds: idsStr || null });
    };
    const filtered = useMemo(() => {
        let arr = events;
        if (selectedCharIds.size > 0) {
            arr = arr.filter((e) => (e.participants ?? []).some((p) => p.participant_type === 'character' && selectedCharIds.has(p.participant_id)));
        }
        return arr;
    }, [events, selectedCharIds]);
    const tickGroups = useMemo(() => groupByTick(filtered), [filtered]);
    const tickKeys = Object.keys(tickGroups).map(Number).sort((a, b) => b - a);
    const hasFilter = selectedCharIds.size > 0;
    const clearFilter = () => setFilter({ charIds: null });
    return (_jsxs("div", { className: "event-panel", children: [_jsxs("div", { className: "event-filter-bar", children: [_jsx("span", { className: "filter-label", children: "\u7B5B\u9009" }), _jsxs("label", { className: "filter-field check", children: [_jsx("input", { type: "checkbox", checked: filter.showRaw, onChange: (e) => setFilter({ showRaw: e.target.checked }) }), "\u539F\u6587"] }), hasFilter && (_jsx("button", { className: "filter-reset", onClick: clearFilter, children: "\u2715 \u91CD\u7F6E" })), _jsxs("div", { className: "filter-summary", children: [_jsxs("span", { children: [filtered.length, " / ", events.length, " \u6761"] }), _jsxs("span", { className: "tick-now", children: ["\u5F53\u524D Tick ", _jsx("b", { children: meta?.tick_num ?? '—' })] })] }), _jsx("button", { className: "btn-ghost", onClick: () => void refresh(), children: "\u27F3 \u5237\u65B0" })] }), allChars.length > 0 && (_jsxs("div", { className: "ev-char-focus", children: [_jsx("span", { className: "filter-sub", children: "\u89D2\u8272\u805A\u7126\uFF08\u9AD8\u4EAE\u5E76\u8FC7\u6EE4\uFF09" }), _jsxs("div", { className: "filter-chips", children: [_jsx("button", { className: clsx('chip chip-btn chip-character', selectedCharIds.size === 0 && 'chip-btn-on'), onClick: () => setFilter({ charIds: null }), children: "\u5168\u90E8" }), allChars.slice(0, 24).map((c) => (_jsx("button", { className: clsx('chip chip-btn chip-character', selectedCharIds.has(c.id) && 'chip-btn-on'), onClick: () => toggleChar(c.id), title: `${c.name} · 重要性 ${c.importance}`, children: c.name }, c.id))), allChars.length > 24 && _jsxs("span", { className: "chip chip-more", children: ["+", allChars.length - 24] })] })] })), _jsx("div", { className: "event-stream", children: loading && events.length === 0 ? (_jsxs("div", { className: "event-stream-empty", children: [_jsx("span", { className: "spinner" }), " \u6B63\u5728\u52A0\u8F7D\u4E8B\u4EF6\u2026"] })) : events.length === 0 ? (_jsxs("div", { className: "event-stream-empty", children: [_jsx("div", { className: "empty-icon", children: "\uD83D\uDCDC" }), _jsx("p", { children: "\u5C1A\u65E0\u4E8B\u4EF6" }), _jsx("p", { className: "empty-hint", children: "\u70B9\u51FB\u5E95\u90E8\u300C\u23ED \u4E0B\u4E00 Tick\u300D\u5F00\u59CB\u63A8\u8FDB\u5267\u60C5\u3002" })] })) : filtered.length === 0 ? (_jsxs("div", { className: "event-stream-empty", children: [_jsx("p", { children: "\u6CA1\u6709\u7B26\u5408\u7B5B\u9009\u6761\u4EF6\u7684\u4E8B\u4EF6" }), _jsx("button", { className: "btn-secondary", onClick: clearFilter, children: "\u6E05\u9664\u7B5B\u9009" })] })) : (tickKeys.map((tick) => (_jsxs("div", { className: "tick-group", children: [_jsxs("div", { className: "tick-group-header", children: [_jsx("span", { className: `tick-badge ${tick <= 0 ? 'prologue' : ''}`, children: tick <= 0 ? '序幕' : `Tick ${tick}` }), tick <= 0 && _jsx("span", { className: "tick-prologue-tag", children: "\u5F00\u573A\u94FA\u57AB" }), _jsx("span", { className: "tick-time", children: tickGroups[tick][0]?.game_time ?? '' }), _jsxs("span", { className: "tick-count", children: [tickGroups[tick].length, " \u4E2A\u4E8B\u4EF6"] })] }), tickGroups[tick].map((e) => (_jsx(EventCard, { event: e, showRaw: filter.showRaw, highlightChars: selectedCharIds, onOpen: (id) => setOpenEventId(id) }, e.id)))] }, tick)))) }), openEventId != null && (_jsx(EventDetailModal, { eventId: openEventId, onClose: () => setOpenEventId(null) }))] }));
}
