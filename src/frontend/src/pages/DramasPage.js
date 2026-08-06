import { jsxs as _jsxs, jsx as _jsx } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AdminNav from '../components/AdminNav';
import { dramasApi } from '../api/client';
import { useGameStore } from '../store/gameStore';
const DRAMA_FILES = [
    'meta.txt', 'characters.txt', 'groups.txt', 'group_hierarchies.txt',
    'items.txt', 'maps.txt', 'map_features.txt', 'events.txt',
    'settings.txt', 'plot_planning.txt',
];
// 从对象中提取显示名称：优先 name/title/key/id
function extractName(obj, idx) {
    const candidates = ['name', 'title', 'key', 'id', 'char_name', 'group_name', 'map_name', 'item_name', 'feature_name'];
    for (const k of candidates) {
        const v = obj[k];
        if (typeof v === 'string' && v.trim())
            return v;
        if (typeof v === 'number')
            return String(v);
    }
    return `第 ${idx + 1} 条`;
}
function tryParseJsonStr(v) {
    if (typeof v !== 'string')
        return v;
    const s = v.trim();
    if ((s.startsWith('{') && s.endsWith('}')) || (s.startsWith('[') && s.endsWith(']'))) {
        try {
            return JSON.parse(s);
        }
        catch { /* ignore */ }
    }
    return v;
}
function PreviewObjCard({ obj, index }) {
    const name = extractName(obj, index);
    // 隐藏纯标题字段，单独展示其他字段
    const titleKeys = new Set(['name', 'title', 'key', 'id']);
    const entries = Object.entries(obj).filter(([k]) => !titleKeys.has(k));
    return (_jsxs("div", { className: "preview-card", children: [_jsxs("div", { className: "preview-card-header", children: [_jsxs("span", { className: "preview-card-index", children: ["#", index + 1] }), _jsxs("span", { className: "preview-card-name", children: ["\u00B7 ", name] })] }), _jsx("div", { className: "preview-card-body", children: entries.length === 0 ? (_jsx("span", { className: "preview-card-empty", children: "\uFF08\u65E0\u989D\u5916\u5B57\u6BB5\uFF09" })) : (_jsx("table", { className: "preview-card-table", children: _jsx("tbody", { children: entries.map(([k, v]) => {
                            const parsed = tryParseJsonStr(v);
                            const display = typeof parsed === 'object' && parsed !== null
                                ? JSON.stringify(parsed, null, 2)
                                : String(parsed ?? '');
                            return (_jsxs("tr", { children: [_jsx("td", { className: "preview-card-key", children: k }), _jsx("td", { className: "preview-card-val", children: _jsx("pre", { children: display }) })] }, k));
                        }) }) })) })] }));
}
export default function DramasPage() {
    const navigate = useNavigate();
    const setNotification = useGameStore((s) => s.setNotification);
    const setError = useGameStore((s) => s.setError);
    const switchSave = useGameStore((s) => s.switchSave);
    const [dramas, setDramas] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showGenerate, setShowGenerate] = useState(false);
    const [genPrompt, setGenPrompt] = useState('');
    const [genName, setGenName] = useState('');
    const [genStyle, setGenStyle] = useState('古风');
    const [genScale, setGenScale] = useState('中型');
    const [generating, setGenerating] = useState(false);
    const [previewDrama, setPreviewDrama] = useState(null);
    const [previewData, setPreviewData] = useState(null);
    const [previewFile, setPreviewFile] = useState('meta.txt');
    const [initDrama, setInitDrama] = useState(null);
    const [initSaveName, setInitSaveName] = useState('');
    const [initOverwrite, setInitOverwrite] = useState(false);
    const [initializing, setInitializing] = useState(false);
    // 校验结果弹窗
    const [validateDrama, setValidateDrama] = useState(null);
    const [validateResult, setValidateResult] = useState(null);
    const refresh = async () => {
        setLoading(true);
        try {
            const list = await dramasApi.list();
            setDramas(list);
        }
        catch (e) {
            setError(`加载剧本列表失败：${e instanceof Error ? e.message : e}`);
        }
        finally {
            setLoading(false);
        }
    };
    useEffect(() => {
        refresh();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
    const handleGenerate = async () => {
        if (!genPrompt.trim()) {
            setError('请填写提示词');
            return;
        }
        setGenerating(true);
        try {
            const fullPrompt = `[风格:${genStyle}] [规模:${genScale}] ${genPrompt}`;
            const r = await dramasApi.generate(fullPrompt, genName || undefined);
            if (r.ok && !r.stub) {
                setNotification(`剧本 "${r.name || genName}" 生成成功`);
                setShowGenerate(false);
                setGenPrompt('');
                refresh();
            }
            else {
                setError(r.message || '一键生成功能尚未接入 LLM 管线（待阶段五）');
            }
        }
        catch (e) {
            setError(`生成失败：${e instanceof Error ? e.message : e}`);
        }
        finally {
            setGenerating(false);
        }
    };
    const handlePreview = async (name) => {
        try {
            const data = await dramasApi.preview(name);
            setPreviewDrama(name);
            setPreviewData(data);
            setPreviewFile('meta.txt');
        }
        catch (e) {
            setError(`预览失败：${e instanceof Error ? e.message : e}`);
        }
    };
    const handleDelete = async (name) => {
        if (!window.confirm(`确定删除剧本 "${name}"？此操作不可恢复。`))
            return;
        try {
            await dramasApi.delete(name);
            setNotification(`已删除剧本 ${name}`);
            refresh();
        }
        catch (e) {
            setError(`删除失败：${e instanceof Error ? e.message : e}`);
        }
    };
    const handleValidate = async (name) => {
        try {
            const r = await dramasApi.validate(name);
            setValidateDrama(name);
            setValidateResult({
                ok: !!r.ok,
                errors: Array.isArray(r.errors) ? r.errors : [],
                warnings: Array.isArray(r.warnings) ? r.warnings : [],
                info: r.info || {},
            });
        }
        catch (e) {
            setError(`校验失败：${e instanceof Error ? e.message : e}`);
        }
    };
    const handleExport = async (name) => {
        try {
            const blob = await dramasApi.exportZip(name);
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${name}.zip`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            setTimeout(() => URL.revokeObjectURL(url), 1000);
            setNotification(`已导出剧本 ${name}.zip`);
        }
        catch (e) {
            setError(`导出失败：${e instanceof Error ? e.message : e}`);
        }
    };
    const handleInit = async () => {
        if (!initDrama)
            return;
        if (!initSaveName.trim()) {
            setError('请填写存档名');
            return;
        }
        setInitializing(true);
        try {
            const r = await dramasApi.init(initDrama, initSaveName.trim(), initOverwrite);
            const stats = r.stats || {};
            setNotification(`剧本已导入！角色 ${stats.characters ?? 0} / 群体 ${stats.groups ?? 0} / 事件 ${stats.events ?? 0}`);
            // 切换激活存档并跳转
            await switchSave(initSaveName.trim());
            setInitDrama(null);
            setInitSaveName('');
            setInitOverwrite(false);
            navigate('/play');
        }
        catch (e) {
            setError(`导入失败：${e instanceof Error ? e.message : e}`);
        }
        finally {
            setInitializing(false);
        }
    };
    const renderPreviewFile = () => {
        if (!previewData)
            return null;
        const content = previewData[previewFile];
        if (content === null || content === undefined) {
            return _jsx("div", { className: "preview-empty", children: "\uFF08\u8BE5\u6587\u4EF6\u4E0D\u5B58\u5728\uFF09" });
        }
        // meta.txt 结构化展示
        if (previewFile === 'meta.txt' && typeof content === 'object' && !Array.isArray(content)) {
            const entries = Object.entries(content);
            return (_jsx("table", { className: "preview-card-table", style: { width: '100%' }, children: _jsx("tbody", { children: entries.map(([k, v]) => {
                        const parsed = tryParseJsonStr(v);
                        const display = typeof parsed === 'object' && parsed !== null
                            ? JSON.stringify(parsed, null, 2)
                            : String(parsed ?? '');
                        return (_jsxs("tr", { children: [_jsx("td", { className: "preview-card-key", style: { width: 200 }, children: k }), _jsx("td", { className: "preview-card-val", children: _jsx("pre", { children: display }) })] }, k));
                    }) }) }));
        }
        // 数组：卡片化展示
        if (Array.isArray(content)) {
            // 若全是字符串，还是按行展示（兼容简单格式）
            const allStrings = content.every((r) => typeof r === 'string');
            if (allStrings) {
                return (_jsxs("div", { children: [_jsxs("div", { className: "preview-count", children: ["\u5171 ", content.length, " \u884C"] }), content.map((row, i) => (_jsx("pre", { className: "preview-row", children: row }, i)))] }));
            }
            // 对象数组 → 卡片
            return (_jsxs("div", { className: "preview-cards-grid", children: [_jsxs("div", { className: "preview-count", children: ["\u5171 ", content.length, " \u6761\u8BB0\u5F55"] }), content.map((row, i) => (_jsx(PreviewObjCard, { obj: row, index: i }, i)))] }));
        }
        // 其他：字符串直接展示
        return _jsx("pre", { className: "preview-row", children: String(content) });
    };
    return (_jsxs("div", { className: "admin-page", children: [_jsx(AdminNav, {}), _jsxs("div", { className: "admin-content", children: [_jsxs("div", { className: "admin-header", children: [_jsx("h1", { children: "\uD83D\uDCDC \u5267\u672C\u7BA1\u7406" }), _jsxs("div", { className: "header-actions", children: [_jsx("button", { onClick: refresh, disabled: loading, className: "btn-secondary", children: loading ? '加载中...' : '🔄 刷新' }), _jsx("button", { onClick: () => setShowGenerate(true), className: "btn-primary", children: "\u2728 \u4E00\u952E\u751F\u6210\u5267\u672C" })] })] }), dramas.length === 0 && !loading ? (_jsx("div", { className: "empty-state", children: _jsx("p", { children: "\u6682\u65E0\u5267\u672C\u3002\u53EF\u4EE5\u624B\u5DE5\u7F16\u5199\u6216\u4F7F\u7528\u300C\u4E00\u952E\u751F\u6210\u300D\u3002" }) })) : (_jsx("div", { className: "drama-grid", children: dramas.map((d) => (_jsxs("div", { className: "drama-card", children: [_jsxs("div", { className: "drama-card-cover", children: [_jsx("span", { className: "drama-cover-icon", children: "\uD83D\uDCD6" }), _jsxs("span", { className: "drama-cover-files", children: [d.files.length, " \u6587\u4EF6"] })] }), _jsxs("div", { className: "drama-card-body", children: [_jsx("h3", { children: d.title }), _jsxs("div", { className: "drama-meta", children: [_jsxs("span", { children: ["\uD83D\uDCC1 ", d.name] }), _jsxs("span", { children: ["\uD83D\uDC64 ", d.protagonist_default || '未指定'] }), _jsxs("span", { children: ["\u23F0 ", d.start_game_time || '—'] })] }), _jsx("p", { className: "drama-summary", children: d.summary || '无简介' }), _jsxs("div", { className: "drama-actions", children: [_jsx("button", { onClick: () => handlePreview(d.name), className: "btn-secondary", children: "\uD83D\uDC41 \u9884\u89C8" }), _jsx("button", { onClick: () => handleValidate(d.name), className: "btn-secondary", children: "\u2705 \u6821\u9A8C" }), _jsx("button", { onClick: () => handleExport(d.name), className: "btn-secondary", children: "\uD83D\uDCE6 \u5BFC\u51FAzip" }), _jsx("button", { onClick: () => { setInitDrama(d.name); setInitSaveName(`${d.name}_run`); }, className: "btn-primary", children: "\u25B6 \u5BFC\u5165\u65B0\u5B58\u6863" }), _jsx("button", { onClick: () => handleDelete(d.name), className: "btn-icon btn-danger", title: "\u5220\u9664", children: "\uD83D\uDDD1" })] })] })] }, d.name))) })), showGenerate && (_jsx("div", { className: "modal-overlay", onClick: () => setShowGenerate(false), children: _jsxs("div", { className: "modal", onClick: (e) => e.stopPropagation(), children: [_jsxs("div", { className: "modal-header", children: [_jsx("h2", { children: "\u2728 \u4E00\u952E\u751F\u6210\u5267\u672C" }), _jsx("button", { onClick: () => setShowGenerate(false), className: "btn-icon", children: "\u2715" })] }), _jsxs("div", { className: "form-group", children: [_jsx("label", { children: "\u63D0\u793A\u8BCD" }), _jsx("textarea", { value: genPrompt, onChange: (e) => setGenPrompt(e.target.value), placeholder: "\u90FD\u5E02\u5F02\u80FD\uFF0C\u4E3B\u89D2\u6C88\u9ED8\uFF0C\u4E0A\u6D77\u5E02\uFF0C\u767D\u94F6\u65F6\u4EE3...", rows: 4 })] }), _jsxs("div", { className: "form-row", children: [_jsxs("div", { className: "form-group", children: [_jsx("label", { children: "\u98CE\u683C" }), _jsxs("select", { value: genStyle, onChange: (e) => setGenStyle(e.target.value), children: [_jsx("option", { children: "\u53E4\u98CE" }), _jsx("option", { children: "\u79D1\u5E7B" }), _jsx("option", { children: "\u90FD\u5E02" }), _jsx("option", { children: "\u897F\u5E7B" }), _jsx("option", { children: "\u4ED9\u4FA0" }), _jsx("option", { children: "\u81EA\u5B9A\u4E49" })] })] }), _jsxs("div", { className: "form-group", children: [_jsx("label", { children: "\u89C4\u6A21" }), _jsxs("select", { value: genScale, onChange: (e) => setGenScale(e.target.value), children: [_jsx("option", { children: "\u5C0F\u578B\uFF085 \u89D2\u8272\uFF09" }), _jsx("option", { children: "\u4E2D\u578B\uFF0815\uFF09" }), _jsx("option", { children: "\u5927\u578B\uFF0830\uFF09" })] })] }), _jsxs("div", { className: "form-group", children: [_jsx("label", { children: "\u5267\u672C\u540D\uFF08\u53EF\u9009\uFF09" }), _jsx("input", { value: genName, onChange: (e) => setGenName(e.target.value), placeholder: "\u7559\u7A7A\u81EA\u52A8\u547D\u540D" })] })] }), _jsxs("div", { className: "modal-actions", children: [_jsx("button", { onClick: () => setShowGenerate(false), className: "btn-secondary", children: "\u53D6\u6D88" }), _jsx("button", { onClick: handleGenerate, disabled: generating, className: "btn-primary", children: generating ? '⏳ 生成中...' : '🚀 开始生成' })] })] }) })), previewDrama && previewData && (_jsx("div", { className: "modal-overlay large", onClick: () => setPreviewDrama(null), children: _jsxs("div", { className: "modal large", onClick: (e) => e.stopPropagation(), children: [_jsxs("div", { className: "modal-header", children: [_jsxs("h2", { children: ["\uD83D\uDC41 \u9884\u89C8\u5267\u672C\uFF1A", previewDrama] }), _jsx("button", { onClick: () => setPreviewDrama(null), className: "btn-icon", children: "\u2715" })] }), _jsx("div", { className: "preview-tabs", children: DRAMA_FILES.map((f) => (_jsx("button", { className: previewFile === f ? 'active' : '', onClick: () => setPreviewFile(f), children: f }, f))) }), _jsx("div", { className: "preview-body", children: renderPreviewFile() })] }) })), initDrama && (_jsx("div", { className: "modal-overlay", onClick: () => setInitDrama(null), children: _jsxs("div", { className: "modal", onClick: (e) => e.stopPropagation(), children: [_jsxs("div", { className: "modal-header", children: [_jsxs("h2", { children: ["\u25B6 \u5BFC\u5165\u5267\u672C \"", initDrama, "\" \u4E3A\u65B0\u5B58\u6863"] }), _jsx("button", { onClick: () => setInitDrama(null), className: "btn-icon", children: "\u2715" })] }), _jsxs("div", { className: "form-group", children: [_jsx("label", { children: "\u65B0\u5B58\u6863\u540D" }), _jsx("input", { value: initSaveName, onChange: (e) => setInitSaveName(e.target.value), placeholder: "my_save" })] }), _jsx("div", { className: "form-group checkbox", children: _jsxs("label", { children: [_jsx("input", { type: "checkbox", checked: initOverwrite, onChange: (e) => setInitOverwrite(e.target.checked) }), "\u540C\u540D\u5B58\u6863\u5DF2\u5B58\u5728\u65F6\u8986\u76D6"] }) }), _jsxs("div", { className: "modal-actions", children: [_jsx("button", { onClick: () => setInitDrama(null), className: "btn-secondary", children: "\u53D6\u6D88" }), _jsx("button", { onClick: handleInit, disabled: initializing, className: "btn-primary", children: initializing ? '⏳ 导入中...' : '🚀 导入并进入游戏' })] })] }) })), validateDrama && validateResult && (_jsx("div", { className: "modal-overlay large", onClick: () => { setValidateDrama(null); setValidateResult(null); }, children: _jsxs("div", { className: "modal large", onClick: (e) => e.stopPropagation(), children: [_jsxs("div", { className: "modal-header", children: [_jsxs("h2", { children: [validateResult.ok ? '✅ ' : '❌ ', "\u6821\u9A8C\u7ED3\u679C\uFF1A", validateDrama] }), _jsx("button", { onClick: () => { setValidateDrama(null); setValidateResult(null); }, className: "btn-icon", children: "\u2715" })] }), _jsxs("div", { className: "validate-summary", children: [_jsx("div", { className: `validate-badge ${validateResult.ok ? 'ok' : 'fail'}`, children: validateResult.ok ? '通过' : `${validateResult.errors.length} 个严重错误` }), _jsxs("div", { className: "validate-counts", children: [_jsxs("span", { children: ["\u9519\u8BEF\uFF1A", _jsx("b", { style: { color: '#ef4444' }, children: validateResult.errors.length })] }), _jsxs("span", { children: ["\u8B66\u544A\uFF1A", _jsx("b", { style: { color: '#eab308' }, children: validateResult.warnings.length })] })] })] }), _jsxs("div", { className: "validate-info", children: [Object.entries(validateResult.info).length > 0 && (_jsxs("details", { open: true, children: [_jsx("summary", { children: "\uD83D\uDCCA \u4FE1\u606F\u7EDF\u8BA1" }), _jsx("pre", { style: { background: '#0d1117', padding: 10, borderRadius: 4, overflow: 'auto' }, children: JSON.stringify(validateResult.info, null, 2) })] })), validateResult.errors.length > 0 && (_jsxs("details", { open: true, children: [_jsxs("summary", { style: { color: '#ef4444' }, children: ["\u274C \u4E25\u91CD\u9519\u8BEF\uFF08", validateResult.errors.length, "\uFF0C\u963B\u65AD\u5BFC\u5165\uFF09"] }), _jsx("ul", { className: "validate-list errors", children: validateResult.errors.slice(0, 100).map((e, i) => (_jsxs("li", { children: ["\u2022 ", e] }, i))) })] })), validateResult.warnings.length > 0 && (_jsxs("details", { children: [_jsxs("summary", { style: { color: '#eab308' }, children: ["\u26A0\uFE0F \u8B66\u544A\uFF08", validateResult.warnings.length, "\uFF0C\u4E0D\u963B\u65AD\u4F46\u5EFA\u8BAE\u4FEE\u590D\uFF09"] }), _jsx("ul", { className: "validate-list warnings", children: validateResult.warnings.slice(0, 100).map((w, i) => (_jsxs("li", { children: ["\u2022 ", w] }, i))) })] }))] }), _jsx("div", { className: "modal-actions", children: _jsx("button", { onClick: () => { setValidateDrama(null); setValidateResult(null); }, className: "btn-primary", children: "\u5173\u95ED" }) })] }) }))] })] }));
}
