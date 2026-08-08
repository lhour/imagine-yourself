// 世界调度页：周期事件调度 + 信息传播追踪（E5）
//   tab 1: 周期事件（scheduled_events）— 查看/启停/创建/删除
//   tab 2: 信息传播追踪 — 定向传播触达状态 + 广播式媒体记录
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import AdminNav from '../components/AdminNav';
import { useGameStore } from '../store/gameStore';
import {
  scheduledEventsApi,
  propagationApi,
  type ScheduledEvent,
  type EventDissemination,
  type PublicKnowledgeRecord,
  type DisseminationStats,
} from '../api/client';

type Tab = 'scheduled' | 'propagation';

const PATTERN_LABELS: Record<string, string> = {
  daily: '每日',
  weekly: '每周',
  monthly: '每月',
  yearly: '每年',
  custom: '自定义',
  once_at: '单次',
};

const SCOPE_LABELS: Record<string, string> = {
  character: '角色',
  group: '群体',
  global: '全局',
};

const STATUS_LABELS: Record<string, string> = {
  pending: '待触达',
  arrived: '已触达',
  distorted: '已失真',
  lost: '已丢失',
};

const STATUS_COLORS: Record<string, string> = {
  pending: '#fbbf24',
  arrived: '#4ade80',
  distorted: '#f97316',
  lost: '#ef4444',
};

export default function WorldSchedulePage() {
  const setNotification = useGameStore((s) => s.setNotification);
  const setError = useGameStore((s) => s.setError);
  const [tab, setTab] = useState<Tab>('scheduled');

  return (
    <div className="admin-page">
      <AdminNav />
      <div className="admin-content world-schedule-page">
        <div className="admin-header">
          <h1>🌐 世界调度</h1>
          <div className="header-actions">
            <Link to="/gameplay" className="btn-secondary">← 玩法选项</Link>
          </div>
        </div>

        <div className="ws-tabs">
          <button
            className={`ws-tab${tab === 'scheduled' ? ' active' : ''}`}
            onClick={() => setTab('scheduled')}
          >
            ⏰ 周期事件调度
          </button>
          <button
            className={`ws-tab${tab === 'propagation' ? ' active' : ''}`}
            onClick={() => setTab('propagation')}
          >
            📡 信息传播追踪
          </button>
        </div>

        {tab === 'scheduled' && (
          <ScheduledEventsTab setNotification={setNotification} setError={setError} />
        )}
        {tab === 'propagation' && (
          <PropagationTab setNotification={setNotification} setError={setError} />
        )}
      </div>
    </div>
  );
}

// ============================================================
// Tab 1: 周期事件调度
// ============================================================

interface ScheduledEventsTabProps {
  setNotification: (msg: string | null) => void;
  setError: (msg: string | null) => void;
}

function ScheduledEventsTab({ setNotification, setError }: ScheduledEventsTabProps) {
  const [items, setItems] = useState<ScheduledEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeOnly, setActiveOnly] = useState(false);
  const [showCreate, setShowCreate] = useState(false);

  const refresh = async () => {
    setLoading(true);
    try {
      const r = await scheduledEventsApi.list({ active_only: activeOnly ? 1 : 0, limit: 200 });
      setItems(r.items ?? []);
    } catch (e: unknown) {
      setError(`加载周期事件失败：${e instanceof Error ? e.message : e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeOnly]);

  const handleToggle = async (item: ScheduledEvent) => {
    try {
      if (item.active === 1) {
        await scheduledEventsApi.deactivate(item.id);
      } else {
        await scheduledEventsApi.activate(item.id);
      }
      await refresh();
      setNotification(item.active === 1 ? `已停用：${item.title}` : `已激活：${item.title}`);
    } catch (e: unknown) {
      setError(`操作失败：${e instanceof Error ? e.message : e}`);
    }
  };

  const handleDelete = async (item: ScheduledEvent) => {
    if (!window.confirm(`确定删除周期事件「${item.title}」？`)) return;
    try {
      await scheduledEventsApi.delete(item.id);
      await refresh();
      setNotification(`已删除：${item.title}`);
    } catch (e: unknown) {
      setError(`删除失败：${e instanceof Error ? e.message : e}`);
    }
  };

  if (loading) {
    return <div className="loading">加载周期事件...</div>;
  }

  return (
    <div className="ws-tab-content">
      <div className="ws-toolbar">
        <label className="ws-filter">
          <input
            type="checkbox"
            checked={activeOnly}
            onChange={(e) => setActiveOnly(e.target.checked)}
          />
          <span>仅显示活跃</span>
        </label>
        <button className="btn-primary" onClick={() => setShowCreate(true)}>
          ➕ 新建周期事件
        </button>
      </div>

      {items.length === 0 ? (
        <div className="empty-hint">
          暂无周期事件。可新建周期事件（如每日上课、月度集日、年度祭典等），
          系统会在到期时自动生成对应事件。
        </div>
      ) : (
        <div className="ws-list">
          {items.map((item) => (
            <div key={item.id} className={`ws-card${item.active === 1 ? '' : ' inactive'}`}>
              <div className="ws-card-head">
                <span className="ws-card-title">{item.title}</span>
                <span
                  className="ws-status-badge"
                  style={{ background: item.active === 1 ? '#22c55e33' : '#6b728033', color: item.active === 1 ? '#4ade80' : '#9ca3af' }}
                >
                  {item.active === 1 ? '● 活跃' : '○ 停用'}
                </span>
              </div>
              {item.desc_raw && <div className="ws-card-desc">{item.desc_raw}</div>}
              <div className="ws-card-meta">
                <span>类型：{item.schedule_type === 'recurring' ? '周期' : '一次性'}</span>
                <span>频率：{PATTERN_LABELS[item.recurrence_pattern] || item.recurrence_pattern}</span>
                <span>范围：{SCOPE_LABELS[item.scope] || item.scope}</span>
                <span>重要度：{item.importance}</span>
                {item.next_trigger_game_time && (
                  <span>下次触发：{item.next_trigger_game_time}</span>
                )}
              </div>
              {item.trigger_condition_raw && (
                <div className="ws-card-condition">
                  <span className="ws-cond-label">触发条件：</span>
                  {item.trigger_condition_raw}
                </div>
              )}
              <div className="ws-card-actions">
                <button
                  className="btn-secondary btn-sm"
                  onClick={() => handleToggle(item)}
                >
                  {item.active === 1 ? '⏸ 停用' : '▶ 激活'}
                </button>
                <button
                  className="btn-danger btn-sm"
                  onClick={() => handleDelete(item)}
                >
                  🗑 删除
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreate && (
        <CreateScheduledEventModal
          onClose={() => setShowCreate(false)}
          onCreated={async () => {
            setShowCreate(false);
            await refresh();
          }}
          setNotification={setNotification}
          setError={setError}
        />
      )}
    </div>
  );
}

interface CreateModalProps {
  onClose: () => void;
  onCreated: () => void;
  setNotification: (msg: string | null) => void;
  setError: (msg: string | null) => void;
}

function CreateScheduledEventModal({ onClose, onCreated, setNotification, setError }: CreateModalProps) {
  const [form, setForm] = useState({
    title: '',
    desc_raw: '',
    importance: 3,
    schedule_type: 'recurring' as 'recurring' | 'one_shot',
    recurrence_pattern: 'daily',
    recurrence_detail_raw: '',
    next_trigger_game_time: '',
    scope: 'global' as 'character' | 'group' | 'global',
    trigger_condition_raw: '',
    expire_condition_raw: '',
  });
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!form.title.trim()) {
      setError('标题不能为空');
      return;
    }
    setSaving(true);
    try {
      await scheduledEventsApi.create({
        ...form,
        scope_target_json: [],
        event_template_json: {},
        created_by: 'human',
      });
      onCreated();
      setNotification(`已创建周期事件：${form.title}`);
    } catch (e: unknown) {
      setError(`创建失败：${e instanceof Error ? e.message : e}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 600 }}>
        <div className="modal-header">
          <h2>➕ 新建周期事件</h2>
          <button onClick={onClose} className="btn-icon">✕</button>
        </div>
        <div className="ws-form">
          <div className="form-group">
            <label>标题 *</label>
            <input
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="如：每日早课 / 月度集日 / 火山喷发预警"
            />
          </div>
          <div className="form-group">
            <label>描述</label>
            <textarea
              value={form.desc_raw}
              onChange={(e) => setForm({ ...form, desc_raw: e.target.value })}
              rows={2}
              placeholder="事件的详细描述"
            />
          </div>
          <div className="ws-form-row">
            <div className="form-group">
              <label>调度类型</label>
              <select
                value={form.schedule_type}
                onChange={(e) => setForm({ ...form, schedule_type: e.target.value as 'recurring' | 'one_shot' })}
              >
                <option value="recurring">周期（重复触发）</option>
                <option value="one_shot">一次性（触发后停用）</option>
              </select>
            </div>
            <div className="form-group">
              <label>频率</label>
              <select
                value={form.recurrence_pattern}
                onChange={(e) => setForm({ ...form, recurrence_pattern: e.target.value })}
              >
                {Object.entries(PATTERN_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label>范围</label>
              <select
                value={form.scope}
                onChange={(e) => setForm({ ...form, scope: e.target.value as 'character' | 'group' | 'global' })}
              >
                {Object.entries(SCOPE_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label>重要度 (0-5)</label>
              <input
                type="number"
                min={0}
                max={5}
                value={form.importance}
                onChange={(e) => setForm({ ...form, importance: Number(e.target.value) })}
              />
            </div>
          </div>
          <div className="form-group">
            <label>下次触发游戏时间</label>
            <input
              value={form.next_trigger_game_time}
              onChange={(e) => setForm({ ...form, next_trigger_game_time: e.target.value })}
              placeholder="如：源石纪元13年9月2日08时00分00秒"
            />
          </div>
          <div className="form-group">
            <label>触发条件（自然语言，可选）</label>
            <input
              value={form.trigger_condition_raw}
              onChange={(e) => setForm({ ...form, trigger_condition_raw: e.target.value })}
              placeholder="如：连续 3 天不下雨"
            />
          </div>
          <div className="form-group">
            <label>过期条件（自然语言，可选）</label>
            <input
              value={form.expire_condition_raw}
              onChange={(e) => setForm({ ...form, expire_condition_raw: e.target.value })}
              placeholder="如：主角离开此地图"
            />
          </div>
        </div>
        <div className="modal-actions">
          <button onClick={onClose} className="btn-secondary">取消</button>
          <button onClick={handleSave} disabled={saving} className="btn-primary">
            {saving ? '⏳ 保存中...' : '💾 创建'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// Tab 2: 信息传播追踪
// ============================================================

function PropagationTab({ setNotification, setError }: { setNotification: (msg: string | null) => void; setError: (msg: string | null) => void; }) {
  const [disseminations, setDisseminations] = useState<EventDissemination[]>([]);
  const [publicKnowledge, setPublicKnowledge] = useState<PublicKnowledgeRecord[]>([]);
  const [stats, setStats] = useState<DisseminationStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [subTab, setSubTab] = useState<'targeted' | 'broadcast'>('targeted');

  const refresh = async () => {
    setLoading(true);
    try {
      const [dResp, pkResp, stResp] = await Promise.all([
        propagationApi.listDisseminations({ status: statusFilter, limit: 200 }),
        propagationApi.listPublicKnowledge({ limit: 100 }),
        propagationApi.disseminationStats(),
      ]);
      setDisseminations(dResp.items ?? []);
      setPublicKnowledge(pkResp.items ?? []);
      setStats(stResp);
    } catch (e: unknown) {
      setError(`加载传播数据失败：${e instanceof Error ? e.message : e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  const handleMarkArrived = async (id: number) => {
    try {
      await propagationApi.markArrived(id);
      await refresh();
      setNotification(`已标记 #${id} 为已触达`);
    } catch (e: unknown) {
      setError(`操作失败：${e instanceof Error ? e.message : e}`);
    }
  };

  const handleMarkLost = async (id: number) => {
    try {
      await propagationApi.markLost(id);
      await refresh();
      setNotification(`已标记 #${id} 为已丢失`);
    } catch (e: unknown) {
      setError(`操作失败：${e instanceof Error ? e.message : e}`);
    }
  };

  if (loading) {
    return <div className="loading">加载传播数据...</div>;
  }

  return (
    <div className="ws-tab-content">
      {/* 统计概览 */}
      {stats && (
        <div className="ws-stats-row">
          <div className="ws-stat-card">
            <div className="ws-stat-label">总记录</div>
            <div className="ws-stat-value">{stats.total}</div>
          </div>
          {(['pending', 'arrived', 'distorted', 'lost'] as const).map((s) => (
            <div key={s} className="ws-stat-card">
              <div className="ws-stat-label" style={{ color: STATUS_COLORS[s] }}>
                {STATUS_LABELS[s]}
              </div>
              <div className="ws-stat-value" style={{ color: STATUS_COLORS[s] }}>
                {stats[s] || 0}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="ws-subtabs">
        <button
          className={`ws-subtab${subTab === 'targeted' ? ' active' : ''}`}
          onClick={() => setSubTab('targeted')}
        >
          📯 定向传播（{disseminations.length}）
        </button>
        <button
          className={`ws-subtab${subTab === 'broadcast' ? ' active' : ''}`}
          onClick={() => setSubTab('broadcast')}
        >
          📺 媒体广播（{publicKnowledge.length}）
        </button>
      </div>

      {subTab === 'targeted' && (
        <>
          <div className="ws-toolbar">
            <label className="ws-filter">
              <span>状态筛选：</span>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="">全部</option>
                {Object.entries(STATUS_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </label>
          </div>

          {disseminations.length === 0 ? (
            <div className="empty-hint">
              暂无定向传播记录。当事件带有传播媒介（口头/书信/电话等）时，
              系统会自动为目标角色创建触达追踪记录。
            </div>
          ) : (
            <div className="ws-table-wrap">
              <table className="ws-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>事件 ID</th>
                    <th>目标角色</th>
                    <th>状态</th>
                    <th>预期触达</th>
                    <th>实际触达</th>
                    <th>失真度</th>
                    <th>跳数</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {disseminations.map((d) => (
                    <tr key={d.id}>
                      <td>{d.id}</td>
                      <td>#{d.event_id}</td>
                      <td>角色#{d.target_char_id}</td>
                      <td>
                        <span
                          className="ws-status-badge"
                          style={{ background: `${STATUS_COLORS[d.status]}33`, color: STATUS_COLORS[d.status] }}
                        >
                          {STATUS_LABELS[d.status] || d.status}
                        </span>
                      </td>
                      <td className="ws-cell-time">{d.expected_arrival_game_time || '—'}</td>
                      <td className="ws-cell-time">{d.arrived_game_time || '—'}</td>
                      <td>
                        {d.distortion_level ? `${(d.distortion_level * 100).toFixed(0)}%` : '—'}
                      </td>
                      <td>{d.hops ?? '—'}</td>
                      <td>
                        {d.status === 'pending' && (
                          <>
                            <button className="btn-sm btn-secondary" onClick={() => handleMarkArrived(d.id)}>
                              ✓ 触达
                            </button>
                            <button className="btn-sm btn-danger" onClick={() => handleMarkLost(d.id)}>
                              ✗ 丢失
                            </button>
                          </>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {subTab === 'broadcast' && (
        <>
          {publicKnowledge.length === 0 ? (
            <div className="empty-hint">
              暂无媒体广播记录。当事件传播媒介为「媒体报道」时，
              系统会创建公共知识记录，角色是否获知由 reach_tags 动态判断。
            </div>
          ) : (
            <div className="ws-list">
              {publicKnowledge.map((pk) => (
                <div key={pk.id} className="ws-card">
                  <div className="ws-card-head">
                    <span className="ws-card-title">事件 #{pk.event_id}</span>
                    <span className="ws-status-badge" style={{ background: '#3b82f633', color: '#60a5fa' }}>
                      {pk.medium || '未知媒介'}
                    </span>
                  </div>
                  <div className="ws-card-meta">
                    <span>覆盖范围：{pk.coverage_scope || '—'}</span>
                    {pk.published_game_time && <span>发布时间：{pk.published_game_time}</span>}
                  </div>
                  {pk.version_raw && (
                    <div className="ws-card-desc">{pk.version_raw}</div>
                  )}
                  {pk.reach_tags_json && pk.reach_tags_json.length > 0 && (
                    <div className="ws-card-meta">
                      <span>触达标签：{pk.reach_tags_json.join(' / ')}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
