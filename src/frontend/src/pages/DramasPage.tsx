import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AdminNav from '../components/AdminNav';
import { dramasApi } from '../api/client';
import { useGameStore } from '../store/gameStore';

interface DramaItem {
  name: string;
  title: string;
  summary: string;
  protagonist_default?: string;
  start_game_time?: string;
  era_name?: string;
  files: string[];
}

interface PreviewData {
  [fileName: string]: unknown;
}

const DRAMA_FILES = [
  'meta.txt', 'characters.txt', 'groups.txt', 'group_hierarchies.txt',
  'items.txt', 'maps.txt', 'map_features.txt', 'events.txt',
  'settings.txt', 'plot_planning.txt',
];

// 从对象中提取显示名称：优先 name/title/key/id
function extractName(obj: Record<string, unknown>, idx: number): string {
  const candidates = ['name', 'title', 'key', 'id', 'char_name', 'group_name', 'map_name', 'item_name', 'feature_name'];
  for (const k of candidates) {
    const v = obj[k];
    if (typeof v === 'string' && v.trim()) return v;
    if (typeof v === 'number') return String(v);
  }
  return `第 ${idx + 1} 条`;
}

function tryParseJsonStr(v: unknown): unknown {
  if (typeof v !== 'string') return v;
  const s = v.trim();
  if ((s.startsWith('{') && s.endsWith('}')) || (s.startsWith('[') && s.endsWith(']'))) {
    try { return JSON.parse(s); } catch { /* ignore */ }
  }
  return v;
}

function PreviewObjCard({ obj, index }: { obj: Record<string, unknown>; index: number }) {
  const name = extractName(obj, index);
  // 隐藏纯标题字段，单独展示其他字段
  const titleKeys = new Set(['name', 'title', 'key', 'id']);
  const entries = Object.entries(obj).filter(([k]) => !titleKeys.has(k));
  return (
    <div className="preview-card">
      <div className="preview-card-header">
        <span className="preview-card-index">#{index + 1}</span>
        <span className="preview-card-name">· {name}</span>
      </div>
      <div className="preview-card-body">
        {entries.length === 0 ? (
          <span className="preview-card-empty">（无额外字段）</span>
        ) : (
          <table className="preview-card-table">
            <tbody>
              {entries.map(([k, v]) => {
                const parsed = tryParseJsonStr(v);
                const display = typeof parsed === 'object' && parsed !== null
                  ? JSON.stringify(parsed, null, 2)
                  : String(parsed ?? '');
                return (
                  <tr key={k}>
                    <td className="preview-card-key">{k}</td>
                    <td className="preview-card-val">
                      <pre>{display}</pre>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default function DramasPage() {
  const navigate = useNavigate();
  const setNotification = useGameStore((s) => s.setNotification);
  const setError = useGameStore((s) => s.setError);
  const switchSave = useGameStore((s) => s.switchSave);

  const [dramas, setDramas] = useState<DramaItem[]>([]);
  const [loading, setLoading] = useState(true);

  const [showGenerate, setShowGenerate] = useState(false);
  const [genPrompt, setGenPrompt] = useState('');
  const [genName, setGenName] = useState('');
  const [genStyle, setGenStyle] = useState('古风');
  const [genScale, setGenScale] = useState('中型');
  const [generating, setGenerating] = useState(false);

  const [previewDrama, setPreviewDrama] = useState<string | null>(null);
  const [previewData, setPreviewData] = useState<PreviewData | null>(null);
  const [previewFile, setPreviewFile] = useState<string>('meta.txt');

  const [initDrama, setInitDrama] = useState<string | null>(null);
  const [initSaveName, setInitSaveName] = useState('');
  const [initOverwrite, setInitOverwrite] = useState(false);
  const [initializing, setInitializing] = useState(false);

  // 校验结果弹窗
  const [validateDrama, setValidateDrama] = useState<string | null>(null);
  const [validateResult, setValidateResult] = useState<{
    ok: boolean; errors: string[]; warnings: string[]; info: Record<string, unknown>;
  } | null>(null);

  const refresh = async () => {
    setLoading(true);
    try {
      const list = await dramasApi.list();
      setDramas(list);
    } catch (e: unknown) {
      setError(`加载剧本列表失败：${e instanceof Error ? e.message : e}`);
    } finally {
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
      } else {
        setError(r.message || '一键生成功能尚未接入 LLM 管线（待阶段五）');
      }
    } catch (e: unknown) {
      setError(`生成失败：${e instanceof Error ? e.message : e}`);
    } finally {
      setGenerating(false);
    }
  };

  const handlePreview = async (name: string) => {
    try {
      const data = await dramasApi.preview(name);
      setPreviewDrama(name);
      setPreviewData(data);
      setPreviewFile('meta.txt');
    } catch (e: unknown) {
      setError(`预览失败：${e instanceof Error ? e.message : e}`);
    }
  };

  const handleDelete = async (name: string) => {
    if (!window.confirm(`确定删除剧本 "${name}"？此操作不可恢复。`)) return;
    try {
      await dramasApi.delete(name);
      setNotification(`已删除剧本 ${name}`);
      refresh();
    } catch (e: unknown) {
      setError(`删除失败：${e instanceof Error ? e.message : e}`);
    }
  };

  const handleValidate = async (name: string) => {
    try {
      const r = await dramasApi.validate(name);
      setValidateDrama(name);
      setValidateResult({
        ok: !!r.ok,
        errors: Array.isArray(r.errors) ? r.errors : [],
        warnings: Array.isArray(r.warnings) ? r.warnings : [],
        info: r.info || {},
      });
    } catch (e: unknown) {
      setError(`校验失败：${e instanceof Error ? e.message : e}`);
    }
  };

  const handleExport = async (name: string) => {
    try {
      const blob = await dramasApi.exportZip(name) as Blob;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${name}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setNotification(`已导出剧本 ${name}.zip`);
    } catch (e: unknown) {
      setError(`导出失败：${e instanceof Error ? e.message : e}`);
    }
  };

  const handleInit = async () => {
    if (!initDrama) return;
    if (!initSaveName.trim()) {
      setError('请填写存档名');
      return;
    }
    setInitializing(true);
    try {
      const r = await dramasApi.init(initDrama, initSaveName.trim(), initOverwrite);
      const stats = r.stats || {};
      setNotification(
        `剧本已导入！角色 ${stats.characters ?? 0} / 群体 ${stats.groups ?? 0} / 事件 ${stats.events ?? 0}`
      );
      // 切换激活存档并跳转
      await switchSave(initSaveName.trim());
      setInitDrama(null);
      setInitSaveName('');
      setInitOverwrite(false);
      navigate('/play');
    } catch (e: unknown) {
      setError(`导入失败：${e instanceof Error ? e.message : e}`);
    } finally {
      setInitializing(false);
    }
  };

  const renderPreviewFile = () => {
    if (!previewData) return null;
    const content = previewData[previewFile];
    if (content === null || content === undefined) {
      return <div className="preview-empty">（该文件不存在）</div>;
    }
    // meta.txt 结构化展示
    if (previewFile === 'meta.txt' && typeof content === 'object' && !Array.isArray(content)) {
      const entries = Object.entries(content as Record<string, unknown>);
      return (
        <table className="preview-card-table" style={{ width: '100%' }}>
          <tbody>
            {entries.map(([k, v]) => {
              const parsed = tryParseJsonStr(v);
              const display = typeof parsed === 'object' && parsed !== null
                ? JSON.stringify(parsed, null, 2)
                : String(parsed ?? '');
              return (
                <tr key={k}>
                  <td className="preview-card-key" style={{ width: 200 }}>{k}</td>
                  <td className="preview-card-val"><pre>{display}</pre></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      );
    }
    // 数组：卡片化展示
    if (Array.isArray(content)) {
      // 若全是字符串，还是按行展示（兼容简单格式）
      const allStrings = content.every((r) => typeof r === 'string');
      if (allStrings) {
        return (
          <div>
            <div className="preview-count">共 {content.length} 行</div>
            {(content as string[]).map((row, i) => (
              <pre key={i} className="preview-row">{row}</pre>
            ))}
          </div>
        );
      }
      // 对象数组 → 卡片
      return (
        <div className="preview-cards-grid">
          <div className="preview-count">共 {content.length} 条记录</div>
          {(content as Record<string, unknown>[]).map((row, i) => (
            <PreviewObjCard key={i} obj={row} index={i} />
          ))}
        </div>
      );
    }
    // 其他：字符串直接展示
    return <pre className="preview-row">{String(content)}</pre>;
  };

  return (
    <div className="admin-page">
      <AdminNav />
      <div className="admin-content">
        <div className="admin-header">
          <h1>📜 剧本管理</h1>
          <div className="header-actions">
            <button onClick={refresh} disabled={loading} className="btn-secondary">
              {loading ? '加载中...' : '🔄 刷新'}
            </button>
            <button onClick={() => setShowGenerate(true)} className="btn-primary">
              ✨ 一键生成剧本
            </button>
          </div>
        </div>

        {dramas.length === 0 && !loading ? (
          <div className="empty-state">
            <p>暂无剧本。可以手工编写或使用「一键生成」。</p>
          </div>
        ) : (
          <div className="drama-grid">
            {dramas.map((d) => (
              <div key={d.name} className="drama-card">
                <div className="drama-card-cover">
                  <span className="drama-cover-icon">📖</span>
                  <span className="drama-cover-files">{d.files.length} 文件</span>
                </div>
                <div className="drama-card-body">
                  <h3>{d.title}</h3>
                  <div className="drama-meta">
                    <span>📁 {d.name}</span>
                    <span>👤 {d.protagonist_default || '未指定'}</span>
                    <span>⏰ {d.start_game_time || '—'}</span>
                  </div>
                  <p className="drama-summary">{d.summary || '无简介'}</p>
                  <div className="drama-actions">
                    <button onClick={() => handlePreview(d.name)} className="btn-secondary">👁 预览</button>
                    <button onClick={() => handleValidate(d.name)} className="btn-secondary">✅ 校验</button>
                    <button onClick={() => handleExport(d.name)} className="btn-secondary">📦 导出zip</button>
                    <button
                      onClick={() => { setInitDrama(d.name); setInitSaveName(`${d.name}_run`); }}
                      className="btn-primary"
                    >
                      ▶ 导入新存档
                    </button>
                    <button onClick={() => handleDelete(d.name)} className="btn-icon btn-danger" title="删除">🗑</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 一键生成 Modal */}
        {showGenerate && (
          <div className="modal-overlay" onClick={() => setShowGenerate(false)}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h2>✨ 一键生成剧本</h2>
                <button onClick={() => setShowGenerate(false)} className="btn-icon">✕</button>
              </div>
              <div className="form-group">
                <label>提示词</label>
                <textarea
                  value={genPrompt}
                  onChange={(e) => setGenPrompt(e.target.value)}
                  placeholder="都市异能，主角沈默，上海市，白银时代..."
                  rows={4}
                />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>风格</label>
                  <select value={genStyle} onChange={(e) => setGenStyle(e.target.value)}>
                    <option>古风</option>
                    <option>科幻</option>
                    <option>都市</option>
                    <option>西幻</option>
                    <option>仙侠</option>
                    <option>自定义</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>规模</label>
                  <select value={genScale} onChange={(e) => setGenScale(e.target.value)}>
                    <option>小型（5 角色）</option>
                    <option>中型（15）</option>
                    <option>大型（30）</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>剧本名（可选）</label>
                  <input value={genName} onChange={(e) => setGenName(e.target.value)} placeholder="留空自动命名" />
                </div>
              </div>
              <div className="modal-actions">
                <button onClick={() => setShowGenerate(false)} className="btn-secondary">取消</button>
                <button onClick={handleGenerate} disabled={generating} className="btn-primary">
                  {generating ? '⏳ 生成中...' : '🚀 开始生成'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 预览 Modal */}
        {previewDrama && previewData && (
          <div className="modal-overlay large" onClick={() => setPreviewDrama(null)}>
            <div className="modal large" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h2>👁 预览剧本：{previewDrama}</h2>
                <button onClick={() => setPreviewDrama(null)} className="btn-icon">✕</button>
              </div>
              <div className="preview-tabs">
                {DRAMA_FILES.map((f) => (
                  <button
                    key={f}
                    className={previewFile === f ? 'active' : ''}
                    onClick={() => setPreviewFile(f)}
                  >
                    {f}
                  </button>
                ))}
              </div>
              <div className="preview-body">{renderPreviewFile()}</div>
            </div>
          </div>
        )}

        {/* 导入新存档 Modal */}
        {initDrama && (
          <div className="modal-overlay" onClick={() => setInitDrama(null)}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h2>▶ 导入剧本 "{initDrama}" 为新存档</h2>
                <button onClick={() => setInitDrama(null)} className="btn-icon">✕</button>
              </div>
              <div className="form-group">
                <label>新存档名</label>
                <input
                  value={initSaveName}
                  onChange={(e) => setInitSaveName(e.target.value)}
                  placeholder="my_save"
                />
              </div>
              <div className="form-group checkbox">
                <label>
                  <input
                    type="checkbox"
                    checked={initOverwrite}
                    onChange={(e) => setInitOverwrite(e.target.checked)}
                  />
                  同名存档已存在时覆盖
                </label>
              </div>
              <div className="modal-actions">
                <button onClick={() => setInitDrama(null)} className="btn-secondary">取消</button>
                <button onClick={handleInit} disabled={initializing} className="btn-primary">
                  {initializing ? '⏳ 导入中...' : '🚀 导入并进入游戏'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 校验结果弹窗 */}
        {validateDrama && validateResult && (
          <div className="modal-overlay large" onClick={() => { setValidateDrama(null); setValidateResult(null); }}>
            <div className="modal large" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h2>
                  {validateResult.ok ? '✅ ' : '❌ '}
                  校验结果：{validateDrama}
                </h2>
                <button onClick={() => { setValidateDrama(null); setValidateResult(null); }} className="btn-icon">✕</button>
              </div>
              <div className="validate-summary">
                <div className={`validate-badge ${validateResult.ok ? 'ok' : 'fail'}`}>
                  {validateResult.ok ? '通过' : `${validateResult.errors.length} 个严重错误`}
                </div>
                <div className="validate-counts">
                  <span>错误：<b style={{ color: '#ef4444' }}>{validateResult.errors.length}</b></span>
                  <span>警告：<b style={{ color: '#eab308' }}>{validateResult.warnings.length}</b></span>
                </div>
              </div>
              <div className="validate-info">
                {Object.entries(validateResult.info).length > 0 && (
                  <details open>
                    <summary>📊 信息统计</summary>
                    <pre style={{ background: '#0d1117', padding: 10, borderRadius: 4, overflow: 'auto' }}>
                      {JSON.stringify(validateResult.info, null, 2)}
                    </pre>
                  </details>
                )}
                {validateResult.errors.length > 0 && (
                  <details open>
                    <summary style={{ color: '#ef4444' }}>
                      ❌ 严重错误（{validateResult.errors.length}，阻断导入）
                    </summary>
                    <ul className="validate-list errors">
                      {validateResult.errors.slice(0, 100).map((e, i) => (
                        <li key={i}>• {e}</li>
                      ))}
                    </ul>
                  </details>
                )}
                {validateResult.warnings.length > 0 && (
                  <details>
                    <summary style={{ color: '#eab308' }}>
                      ⚠️ 警告（{validateResult.warnings.length}，不阻断但建议修复）
                    </summary>
                    <ul className="validate-list warnings">
                      {validateResult.warnings.slice(0, 100).map((w, i) => (
                        <li key={i}>• {w}</li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>
              <div className="modal-actions">
                <button onClick={() => { setValidateDrama(null); setValidateResult(null); }} className="btn-primary">
                  关闭
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
