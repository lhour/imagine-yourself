import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import AdminNav from '../components/AdminNav';
import { agentApi } from '../api/client';
import { useGameStore } from '../store/gameStore';
function NewVersionModal({ title, existing, onClose, onCreate, }) {
    const [newVersion, setNewVersion] = useState('');
    const [fromVersion, setFromVersion] = useState(existing[0] ?? '');
    const submit = (e) => {
        e.preventDefault();
        if (!newVersion.trim())
            return;
        onCreate({ new_version: newVersion.trim(), from_version: fromVersion });
    };
    return (_jsx("div", { className: "modal-overlay", onClick: onClose, children: _jsxs("div", { className: "modal-card", onClick: (e) => e.stopPropagation(), children: [_jsx("h3", { children: title }), _jsxs("form", { onSubmit: submit, style: { display: 'flex', flexDirection: 'column', gap: 10 }, children: [_jsxs("label", { className: "form-group", style: { marginBottom: 0 }, children: [_jsx("span", { children: "\u65B0\u7248\u672C\u53F7" }), _jsx("input", { required: true, placeholder: "\u4F8B\uFF1A1.2.0 / alpha / hotfix-char", value: newVersion, onChange: (e) => setNewVersion(e.target.value) })] }), _jsxs("label", { className: "form-group", style: { marginBottom: 0 }, children: [_jsx("span", { children: "\u57FA\u4E8E\u54EA\u4E2A\u7248\u672C\uFF08\u7559\u7A7A\u5219\u65B0\u5EFA\u7A7A\u7248\u672C\uFF09" }), _jsxs("select", { value: fromVersion, onChange: (e) => setFromVersion(e.target.value), children: [_jsx("option", { value: "", children: "\uFF08\u65B0\u5EFA\u7A7A\u7248\u672C\uFF09" }), existing.map((v) => (_jsx("option", { value: v, children: v }, v)))] })] }), _jsxs("div", { className: "modal-actions", children: [_jsx("button", { type: "button", className: "btn-secondary", onClick: onClose, children: "\u53D6\u6D88" }), _jsx("button", { type: "submit", className: "btn-primary", children: "\u521B\u5EFA\u65B0\u7248\u672C" })] })] })] }) }));
}
export default function ModelPage() {
    const setNotification = useGameStore((s) => s.setNotification);
    const setError = useGameStore((s) => s.setError);
    const [tab, setTab] = useState('prompts');
    const [skills, setSkills] = useState([]);
    const [selectedSkill, setSelectedSkill] = useState(null);
    const [skillVersions, setSkillVersions] = useState([]);
    const [selectedSkillVersion, setSelectedSkillVersion] = useState(null);
    const [skillVersionDetail, setSkillVersionDetail] = useState(null);
    const [skillDraft, setSkillDraft] = useState({ skill_md: '' });
    const [skillDirty, setSkillDirty] = useState(false);
    const [prompts, setPrompts] = useState([]);
    const [selectedPrompt, setSelectedPrompt] = useState(null);
    const [promptVersions, setPromptVersions] = useState([]);
    const [selectedPromptVersion, setSelectedPromptVersion] = useState(null);
    const [promptVersionDetail, setPromptVersionDetail] = useState(null);
    const [promptDraft, setPromptDraft] = useState({
        system_prompt: '', user_prompt: '',
    });
    const [promptDirty, setPromptDirty] = useState(false);
    const [variables, setVariables] = useState(null);
    const [loading, setLoading] = useState(false);
    const [showNewPromptVersion, setShowNewPromptVersion] = useState(false);
    const [showNewSkillVersion, setShowNewSkillVersion] = useState(false);
    const [saving, setSaving] = useState(false);
    const refreshSkills = async () => {
        setLoading(true);
        try {
            const r = await agentApi.listSkills();
            const items = r.items || r.skills || [];
            setSkills(items);
            if (items.length > 0 && !selectedSkill)
                setSelectedSkill(items[0].name);
        }
        catch (e) {
            setError(`加载 skills 失败：${e instanceof Error ? e.message : e}`);
        }
        finally {
            setLoading(false);
        }
    };
    const refreshPrompts = async () => {
        setLoading(true);
        try {
            const r = await agentApi.listPrompts();
            const arr = r.items || r.prompts || [];
            setPrompts(arr);
            if (arr.length > 0 && !selectedPrompt)
                setSelectedPrompt(arr[0]);
        }
        catch (e) {
            setError(`加载 prompts 失败：${e instanceof Error ? e.message : e}`);
        }
        finally {
            setLoading(false);
        }
    };
    const refreshVariables = async () => {
        setLoading(true);
        try {
            const r = await agentApi.variables();
            setVariables((r.variables || r));
        }
        catch (e) {
            setError(`加载 variables 失败：${e instanceof Error ? e.message : e}`);
        }
        finally {
            setLoading(false);
        }
    };
    useEffect(() => {
        if (tab === 'prompts' && prompts.length === 0)
            void refreshPrompts();
        if (tab === 'skills' && skills.length === 0)
            void refreshSkills();
        if (tab === 'variables' && variables === null)
            void refreshVariables();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [tab]);
    // Skill version list on selection
    useEffect(() => {
        if (!selectedSkill)
            return;
        (async () => {
            try {
                const r = await agentApi.listSkillVersions(selectedSkill);
                const arr = r.versions || [];
                setSkillVersions(arr);
                const active = skills.find((s) => s.name === selectedSkill)?.active_version
                    ?? skills.find((s) => s.name === selectedSkill)?.default_version;
                const def = active && arr.includes(active) ? active : arr[arr.length - 1] ?? null;
                setSelectedSkillVersion(def);
            }
            catch (e) {
                setError(`加载 skill 版本失败：${e instanceof Error ? e.message : e}`);
            }
        })();
    }, [selectedSkill, skills, setError]);
    useEffect(() => {
        if (!selectedSkill || !selectedSkillVersion)
            return;
        (async () => {
            try {
                const r = await agentApi.getSkillVersion(selectedSkill, selectedSkillVersion);
                setSkillVersionDetail(r);
                setSkillDraft({
                    skill_md: r.skill_md ?? '',
                    system_prompt: r.system_prompt ?? '',
                });
                setSkillDirty(false);
            }
            catch (e) {
                setError(`加载 skill 版本详情失败：${e instanceof Error ? e.message : e}`);
            }
        })();
    }, [selectedSkill, selectedSkillVersion, setError]);
    useEffect(() => {
        if (!selectedPrompt)
            return;
        (async () => {
            try {
                const r = await agentApi.listPromptVersions(selectedPrompt);
                const arr = r.versions || [];
                setPromptVersions(arr);
                const def = arr[arr.length - 1] ?? null;
                setSelectedPromptVersion(def);
            }
            catch (e) {
                setError(`加载 prompt 版本失败：${e instanceof Error ? e.message : e}`);
            }
        })();
    }, [selectedPrompt, setError]);
    useEffect(() => {
        if (!selectedPrompt || !selectedPromptVersion)
            return;
        (async () => {
            try {
                const r = await agentApi.getPromptVersion(selectedPrompt, selectedPromptVersion);
                setPromptVersionDetail(r);
                setPromptDraft({
                    system_prompt: r.system_prompt ?? '',
                    user_prompt: r.user_prompt ?? '',
                });
                setPromptDirty(false);
            }
            catch (e) {
                setError(`加载 prompt 版本详情失败：${e instanceof Error ? e.message : e}`);
            }
        })();
    }, [selectedPrompt, selectedPromptVersion, setError]);
    const handleSetActiveSkill = async (version) => {
        if (!selectedSkill)
            return;
        try {
            await agentApi.setSkillActive(selectedSkill, version);
            setNotification(`已将 ${selectedSkill} 激活版本设为 ${version}`);
            await refreshSkills();
        }
        catch (e) {
            setError(`设置失败：${e instanceof Error ? e.message : e}`);
        }
    };
    const handleSetActivePrompt = async (version) => {
        if (!selectedPrompt)
            return;
        try {
            await agentApi.setPromptActive(selectedPrompt, version);
            setNotification(`已将 ${selectedPrompt} 激活版本设为 ${version}`);
            await refreshPrompts();
        }
        catch (e) {
            setError(`设置失败：${e instanceof Error ? e.message : e}`);
        }
    };
    const saveSkill = async () => {
        if (!selectedSkill || !selectedSkillVersion)
            return;
        setSaving(true);
        try {
            await agentApi.updateSkillVersion(selectedSkill, selectedSkillVersion, skillDraft);
            setSkillDirty(false);
            setNotification('skill.md 已保存');
        }
        catch (e) {
            setError(`保存失败：${e instanceof Error ? e.message : e}`);
        }
        finally {
            setSaving(false);
        }
    };
    const deleteSkillVersion = async () => {
        if (!selectedSkill || !selectedSkillVersion)
            return;
        if (skillVersions.length <= 1) {
            setError('至少保留一个版本');
            return;
        }
        if (!confirm(`确认删除 skill 版本 ${selectedSkillVersion}？`))
            return;
        try {
            await agentApi.deleteSkillVersion(selectedSkill, selectedSkillVersion);
            setNotification('版本已删除');
            const idx = skillVersions.indexOf(selectedSkillVersion);
            const next = skillVersions[idx === 0 ? 1 : idx - 1];
            const remaining = skillVersions.filter((v) => v !== selectedSkillVersion);
            setSkillVersions(remaining);
            setSelectedSkillVersion(next ?? null);
        }
        catch (e) {
            setError(`删除失败：${e instanceof Error ? e.message : e}`);
        }
    };
    const savePrompt = async () => {
        if (!selectedPrompt || !selectedPromptVersion)
            return;
        setSaving(true);
        try {
            await agentApi.updatePromptVersion(selectedPrompt, selectedPromptVersion, promptDraft);
            setPromptDirty(false);
            setNotification('prompt 版本已保存');
        }
        catch (e) {
            setError(`保存失败：${e instanceof Error ? e.message : e}`);
        }
        finally {
            setSaving(false);
        }
    };
    const deletePromptVersion = async () => {
        if (!selectedPrompt || !selectedPromptVersion)
            return;
        if (promptVersions.length <= 1) {
            setError('至少保留一个版本');
            return;
        }
        if (!confirm(`确认删除 prompt 版本 ${selectedPromptVersion}？`))
            return;
        try {
            await agentApi.deletePromptVersion(selectedPrompt, selectedPromptVersion);
            setNotification('版本已删除');
            const idx = promptVersions.indexOf(selectedPromptVersion);
            const next = promptVersions[idx === 0 ? 1 : idx - 1];
            const remaining = promptVersions.filter((v) => v !== selectedPromptVersion);
            setPromptVersions(remaining);
            setSelectedPromptVersion(next ?? null);
        }
        catch (e) {
            setError(`删除失败：${e instanceof Error ? e.message : e}`);
        }
    };
    const activeSkillVersion = skills.find((s) => s.name === selectedSkill)?.active_version
        ?? skills.find((s) => s.name === selectedSkill)?.default_version;
    return (_jsxs("div", { className: "admin-page", children: [_jsx(AdminNav, {}), _jsxs("div", { className: "admin-content", children: [_jsx("div", { className: "admin-header", children: _jsx("h1", { children: "\uD83E\uDD16 \u6A21\u578B\u7BA1\u7406" }) }), _jsxs("div", { className: "tab-bar", children: [_jsx("button", { className: tab === 'prompts' ? 'active' : '', onClick: () => setTab('prompts'), children: "Prompts" }), _jsx("button", { className: tab === 'skills' ? 'active' : '', onClick: () => setTab('skills'), children: "Skills" }), _jsx("button", { className: tab === 'variables' ? 'active' : '', onClick: () => setTab('variables'), children: "Variables" })] }), loading && _jsx("div", { className: "loading", children: "\u52A0\u8F7D\u4E2D..." }), tab === 'prompts' && (_jsxs("div", { className: "three-pane", children: [_jsxs("div", { className: "pane-left", children: [_jsx("h3", { children: "Prompt \u5217\u8868" }), _jsx("ul", { className: "item-list", children: prompts.map((name) => (_jsx("li", { className: selectedPrompt === name ? 'active' : '', onClick: () => setSelectedPrompt(name), children: name }, name))) })] }), _jsxs("div", { className: "pane-middle", children: [_jsx("h3", { children: "\u7248\u672C\u65F6\u95F4\u7EBF" }), _jsx("button", { className: "btn-primary small", style: { marginBottom: 10, width: '100%' }, disabled: !selectedPrompt, onClick: () => setShowNewPromptVersion(true), children: "\uFF0B \u65B0\u5EFA\u7248\u672C\uFF08\u590D\u5236\u5FEB\u7167\uFF09" }), !selectedPrompt ? (_jsx("div", { className: "empty-hint", children: "\u8BF7\u9009\u5DE6\u4FA7 prompt" })) : promptVersions.length === 0 ? (_jsx("div", { className: "empty-hint", children: "\u65E0\u7248\u672C" })) : (_jsx("ul", { className: "version-list", children: promptVersions.map((v) => (_jsx("li", { className: selectedPromptVersion === v ? 'active' : '', onClick: () => setSelectedPromptVersion(v), title: `版本 ${v}`, children: v }, v))) })), _jsx("div", { style: { display: 'flex', gap: 6, marginTop: 10 }, children: selectedPromptVersion && (_jsxs(_Fragment, { children: [_jsx("button", { onClick: () => handleSetActivePrompt(selectedPromptVersion), className: "btn-primary small", style: { flex: 1 }, children: "\u8BBE\u4E3A\u6FC0\u6D3B" }), _jsx("button", { onClick: deletePromptVersion, className: "btn-secondary btn-danger small", children: "\u5220" })] })) })] }), _jsxs("div", { className: "pane-right", children: [_jsxs("div", { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }, children: [_jsxs("h3", { style: { margin: 0 }, children: ["Prompt \u7F16\u8F91\u5668", promptDirty && _jsx("span", { style: { color: '#e0b060', marginLeft: 8, fontSize: 12 }, children: "\uFF08\u6709\u672A\u4FDD\u5B58\u4FEE\u6539\uFF09" })] }), _jsxs("div", { style: { display: 'flex', gap: 6 }, children: [_jsx("button", { className: "btn-secondary small", onClick: () => {
                                                            if (!promptVersionDetail)
                                                                return;
                                                            setPromptDraft({
                                                                system_prompt: promptVersionDetail.system_prompt ?? '',
                                                                user_prompt: promptVersionDetail.user_prompt ?? '',
                                                            });
                                                            setPromptDirty(false);
                                                        }, disabled: !promptVersionDetail, children: "\u21BA \u8FD8\u539F" }), _jsx("button", { className: "btn-primary small", onClick: savePrompt, disabled: !promptDirty || saving, children: saving ? '保存中…' : '💾 保存版本' })] })] }), !promptVersionDetail ? (_jsx("div", { className: "empty-hint", children: "\u9009\u62E9\u7248\u672C\u67E5\u770B\u8BE6\u60C5" })) : (_jsxs("div", { className: "dual-editor", children: [_jsxs("div", { className: "editor-col", children: [_jsx("label", { children: "system_prompt.md" }), _jsx("textarea", { value: promptDraft.system_prompt, rows: 18, onChange: (e) => { setPromptDraft({ ...promptDraft, system_prompt: e.target.value }); setPromptDirty(true); } })] }), _jsxs("div", { className: "editor-col", children: [_jsx("label", { children: "user_prompt.md" }), _jsx("textarea", { value: promptDraft.user_prompt, rows: 18, onChange: (e) => { setPromptDraft({ ...promptDraft, user_prompt: e.target.value }); setPromptDirty(true); } })] })] }))] })] })), tab === 'skills' && (_jsxs("div", { className: "three-pane", children: [_jsxs("div", { className: "pane-left", children: [_jsx("h3", { children: "Skill \u5217\u8868" }), _jsx("ul", { className: "item-list", children: skills.map((s) => (_jsxs("li", { className: selectedSkill === s.name ? 'active' : '', onClick: () => setSelectedSkill(s.name), children: [s.name, _jsx("span", { className: "badge", children: s.active_version || s.default_version })] }, s.name))) })] }), _jsxs("div", { className: "pane-middle", children: [_jsx("h3", { children: "\u7248\u672C\u65F6\u95F4\u7EBF" }), _jsx("button", { className: "btn-primary small", style: { marginBottom: 10, width: '100%' }, disabled: !selectedSkill, onClick: () => setShowNewSkillVersion(true), children: "\uFF0B \u65B0\u5EFA\u7248\u672C\uFF08copytree\uFF09" }), !selectedSkill ? (_jsx("div", { className: "empty-hint", children: "\u8BF7\u9009\u5DE6\u4FA7 skill" })) : (_jsxs(_Fragment, { children: [_jsx("ul", { className: "version-list", children: skillVersions.map((v) => (_jsxs("li", { className: selectedSkillVersion === v ? 'active' : '', onClick: () => setSelectedSkillVersion(v), children: [v, v === activeSkillVersion && _jsx("span", { className: "badge", style: { marginLeft: 6 }, children: "\u6FC0\u6D3B" })] }, v))) }), _jsx("div", { style: { display: 'flex', gap: 6, marginTop: 10 }, children: selectedSkillVersion && (_jsxs(_Fragment, { children: [_jsx("button", { onClick: () => handleSetActiveSkill(selectedSkillVersion), className: "btn-primary small", style: { flex: 1 }, children: "\u8BBE\u4E3A\u6FC0\u6D3B" }), _jsx("button", { onClick: deleteSkillVersion, className: "btn-secondary btn-danger small", children: "\u5220" })] })) })] }))] }), _jsxs("div", { className: "pane-right", children: [_jsxs("div", { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }, children: [_jsxs("h3", { style: { margin: 0 }, children: ["Skill \u7F16\u8F91\u5668", skillDirty && _jsx("span", { style: { color: '#e0b060', marginLeft: 8, fontSize: 12 }, children: "\uFF08\u6709\u672A\u4FDD\u5B58\u4FEE\u6539\uFF09" })] }), _jsxs("div", { style: { display: 'flex', gap: 6 }, children: [_jsx("button", { className: "btn-secondary small", onClick: () => {
                                                            if (!skillVersionDetail)
                                                                return;
                                                            setSkillDraft({
                                                                skill_md: skillVersionDetail.skill_md ?? '',
                                                                system_prompt: skillVersionDetail.system_prompt ?? '',
                                                            });
                                                            setSkillDirty(false);
                                                        }, disabled: !skillVersionDetail, children: "\u21BA \u8FD8\u539F" }), _jsx("button", { className: "btn-primary small", onClick: saveSkill, disabled: !skillDirty || saving, children: saving ? '保存中…' : '💾 保存版本' })] })] }), !skillVersionDetail ? (_jsx("div", { className: "empty-hint", children: "\u9009\u62E9\u7248\u672C\u67E5\u770B skill.md" })) : (_jsx("div", { children: _jsxs("div", { className: "single-editor", children: [_jsx("label", { children: "skill.md" }), _jsx("textarea", { value: skillDraft.skill_md, rows: 24, onChange: (e) => { setSkillDraft({ ...skillDraft, skill_md: e.target.value }); setSkillDirty(true); } })] }) }))] })] })), tab === 'variables' && (_jsxs("div", { className: "variables-tab", children: [_jsx("h3", { children: "variables.json \u5B9A\u4E49\u7684\u53D8\u91CF\u5B57\u5178" }), !variables ? (_jsx("div", { className: "empty-hint", children: "\u52A0\u8F7D\u4E2D" })) : Object.keys(variables).length === 0 ? (_jsx("div", { className: "empty-hint", children: "variables.json \u4E3A\u7A7A" })) : (_jsxs("table", { className: "data-table", children: [_jsx("thead", { children: _jsxs("tr", { children: [_jsx("th", { style: { width: 220 }, children: "\u53D8\u91CF\u540D" }), _jsx("th", { children: "\u542B\u4E49 / \u6765\u6E90" }), _jsx("th", { style: { width: 320 }, children: "\u5F53\u524D\u503C" })] }) }), _jsx("tbody", { children: Object.entries(variables).map(([k, v]) => {
                                            const desc = typeof v === 'object' && v
                                                ? (v.description ?? '') +
                                                    (v.source ? ` · 来源：${v.source}` : '')
                                                : '';
                                            const value = typeof v === 'object' && v
                                                ? (v.value ?? '')
                                                : v;
                                            return (_jsxs("tr", { children: [_jsx("td", { children: _jsxs("code", { children: ["$", `{${k}}`] }) }), _jsx("td", { children: desc || '—' }), _jsx("td", { children: _jsx("code", { style: { whiteSpace: 'pre-wrap', wordBreak: 'break-all' }, children: typeof value === 'object' ? JSON.stringify(value) : String(value ?? '') }) })] }, k));
                                        }) })] }))] }))] }), showNewPromptVersion && selectedPrompt && (_jsx(NewVersionModal, { title: `为 Prompt「${selectedPrompt}」创建新版本`, existing: promptVersions, onClose: () => setShowNewPromptVersion(false), onCreate: async ({ new_version, from_version }) => {
                    try {
                        await agentApi.createPromptVersion(selectedPrompt, { new_version, from_version });
                        setNotification('新版本已创建');
                        setShowNewPromptVersion(false);
                        const r = await agentApi.listPromptVersions(selectedPrompt);
                        setPromptVersions(r.versions || []);
                        setSelectedPromptVersion(new_version);
                    }
                    catch (e) {
                        setError(`创建失败：${e instanceof Error ? e.message : e}`);
                    }
                } })), showNewSkillVersion && selectedSkill && (_jsx(NewVersionModal, { title: `为 Skill「${selectedSkill}」创建新版本`, existing: skillVersions, onClose: () => setShowNewSkillVersion(false), onCreate: async ({ new_version, from_version }) => {
                    try {
                        await agentApi.createSkillVersion(selectedSkill, { new_version, from_version });
                        setNotification('新版本已创建');
                        setShowNewSkillVersion(false);
                        const r = await agentApi.listSkillVersions(selectedSkill);
                        setSkillVersions(r.versions || []);
                        setSelectedSkillVersion(new_version);
                    }
                    catch (e) {
                        setError(`创建失败：${e instanceof Error ? e.message : e}`);
                    }
                } }))] }));
}
