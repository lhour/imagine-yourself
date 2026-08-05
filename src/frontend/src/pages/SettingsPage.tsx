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

  const update = (section: keyof ConfigData, field: string, value: unknown) => {
    if (!config) return;
    setConfig({
      ...config,
      [section]: {
        ...(config[section] || {}),
        [field]: value,
      },
    });
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
      <div className="admin-content">
        <div className="admin-header">
          <h1>⚙ 全局设置</h1>
          <div className="header-actions">
            <button onClick={handleReset} className="btn-secondary">↩ 重置默认</button>
            <button onClick={handleSave} disabled={saving} className="btn-primary">
              {saving ? '⏳ 保存中...' : '💾 保存'}
            </button>
          </div>
        </div>

        <div className="settings-sections">
          {/* UI 默认 */}
          <section>
            <h2>🖥 UI 默认值</h2>
            <div className="form-grid">
              <label>默认 TPS
                <input
                  type="number"
                  step="0.1"
                  value={config.ui_defaults?.default_tps ?? 1.0}
                  onChange={(e) => update('ui_defaults', 'default_tps', parseFloat(e.target.value))}
                />
              </label>
              <label>展示模式
                <select
                  value={config.ui_defaults?.default_era_display_mode ?? 'polished'}
                  onChange={(e) => update('ui_defaults', 'default_era_display_mode', e.target.value)}
                >
                  <option value="polished">润色版</option>
                  <option value="raw">原始版</option>
                </select>
              </label>
              <label>热力图透明度
                <input
                  type="number"
                  step="0.05"
                  min="0"
                  max="1"
                  value={config.ui_defaults?.default_heatmap_opacity ?? 0.55}
                  onChange={(e) => update('ui_defaults', 'default_heatmap_opacity', parseFloat(e.target.value))}
                />
              </label>
              <label>事件重要性阈值
                <input
                  type="number"
                  min="0"
                  max="5"
                  value={config.ui_defaults?.event_importance_threshold ?? 0}
                  onChange={(e) => update('ui_defaults', 'event_importance_threshold', parseInt(e.target.value))}
                />
              </label>
              <label>主题
                <select
                  value={config.ui_defaults?.theme ?? 'dark'}
                  onChange={(e) => update('ui_defaults', 'theme', e.target.value)}
                >
                  <option value="dark">深色</option>
                  <option value="light">浅色</option>
                </select>
              </label>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={config.ui_defaults?.show_debug_info ?? false}
                  onChange={(e) => update('ui_defaults', 'show_debug_info', e.target.checked)}
                />
                显示调试信息
              </label>
            </div>
          </section>

          {/* 模拟参数 */}
          <section>
            <h2>⏱ 模拟参数</h2>
            <div className="form-grid">
              <label>默认 TPS
                <input
                  type="number"
                  step="0.1"
                  value={config.simulation?.tps_default ?? 1.0}
                  onChange={(e) => update('simulation', 'tps_default', parseFloat(e.target.value))}
                />
              </label>
              <label>最大 TPS
                <input
                  type="number"
                  value={config.simulation?.tps_max ?? 240}
                  onChange={(e) => update('simulation', 'tps_max', parseFloat(e.target.value))}
                />
              </label>
              <label>每 tick 最大事件数
                <input
                  type="number"
                  value={config.simulation?.max_events_per_tick ?? 20}
                  onChange={(e) => update('simulation', 'max_events_per_tick', parseInt(e.target.value))}
                />
              </label>
              <label>每 tick 记忆衰减率
                <input
                  type="number"
                  step="0.005"
                  min="0"
                  max="1"
                  value={config.simulation?.memory_decay_per_tick ?? 0.01}
                  onChange={(e) => update('simulation', 'memory_decay_per_tick', parseFloat(e.target.value))}
                />
              </label>
              <label>热力图刷新间隔（tick）
                <input
                  type="number"
                  value={config.simulation?.heatmap_update_interval_ticks ?? 10}
                  onChange={(e) => update('simulation', 'heatmap_update_interval_ticks', parseInt(e.target.value))}
                />
              </label>
            </div>
          </section>

          {/* 记忆系统 */}
          <section>
            <h2>🧠 记忆系统</h2>
            <div className="form-grid">
              <label>检索默认上限
                <input
                  type="number"
                  value={config.memory?.retrieve_max_default ?? 30}
                  onChange={(e) => update('memory', 'retrieve_max_default', parseInt(e.target.value))}
                />
              </label>
              <label>宫殿默认深度
                <input
                  type="number"
                  min="1"
                  max="5"
                  value={config.memory?.palace_default_depth ?? 2}
                  onChange={(e) => update('memory', 'palace_default_depth', parseInt(e.target.value))}
                />
              </label>
              <label>索引采样率
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="1"
                  value={config.memory?.index_sampling_rate ?? 1.0}
                  onChange={(e) => update('memory', 'index_sampling_rate', parseFloat(e.target.value))}
                />
              </label>
            </div>
          </section>

          {/* LLM 管线 */}
          <section>
            <h2>🤖 LLM 管线</h2>
            <div className="form-grid">
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={config.llm_pipeline?.enabled ?? false}
                  onChange={(e) => update('llm_pipeline', 'enabled', e.target.checked)}
                />
                启用 LLM 管线（关闭时调用 /api/agent/tick 只更新元信息）
              </label>
              <label>Provider
                <select
                  value={config.llm_pipeline?.provider ?? 'stub'}
                  onChange={(e) => update('llm_pipeline', 'provider', e.target.value)}
                >
                  <option value="stub">stub（不调 LLM）</option>
                  <option value="deepseek">DeepSeek</option>
                  <option value="openai">OpenAI 兼容</option>
                </select>
              </label>
              <label>模型名
                <input
                  value={config.llm_pipeline?.model ?? ''}
                  placeholder="deepseek-v4-flash"
                  onChange={(e) => update('llm_pipeline', 'model', e.target.value)}
                />
              </label>
              <label>API Base
                <input
                  value={config.llm_pipeline?.api_base ?? ''}
                  placeholder="https://api.deepseek.com"
                  onChange={(e) => update('llm_pipeline', 'api_base', e.target.value)}
                />
              </label>
              <label>API Key（密文）
                <input
                  type="password"
                  value={config.llm_pipeline?.api_key ?? ''}
                  placeholder="sk-..."
                  onChange={(e) => update('llm_pipeline', 'api_key', e.target.value)}
                />
              </label>
              <label>单请求最大 Token
                <input
                  type="number"
                  value={config.llm_pipeline?.max_tokens_per_request ?? 2048}
                  onChange={(e) => update('llm_pipeline', 'max_tokens_per_request', parseInt(e.target.value))}
                />
              </label>
            </div>
            <div style={{ marginTop: 16, display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <button
                className={`btn-secondary test-conn-btn ${connStatus}`}
                onClick={handleTestConnection}
                disabled={connStatus === 'testing'}
              >
                <span className="dot" />
                {connStatus === 'testing' ? '测试中…' :
                  connStatus === 'ok' ? '✓ 连接成功' :
                    connStatus === 'fail' ? '✗ 连接失败' :
                      '🧪 测试连接'}
              </button>
              {connMsg && (
                <span className={connStatus === 'ok' ? 'muted' : ''} style={{
                  color: connStatus === 'fail' ? '#ef4444' : connStatus === 'ok' ? '#4ade80' : '#888',
                  fontSize: 12,
                }}>{connMsg}</span>
              )}
            </div>
          </section>

          {/* 内容偏好 */}
          <section>
            <h2>🎨 内容偏好</h2>
            <div className="form-grid">
              <label>润色长度（UI 默认）
                <select
                  value={config.ui_defaults?.default_polish_length ?? 'medium'}
                  onChange={(e) => update('ui_defaults', 'default_polish_length', e.target.value)}
                >
                  {POLISH_LEN_OPTS.map((o) => (
                    <option key={o.v} value={o.v}>{o.label}</option>
                  ))}
                </select>
              </label>
              <label>润色长度（模拟管线）
                <select
                  value={config.simulation?.polish_length ?? 'medium'}
                  onChange={(e) => update('simulation', 'polish_length', e.target.value)}
                >
                  {POLISH_LEN_OPTS.map((o) => (
                    <option key={o.v} value={o.v}>{o.label}</option>
                  ))}
                </select>
              </label>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={config.simulation?.gore_enabled ?? false}
                  onChange={(e) => update('simulation', 'gore_enabled', e.target.checked)}
                />
                允许血腥描写
              </label>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={config.simulation?.adult_content ?? false}
                  onChange={(e) => update('simulation', 'adult_content', e.target.checked)}
                />
                允许成人内容
              </label>
              <label style={{ gridColumn: '1 / -1' }}>
                暴力等级：{config.simulation?.violence_level ?? 2} / 5
                <input
                  type="range"
                  min={0} max={5} step={1}
                  value={config.simulation?.violence_level ?? 2}
                  onChange={(e) => update('simulation', 'violence_level', Number(e.target.value))}
                />
              </label>
            </div>
          </section>

          {/* 日志配置 */}
          <section>
            <h2>📝 日志配置</h2>
            <div className="form-grid">
              <label style={{ gridColumn: '1 / -1' }}>
                日志目录（LOG_DIR，相对于项目根或绝对路径）
                <input
                  type="text"
                  value={config.logging?.log_dir ?? 'logs/'}
                  onChange={(e) => update('logging', 'log_dir', e.target.value)}
                  placeholder="logs/ 或 D:/game_logs/"
                />
              </label>
              <label>日志级别
                <select
                  value={config.logging?.log_level ?? 'info'}
                  onChange={(e) => update('logging', 'log_level', e.target.value)}
                >
                  <option value="debug">DEBUG（详细）</option>
                  <option value="info">INFO（默认）</option>
                  <option value="warn">WARN（仅警告）</option>
                  <option value="error">ERROR（仅错误）</option>
                </select>
              </label>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={config.logging?.console_log_enabled ?? true}
                  onChange={(e) => update('logging', 'console_log_enabled', e.target.checked)}
                />
                同步输出到控制台
              </label>
            </div>
          </section>

          {/* 快照策略 */}
          <section>
            <h2>💾 快照策略</h2>
            <div className="form-grid">
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={config.snapshots?.auto_snapshot_enabled ?? false}
                  onChange={(e) => update('snapshots', 'auto_snapshot_enabled', e.target.checked)}
                />
                启用自动快照
              </label>
              <label>自动快照间隔（tick 数）
                <input
                  type="number"
                  min={1}
                  value={config.snapshots?.auto_snapshot_interval_ticks ?? 100}
                  onChange={(e) => update('snapshots', 'auto_snapshot_interval_ticks', parseInt(e.target.value))}
                />
              </label>
              <label>每存档最大快照数（超过自动删除最旧）
                <input
                  type="number"
                  min={1}
                  value={config.snapshots?.max_snapshots_per_save ?? 50}
                  onChange={(e) => update('snapshots', 'max_snapshots_per_save', parseInt(e.target.value))}
                />
              </label>
              <label>保留每日快照数（0=不单独保留）
                <input
                  type="number"
                  min={0}
                  value={config.snapshots?.keep_daily_snapshots ?? 1}
                  onChange={(e) => update('snapshots', 'keep_daily_snapshots', parseInt(e.target.value))}
                />
              </label>
            </div>
          </section>

          {/* 隐私 */}
          <section>
            <h2>🔒 隐私</h2>
            <div className="form-grid">
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={config.privacy?.allow_data_collection ?? false}
                  onChange={(e) => update('privacy', 'allow_data_collection', e.target.checked)}
                />
                允许匿名数据采集
              </label>
              <label>数据保留天数（0=永久）
                <input
                  type="number"
                  min="0"
                  value={config.privacy?.retention_days ?? 0}
                  onChange={(e) => update('privacy', 'retention_days', parseInt(e.target.value))}
                />
              </label>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
