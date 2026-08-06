import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import AdminNav from '../components/AdminNav';
import { configApi, agentApi } from '../api/client';
import { useGameStore } from '../store/gameStore';
const POLISH_LEN_OPTS = [
    { v: 'short', label: '短（1句）' },
    { v: 'medium', label: '中（3~5句）' },
    { v: 'long', label: '长（段落）' },
    { v: 'epic', label: '史诗（多段）' },
];
export default function SettingsPage() {
    const setNotification = useGameStore((s) => s.setNotification);
    const setError = useGameStore((s) => s.setError);
    const [config, setConfig] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [connStatus, setConnStatus] = useState('idle');
    const [connMsg, setConnMsg] = useState('');
    const refresh = async () => {
        setLoading(true);
        try {
            const r = await configApi.get();
            setConfig(r.config);
        }
        catch (e) {
            setError(`加载配置失败：${e instanceof Error ? e.message : e}`);
        }
        finally {
            setLoading(false);
        }
    };
    useEffect(() => {
        refresh();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
    const update = (section, field, value) => {
        if (!config)
            return;
        setConfig({
            ...config,
            [section]: {
                ...(config[section] || {}),
                [field]: value,
            },
        });
    };
    const handleSave = async () => {
        if (!config)
            return;
        setSaving(true);
        try {
            const r = await configApi.patch(config);
            setConfig(r.config);
            setNotification(`已更新字段：${(r.updated_keys || []).join(', ')}`);
        }
        catch (e) {
            setError(`保存失败：${e instanceof Error ? e.message : e}`);
        }
        finally {
            setSaving(false);
        }
    };
    const handleReset = async () => {
        if (!window.confirm('确定重置全部配置为默认值？'))
            return;
        try {
            const r = await configApi.reset();
            setConfig(r.config);
            setNotification('已重置为默认配置');
        }
        catch (e) {
            setError(`重置失败：${e instanceof Error ? e.message : e}`);
        }
    };
    const handleTestConnection = async () => {
        setConnStatus('testing');
        setConnMsg('');
        try {
            const body = {};
            if (config?.llm_pipeline?.model)
                body.model = config.llm_pipeline.model;
            const r = await agentApi.testConnection(body);
            if (r.ok) {
                setConnStatus('ok');
                setConnMsg(r.message || `连接成功（模型：${r.model || 'default'}，耗时 ${r.latency_ms ?? '?'}ms）`);
                setNotification('API 连接测试通过');
            }
            else {
                setConnStatus('fail');
                setConnMsg(r.message || '连接失败：未知错误');
            }
        }
        catch (e) {
            setConnStatus('fail');
            const msg = e instanceof Error ? e.message : String(e);
            setConnMsg(`请求异常：${msg}`);
        }
    };
    if (loading || !config) {
        return (_jsxs("div", { className: "admin-page", children: [_jsx(AdminNav, {}), _jsx("div", { className: "admin-content", children: _jsx("div", { className: "loading", children: "\u52A0\u8F7D\u4E2D..." }) })] }));
    }
    return (_jsxs("div", { className: "admin-page", children: [_jsx(AdminNav, {}), _jsxs("div", { className: "admin-content", children: [_jsxs("div", { className: "admin-header", children: [_jsx("h1", { children: "\u2699 \u5168\u5C40\u8BBE\u7F6E" }), _jsxs("div", { className: "header-actions", children: [_jsx("button", { onClick: handleReset, className: "btn-secondary", children: "\u21A9 \u91CD\u7F6E\u9ED8\u8BA4" }), _jsx("button", { onClick: handleSave, disabled: saving, className: "btn-primary", children: saving ? '⏳ 保存中...' : '💾 保存' })] })] }), _jsxs("div", { className: "settings-sections", children: [_jsxs("section", { children: [_jsx("h2", { children: "\uD83D\uDDA5 UI \u9ED8\u8BA4\u503C" }), _jsxs("div", { className: "form-grid", children: [_jsxs("label", { children: ["\u9ED8\u8BA4 TPS", _jsx("input", { type: "number", step: "0.1", value: config.ui_defaults?.default_tps ?? 1.0, onChange: (e) => update('ui_defaults', 'default_tps', parseFloat(e.target.value)) })] }), _jsxs("label", { children: ["\u5C55\u793A\u6A21\u5F0F", _jsxs("select", { value: config.ui_defaults?.default_era_display_mode ?? 'polished', onChange: (e) => update('ui_defaults', 'default_era_display_mode', e.target.value), children: [_jsx("option", { value: "polished", children: "\u6DA6\u8272\u7248" }), _jsx("option", { value: "raw", children: "\u539F\u59CB\u7248" })] })] }), _jsxs("label", { children: ["\u70ED\u529B\u56FE\u900F\u660E\u5EA6", _jsx("input", { type: "number", step: "0.05", min: "0", max: "1", value: config.ui_defaults?.default_heatmap_opacity ?? 0.55, onChange: (e) => update('ui_defaults', 'default_heatmap_opacity', parseFloat(e.target.value)) })] }), _jsxs("label", { children: ["\u4E8B\u4EF6\u91CD\u8981\u6027\u9608\u503C", _jsx("input", { type: "number", min: "0", max: "5", value: config.ui_defaults?.event_importance_threshold ?? 0, onChange: (e) => update('ui_defaults', 'event_importance_threshold', parseInt(e.target.value)) })] }), _jsxs("label", { children: ["\u4E3B\u9898", _jsxs("select", { value: config.ui_defaults?.theme ?? 'dark', onChange: (e) => update('ui_defaults', 'theme', e.target.value), children: [_jsx("option", { value: "dark", children: "\u6DF1\u8272" }), _jsx("option", { value: "light", children: "\u6D45\u8272" })] })] }), _jsxs("label", { className: "checkbox", children: [_jsx("input", { type: "checkbox", checked: config.ui_defaults?.show_debug_info ?? false, onChange: (e) => update('ui_defaults', 'show_debug_info', e.target.checked) }), "\u663E\u793A\u8C03\u8BD5\u4FE1\u606F"] })] })] }), _jsxs("section", { children: [_jsx("h2", { children: "\u23F1 \u6A21\u62DF\u53C2\u6570" }), _jsxs("div", { className: "form-grid", children: [_jsxs("label", { children: ["\u9ED8\u8BA4 TPS", _jsx("input", { type: "number", step: "0.1", value: config.simulation?.tps_default ?? 1.0, onChange: (e) => update('simulation', 'tps_default', parseFloat(e.target.value)) })] }), _jsxs("label", { children: ["\u6700\u5927 TPS", _jsx("input", { type: "number", value: config.simulation?.tps_max ?? 240, onChange: (e) => update('simulation', 'tps_max', parseFloat(e.target.value)) })] }), _jsxs("label", { children: ["\u6BCF tick \u6700\u5927\u4E8B\u4EF6\u6570", _jsx("input", { type: "number", value: config.simulation?.max_events_per_tick ?? 20, onChange: (e) => update('simulation', 'max_events_per_tick', parseInt(e.target.value)) })] }), _jsxs("label", { children: ["\u6BCF tick \u8BB0\u5FC6\u8870\u51CF\u7387", _jsx("input", { type: "number", step: "0.005", min: "0", max: "1", value: config.simulation?.memory_decay_per_tick ?? 0.01, onChange: (e) => update('simulation', 'memory_decay_per_tick', parseFloat(e.target.value)) })] }), _jsxs("label", { children: ["\u70ED\u529B\u56FE\u5237\u65B0\u95F4\u9694\uFF08tick\uFF09", _jsx("input", { type: "number", value: config.simulation?.heatmap_update_interval_ticks ?? 10, onChange: (e) => update('simulation', 'heatmap_update_interval_ticks', parseInt(e.target.value)) })] })] })] }), _jsxs("section", { children: [_jsx("h2", { children: "\uD83E\uDDE0 \u8BB0\u5FC6\u7CFB\u7EDF" }), _jsxs("div", { className: "form-grid", children: [_jsxs("label", { children: ["\u68C0\u7D22\u9ED8\u8BA4\u4E0A\u9650", _jsx("input", { type: "number", value: config.memory?.retrieve_max_default ?? 30, onChange: (e) => update('memory', 'retrieve_max_default', parseInt(e.target.value)) })] }), _jsxs("label", { children: ["\u5BAB\u6BBF\u9ED8\u8BA4\u6DF1\u5EA6", _jsx("input", { type: "number", min: "1", max: "5", value: config.memory?.palace_default_depth ?? 2, onChange: (e) => update('memory', 'palace_default_depth', parseInt(e.target.value)) })] }), _jsxs("label", { children: ["\u7D22\u5F15\u91C7\u6837\u7387", _jsx("input", { type: "number", step: "0.1", min: "0", max: "1", value: config.memory?.index_sampling_rate ?? 1.0, onChange: (e) => update('memory', 'index_sampling_rate', parseFloat(e.target.value)) })] })] })] }), _jsxs("section", { children: [_jsx("h2", { children: "\uD83E\uDD16 LLM \u7BA1\u7EBF" }), _jsxs("div", { className: "form-grid", children: [_jsxs("label", { className: "checkbox", children: [_jsx("input", { type: "checkbox", checked: config.llm_pipeline?.enabled ?? false, onChange: (e) => update('llm_pipeline', 'enabled', e.target.checked) }), "\u542F\u7528 LLM \u7BA1\u7EBF\uFF08\u5173\u95ED\u65F6\u8C03\u7528 /api/agent/tick \u53EA\u66F4\u65B0\u5143\u4FE1\u606F\uFF09"] }), _jsxs("label", { children: ["Provider", _jsxs("select", { value: config.llm_pipeline?.provider ?? 'stub', onChange: (e) => update('llm_pipeline', 'provider', e.target.value), children: [_jsx("option", { value: "stub", children: "stub\uFF08\u4E0D\u8C03 LLM\uFF09" }), _jsx("option", { value: "deepseek", children: "DeepSeek" }), _jsx("option", { value: "openai", children: "OpenAI \u517C\u5BB9" })] })] }), _jsxs("label", { children: ["\u6A21\u578B\u540D", _jsx("input", { value: config.llm_pipeline?.model ?? '', placeholder: "deepseek-v4-flash", onChange: (e) => update('llm_pipeline', 'model', e.target.value) })] }), _jsxs("label", { children: ["API Base", _jsx("input", { value: config.llm_pipeline?.api_base ?? '', placeholder: "https://api.deepseek.com", onChange: (e) => update('llm_pipeline', 'api_base', e.target.value) })] }), _jsxs("label", { children: ["API Key\uFF08\u5BC6\u6587\uFF09", _jsx("input", { type: "password", value: config.llm_pipeline?.api_key ?? '', placeholder: "sk-...", onChange: (e) => update('llm_pipeline', 'api_key', e.target.value) })] }), _jsxs("label", { children: ["\u5355\u8BF7\u6C42\u6700\u5927 Token", _jsx("input", { type: "number", value: config.llm_pipeline?.max_tokens_per_request ?? 2048, onChange: (e) => update('llm_pipeline', 'max_tokens_per_request', parseInt(e.target.value)) })] })] }), _jsxs("div", { style: { marginTop: 16, display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }, children: [_jsxs("button", { className: `btn-secondary test-conn-btn ${connStatus}`, onClick: handleTestConnection, disabled: connStatus === 'testing', children: [_jsx("span", { className: "dot" }), connStatus === 'testing' ? '测试中…' :
                                                        connStatus === 'ok' ? '✓ 连接成功' :
                                                            connStatus === 'fail' ? '✗ 连接失败' :
                                                                '🧪 测试连接'] }), connMsg && (_jsx("span", { className: connStatus === 'ok' ? 'muted' : '', style: {
                                                    color: connStatus === 'fail' ? '#ef4444' : connStatus === 'ok' ? '#4ade80' : '#888',
                                                    fontSize: 12,
                                                }, children: connMsg }))] })] }), _jsxs("section", { children: [_jsx("h2", { children: "\uD83C\uDFA8 \u5185\u5BB9\u504F\u597D" }), _jsxs("div", { className: "form-grid", children: [_jsxs("label", { children: ["\u6DA6\u8272\u957F\u5EA6\uFF08UI \u9ED8\u8BA4\uFF09", _jsx("select", { value: config.ui_defaults?.default_polish_length ?? 'medium', onChange: (e) => update('ui_defaults', 'default_polish_length', e.target.value), children: POLISH_LEN_OPTS.map((o) => (_jsx("option", { value: o.v, children: o.label }, o.v))) })] }), _jsxs("label", { children: ["\u6DA6\u8272\u957F\u5EA6\uFF08\u6A21\u62DF\u7BA1\u7EBF\uFF09", _jsx("select", { value: config.simulation?.polish_length ?? 'medium', onChange: (e) => update('simulation', 'polish_length', e.target.value), children: POLISH_LEN_OPTS.map((o) => (_jsx("option", { value: o.v, children: o.label }, o.v))) })] }), _jsxs("label", { className: "checkbox", children: [_jsx("input", { type: "checkbox", checked: config.simulation?.gore_enabled ?? false, onChange: (e) => update('simulation', 'gore_enabled', e.target.checked) }), "\u5141\u8BB8\u8840\u8165\u63CF\u5199"] }), _jsxs("label", { className: "checkbox", children: [_jsx("input", { type: "checkbox", checked: config.simulation?.adult_content ?? false, onChange: (e) => update('simulation', 'adult_content', e.target.checked) }), "\u5141\u8BB8\u6210\u4EBA\u5185\u5BB9"] }), _jsxs("label", { style: { gridColumn: '1 / -1' }, children: ["\u66B4\u529B\u7B49\u7EA7\uFF1A", config.simulation?.violence_level ?? 2, " / 5", _jsx("input", { type: "range", min: 0, max: 5, step: 1, value: config.simulation?.violence_level ?? 2, onChange: (e) => update('simulation', 'violence_level', Number(e.target.value)) })] })] })] }), _jsxs("section", { children: [_jsx("h2", { children: "\uD83D\uDCDD \u65E5\u5FD7\u914D\u7F6E" }), _jsxs("div", { className: "form-grid", children: [_jsxs("label", { style: { gridColumn: '1 / -1' }, children: ["\u65E5\u5FD7\u76EE\u5F55\uFF08LOG_DIR\uFF0C\u76F8\u5BF9\u4E8E\u9879\u76EE\u6839\u6216\u7EDD\u5BF9\u8DEF\u5F84\uFF09", _jsx("input", { type: "text", value: config.logging?.log_dir ?? 'logs/', onChange: (e) => update('logging', 'log_dir', e.target.value), placeholder: "logs/ \u6216 D:/game_logs/" })] }), _jsxs("label", { children: ["\u65E5\u5FD7\u7EA7\u522B", _jsxs("select", { value: config.logging?.log_level ?? 'info', onChange: (e) => update('logging', 'log_level', e.target.value), children: [_jsx("option", { value: "debug", children: "DEBUG\uFF08\u8BE6\u7EC6\uFF09" }), _jsx("option", { value: "info", children: "INFO\uFF08\u9ED8\u8BA4\uFF09" }), _jsx("option", { value: "warn", children: "WARN\uFF08\u4EC5\u8B66\u544A\uFF09" }), _jsx("option", { value: "error", children: "ERROR\uFF08\u4EC5\u9519\u8BEF\uFF09" })] })] }), _jsxs("label", { className: "checkbox", children: [_jsx("input", { type: "checkbox", checked: config.logging?.console_log_enabled ?? true, onChange: (e) => update('logging', 'console_log_enabled', e.target.checked) }), "\u540C\u6B65\u8F93\u51FA\u5230\u63A7\u5236\u53F0"] })] })] }), _jsxs("section", { children: [_jsx("h2", { children: "\uD83D\uDCBE \u5FEB\u7167\u7B56\u7565" }), _jsxs("div", { className: "form-grid", children: [_jsxs("label", { className: "checkbox", children: [_jsx("input", { type: "checkbox", checked: config.snapshots?.auto_snapshot_enabled ?? false, onChange: (e) => update('snapshots', 'auto_snapshot_enabled', e.target.checked) }), "\u542F\u7528\u81EA\u52A8\u5FEB\u7167"] }), _jsxs("label", { children: ["\u81EA\u52A8\u5FEB\u7167\u95F4\u9694\uFF08tick \u6570\uFF09", _jsx("input", { type: "number", min: 1, value: config.snapshots?.auto_snapshot_interval_ticks ?? 100, onChange: (e) => update('snapshots', 'auto_snapshot_interval_ticks', parseInt(e.target.value)) })] }), _jsxs("label", { children: ["\u6BCF\u5B58\u6863\u6700\u5927\u5FEB\u7167\u6570\uFF08\u8D85\u8FC7\u81EA\u52A8\u5220\u9664\u6700\u65E7\uFF09", _jsx("input", { type: "number", min: 1, value: config.snapshots?.max_snapshots_per_save ?? 50, onChange: (e) => update('snapshots', 'max_snapshots_per_save', parseInt(e.target.value)) })] }), _jsxs("label", { children: ["\u4FDD\u7559\u6BCF\u65E5\u5FEB\u7167\u6570\uFF080=\u4E0D\u5355\u72EC\u4FDD\u7559\uFF09", _jsx("input", { type: "number", min: 0, value: config.snapshots?.keep_daily_snapshots ?? 1, onChange: (e) => update('snapshots', 'keep_daily_snapshots', parseInt(e.target.value)) })] })] })] }), _jsxs("section", { children: [_jsx("h2", { children: "\uD83D\uDD12 \u9690\u79C1" }), _jsxs("div", { className: "form-grid", children: [_jsxs("label", { className: "checkbox", children: [_jsx("input", { type: "checkbox", checked: config.privacy?.allow_data_collection ?? false, onChange: (e) => update('privacy', 'allow_data_collection', e.target.checked) }), "\u5141\u8BB8\u533F\u540D\u6570\u636E\u91C7\u96C6"] }), _jsxs("label", { children: ["\u6570\u636E\u4FDD\u7559\u5929\u6570\uFF080=\u6C38\u4E45\uFF09", _jsx("input", { type: "number", min: "0", value: config.privacy?.retention_days ?? 0, onChange: (e) => update('privacy', 'retention_days', parseInt(e.target.value)) })] })] })] })] })] })] }));
}
