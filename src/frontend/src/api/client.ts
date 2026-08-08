// v3 API 客户端 — 与 src.backend.http 路由对应
import axios from 'axios';
import type { AnchorPlot } from './types';

export const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// 响应拦截器：提取后端返回的详细错误消息
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.data?.detail) {
      error.message = error.response.data.detail;
    } else if (error.response?.data?.message) {
      error.message = error.response.data.message;
    }
    return Promise.reject(error);
  }
);

// 重型 LLM 管线（tick / 时间跨越）耗时远超普通请求，
// 单独放宽超时，避免 30s 默认超时导致 net::ERR_ABORTED。
const LLM_TIMEOUT = 600000; // 10 分钟

// ============================================================
// 存档管理
// ============================================================

export const savesApi = {
  list: () => api.get<{ saves: string[] }>('/saves').then((r) => r.data.saves),
  batchMeta: () => api.get<{ metas: Array<Record<string, unknown>> }>('/saves/batch-meta').then((r) => r.data.metas),
  getActive: () => api.get<{ active_save: string | null }>('/saves/active').then((r) => r.data.active_save),
  create: (name: string) => api.post('/saves', { name }).then((r) => r.data),
  switch: (name: string) => api.post(`/saves/${name}/switch`).then((r) => r.data),
  delete: (name: string) => api.delete(`/saves/${name}`).then((r) => r.data),
  getMeta: () => api.get('/saves/meta').then((r) => r.data),
  updateMeta: (fields: Record<string, unknown>) =>
    api.patch('/saves/meta', fields).then((r) => r.data),
  getProtagonist: () => api.get('/saves/protagonist').then((r) => r.data),
  setProtagonist: (charId: number) =>
    api.post('/saves/protagonist', { char_id: charId }).then((r) => r.data),
  // 快照
  listSnapshots: () => api.get('/saves/snapshots').then((r) => r.data),
  createSnapshot: () => api.post('/saves/snapshots').then((r) => r.data),
  restoreSnapshot: (snapshotFile: string) =>
    api.post('/saves/snapshots/restore', null, { params: { snapshot_file: snapshotFile } }).then((r) => r.data),
  deleteSnapshot: (snapshotFile: string) =>
    api.delete(`/saves/snapshots/${snapshotFile}`).then((r) => r.data),
};

// ============================================================
// 实体 CRUD（通用）
// ============================================================

export const entitiesApi = {
  list: <T>(slug: string, params?: Record<string, unknown>) =>
    api.get<{ items: T[]; count: number; total: number }>(`/entities/${slug}`, { params })
      .then((r) => r.data.items),
  get: <T>(slug: string, id: number) =>
    api.get<T>(`/entities/${slug}/${id}`).then((r) => r.data),
  create: <T>(slug: string, body: Partial<T>) =>
    api.post<T>(`/entities/${slug}`, body).then((r) => r.data),
  update: <T>(slug: string, id: number, body: Partial<T>) =>
    api.patch<T>(`/entities/${slug}/${id}`, body).then((r) => r.data),
  delete: (slug: string, id: number) =>
    api.delete(`/entities/${slug}/${id}`).then((r) => r.data),
  slugs: () =>
    api.get<{ slugs: string[]; count: number }>('/entities/_slugs').then((r) => r.data),
  // 角色完整档案
  characterProfile: (charId: number) =>
    api.get(`/characters/${charId}/profile`).then((r) => r.data),
};

// ============================================================
// 世界（事件 + 时间推进）
// ============================================================

export const worldApi = {
  status: () => api.get('/world/status').then((r) => r.data),
  events: (params?: {
    limit?: number;
    event_type?: string;
    event_types?: string;
    importance_min?: number;
    tick_from?: number;
    tick_to?: number;
    char_ids?: string;
    map_ids?: string;
    before_id?: number;
  }) => api.get('/world/events', { params }).then((r) => r.data),
  getEvent: (eventId: number) => api.get(`/world/events/${eventId}`).then((r) => r.data),
  createEvent: (body: Record<string, unknown>) =>
    api.post('/world/events', body).then((r) => r.data),
  tick: (seconds: number, maxActors: number = 5) =>
    api.post('/world/tick', { seconds, max_actors: maxActors }).then((r) => r.data),
  timeJump: (seconds: number) =>
    api.post('/world/time_jump', { seconds }).then((r) => r.data),
};

// ============================================================
// 记忆系统
// ============================================================

export const memoryApi = {
  retrieve: (charId: number, opts?: Record<string, unknown>) =>
    api.post('/memory/retrieve', { char_id: charId, ...opts }).then((r) => r.data),
  encodeEvent: (eventId: number) =>
    api.post(`/memory/encode_event/${eventId}`).then((r) => r.data),
  palace: (memoryId: number, depth: number = 2) =>
    api.get(`/memory/palace/${memoryId}`, { params: { depth } }).then((r) => r.data),
};

// ============================================================
// 地图与距离
// ============================================================

export const mapsApi = {
  features: (mapId: number, opts?: { layer_z_min?: number; layer_z_max?: number }) =>
    api.get(`/maps/${mapId}/features`, { params: opts }).then((r) => r.data),
  children: (mapId: number) =>
    api.get(`/maps/${mapId}/children`).then((r) => r.data),
  heatmaps: (mapId: number) =>
    api.get(`/maps/${mapId}/heatmaps`).then((r) => r.data),
  distance: (from: { type: string; id: number }, to: { type: string; id: number }) =>
    api.post('/maps/distance', { from, to }).then((r) => r.data),
  distanceMatrix: (mapId: number, ids: number[], idType: string = 'feature') =>
    api.get(`/maps/${mapId}/distance_matrix`, { params: { ids: ids.join(','), id_type: idType } }).then((r) => r.data),
  pathTo: (fromMapId: number, targetMapId: number) =>
    api.get('/maps/path_to', { params: { from_map_id: fromMapId, target_map_id: targetMapId } }).then((r) => r.data),
};

// ============================================================
// 群体热力图
// ============================================================

export const groupsApi = {
  heatmap: (groupId: number) =>
    api.get(`/groups/${groupId}/heatmap`).then((r) => r.data),
  refreshHeatmap: (groupId: number) =>
    api.post(`/groups/${groupId}/refresh_heatmap`).then((r) => r.data),
};

// ============================================================
// 锚点剧情
// ============================================================

export const anchorsApi = {
  list: (params?: {
    status?: string;
    min_inevitability?: number;
    plot_arc?: string;
    limit?: number;
  }) => api.get<{ items: AnchorPlot[]; count: number }>('/anchors', { params }).then((r) => r.data),
  get: (id: number) => api.get<AnchorPlot>(`/anchors/${id}`).then((r) => r.data),
  create: (body: Partial<AnchorPlot> & { title: string; desc_raw?: string }) =>
    api.post<AnchorPlot>('/anchors', body).then((r) => r.data),
  update: (id: number, body: Partial<AnchorPlot>) =>
    api.put<AnchorPlot>(`/anchors/${id}`, body).then((r) => r.data),
  delete: (id: number) => api.delete(`/anchors/${id}`).then((r) => r.data),
  activate: (id: number) => api.post<AnchorPlot>(`/anchors/${id}/activate`).then((r) => r.data),
  fulfill: (id: number, body?: { event_id?: number; reason?: string }) =>
    api.post<AnchorPlot>(`/anchors/${id}/fulfill`, body ?? {}).then((r) => r.data),
  abandon: (id: number, body?: { reason?: string }) =>
    api.post<AnchorPlot>(`/anchors/${id}/abandon`, body ?? {}).then((r) => r.data),
};

// ============================================================
// LLM 管线（agent）
// ============================================================

export const agentApi = {
  // 管线
  tick: (seconds: number = 60, maxActors: number = 5, playerAction?: string) =>
    api.post('/agent/tick', { seconds, max_actors: maxActors, player_action: playerAction }, { timeout: LLM_TIMEOUT }).then((r) => r.data),
  timeJump: (seconds: number) =>
    api.post('/agent/time_jump', { seconds }, { timeout: LLM_TIMEOUT }).then((r) => r.data),
  // 统一时间推进：按跨度自动选择 tick/time_jump
  advance: (seconds: number, opts?: { player_action?: string }) =>
    api.post('/agent/advance', { seconds, player_action: opts?.player_action }, { timeout: LLM_TIMEOUT }).then((r) => r.data),
  callSkill: (name: string, body: Record<string, unknown>) =>
    api.post(`/agent/skills/${name}/call`, body).then((r) => r.data),
  testConnection: (body?: {
    system_prompt?: string;
    user_prompt?: string;
    model?: string;
  }) =>
    api.post('/agent/_test_connection', body ?? {}).then((r) => r.data),

  // Skills
  listSkills: () =>
    api.get('/agent/skills').then((r) => r.data),
  getSkill: (name: string) =>
    api.get(`/agent/skills/${name}`).then((r) => r.data),
  createSkill: (body: {
    name: string;
    description?: string;
    tools?: string[];
    params?: Record<string, unknown>;
    skill_md?: string;
  }) =>
    api.post('/agent/skills', body).then((r) => r.data),
  deleteSkill: (name: string) =>
    api.delete(`/agent/skills/${name}`).then((r) => r.data),
  updateSkillConfig: (name: string, body: {
    description?: string;
    tools?: string[];
    params?: Record<string, unknown>;
    default_version?: string;
  }) =>
    api.patch(`/agent/skills/${name}/config`, body).then((r) => r.data),
  listSkillVersions: (name: string) =>
    api.get(`/agent/skills/${name}/versions`).then((r) => r.data),
  getSkillVersion: (name: string, version: string) =>
    api.get(`/agent/skills/${name}/versions/${version}`).then((r) => r.data),
  createSkillVersion: (name: string, body: {
    new_version: string;
    from_version?: string;
    skill_md?: string;
    system_prompt?: string;
  }) =>
    api.post(`/agent/skills/${name}/versions`, body).then((r) => r.data),
  updateSkillVersion: (name: string, version: string, body: {
    skill_md?: string;
    system_prompt?: string;
  }) =>
    api.put(`/agent/skills/${name}/versions/${version}`, body).then((r) => r.data),
  deleteSkillVersion: (name: string, version: string) =>
    api.delete(`/agent/skills/${name}/versions/${version}`).then((r) => r.data),
  setSkillActive: (name: string, version: string) =>
    api.put(`/agent/skills/${name}/active`, { version }).then((r) => r.data),
  renderSkill: (name: string) =>
    api.get(`/agent/skills/${name}/render`).then((r) => r.data),

  // Prompts
  listPrompts: () =>
    api.get('/agent/prompts').then((r) => r.data),

  // Tools
  listTools: () =>
    api.get('/agent/tools').then((r) => r.data),
  toolSlugs: () =>
    api.get('/agent/tools/_slugs').then((r) => r.data),
  getTool: (name: string) =>
    api.get(`/agent/tools/${name}`).then((r) => r.data),
  updateToolDescription: (name: string, description: string) =>
    api.put(`/agent/tools/${name}/description`, { description }).then((r) => r.data),

  // Variables
  variables: () =>
    api.get('/agent/variables').then((r) => r.data),
  // Prompts 版本管理
  listPromptVersions: (name: string) =>
    api.get(`/agent/prompts/${name}/versions`).then((r) => r.data),
  getPromptVersion: (name: string, version: string) =>
    api.get(`/agent/prompts/${name}/versions/${version}`).then((r) => r.data),
  createPromptVersion: (name: string, body: {
    new_version: string;
    from_version?: string;
    system_prompt?: string;
    user_prompt?: string;
  }) =>
    api.post(`/agent/prompts/${name}/versions`, body).then((r) => r.data),
  updatePromptVersion: (name: string, version: string, body: {
    system_prompt?: string;
    user_prompt?: string;
  }) =>
    api.put(`/agent/prompts/${name}/versions/${version}`, body).then((r) => r.data),
  deletePromptVersion: (name: string, version: string) =>
    api.delete(`/agent/prompts/${name}/versions/${version}`).then((r) => r.data),
  setPromptActive: (name: string, version: string) =>
    api.put(`/agent/prompts/${name}/active`, { version }).then((r) => r.data),
  renderPrompt: (name: string) =>
    api.get(`/agent/prompts/${name}/render`).then((r) => r.data),
};

// ============================================================
// 剧本管理
// ============================================================

export const dramasApi = {
  list: () => api.get('/dramas').then((r) => r.data.items),
  get: (name: string) => api.get(`/dramas/${name}`).then((r) => r.data),
  validate: (name: string) => api.get(`/dramas/${name}/validate`).then((r) => r.data),
  preview: (name: string) => api.get(`/dramas/${name}/preview`).then((r) => r.data),
  init: (name: string, saveName: string, overwrite = false) =>
    api.post(`/dramas/${name}/init`, { save_name: saveName, overwrite }).then((r) => r.data),
  patchFile: (name: string, fileName: string, content: string) =>
    api.patch(`/dramas/${name}`, { file_name: fileName, content }).then((r) => r.data),
  delete: (name: string) => api.delete(`/dramas/${name}`).then((r) => r.data),
  generate: (
    prompt: string,
    name?: string,
    opts?: {
      skip_steps?: string;
      only_steps?: string;
    }
  ) =>
    api.post('/dramas/_generate', { prompt, name, ...(opts ?? {}) }).then((r) => r.data),
  generateStep: (name: string, step: number) =>
    api.post(`/dramas/${name}/_generate_step`, { step }).then((r) => r.data),
  generateStatus: (name: string) =>
    api.get(`/dramas/${name}/_generate_status`).then((r) => r.data),
  exportZip: (name: string) =>
    api.get(`/dramas/${name}/export`, { responseType: 'blob' }).then((r) => r.data),
  getGameplayOptions: (name: string) =>
    api.get(`/dramas/${name}/gameplay_options`).then((r) => r.data.options),
  saveGameplayOptions: (name: string, options: object) =>
    api.put(`/dramas/${name}/gameplay_options`, options).then((r) => r.data.options),
};

// ============================================================
// 全局配置
// ============================================================

export const configApi = {
  get: () => api.get('/config').then((r) => r.data),
  patch: (body: Record<string, unknown>) =>
    api.patch('/config', body).then((r) => r.data),
  reset: () => api.post('/config/_reset').then((r) => r.data),
};

// ============================================================
// 请求日志 / 调用链追踪
// ============================================================

export interface TraceSummary {
  id: string;
  ts?: string;
  name?: string;
  action?: string;
  save?: string;
  span_count: number;
  model_rounds: number;
  tool_calls: number;
  skills: number;
  duration_ms?: number;
  status?: string;
  total_tokens?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  cache_hit_tokens?: number;
  cache_miss_tokens?: number;
}

export const tracesApi = {
  list: (limit = 200, action?: string) =>
    api.get<{ items: TraceSummary[]; count: number }>('/traces', { params: { limit, action } })
      .then((r) => r.data),
  get: <T = Record<string, unknown>>(tid: string) =>
    api.get<T>(`/traces/${tid}`).then((r) => r.data),
  clear: () =>
    api.delete<{ cleared: number }>('/traces').then((r) => r.data),
};

// ============================================================
// v5 新功能：玩法选项 / 实体配额 / 操作日志 / 世界背景
// ============================================================

export interface QuotaUsage {
  entity_type: string;
  name: string;
  allowed: boolean;
  per_tick: { current: number; limit: number };
  per_100tick: { current: number; limit: number };
  max_total: { current: number; limit: number };
}

export const v5Api = {
  // 玩法选项
  getGameplayOptions: () =>
    api.get<{ gameplay_options: Record<string, unknown>; quota_usage: QuotaUsage[] }>('/v5/gameplay_options')
      .then((r) => r.data),
  setGameplayOptions: (options: object) =>
    api.put('/v5/gameplay_options', { options }).then((r) => r.data),
  patchGameplayOptions: (patch: Record<string, unknown>) =>
    api.patch('/v5/gameplay_options', { patch }).then((r) => r.data),

  // 实体配额
  getEntityQuota: () =>
    api.get<{ quota_usage: QuotaUsage[] }>('/v5/entity_quota').then((r) => r.data),
  checkEntityQuota: (entityType: string) =>
    api.get<{ entity_type: string; passed: boolean; message?: string }>(`/v5/entity_quota/${entityType}`)
      .then((r) => r.data),

  // 操作日志
  queryOperationLog: (params?: { op_type?: string; actor?: string; op_entity_type?: string; limit?: number }) =>
    api.get<{ logs: Record<string, unknown>[]; count: number }>('/v5/operation_log', { params })
      .then((r) => r.data),
  getOperationLogSummary: () =>
    api.get('/v5/operation_log/summary').then((r) => r.data),

  // 世界背景
  getWorldBackground: () =>
    api.get('/v5/world_background').then((r) => r.data),
  setWorldBackground: (body: {
    world_background_raw?: string;
    world_background_polished?: string;
    civilization_summary?: string;
  }) =>
    api.put('/v5/world_background', body).then((r) => r.data),

  // 上下文打包（调试）
  getPackedContext: () =>
    api.get('/v5/packed_context').then((r) => r.data),
};

// ============================================================
// 知识库
// ============================================================

export interface KnowledgeCategory {
  id: number;
  name: string;
  description: string;
  item_count: number;
}

export interface KnowledgeItem {
  id: number;
  category_id: number;
  title: string;
  content: string;
  keywords: string[];
  tags: string[];
  source: string;
  importance: number;
  created_at: string;
  updated_at: string;
  score?: number;
}

export const knowledgeApi = {
  // 分类
  listCategories: () =>
    api.get<{ categories: KnowledgeCategory[] }>('/knowledge/categories')
      .then((r) => r.data.categories),
  createCategory: (name: string, description = '') =>
    api.post('/knowledge/categories', { name, description }).then((r) => r.data),
  updateCategory: (id: number, name: string, description = '') =>
    api.put(`/knowledge/categories/${id}`, { name, description }).then((r) => r.data),
  deleteCategory: (id: number) =>
    api.delete(`/knowledge/categories/${id}`).then((r) => r.data),

  // 条目
  listItems: (categoryId = 0, page = 1, pageSize = 20) =>
    api.get<{ items: KnowledgeItem[]; total: number; page: number; page_size: number; total_pages: number }>('/knowledge/items', {
      params: { category_id: categoryId, page, page_size: pageSize },
    }).then((r) => r.data),
  getItem: (id: number) =>
    api.get<KnowledgeItem>(`/knowledge/items/${id}`).then((r) => r.data),
  createItem: (item: { title: string; content: string; category_id?: number; keywords?: string[]; tags?: string[]; importance?: number }) =>
    api.post('/knowledge/items', item).then((r) => r.data),
  updateItem: (id: number, item: { title?: string; content?: string; category_id?: number; keywords?: string[]; tags?: string[]; importance?: number }) =>
    api.put(`/knowledge/items/${id}`, item).then((r) => r.data),
  deleteItem: (id: number) =>
    api.delete(`/knowledge/items/${id}`).then((r) => r.data),

  // 检索
  search: (query: string, categoryId = 0, topK = 10) =>
    api.post<{ results: KnowledgeItem[]; total: number }>('/knowledge/search', {
      query, category_id: categoryId, top_k: topK, mode: 'keyword',
    }).then((r) => r.data),
  getRandom: (categoryId = 0, count = 5) =>
    api.get<{ items: KnowledgeItem[] }>('/knowledge/items/random', {
      params: { category_id: categoryId, count },
    }).then((r) => r.data),

  // 统计
  getStats: () =>
    api.get<{ total_items: number; total_categories: number; total_searches: number; db_size_bytes: number }>('/knowledge/stats')
      .then((r) => r.data),

  // 批量导入
  batchImport: (items: Array<{ title: string; content: string; category_id?: number; keywords?: string[]; tags?: string[]; importance?: number }>) =>
    api.post('/knowledge/items/batch', items).then((r) => r.data),
};

// ============================================================
// 周期事件调度（10.3）
// ============================================================

export interface ScheduledEvent {
  id: number;
  title: string;
  desc_raw?: string;
  importance: number;
  schedule_type: 'recurring' | 'one_shot';
  recurrence_pattern: string;
  recurrence_detail_raw?: string;
  next_trigger_game_time?: string;
  scope: 'character' | 'group' | 'global';
  scope_target_json?: number[];
  event_template_json?: Record<string, unknown>;
  trigger_condition_raw?: string;
  expire_condition_raw?: string;
  active: number;
  created_by?: string;
  created_tick?: number;
  deactivated_tick?: number | null;
  custom_attrs?: Record<string, unknown>;
}

export const scheduledEventsApi = {
  list: (params?: { active_only?: number; scope?: string; limit?: number }) =>
    api.get<{ items: ScheduledEvent[]; count: number }>('/scheduled-events', { params }).then((r) => r.data),
  get: (id: number) => api.get<ScheduledEvent>(`/scheduled-events/${id}`).then((r) => r.data),
  create: (body: Partial<ScheduledEvent> & { title: string }) =>
    api.post<ScheduledEvent>('/scheduled-events', body).then((r) => r.data),
  update: (id: number, body: Partial<ScheduledEvent>) =>
    api.put<ScheduledEvent>(`/scheduled-events/${id}`, body).then((r) => r.data),
  delete: (id: number) => api.delete(`/scheduled-events/${id}`).then((r) => r.data),
  activate: (id: number) => api.post<ScheduledEvent>(`/scheduled-events/${id}/activate`).then((r) => r.data),
  deactivate: (id: number) => api.post<ScheduledEvent>(`/scheduled-events/${id}/deactivate`).then((r) => r.data),
};

// ============================================================
// 信息传播追踪（10.1）
// ============================================================

export interface EventDissemination {
  id: number;
  event_id: number;
  target_char_id: number;
  status: 'pending' | 'arrived' | 'distorted' | 'lost';
  expected_arrival_game_time?: string;
  arrived_game_time?: string;
  distortion_level?: number;
  received_version_raw?: string;
  source_path_json?: number[];
  hops?: number;
  created_tick?: number;
  updated_tick?: number;
}

export interface PublicKnowledgeRecord {
  id: number;
  event_id: number;
  published_game_time?: string;
  medium?: string;
  coverage_scope?: string;
  version_raw?: string;
  reach_tags_json?: string[];
}

export interface DisseminationStats {
  pending: number;
  arrived: number;
  distorted: number;
  lost: number;
  total: number;
  [key: string]: number;
}

export const propagationApi = {
  listDisseminations: (params?: { status?: string; event_id?: number; target_char_id?: number; limit?: number }) =>
    api.get<{ items: EventDissemination[]; count: number }>('/propagation/disseminations', { params }).then((r) => r.data),
  disseminationStats: () => api.get<DisseminationStats>('/propagation/disseminations/stats').then((r) => r.data),
  listPublicKnowledge: (params?: { medium?: string; limit?: number }) =>
    api.get<{ items: PublicKnowledgeRecord[]; count: number }>('/propagation/public-knowledge', { params }).then((r) => r.data),
  markArrived: (id: number) => api.post<EventDissemination>(`/propagation/disseminations/${id}/mark-arrived`).then((r) => r.data),
  markLost: (id: number) => api.post<EventDissemination>(`/propagation/disseminations/${id}/mark-lost`).then((r) => r.data),
};
