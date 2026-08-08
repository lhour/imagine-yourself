import { useEffect, useState } from 'react';
import AdminNav from '../components/AdminNav';
import { configApi, agentApi } from '../api/client';
import { useGameStore } from '../store/gameStore';

interface ConfigData {
  ui_defaults?: {
    default_tps?: number;
    default_era_display_mode?: string;
    default_heatmap_opacity?: number;
    default_map_zoom?: number;
    event_importance_threshold?: number;
    show_debug_info?: boolean;
    theme?: string;
    default_polish_length?: 'short' | 'medium' | 'long' | 'epic';
  };
  simulation?: {
    tps_default?: number;
    tps_min?: number;
    tps_max?: number;
    max_events_per_tick?: number;
    memory_decay_per_tick?: number;
    heatmap_update_interval_ticks?: number;
    polish_length?: 'short' | 'medium' | 'long' | 'epic';
    gore_enabled?: boolean;
    adult_content?: boolean;
    violence_level?: number;
  };
  memory?: {
    retrieve_max_default?: number;
    palace_default_depth?: number;
    index_sampling_rate?: number;
  };
  llm_pipeline?: {
    enabled?: boolean;
    provider?: string;
    model?: string;
    api_base?: string;
    api_key?: string;
    max_tokens_per_request?: number;
  };
  privacy?: {
    allow_data_collection?: boolean;
    retention_days?: number;
  };
  logging?: {
    log_dir?: string;
    log_level?: 'debug' | 'info' | 'warn' | 'error';
    console_log_enabled?: boolean;
  };
  snapshots?: {
    auto_snapshot_enabled?: boolean;
    auto_snapshot_interval_ticks?: number;
    max_snapshots_per_save?: number;
    keep_daily_snapshots?: number;
  };
}

const POLISH_LEN_OPTS = [
  { v: 'short', label: '短（1句）' },
  { v: 'medium', label: '中（3~5句）' },
  { v: 'long', label: '长（段落）' },
  { v: 'epic', label: '史诗（多段）' },
] as const;

type ConnStatus = 'idle' | 'testing' | 'ok' | 'fail';

/** 单个表单字段的描述信息，用于生成说明文字 */
interface FieldDef {
  key: string;          // 形如 "ui_defaults.default_tps"
  label: string;        // 显示名
  description: string; // 说明文字
  type: 'number' | 'text' | 'password' | 'select' | 'checkbox' | 'range';
  placeholder?: string;
  options?: { v: string | number; label: string }[];
  min?: number;
  max?: number;
  step?: number;
  defaultVal?: unknown;
}

const FIELDS: FieldDef[] = [
  // UI 默认
  { key: 'ui_defaults.default_tps', label: '默认 TPS', description: 'UI 中每秒推进的 tick 数，影响时间推进速度的体感', type: 'number', step: 0.1, defaultVal: 1.0 },
  { key: 'ui_defaults.default_era_display_mode', label: '展示模式', description: '剧情文本默认展示哪一层：润色版（经过 polisher）或原始版（LLM 直出）', type: 'select', options: [{ v: 'polished', label: '润色版' }, { v: 'raw', label: '原始版' }], defaultVal: 'polished' },
  { key: 'ui_defaults.default_heatmap_opacity', label: '热力图透明度', description: '地图上群体热力图默认透明度（0–1）', type: 'number', min: 0, max: 1, step: 0.05, defaultVal: 0.55 },
  { key: 'ui_defaults.event_importance_threshold', label: '事件重要性阈值', description: '低于该重要性的事件不会在 UI 中高亮显示', type: 'number', min: 0, max: 5, defaultVal: 0 },
  { key: 'ui_defaults.theme', label: '主题', description: '前端 UI 主题色', type: 'select', options: [{ v: 'dark', label: '深色' }, { v: 'light', label: '浅色' }], defaultVal: 'dark' },
  { key: 'ui_defaults.show_debug_info', label: '显示调试信息', description: '是否在 UI 中额外显示调试数据（如 ID、坐标、中间态）', type: 'checkbox', defaultVal: false },
  { key: 'ui_defaults.default_polish_length', label: '润色长度（UI 默认）', description: '玩家切换润色长度时的默认选择', type: 'select', options: POLISH_LEN_OPTS.map((o) => ({ v: o.v, label: o.label })), defaultVal: 'medium' },

  // 模拟参数
  { key: 'simulation.tps_default', label: '模拟默认 TPS', description: '管线内每 tick 推进的虚拟秒数，决定世界演化节奏', type: 'number', step: 0.1, defaultVal: 1.0 },
  { key: 'simulation.tps_max', label: '模拟最大 TPS', description: '时间跨越时单次 tick 最多推进的秒数上限，防止一次性过大跳变', type: 'number', defaultVal: 240 },
  { key: 'simulation.max_events_per_tick', label: '每 tick 最大事件数', description: '每个 tick 最多生成/推进的事件数量，避免 LLM 输出过长', type: 'number', defaultVal: 20 },
  { key: 'simulation.memory_decay_per_tick', label: '每 tick 记忆衰减率', description: '每 tick 后所有记忆 importance 衰减的比例（0–1），值越大记忆越容易被遗忘', type: 'number', min: 0, max: 1, step: 0.005, defaultVal: 0.01 },
  { key: 'simulation.heatmap_update_interval_ticks', label: '热力图刷新间隔（tick）', description: '每 N 个 tick 刷新一次世界/群体热力图', type: 'number', defaultVal: 10 },
  { key: 'simulation.polish_length', label: '润色长度（管线）', description: 'polisher skill 默认输出的长度档位', type: 'select', options: POLISH_LEN_OPTS.map((o) => ({ v: o.v, label: o.label })), defaultVal: 'medium' },
  { key: 'simulation.gore_enabled', label: '允许血腥描写', description: '打开后，polisher 允许较强烈的血腥描写', type: 'checkbox', defaultVal: false },
  { key: 'simulation.adult_content', label: '允许成人内容', description: '打开后，polisher 允许较露骨的成人向描写', type: 'checkbox', defaultVal: false },
  { key: 'simulation.violence_level', label: '暴力等级', description: '0–5，暴力描写的上限档位', type: 'range', min: 0, max: 5, step: 1, defaultVal: 2 },

  // 记忆系统
  { key: 'memory.retrieve_max_default', label: '检索默认上限', description: 'memory_retrieve 工具默认返回的最大条数', type: 'number', defaultVal: 30 },
  { key: 'memory.palace_default_depth', label: '宫殿默认深度', description: '记忆宫殿默认层级深度（1–5），越深越结构化但越慢', type: 'number', min: 1, max: 5, defaultVal: 2 },
  { key: 'memory.index_sampling_rate', label: '索引采样率', description: '记忆写入索引时的采样率（0–1），值越小索引越稀疏', type: 'number', min: 0, max: 1, step: 0.1, defaultVal: 1.0 },

  // LLM 管线
  { key: 'llm_pipeline.enabled', label: '启用 LLM 管线', description: '关闭时 tick/advance 只更新元信息，不调用 LLM', type: 'checkbox', defaultVal: false },
  { key: 'llm_pipeline.provider', label: 'Provider', description: '选择要使用的 LLM 提供方', type: 'select', options: [
    { v: 'stub', label: 'stub（不调 LLM）' },
    { v: 'deepseek', label: 'DeepSeek' },
    { v: 'openai', label: 'OpenAI 兼容' },
  ], defaultVal: 'stub' },
  { key: 'llm_pipeline.model', label: '模型名', description: '要调用的具体模型名（需与 Provider 匹配）', type: 'text', placeholder: 'deepseek-v4-flash', defaultVal: '' },
  { key: 'llm_pipeline.api_base', label: 'API Base', description: 'LLM 服务端点 URL', type: 'text', placeholder: 'https://api.deepseek.com', defaultVal: '' },
  { key: 'llm_pipeline.api_key', label: 'API Key', description: '用于访问 LLM 服务的密钥（会加密存储，展示时隐藏）', type: 'password', placeholder: 'sk-...', defaultVal: '' },
  { key: 'llm_pipeline.max_tokens_per_request', label: '单请求最大 Token', description: '单次 LLM 请求的最大 token 上限', type: 'number', defaultVal: 2048 },

  // 内容偏好（补充 UI 字段引用）
  // (已在 ui_defaults.default_polish_length / simulation.polish_length 中覆盖)

  // 日志
  { key: 'logging.log_dir', label: '日志目录（LOG_DIR）', description: '日志落盘目录。支持绝对路径或相对项目根路径（如 logs/）', type: 'text', placeholder: 'logs/ 或 D:/game_logs/', defaultVal: 'logs/' },
  { key: 'logging.log_level', label: '日志级别', description: '仅该级别以上的日志会写入文件', type: 'select', options: [
    { v: 'debug', label: 'DEBUG（详细）' },
    { v: 'info', label: 'INFO（默认）' },
    { v: 'warn', label: 'WARN（仅警告）' },
    { v: 'error', label: 'ERROR（仅错误）' },
  ], defaultVal: 'info' },
  { key: 'logging.console_log_enabled', label: '同步输出到控制台', description: '开启后，日志也会输出到后端 stdout', type: 'checkbox', defaultVal: true },

  // 快照
  { key: 'snapshots.auto_snapshot_enabled', label: '启用自动快照', description: '开启后会按间隔自动保存游戏快照', type: 'checkbox', defaultVal: false },
  { key: 'snapshots.auto_snapshot_interval_ticks', label: '自动快照间隔（tick）', description: '每 N 个 tick 自动存一次快照', type: 'number', min: 1, defaultVal: 100 },
  { key: 'snapshots.max_snapshots_per_save', label: '每存档最大快照数', description: '超过后自动删除最旧的快照', type: 'number', min: 1, defaultVal: 50 },
  { key: 'snapshots.keep_daily_snapshots', label: '保留每日快照数', description: '每日保留 N 份快照作为长期归档（0 = 不保留）', type: 'number', min: 0, defaultVal: 1 },

  // 隐私
  { key: 'privacy.allow_data_collection', label: '允许匿名数据采集', description: '开启后允许收集匿名运行数据用于质量提升', type: 'checkbox', defaultVal: false },
  { key: 'privacy.retention_days', label: '数据保留天数', description: '日志与匿名数据保留天数（0 = 永久）', type: 'number', min: 0, defaultVal: 0 },
];

const SECTIONS: { id: string; title: string; icon: string; fields: string[] }[] = [
  { id: 'ui', title: 'UI 默认值', icon: '🖥', fields: FIELDS.filter((f) => f.key.startsWith('ui_defaults')).map((f) => f.key) },
  { id: 'sim', title: '模拟参数', icon: '⏱', fields: FIELDS.filter((f) => f.key.startsWith('simulation')).map((f) => f.key) },
  { id: 'mem', title: '记忆系统', icon: '🧠', fields: FIELDS.filter((f) => f.key.startsWith('memory')).map((f) => f.key) },
  { id: 'llm', title: 'LLM 管线', icon: '🤖', fields: FIELDS.filter((f) => f.key.startsWith('llm_pipeline')).map((f) => f.key) },
  { id: 'log', title: '日志配置', icon: '📝', fields: FIELDS.filter((f) => f.key.startsWith('logging')).map((f) => f.key) },
  { id: 'snap', title: '快照策略', icon: '💾', fields: FIELDS.filter((f) => f.key.startsWith('snapshots')).map((f) => f.key) },
  { id: 'priv', title: '隐私', icon: '🔒', fields: FIELDS.filter((f) => f.key.startsWith('privacy')).map((f) => f.key) },
];

function getDefault(def: unknown) {
  return def;
}

export default function SettingsPage() {
  const setNotification = useGameStore((s) => s.setNotification);
  const setError = useGameStore((s) => s.setError);

  const [config, setConfig] = useState<ConfigData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [connStatus, setConnStatus] = useState<ConnStatus>('idle');
  const [connMsg, setConnMsg] = useState<string>('');

  const refresh = async () => {
    setLoading(true);
    try {
      const r = await configApi.get();
      setConfig(r.config);
    } catch (e: unknown) {
      setError(`加载配置失败：${e instanceof Error ? e.message : e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const getNested = (cfg: ConfigData, key: string): unknown => {
    const parts = key.split('.');
    let cur: unknown = cfg;
    for (const p of parts) {
      if (cur && typeof cur === 'object' && p in (cur as Record<string, unknown>)) {
        cur = (cur as Record<string, unknown>)[p];
      } else {
        return undefined;
      }
    }
    return cur;
  };

  const setNested = (cfg: ConfigData, key: string, value: unknown): ConfigData => {
    const parts = key.split('.');
    const out: ConfigData = JSON.parse(JSON.stringify(cfg));
    let cur: Record<string, unknown> = out as Record<string, unknown>;
    for (let i = 0; i < parts.length - 1; i++) {
      const p = parts[i];
      if (!(p in cur) || typeof cur[p] !== 'object' || cur[p] === null) {
        cur[p] = {};
      }
      cur = cur[p] as Record<string, unknown>;
    }
    cur[parts[parts.length - 1]] = value;
    return out;
  };

  const update = (key: string, value: unknown) => {
    if (!config) return;
    setConfig(setNested(config, key, value));
  };

  const getFieldValue = (f: FieldDef): unknown => {
    if (!config) return getDefault(f.defaultVal);
    const v = getNested(config, f.key);
    if (v === undefined || v === null || v === '') return getDefault(f.defaultVal);
    return v;
  };

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    try {
      const r = await configApi.patch(config as Record<string, unknown>);
      setConfig(r.config);
      setNotification(`已更新字段：${(r.updated_keys || []).join(', ')}`);
    } catch (e: unknown) {
      setError(`保存失败：${e instanceof Error ? e.message : e}`);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!window.confirm('确定重置全部配置为默认值？')) return;
    try {
      const r = await configApi.reset();
      setConfig(r.config);
      setNotification('已重置为默认配置');
    } catch (e: unknown) {
      setError(`重置失败：${e instanceof Error ? e.message : e}`);
    }
  };

  const handleTestConnection = async () => {
    setConnStatus('testing');
    setConnMsg('');
    try {
      const body: { model?: string; api_base?: string; api_key?: string } = {};
      if (config?.llm_pipeline?.model) body.model = config.llm_pipeline.model;
      const r = await agentApi.testConnection(body);
      if (r.ok) {
        setConnStatus('ok');
        setConnMsg(r.message || `连接成功（模型：${r.model || 'default'}，耗时 ${r.latency_ms ?? '?'}ms）`);
        setNotification('API 连接测试通过');
      } else {
        setConnStatus('fail');
        setConnMsg(r.message || '连接失败：未知错误');
      }
    } catch (e: unknown) {
      setConnStatus('fail');
      const msg = e instanceof Error ? e.message : String(e);
      setConnMsg(`请求异常：${msg}`);
    }
  };

  if (loading || !config) {
    return (
      <div className="admin-page">
        <AdminNav />
        <div className="admin-content"><div className="loading">加载中...</div></div>
      </div>
    );
  }

  return (
    <div className="admin-page">
      <AdminNav />
      <div className="admin-content settings-page">
        <div className="admin-header">
          <h1>⚙ 全局设置</h1>
          <div className="header-actions">
            <button onClick={handleReset} className="btn-secondary">↩ 重置默认</button>
            <button onClick={handleSave} disabled={saving} className="btn-primary">
              {saving ? '⏳ 保存中...' : '💾 保存'}
            </button>
          </div>
        </div>

        <div className="settings-sections-vertical">
          {SECTIONS.map((sec) => (
            <section key={sec.id} className="settings-section">
              <h2>{sec.icon} {sec.title}</h2>
              <div className="settings-fields">
                {sec.fields.map((key) => {
                  const f = FIELDS.find((x) => x.key === key)!;
                  const val = getFieldValue(f);
                  const commonLabel = (
                    <label className="field-label" htmlFor={`field-${f.key}`}>
                      {f.label}
                    </label>
                  );
                  const desc = <div className="field-desc">{f.description}</div>;

                  let control: React.ReactNode;
                  switch (f.type) {
                    case 'select':
                      control = (
                        <select
                          id={`field-${f.key}`}
                          value={String(val ?? '')}
                          onChange={(e) => update(f.key, e.target.value)}
                        >
                          {(f.options || []).map((o) => (
                            <option key={String(o.v)} value={String(o.v)}>{o.label}</option>
                          ))}
                        </select>
                      );
                      break;
                    case 'checkbox':
                      control = (
                        <div className="field-checkbox-row">
                          <input
                            id={`field-${f.key}`}
                            type="checkbox"
                            checked={Boolean(val)}
                            onChange={(e) => update(f.key, e.target.checked)}
                          />
                          <span className="checkbox-text">{Boolean(val) ? '开启' : '关闭'}</span>
                        </div>
                      );
                      break;
                    case 'range':
                      control = (
                        <div>
                          <div className="field-range-value">{val as number} / {(f.max ?? 5)}</div>
                          <input
                            id={`field-${f.key}`}
                            type="range"
                            min={f.min}
                            max={f.max}
                            step={f.step}
                            value={val as number}
                            onChange={(e) => update(f.key, Number(e.target.value))}
                          />
                        </div>
                      );
                      break;
                    case 'password':
                      control = (
                        <input
                          id={`field-${f.key}`}
                          type="password"
                          value={String(val ?? '')}
                          onChange={(e) => update(f.key, e.target.value)}
                          placeholder={f.placeholder}
                          autoComplete="new-password"
                        />
                      );
                      break;
                    case 'number':
                      control = (
                        <input
                          id={`field-${f.key}`}
                          type="number"
                          step={f.step}
                          min={f.min}
                          max={f.max}
                          value={val as number | string}
                          onChange={(e) => update(f.key, Number(e.target.value))}
                        />
                      );
                      break;
                    case 'text':
                    default:
                      control = (
                        <input
                          id={`field-${f.key}`}
                          type="text"
                          value={String(val ?? '')}
                          onChange={(e) => update(f.key, e.target.value)}
                          placeholder={f.placeholder}
                        />
                      );
                  }

                  const row = (
                    <div className="settings-field" key={f.key}>
                      <div className="settings-field-head">
                        {commonLabel}
                        {desc}
                      </div>
                      <div className="settings-field-control">
                        {control}
                      </div>
                    </div>
                  );
                  // 在 llm_pipeline 区块尾部插入测试连接按钮
                  if (f.key === 'llm_pipeline.max_tokens_per_request') {
                    return (
                      <div key="llm_max_tokens_and_test" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                        {row}
                        <div className="conn-test-row">
                          <button
                            className={`btn-secondary test-conn-btn ${connStatus}`}
                            onClick={handleTestConnection}
                            disabled={connStatus === 'testing'}
                          >
                            <span className="dot" />
                            {connStatus === 'testing' ? '测试中…' :
                              connStatus === 'ok' ? '✓ 连接成功' :
                                connStatus === 'fail' ? '✗ 连接失败' :
                                  '🧪 测试 API 连接'}
                          </button>
                          {connMsg && (
                            <span style={{
                              color: connStatus === 'fail' ? '#ef4444' : connStatus === 'ok' ? '#4ade80' : '#888',
                              fontSize: 12,
                            }}>{connMsg}</span>
                          )}
                        </div>
                      </div>
                    );
                  }
                  return row;
                })}
              </div>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
