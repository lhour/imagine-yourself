import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import { useGameStore } from '../store/gameStore';
import { memoryApi, entitiesApi } from '../api/client';
const TABS = [
    { key: 'characters', label: '角色', icon: '🧍' },
    { key: 'groups', label: '群体', icon: '👥' },
    { key: 'items', label: '物品', icon: '🎒' },
    { key: 'maps', label: '地图', icon: '🗺' },
    { key: 'memory', label: '记忆', icon: '🧠' },
];
function importanceDots(n) {
    const v = Math.max(0, Math.min(5, n));
    return '★'.repeat(v) + '☆'.repeat(5 - v);
}
export default function RightPanel() {
    const rightTab = useGameStore((s) => s.rightTab);
    const setRightTab = useGameStore((s) => s.setRightTab);
    const characters = useGameStore((s) => s.characters);
    const groups = useGameStore((s) => s.groups);
    const items = useGameStore((s) => s.items);
    const maps = useGameStore((s) => s.maps);
    const openMapBrowser = useGameStore((s) => s.openMapBrowser);
    const refreshCharacters = useGameStore((s) => s.refreshCharacters);
    const refreshGroups = useGameStore((s) => s.refreshGroups);
    const refreshItems = useGameStore((s) => s.refreshItems);
    const refreshMaps = useGameStore((s) => s.refreshMaps);
    const [profileCharId, setProfileCharId] = useState(null);
    return (_jsxs("div", { className: "right-panel", children: [_jsx("div", { className: "tab-bar", children: TABS.map((t) => (_jsxs("button", { className: `tab-btn ${rightTab === t.key ? 'active' : ''}`, onClick: () => setRightTab(t.key), children: [_jsx("span", { children: t.icon }), _jsx("span", { children: t.label })] }, t.key))) }), _jsxs("div", { className: "tab-content", children: [rightTab === 'characters' && (_jsx(CharacterTab, { chars: characters, onRefresh: refreshCharacters, onOpen: setProfileCharId })), rightTab === 'groups' && (_jsx(GroupTab, { groups: groups, onRefresh: refreshGroups })), rightTab === 'items' && _jsx(ItemTab, { items: items, onRefresh: refreshItems }), rightTab === 'maps' && (_jsx(MapTab, { maps: maps, onRefresh: refreshMaps, onOpen: openMapBrowser })), rightTab === 'memory' && _jsx(MemoryTab, { onOpen: setProfileCharId })] }), profileCharId != null && (_jsx(CharacterProfileModal, { charId: profileCharId, onClose: () => setProfileCharId(null) }))] }));
}
// ============================================================
// 角色
// ============================================================
function CharacterTab({ chars, onRefresh, onOpen }) {
    if (!Array.isArray(chars) || chars.length === 0) {
        return _jsx(EmptyHint, { text: "\u5C1A\u65E0\u89D2\u8272", onRefresh: onRefresh });
    }
    return (_jsx(_Fragment, { children: chars.map((c) => (_jsxs("div", { className: "entity-card clickable", onClick: () => onOpen(c.id), children: [_jsxs("div", { className: "entity-name", children: [c.name, _jsx("span", { className: "importance-dots small", children: importanceDots(c.importance) })] }), _jsxs("div", { className: "entity-desc", children: [c.gender ?? '—', " \u00B7 ", c.age != null ? `${c.age}岁` : '—', c.status ? ` · ${c.status}` : ''] }), c.appearance_polished && (_jsxs("div", { className: "entity-desc", children: [c.appearance_polished.slice(0, 40), "\u2026"] }))] }, c.id))) }));
}
// ============================================================
// 群体
// ============================================================
function GroupTab({ groups, onRefresh }) {
    if (!Array.isArray(groups) || groups.length === 0) {
        return _jsx(EmptyHint, { text: "\u5C1A\u65E0\u7FA4\u4F53", onRefresh: onRefresh });
    }
    return (_jsx(_Fragment, { children: groups.map((g) => (_jsxs("div", { className: "entity-card", children: [_jsxs("div", { className: "entity-name", children: [g.name, _jsx("span", { className: "importance-dots small", children: importanceDots(g.importance) })] }), _jsxs("div", { className: "entity-desc", children: [g.group_type, g.heatmap_grid ? ' · 有热力图' : ' · 点状分布'] }), g.desc_polished && (_jsxs("div", { className: "entity-desc", children: [g.desc_polished.slice(0, 40), "\u2026"] }))] }, g.id))) }));
}
// ============================================================
// 物品
// ============================================================
function ItemTab({ items, onRefresh }) {
    if (!Array.isArray(items) || items.length === 0) {
        return _jsx(EmptyHint, { text: "\u5C1A\u65E0\u7269\u54C1", onRefresh: onRefresh });
    }
    return (_jsx(_Fragment, { children: items.map((it) => (_jsxs("div", { className: "entity-card", children: [_jsxs("div", { className: "entity-name", children: [it.name, _jsx("span", { className: "importance-dots small", children: importanceDots(it.importance) })] }), _jsxs("div", { className: "entity-desc", children: [it.item_type, " \u00B7 \u7A00\u6709\u5EA6 ", it.rarity, it.is_stackable ? ` · 堆叠×${it.stack_size}` : ''] })] }, it.id))) }));
}
// ============================================================
// 地图
// ============================================================
function MapTab({ maps, onRefresh, onOpen, }) {
    if (!Array.isArray(maps) || maps.length === 0) {
        return _jsx(EmptyHint, { text: "\u5C1A\u65E0\u5730\u56FE", onRefresh: onRefresh });
    }
    // 按 parent_map_id 组织成树
    const roots = maps.filter((m) => m.parent_map_id == null);
    const childrenOf = (pid) => maps.filter((m) => m.parent_map_id === pid);
    const renderNode = (m, depth) => {
        const kids = childrenOf(m.id);
        return (_jsxs("div", { style: { marginLeft: depth * 12 }, children: [_jsxs("div", { className: "entity-card", onClick: () => onOpen(m.id), children: [_jsxs("div", { className: "entity-name", children: [m.name, m.is_mobile ? _jsx("span", { className: "small muted", children: " (\u79FB\u52A8)" }) : null] }), _jsxs("div", { className: "entity-desc", children: [m.map_type, " \u00B7 ", m.coord_system, kids.length ? ` · ${kids.length} 子地图` : ''] })] }), kids.map((k) => renderNode(k, depth + 1))] }, m.id));
    };
    return _jsx(_Fragment, { children: roots.map((r) => renderNode(r, 0)) });
}
function MemoryTab({ onOpen }) {
    const protagonist = useGameStore((s) => s.protagonist);
    const [memories, setMemories] = useState([]);
    const [impressions, setImpressions] = useState([]);
    const [loading, setLoading] = useState(false);
    const load = async () => {
        if (!protagonist)
            return;
        setLoading(true);
        try {
            const r = await memoryApi.retrieve(protagonist.id, { max_count: 30, expand_palace: true });
            setMemories(Array.isArray(r?.memories) ? r.memories : []);
            setImpressions(Array.isArray(r?.outline) ? r.outline : []);
        }
        catch { /* ignore */ }
        finally {
            setLoading(false);
        }
    };
    useEffect(() => { void load(); }, [protagonist?.id]);
    if (!protagonist) {
        return _jsx("div", { className: "entity-card entity-desc", children: "\u5C1A\u672A\u8BBE\u5B9A\u4E3B\u89D2\uFF0C\u65E0\u6CD5\u67E5\u770B\u8BB0\u5FC6\u3002" });
    }
    return (_jsxs("div", { className: "memory-panel", children: [_jsxs("div", { className: "entity-card entity-desc", children: ["\u4E3B\u89D2 ", _jsx("strong", { children: protagonist.name }), " \u7684\u8BB0\u5FC6", _jsx("button", { className: "small", style: { marginLeft: 8 }, onClick: () => void load(), children: "\u27F3 \u5237\u65B0" })] }), loading && _jsx("div", { className: "entity-desc", children: "\u52A0\u8F7D\u4E2D\u2026" }), impressions.length > 0 && (_jsxs("div", { className: "mem-section", children: [_jsxs("div", { className: "mem-title", children: ["\u89D2\u8272\u5370\u8C61\uFF08", impressions.length, "\uFF09"] }), impressions.map((im, i) => (_jsxs("div", { className: "entity-card clickable", onClick: () => onOpen(im.target_char_id), children: [_jsx("div", { className: "entity-name", children: im.target_name || `#${im.target_char_id}` }), _jsx("div", { className: "entity-desc", children: im.impression_polished || '—' }), _jsxs("div", { className: "entity-desc small muted", children: ["\u597D\u611F ", im.favorability ?? '—', " \u00B7 \u4FE1\u4EFB ", im.trust ?? '—', " \u00B7 \u6050\u60E7 ", im.fear ?? '—'] })] }, i)))] })), _jsxs("div", { className: "mem-section", children: [_jsxs("div", { className: "mem-title", children: ["\u8BB0\u5FC6\uFF08", memories.length, "\uFF09"] }), memories.length === 0 ? (_jsx("div", { className: "entity-desc", children: "\u6682\u65E0\u8BB0\u5FC6\u3002\u63A8\u8FDB tick \u540E\u89D2\u8272\u4F1A\u7D2F\u79EF\u8BB0\u5FC6\u3002" })) : (memories.map((m) => (_jsxs("div", { className: "entity-card", children: [_jsxs("div", { className: "entity-name", children: [m.is_false ? '⚠ 虚假记忆' : '记忆', _jsxs("span", { className: "importance-dots small", children: ["\u6DF1\u5EA6 ", m.depth] })] }), _jsx("div", { className: "entity-desc", children: m.memory_polished || m.memory_raw }), _jsxs("div", { className: "entity-desc small muted", children: ["\u6B63\u786E\u7387 ", m.correctness ?? '—', "%", m.remember_tick != null ? ` · Tick ${m.remember_tick}` : ''] })] }, m.id))))] })] }));
}
function CharacterProfileModal({ charId, onClose }) {
    const [profile, setProfile] = useState(null);
    const [err, setErr] = useState(null);
    useEffect(() => {
        let active = true;
        entitiesApi.characterProfile(charId)
            .then((r) => { if (active)
            setProfile(r); })
            .catch((e) => { if (active)
            setErr(e.message ?? '加载失败'); });
        return () => { active = false; };
    }, [charId]);
    const ch = profile?.character;
    return (_jsx("div", { className: "modal-mask", onClick: onClose, children: _jsxs("div", { className: "modal-body profile-drawer", onClick: (e) => e.stopPropagation(), children: [_jsxs("div", { className: "profile-head", children: [_jsxs("div", { children: [_jsx("h3", { children: ch?.name || `角色 #${charId}` }), _jsxs("div", { className: "entity-desc", children: [ch?.gender ?? '—', " \u00B7 ", ch?.age != null ? `${ch.age}岁` : '—', ch?.status ? ` · ${ch.status}` : ''] })] }), _jsx("button", { className: "close-x", onClick: onClose, children: "\u2715" })] }), err && _jsx("p", { style: { color: '#b91c1c' }, children: err }), !profile && !err && _jsxs("div", { className: "entity-desc", children: [_jsx("span", { className: "spinner" }), " \u52A0\u8F7D\u4E2D\u2026"] }), profile && (_jsxs("div", { className: "profile-body", children: [ch?.appearance_polished && (_jsxs("div", { className: "profile-sec", children: [_jsx("div", { className: "prof-sec-title", children: "\u5916\u8C8C" }), _jsx("div", { className: "entity-desc", children: ch.appearance_polished })] })), ch?.personality_polished && (_jsxs("div", { className: "profile-sec", children: [_jsx("div", { className: "prof-sec-title", children: "\u6027\u683C" }), _jsx("div", { className: "entity-desc", children: ch.personality_polished })] })), _jsxs("div", { className: "profile-sec", children: [_jsxs("div", { className: "prof-sec-title", children: ["\u89D2\u8272\u5370\u8C61\uFF08", profile.impressions.length, "\uFF09"] }), profile.impressions.length === 0 ? _jsx("div", { className: "entity-desc muted", children: "\u2014" }) :
                                    profile.impressions.map((im, i) => (_jsxs("div", { className: "entity-card", children: [_jsx("div", { className: "entity-name", children: im.target_name || `#${im.target_char_id}` }), _jsx("div", { className: "entity-desc", children: im.impression_polished || '—' })] }, i)))] }), _jsxs("div", { className: "profile-sec", children: [_jsxs("div", { className: "prof-sec-title", children: ["\u8BB0\u5FC6\uFF08", profile.memories.length, "\uFF09"] }), profile.memories.length === 0 ? _jsx("div", { className: "entity-desc muted", children: "\u2014" }) :
                                    profile.memories.slice(0, 20).map((m) => (_jsxs("div", { className: "entity-card", children: [_jsx("div", { className: "entity-desc", children: m.memory_polished || m.memory_raw }), _jsxs("div", { className: "entity-desc small muted", children: ["\u6DF1\u5EA6 ", m.depth, " \u00B7 \u6B63\u786E\u7387 ", m.correctness, "%"] })] }, m.id)))] }), _jsxs("div", { className: "profile-sec", children: [_jsxs("div", { className: "prof-sec-title", children: ["\u4EFB\u52A1\uFF08", profile.quests.length, "\uFF09"] }), profile.quests.length === 0 ? _jsx("div", { className: "entity-desc muted", children: "\u2014" }) :
                                    profile.quests.map((q) => (_jsxs("div", { className: "entity-card", children: [_jsxs("div", { className: "entity-name", children: [q.title, " ", _jsxs("span", { className: "small muted", children: ["[", q.status, "]"] })] }), _jsx("div", { className: "entity-desc", children: q.desc_polished || '—' })] }, q.id)))] }), _jsxs("div", { className: "profile-sec", children: [_jsxs("div", { className: "prof-sec-title", children: ["\u7EB2\u9886\uFF08", profile.agendas.length, "\uFF09"] }), profile.agendas.length === 0 ? _jsx("div", { className: "entity-desc muted", children: "\u2014" }) :
                                    profile.agendas.map((a) => (_jsxs("div", { className: "entity-card", children: [_jsxs("div", { className: "entity-name", children: [a.title, " ", _jsxs("span", { className: "small muted", children: ["[", a.status, "]"] })] }), _jsx("div", { className: "entity-desc", children: a.principle_polished || '—' })] }, a.id)))] }), _jsxs("div", { className: "profile-sec", children: [_jsxs("div", { className: "prof-sec-title", children: ["\u7FA4\u4F53\u5173\u7CFB\uFF08", profile.groups.length, "\uFF09"] }), profile.groups.length === 0 ? _jsx("div", { className: "entity-desc muted", children: "\u2014" }) :
                                    profile.groups.map((g, i) => (_jsxs("div", { className: "entity-card", children: [_jsx("div", { className: "entity-name", children: g.group_name || `#${g.group_id}` }), _jsxs("div", { className: "entity-desc", children: ["\u8EAB\u4EFD ", g.role_raw || '—', " \u00B7 \u91CD\u8981\u6027 ", g.importance_in_group ?? '—'] })] }, i)))] }), _jsxs("div", { className: "profile-sec", children: [_jsxs("div", { className: "prof-sec-title", children: ["\u6700\u8FD1\u53C2\u4E0E\u4E8B\u4EF6\uFF08", profile.recent_events.length, "\uFF09"] }), profile.recent_events.length === 0 ? _jsx("div", { className: "entity-desc muted", children: "\u2014" }) :
                                    profile.recent_events.slice(0, 15).map((e) => (_jsxs("div", { className: "entity-card", children: [_jsxs("div", { className: "entity-desc", children: ["Tick ", e.tick_num, " \u00B7 ", e.event_type] }), _jsx("div", { className: "entity-desc", children: e.content_polished || '—' })] }, e.event_id)))] })] }))] }) }));
}
// ============================================================
// 空状态提示
// ============================================================
function EmptyHint({ text, onRefresh }) {
    return (_jsxs("div", { className: "event-stream-empty", style: { height: 'auto', padding: '24px 8px' }, children: [_jsx("div", { style: { marginBottom: 8 }, children: text }), _jsx("button", { className: "small", onClick: onRefresh, children: "\u27F3 \u5237\u65B0" })] }));
}
