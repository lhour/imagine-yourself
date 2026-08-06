import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useMemo, useState } from 'react';
import { entitiesApi } from '../api/client';
import '../styles/QuestAgendaPanel.css';
const QUEST_STATUS_COLOR = {
    open: '#3b82f6',
    in_progress: '#f59e0b',
    done: '#10b981',
    failed: '#ef4444',
    blocked: '#94a3b8',
};
const AGENDA_STATUS_COLOR = {
    active: '#10b981',
    blocked: '#f59e0b',
    completed: '#3b82f6',
    archived: '#94a3b8',
};
function NewQuestModal({ chars, onClose, onCreated, }) {
    const [form, setForm] = useState({
        char_id: chars[0]?.id ?? 0,
        title: '',
        desc_raw: '',
        quest_type: 'main',
        priority: 3,
        success_condition_raw: '',
        fail_condition_raw: '',
    });
    const [loading, setLoading] = useState(false);
    const submit = async (e) => {
        e.preventDefault();
        if (!form.title || !form.char_id)
            return;
        setLoading(true);
        try {
            await entitiesApi.create('character_quest', {
                ...form,
                status: 'open',
                start_tick: 0,
            });
            onCreated();
            onClose();
        }
        finally {
            setLoading(false);
        }
    };
    return (_jsx("div", { className: "modal-mask", onClick: onClose, children: _jsxs("div", { className: "modal-body", onClick: (e) => e.stopPropagation(), children: [_jsx("h3", { children: "\u65B0\u5EFA\u4EFB\u52A1" }), _jsxs("form", { onSubmit: submit, className: "modal-form", children: [_jsxs("label", { children: [_jsx("span", { children: "\u6240\u5C5E\u89D2\u8272" }), _jsx("select", { value: form.char_id, onChange: (e) => setForm({ ...form, char_id: Number(e.target.value) }), children: chars.map((c) => (_jsx("option", { value: c.id, children: c.name }, c.id))) })] }), _jsxs("label", { children: [_jsx("span", { children: "\u4EFB\u52A1\u6807\u9898" }), _jsx("input", { required: true, value: form.title, onChange: (e) => setForm({ ...form, title: e.target.value }), placeholder: "\u4F8B\uFF1A\u593A\u56DE\u5931\u843D\u7684\u5723\u7269" })] }), _jsxs("label", { children: [_jsx("span", { children: "\u7C7B\u578B" }), _jsxs("select", { value: form.quest_type, onChange: (e) => setForm({ ...form, quest_type: e.target.value }), children: [_jsx("option", { value: "main", children: "\u4E3B\u7EBF" }), _jsx("option", { value: "side", children: "\u652F\u7EBF" }), _jsx("option", { value: "character", children: "\u89D2\u8272" }), _jsx("option", { value: "world", children: "\u4E16\u754C" }), _jsx("option", { value: "daily", children: "\u65E5\u5E38" })] })] }), _jsxs("label", { children: [_jsx("span", { children: "\u4F18\u5148\u7EA7\uFF081~5\uFF09" }), _jsx("input", { type: "number", min: 1, max: 5, value: form.priority, onChange: (e) => setForm({ ...form, priority: Number(e.target.value) }) })] }), _jsxs("label", { children: [_jsx("span", { children: "\u4EFB\u52A1\u63CF\u8FF0\uFF08\u7ED3\u6784\u5316\uFF09" }), _jsx("textarea", { rows: 3, value: form.desc_raw, onChange: (e) => setForm({ ...form, desc_raw: e.target.value }), placeholder: "\u4E8B\u4EF6\u94FE\u5173\u952E\u8282\u70B9 + \u89E6\u53D1\u6761\u4EF6" })] }), _jsxs("div", { className: "row-2", children: [_jsxs("label", { children: [_jsx("span", { children: "\u6210\u529F\u6761\u4EF6" }), _jsx("textarea", { rows: 2, value: form.success_condition_raw, onChange: (e) => setForm({ ...form, success_condition_raw: e.target.value }) })] }), _jsxs("label", { children: [_jsx("span", { children: "\u5931\u8D25\u6761\u4EF6" }), _jsx("textarea", { rows: 2, value: form.fail_condition_raw, onChange: (e) => setForm({ ...form, fail_condition_raw: e.target.value }) })] })] }), _jsxs("div", { className: "modal-actions", children: [_jsx("button", { type: "button", onClick: onClose, children: "\u53D6\u6D88" }), _jsx("button", { type: "submit", disabled: loading, children: loading ? '创建中…' : '创建任务' })] })] })] }) }));
}
function NewAgendaModal({ chars, onClose, onCreated, }) {
    const [form, setForm] = useState({
        char_id: chars[0]?.id ?? 0,
        title: '',
        principle_raw: '',
        priority: 3,
    });
    const [loading, setLoading] = useState(false);
    const submit = async (e) => {
        e.preventDefault();
        if (!form.title || !form.principle_raw || !form.char_id)
            return;
        setLoading(true);
        try {
            await entitiesApi.create('character_agenda', {
                ...form,
                status: 'active',
                start_tick: 0,
            });
            onCreated();
            onClose();
        }
        finally {
            setLoading(false);
        }
    };
    return (_jsx("div", { className: "modal-mask", onClick: onClose, children: _jsxs("div", { className: "modal-body", onClick: (e) => e.stopPropagation(), children: [_jsx("h3", { children: "\u65B0\u5EFA\u7EB2\u9886" }), _jsxs("form", { onSubmit: submit, className: "modal-form", children: [_jsxs("label", { children: [_jsx("span", { children: "\u6240\u5C5E\u89D2\u8272" }), _jsx("select", { value: form.char_id, onChange: (e) => setForm({ ...form, char_id: Number(e.target.value) }), children: chars.map((c) => (_jsx("option", { value: c.id, children: c.name }, c.id))) })] }), _jsxs("label", { children: [_jsx("span", { children: "\u7EB2\u9886\u6807\u9898" }), _jsx("input", { required: true, value: form.title, onChange: (e) => setForm({ ...form, title: e.target.value }), placeholder: "\u4F8B\uFF1A\u7EDD\u4E0D\u80CC\u53DB\u5BB6\u65CF" })] }), _jsxs("label", { children: [_jsx("span", { children: "\u4F18\u5148\u7EA7\uFF081~5\uFF09" }), _jsx("input", { type: "number", min: 1, max: 5, value: form.priority, onChange: (e) => setForm({ ...form, priority: Number(e.target.value) }) })] }), _jsxs("label", { children: [_jsx("span", { children: "\u884C\u4E3A\u51C6\u5219\uFF08\u7ED3\u6784\u5316 raw\uFF09" }), _jsx("textarea", { rows: 4, required: true, value: form.principle_raw, onChange: (e) => setForm({ ...form, principle_raw: e.target.value }), placeholder: "\u89E6\u53D1\u573A\u666F\u3001\u4EE3\u4EF7\u3001\u8FDD\u80CC\u4F1A\u53D1\u751F\u4EC0\u4E48\u3001\u4F55\u65F6\u8BA9\u4F4D\u7ED9\u5176\u4ED6\u7EB2\u9886" })] }), _jsxs("div", { className: "modal-actions", children: [_jsx("button", { type: "button", onClick: onClose, children: "\u53D6\u6D88" }), _jsx("button", { type: "submit", disabled: loading, children: loading ? '创建中…' : '创建纲领' })] })] })] }) }));
}
export default function QuestAgendaPanel() {
    const [tab, setTab] = useState('quests');
    const [quests, setQuests] = useState([]);
    const [agendas, setAgendas] = useState([]);
    const [chars, setChars] = useState([]);
    const [showQuestModal, setShowQuestModal] = useState(false);
    const [showAgendaModal, setShowAgendaModal] = useState(false);
    const [filterChar, setFilterChar] = useState('all');
    const refresh = async () => {
        const [qs, ags, cs] = await Promise.all([
            entitiesApi.list('character_quest'),
            entitiesApi.list('character_agenda'),
            entitiesApi.list('character'),
        ]);
        setQuests(Array.isArray(qs) ? qs : []);
        setAgendas(Array.isArray(ags) ? ags : []);
        setChars(Array.isArray(cs) ? cs : []);
    };
    useEffect(() => { void refresh(); }, []);
    const charMap = useMemo(() => {
        const m = new Map();
        chars.forEach((c) => m.set(c.id, c));
        return m;
    }, [chars]);
    const qs = useMemo(() => quests.filter((q) => filterChar === 'all' || q.char_id === filterChar), [quests, filterChar]);
    const ags = useMemo(() => agendas.filter((a) => filterChar === 'all' || a.char_id === filterChar), [agendas, filterChar]);
    return (_jsxs("div", { className: "qa-panel", children: [_jsxs("div", { className: "qa-header", children: [_jsxs("div", { className: "qa-tabs", children: [_jsxs("button", { className: tab === 'quests' ? 'qa-tab qa-tab-active' : 'qa-tab', onClick: () => setTab('quests'), children: ["\u4EFB\u52A1 (", quests.length, ")"] }), _jsxs("button", { className: tab === 'agendas' ? 'qa-tab qa-tab-active' : 'qa-tab', onClick: () => setTab('agendas'), children: ["\u7EB2\u9886 (", agendas.length, ")"] })] }), _jsxs("select", { className: "qa-filter", value: filterChar, onChange: (e) => setFilterChar(e.target.value === 'all' ? 'all' : Number(e.target.value)), children: [_jsx("option", { value: "all", children: "\u5168\u90E8\u89D2\u8272" }), chars.map((c) => (_jsx("option", { value: c.id, children: c.name }, c.id)))] }), _jsx("div", { className: "qa-newbtns", children: tab === 'quests' ? (_jsx("button", { className: "qa-new", onClick: () => setShowQuestModal(true), children: "+ \u65B0\u5EFA\u4EFB\u52A1" })) : (_jsx("button", { className: "qa-new", onClick: () => setShowAgendaModal(true), children: "+ \u65B0\u5EFA\u7EB2\u9886" })) })] }), _jsxs("div", { className: "qa-list", children: [tab === 'quests' && qs.length === 0 && (_jsx("div", { className: "qa-empty", children: "\u6682\u65E0\u4EFB\u52A1\uFF1B\u70B9\u53F3\u4E0A\u89D2\"\u65B0\u5EFA\u4EFB\u52A1\"\u5F00\u59CB\u89C4\u5212\u3002" })), tab === 'quests' && qs.map((q) => (_jsxs("div", { className: `qa-card qa-card-status-${q.status}`, children: [_jsxs("div", { className: "qa-card-top", children: [_jsx("span", { className: "qa-dot", style: { background: QUEST_STATUS_COLOR[q.status] ?? '#aaa' } }), _jsx("span", { className: "qa-ctype", children: q.quest_type }), _jsx("span", { className: "qa-title", children: q.title }), _jsxs("span", { className: "qa-prio", children: ["P", q.priority] })] }), _jsxs("div", { className: "qa-card-meta", children: [_jsx("span", { className: "qa-char", children: charMap.get(q.char_id)?.name ?? `#${q.char_id}` }), _jsx("span", { className: "qa-status", children: q.status }), _jsxs("span", { className: "qa-tick", children: ["tick ", q.start_tick] })] }), _jsx("div", { className: "qa-card-body", children: q.desc_polished || q.desc_raw || '（未填写描述）' }), (q.success_condition_raw || q.fail_condition_raw || q.blocked_reason_raw) && (_jsxs("div", { className: "qa-card-cond", children: [q.success_condition_raw && (_jsxs("div", { children: [_jsx("b", { children: "\u6210\u529F\uFF1A" }), q.success_condition_raw] })), q.fail_condition_raw && (_jsxs("div", { children: [_jsx("b", { children: "\u5931\u8D25\uFF1A" }), q.fail_condition_raw] })), q.blocked_reason_raw && (_jsxs("div", { className: "qa-blocked", children: [_jsx("b", { children: "\u963B\u788D\uFF1A" }), q.blocked_reason_raw] }))] }))] }, q.id))), tab === 'agendas' && ags.length === 0 && (_jsx("div", { className: "qa-empty", children: "\u6682\u65E0\u7EB2\u9886\uFF1B\u70B9\u53F3\u4E0A\u89D2\"\u65B0\u5EFA\u7EB2\u9886\"\u5B9A\u4E49\u89D2\u8272\u7684\u957F\u671F\u884C\u4E3A\u51C6\u5219\u3002" })), tab === 'agendas' && ags.map((a) => (_jsxs("div", { className: `qa-card qa-card-agenda qa-card-status-${a.status}`, children: [_jsxs("div", { className: "qa-card-top", children: [_jsx("span", { className: "qa-dot", style: { background: AGENDA_STATUS_COLOR[a.status] ?? '#aaa' } }), _jsx("span", { className: "qa-title", children: a.title }), _jsxs("span", { className: "qa-prio", children: ["P", a.priority] })] }), _jsxs("div", { className: "qa-card-meta", children: [_jsx("span", { className: "qa-char", children: charMap.get(a.char_id)?.name ?? `#${a.char_id}` }), _jsx("span", { className: "qa-status", children: a.status })] }), _jsx("div", { className: "qa-card-body", children: a.principle_polished || a.principle_raw || '（未填写准则）' }), (a.conflict_with || a.blocked_reason_raw) && (_jsxs("div", { className: "qa-card-cond", children: [a.conflict_with && _jsxs("div", { children: [_jsx("b", { children: "\u51B2\u7A81\uFF1A" }), a.conflict_with] }), a.blocked_reason_raw && (_jsxs("div", { className: "qa-blocked", children: [_jsx("b", { children: "\u963B\u788D\uFF1A" }), a.blocked_reason_raw] }))] }))] }, a.id)))] }), showQuestModal && (_jsx(NewQuestModal, { chars: chars, onClose: () => setShowQuestModal(false), onCreated: refresh })), showAgendaModal && (_jsx(NewAgendaModal, { chars: chars, onClose: () => setShowAgendaModal(false), onCreated: refresh }))] }));
}
