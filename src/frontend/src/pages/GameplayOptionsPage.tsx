import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import AdminNav from '../components/AdminNav';
import { v5Api } from '../api/client';
import { useGameStore } from '../store/gameStore';

interface QuotaUsageItem {
  entity_type: string;
  name: string;
  allowed: boolean;
  per_tick: { current: number; limit: number };
  per_100tick: { current: number; limit: number };
  max_total: { current: number; limit: number };
}

interface GameplayOptions {
  player_sexuality: string;
  death_likelihood: number;
  favorability_bias: number;
  luck_bias: number;
  challenge_bias: number;
  writing_style: string;
  dynamic_entity: Record<string, {
    per_tick: number;
    per_100tick: number;
    max_total: number;
    allowed: boolean;
  }>;
  context_budget: {
    max_dynamic_entities_per_prompt: number;
    max_static_bytes: number;
    over_budget_policy: string;
  };
  world_modify_allowed: boolean;
}

const DEFAULT_OPTIONS: GameplayOptions = {
  player_sexuality: '异主角',
  death_likelihood: 3,
  favorability_bias: 0,
  luck_bias: 0,
  challenge_bias: 0,
  writing_style: '直白',
  dynamic_entity: {
    character: { per_tick: 1, per_100tick: 30, max_total: 120, allowed: true },
    group: { per_tick: 1, per_100tick: 10, max_total: 40, allowed: true },
    setting: { per_tick: 2, per_100tick: 30, max_total: 100, allowed: true },
    map: { per_tick: 1, per_100tick: 8, max_total: 25, allowed: true },
    map_feature: { per_tick: 3, per_100tick: 50, max_total: 200, allowed: true },
    item: { per_tick: 2, per_100tick: 30, max_total: 150, allowed: true },
  },
  context_budget: {
    max_dynamic_entities_per_prompt: 40,
    max_static_bytes: 12000,
    over_budget_policy: 'recency+importance',
  },
  world_modify_allowed: false,
};

const ENTITY_TYPE_NAMES: Record<string, string> = {
  character: '角色',
  group: '群体',
  setting: '设定',
  map: '地图',
  map_feature: '地图要素',
  item: '物品',
};

const SEXUALITY_OPTS = ['男', '女', '同主角', '异主角'];
const WRITING_STYLE_OPTS = ['直白', '隐晦', '写意', '克制'];
const BIAS_OPTS = [
  { v: -5, label: '极端(-5)' },
  { v: -3, label: '较低(-3)' },
  { v: -1, label: '略低(-1)' },
  { v: 0, label: '中性(0)' },
  { v: 1, label: '略高(1)' },
  { v: 3, label: '较高(3)' },
  { v: 5, label: '极端(5)' },
];

const DEATH_OPTS = [
  { v: 0, label: '几乎不会死' },
  { v: 1, label: '很少死亡' },
  { v: 2, label: '偶发死亡' },
  { v: 3, label: '正常概率' },
  { v: 4, label: '较频繁' },
  { v: 5, label: '频繁且残酷' },
];

export default function GameplayOptionsPage() {
  const setNotification = useGameStore((s) => s.setNotification);
  const setError = useGameStore((s) => s.setError);

  const [options, setOptions] = useState<GameplayOptions>(DEFAULT_OPTIONS);
  const [quotaUsage, setQuotaUsage] = useState<QuotaUsageItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const refresh = async () => {
    setLoading(true);
    try {
      const r = await v5Api.getGameplayOptions();
      const merged = { ...DEFAULT_OPTIONS, ...r.gameplay_options } as GameplayOptions;
      // 合并嵌套对象
      if (r.gameplay_options.dynamic_entity) {
        merged.dynamic_entity = {
          ...DEFAULT_OPTIONS.dynamic_entity,
          ...r.gameplay_options.dynamic_entity,
        };
      }
      if (r.gameplay_options.context_budget) {
        merged.context_budget = {
          ...DEFAULT_OPTIONS.context_budget,
          ...r.gameplay_options.context_budget,
        };
      }
      setOptions(merged);
      setQuotaUsage(r.quota_usage || []);
    } catch (e: unknown) {
      setError(`加载玩法选项失败：${e instanceof Error ? e.message : e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const result = await v5Api.setGameplayOptions(options);
      setOptions((result.gameplay_options as GameplayOptions) || options);
      await refresh();
      setNotification('玩法选项已保存');
    } catch (e: unknown) {
      setError(`保存失败：${e instanceof Error ? e.message : e}`);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (!window.confirm('确定重置为默认玩法选项？')) return;
    setOptions(DEFAULT_OPTIONS);
  };

  const updateOption = <K extends keyof GameplayOptions>(key: K, value: GameplayOptions[K]) => {
    setOptions((prev) => ({ ...prev, [key]: value }));
  };

  const updateDynamicEntity = (
    et: string,
    field: 'per_tick' | 'per_100tick' | 'max_total' | 'allowed',
    value: number | boolean,
  ) => {
    setOptions((prev) => ({
      ...prev,
      dynamic_entity: {
        ...prev.dynamic_entity,
        [et]: {
          ...prev.dynamic_entity[et],
          [field]: value,
        },
      },
    }));
  };

  const updateContextBudget = (
    field: keyof GameplayOptions['context_budget'],
    value: number | string,
  ) => {
    setOptions((prev) => ({
      ...prev,
      context_budget: {
        ...prev.context_budget,
        [field]: value,
      },
    }));
  };

  if (loading) {
    return (
      <div className="admin-page">
        <AdminNav />
        <div className="admin-content"><div className="loading">加载玩法选项...</div></div>
      </div>
    );
  }

  return (
    <div className="admin-page">
      <AdminNav />
      <div className="admin-content gameplay-options-page">
        <div className="admin-header">
          <h1>🎮 玩法选项配置</h1>
          <div className="header-actions">
            <button onClick={handleReset} className="btn-secondary">↩ 重置默认</button>
            <button onClick={handleSave} disabled={saving} className="btn-primary">
              {saving ? '⏳ 保存中...' : '💾 保存配置'}
            </button>
          </div>
        </div>

        <div style={{ marginBottom: 16, padding: '8px 12px', background: 'var(--accent-soft)', border: '1px solid var(--accent)', borderRadius: 6, fontSize: 13 }}>
          💾 当前为<strong>存档级</strong>配置（仅影响本存档，不影响剧本和其他存档）。剧本默认玩法可在「剧本管理」页面配置。
          <span style={{ marginLeft: 12, color: 'var(--accent)' }}>
            <Link to="/world-schedule">🌐 前往世界调度（周期事件 / 信息传播）→</Link>
          </span>
        </div>

        {/* 核心叙事选项 */}
        <section className="settings-section">
          <h2>🎭 叙事风格</h2>
          <div className="settings-fields">
            <div className="settings-field">
              <div className="settings-field-head">
                <label className="field-label">主角性取向</label>
                <div className="field-desc">决定叙事中主角对其他角色的情感视角</div>
              </div>
              <div className="settings-field-control">
                <select
                  value={options.player_sexuality}
                  onChange={(e) => updateOption('player_sexuality', e.target.value)}
                >
                  {SEXUALITY_OPTS.map((v) => (
                    <option key={v} value={v}>{v}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="settings-field">
              <div className="settings-field-head">
                <label className="field-label">叙事笔法</label>
                <div className="field-desc">描绘角色动作神态的写作风格</div>
              </div>
              <div className="settings-field-control">
                <select
                  value={options.writing_style}
                  onChange={(e) => updateOption('writing_style', e.target.value)}
                >
                  {WRITING_STYLE_OPTS.map((v) => (
                    <option key={v} value={v}>{v}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        </section>

        {/* 概率倾向 */}
        <section className="settings-section">
          <h2>⚖ 概率倾向</h2>
          <div className="settings-fields">
            <div className="settings-field">
              <div className="settings-field-head">
                <label className="field-label">死亡事件概率</label>
                <div className="field-desc">0=几乎不死，5=频繁且残酷</div>
              </div>
              <div className="settings-field-control">
                <select
                  value={options.death_likelihood}
                  onChange={(e) => updateOption('death_likelihood', Number(e.target.value))}
                >
                  {DEATH_OPTS.map((o) => (
                    <option key={o.v} value={o.v}>{o.label}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="settings-field">
              <div className="settings-field-head">
                <label className="field-label">好感度倾向</label>
                <div className="field-desc">正值容易增加好感，负值关系冷淡</div>
              </div>
              <div className="settings-field-control">
                <select
                  value={options.favorability_bias}
                  onChange={(e) => updateOption('favorability_bias', Number(e.target.value))}
                >
                  {BIAS_OPTS.map((o) => (
                    <option key={`f-${o.v}`} value={o.v}>{o.label}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="settings-field">
              <div className="settings-field-head">
                <label className="field-label">运气倾向</label>
                <div className="field-desc">正值容易遇好运，负值经常背运</div>
              </div>
              <div className="settings-field-control">
                <select
                  value={options.luck_bias}
                  onChange={(e) => updateOption('luck_bias', Number(e.target.value))}
                >
                  {BIAS_OPTS.map((o) => (
                    <option key={`l-${o.v}`} value={o.v}>{o.label}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="settings-field">
              <div className="settings-field-head">
                <label className="field-label">挑战倾向</label>
                <div className="field-desc">正值更多高难度挑战，负值更顺遂</div>
              </div>
              <div className="settings-field-control">
                <select
                  value={options.challenge_bias}
                  onChange={(e) => updateOption('challenge_bias', Number(e.target.value))}
                >
                  {BIAS_OPTS.map((o) => (
                    <option key={`c-${o.v}`} value={o.v}>{o.label}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        </section>

        {/* 动态实体配额 */}
        <section className="settings-section">
          <h2>📊 动态实体配额</h2>
          <div className="field-desc" style={{ marginBottom: 16 }}>
            控制模型在叙事中引入新实体的频率。三档限制：单 tick 上限、100 tick 累计、全局累计。
          </div>
          <div className="quota-table">
            <table>
              <thead>
                <tr>
                  <th>实体类型</th>
                  <th>允许</th>
                  <th>每 tick 上限</th>
                  <th>100 tick 累计</th>
                  <th>全局累计</th>
                  <th>当前使用</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(options.dynamic_entity).map(([et, q]) => {
                  const usage = quotaUsage.find((u) => u.entity_type === et);
                  return (
                    <tr key={et}>
                      <td className="entity-name">{ENTITY_TYPE_NAMES[et] || et}</td>
                      <td>
                        <label className="switch">
                          <input
                            type="checkbox"
                            checked={q.allowed}
                            onChange={(e) => updateDynamicEntity(et, 'allowed', e.target.checked)}
                          />
                          <span className="switch-slider" />
                        </label>
                      </td>
                      <td>
                        <input
                          type="number"
                          min={0}
                          max={20}
                          value={q.per_tick}
                          onChange={(e) => updateDynamicEntity(et, 'per_tick', Number(e.target.value))}
                          className="quota-input"
                        />
                      </td>
                      <td>
                        <input
                          type="number"
                          min={0}
                          max={500}
                          value={q.per_100tick}
                          onChange={(e) => updateDynamicEntity(et, 'per_100tick', Number(e.target.value))}
                          className="quota-input"
                        />
                      </td>
                      <td>
                        <input
                          type="number"
                          min={0}
                          max={10000}
                          value={q.max_total}
                          onChange={(e) => updateDynamicEntity(et, 'max_total', Number(e.target.value))}
                          className="quota-input"
                        />
                      </td>
                      <td className="quota-usage">
                        {usage && (
                          <span className="usage-badge">
                            {usage.per_tick.current}/{usage.per_tick.limit}
                            <span className="usage-sep">|</span>
                            {usage.per_100tick.current}/{usage.per_100tick.limit}
                            <span className="usage-sep">|</span>
                            {usage.max_total.current}/{usage.max_total.limit}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        {/* 上下文预算 */}
        <section className="settings-section">
          <h2>💾 上下文预算</h2>
          <div className="settings-fields">
            <div className="settings-field">
              <div className="settings-field-head">
                <label className="field-label">单次动态实体上限</label>
                <div className="field-desc">单次 tick 注入 prompt 的动态实体数上限</div>
              </div>
              <div className="settings-field-control">
                <input
                  type="number"
                  min={1}
                  max={200}
                  value={options.context_budget.max_dynamic_entities_per_prompt}
                  onChange={(e) => updateContextBudget('max_dynamic_entities_per_prompt', Number(e.target.value))}
                />
              </div>
            </div>

            <div className="settings-field">
              <div className="settings-field-head">
                <label className="field-label">恒定背景字节预算</label>
                <div className="field-desc">世界背景、核心设定等恒定信息的字节上限</div>
              </div>
              <div className="settings-field-control">
                <input
                  type="number"
                  min={1000}
                  max={100000}
                  step={1000}
                  value={options.context_budget.max_static_bytes}
                  onChange={(e) => updateContextBudget('max_static_bytes', Number(e.target.value))}
                />
              </div>
            </div>

            <div className="settings-field">
              <div className="settings-field-head">
                <label className="field-label">超预算策略</label>
                <div className="field-desc">超出预算时如何降级处理</div>
              </div>
              <div className="settings-field-control">
                <select
                  value={options.context_budget.over_budget_policy}
                  onChange={(e) => updateContextBudget('over_budget_policy', e.target.value)}
                >
                  <option value="recency+importance">最近+重要度优先</option>
                  <option value="recency">仅最近优先</option>
                  <option value="importance">仅重要度优先</option>
                </select>
              </div>
            </div>
          </div>
        </section>

        {/* 世界修改权限 */}
        <section className="settings-section">
          <h2>🔧 世界变更权限</h2>
          <div className="settings-fields">
            <div className="settings-field">
              <div className="settings-field-head">
                <label className="field-label">允许模型追加设定</label>
                <div className="field-desc">
                  开启后，模型可以在叙事中追加新的世界设定（不可删除初始设定）。
                  关闭时，模型无法修改或追加任何设定。
                </div>
              </div>
              <div className="settings-field-control">
                <label className="switch">
                  <input
                    type="checkbox"
                    checked={options.world_modify_allowed}
                    onChange={(e) => updateOption('world_modify_allowed', e.target.checked)}
                  />
                  <span className="switch-slider" />
                </label>
                <span style={{ marginLeft: 12, color: options.world_modify_allowed ? '#4ade80' : '#888' }}>
                  {options.world_modify_allowed ? '已开启 - 允许追加' : '已关闭 - 禁止修改'}
                </span>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
