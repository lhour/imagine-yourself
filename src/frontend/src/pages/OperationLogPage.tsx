import { useEffect, useState } from 'react';
import AdminNav from '../components/AdminNav';
import { v5Api } from '../api/client';
import { useGameStore } from '../store/gameStore';
import './OperationLogPage.css';

interface QuotaUsageItem {
  entity_type: string;
  name: string;
  allowed: boolean;
  per_tick: { current: number; limit: number };
  per_100tick: { current: number; limit: number };
  max_total: { current: number; limit: number };
}

interface OperationLog {
  id: number;
  op_type: string;
  op_entity_type: string | null;
  op_entity_id: number | null;
  actor: string;
  tool: string;
  args_json: string;
  result_json: string;
  tick_num: number;
  game_time: string;
  created_at: string;
  success: number;
  error_msg: string | null;
}

interface LogSummary {
  total: number;
  by_type: Record<string, number>;
  dynamic_entities: {
    entity_type: string;
    entity_id: number;
    tool: string;
    tick: number;
    created_at: string;
  }[];
}

const ENTITY_TYPE_NAMES: Record<string, string> = {
  character: '角色',
  group: '群体',
  setting: '设定',
  map: '地图',
  map_feature: '地图要素',
  item: '物品',
};

const OP_TYPE_NAMES: Record<string, string> = {
  create_dynamic_entity: '动态创建实体',
  append_setting: '追加设定',
  append_world_note: '追加世界说明',
  web_fetch: '网络抓取',
  kb_add: '知识库添加',
  kb_search: '知识库检索',
};

export default function OperationLogPage() {
  const setError = useGameStore((s) => s.setError);

  const [quotaUsage, setQuotaUsage] = useState<QuotaUsageItem[]>([]);
  const [logs, setLogs] = useState<OperationLog[]>([]);
  const [summary, setSummary] = useState<LogSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterType, setFilterType] = useState('');
  const [filterEntity, setFilterEntity] = useState('');
  const [selectedLog, setSelectedLog] = useState<OperationLog | null>(null);

  const refresh = async () => {
    setLoading(true);
    try {
      const [quotaResp, logsResp, summaryResp] = await Promise.all([
        v5Api.getEntityQuota(),
        v5Api.queryOperationLog({ limit: 100 }),
        v5Api.getOperationLogSummary(),
      ]);
      setQuotaUsage(quotaResp.quota_usage || []);
      setLogs((logsResp.logs || []) as unknown as OperationLog[]);
      setSummary(summaryResp || null);
    } catch (e: unknown) {
      setError(`加载操作日志失败：${e instanceof Error ? e.message : e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filteredLogs = logs.filter((log) => {
    if (filterType && log.op_type !== filterType) return false;
    if (filterEntity && log.op_entity_type !== filterEntity) return false;
    return true;
  });

  const formatArgs = (jsonStr: string) => {
    try {
      return JSON.parse(jsonStr);
    } catch {
      return jsonStr;
    }
  };

  return (
    <div className="admin-page">
      <AdminNav />
      <div className="admin-content operation-log-page">
        <div className="admin-header">
          <h1>📋 操作日志（只读监控）</h1>
          <div className="header-actions">
            <button onClick={refresh} className="btn-secondary">🔄 刷新</button>
          </div>
        </div>

        <div style={{ marginBottom: 16, padding: '8px 12px', background: 'var(--accent-soft)', border: '1px solid var(--accent)', borderRadius: 6, fontSize: 13 }}>
          📊 本页为<strong>只读监控</strong>：展示操作日志与配额实时使用情况。<strong>配额额度</strong>的配置请前往「剧本管理 → 玩法配置」或「存档 → 玩法」页面。
        </div>

        {loading ? (
          <div className="loading">加载中...</div>
        ) : (
          <>
            {/* 配额使用概况 */}
            <section className="settings-section">
              <h2>📊 配额使用概况</h2>
              <div className="quota-grid">
                {quotaUsage.map((q) => {
                  const perTickPct = Math.min(100, (q.per_tick.current / Math.max(1, q.per_tick.limit)) * 100);
                  const per100Pct = Math.min(100, (q.per_100tick.current / Math.max(1, q.per_100tick.limit)) * 100);
                  const totalPct = Math.min(100, (q.max_total.current / Math.max(1, q.max_total.limit)) * 100);

                  return (
                    <div key={q.entity_type} className="quota-card">
                      <div className="quota-card-header">
                        <span className="quota-card-name">{q.name}</span>
                        <span className={`quota-status ${q.allowed ? 'allowed' : 'denied'}`}>
                          {q.allowed ? '允许' : '禁止'}
                        </span>
                      </div>
                      <div className="quota-bars">
                        <div className="quota-bar-row">
                          <span className="quota-bar-label">单 tick</span>
                          <div className="quota-bar">
                            <div
                              className={`quota-bar-fill ${perTickPct >= 90 ? 'critical' : perTickPct >= 70 ? 'warning' : ''}`}
                              style={{ width: `${perTickPct}%` }}
                            />
                          </div>
                          <span className="quota-bar-value">{q.per_tick.current}/{q.per_tick.limit}</span>
                        </div>
                        <div className="quota-bar-row">
                          <span className="quota-bar-label">100 tick</span>
                          <div className="quota-bar">
                            <div
                              className={`quota-bar-fill ${per100Pct >= 90 ? 'critical' : per100Pct >= 70 ? 'warning' : ''}`}
                              style={{ width: `${per100Pct}%` }}
                            />
                          </div>
                          <span className="quota-bar-value">{q.per_100tick.current}/{q.per_100tick.limit}</span>
                        </div>
                        <div className="quota-bar-row">
                          <span className="quota-bar-label">全局</span>
                          <div className="quota-bar">
                            <div
                              className={`quota-bar-fill ${totalPct >= 90 ? 'critical' : totalPct >= 70 ? 'warning' : ''}`}
                              style={{ width: `${totalPct}%` }}
                            />
                          </div>
                          <span className="quota-bar-value">{q.max_total.current}/{q.max_total.limit}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>

            {/* 日志摘要 */}
            {summary && (
              <section className="settings-section">
                <h2>📈 日志摘要</h2>
                <div className="summary-row">
                  <div className="summary-stat">
                    <span className="stat-value">{summary.total}</span>
                    <span className="stat-label">总操作数</span>
                  </div>
                  {Object.entries(summary.by_type).map(([type, count]) => (
                    <div key={type} className="summary-stat">
                      <span className="stat-value">{count}</span>
                      <span className="stat-label">{OP_TYPE_NAMES[type] || type}</span>
                    </div>
                  ))}
                </div>

                {summary.dynamic_entities.length > 0 && (
                  <div className="recent-entities">
                    <h3>最近动态实体创建</h3>
                    <div className="entity-chips">
                      {summary.dynamic_entities.slice(0, 10).map((e, idx) => (
                        <span key={idx} className="entity-chip">
                          {ENTITY_TYPE_NAMES[e.entity_type] || e.entity_type} #{e.entity_id}
                          <span className="chip-tool">({e.tool})</span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </section>
            )}

            {/* 日志列表 */}
            <section className="settings-section">
              <h2>📝 操作日志明细</h2>

              <div className="log-filters">
                <select
                  value={filterType}
                  onChange={(e) => setFilterType(e.target.value)}
                >
                  <option value="">全部操作类型</option>
                  {Object.entries(OP_TYPE_NAMES).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
                <select
                  value={filterEntity}
                  onChange={(e) => setFilterEntity(e.target.value)}
                >
                  <option value="">全部实体类型</option>
                  {Object.entries(ENTITY_TYPE_NAMES).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
                <span className="log-count">共 {filteredLogs.length} 条</span>
              </div>

              <div className="log-list">
                {filteredLogs.length === 0 ? (
                  <div className="empty-state">暂无操作日志</div>
                ) : (
                  filteredLogs.map((log) => (
                    <div
                      key={log.id}
                      className={`log-item ${selectedLog?.id === log.id ? 'selected' : ''} ${log.success ? 'success' : 'failed'}`}
                      onClick={() => setSelectedLog(log)}
                    >
                      <div className="log-item-header">
                        <span className={`log-status ${log.success ? 'ok' : 'err'}`}>
                          {log.success ? '✓' : '✗'}
                        </span>
                        <span className="log-op-type">
                          {OP_TYPE_NAMES[log.op_type] || log.op_type}
                        </span>
                        {log.op_entity_type && (
                          <span className="log-entity">
                            {ENTITY_TYPE_NAMES[log.op_entity_type] || log.op_entity_type}
                            {log.op_entity_id ? ` #${log.op_entity_id}` : ''}
                          </span>
                        )}
                        <span className="log-actor">{log.actor}</span>
                        <span className="log-tool">{log.tool}</span>
                        <span className="log-time">tick {log.tick_num}</span>
                      </div>
                      {log.error_msg && (
                        <div className="log-error">⚠ {log.error_msg}</div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </section>

            {/* 日志详情 */}
            {selectedLog && (
              <section className="settings-section log-detail-section">
                <h2>🔍 日志详情 #{selectedLog.id}</h2>
                <div className="log-detail">
                  <div className="detail-row">
                    <span className="detail-label">操作类型</span>
                    <span className="detail-value">{OP_TYPE_NAMES[selectedLog.op_type] || selectedLog.op_type}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">实体</span>
                    <span className="detail-value">
                      {selectedLog.op_entity_type ? (ENTITY_TYPE_NAMES[selectedLog.op_entity_type] || selectedLog.op_entity_type) : '-'}
                      {selectedLog.op_entity_id ? ` #${selectedLog.op_entity_id}` : ''}
                    </span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">执行者</span>
                    <span className="detail-value">{selectedLog.actor}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">工具</span>
                    <span className="detail-value code">{selectedLog.tool}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Tick</span>
                    <span className="detail-value">{selectedLog.tick_num}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">时间</span>
                    <span className="detail-value">{selectedLog.created_at}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">状态</span>
                    <span className={`detail-value ${selectedLog.success ? 'ok' : 'err'}`}>
                      {selectedLog.success ? '成功' : '失败'}
                    </span>
                  </div>
                  {selectedLog.error_msg && (
                    <div className="detail-row">
                      <span className="detail-label">错误</span>
                      <span className="detail-value err">{selectedLog.error_msg}</span>
                    </div>
                  )}
                  <div className="detail-json">
                    <div className="detail-json-block">
                      <div className="detail-json-title">参数</div>
                      <pre>{JSON.stringify(formatArgs(selectedLog.args_json), null, 2)}</pre>
                    </div>
                    <div className="detail-json-block">
                      <div className="detail-json-title">结果</div>
                      <pre>{JSON.stringify(formatArgs(selectedLog.result_json), null, 2)}</pre>
                    </div>
                  </div>
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </div>
  );
}
