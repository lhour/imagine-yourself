// v3 API 客户端 — 与 src.backend.http 路由对应
import axios from 'axios';

export const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// ============================================================
// 存档管理
// ============================================================

export const savesApi = {
  list: () => api.get<{ saves: string[] }>('/saves').then((r) => r.data.saves),
  create: (name: string) => api.post('/saves', { name }).then((r) => r.data),
  switch: (name: string) => api.post(`/saves/${name}/switch`).then((r) => r.data),
  delete: (name: string) => api.delete(`/saves/${name}`).then((r) => r.data),
  getMeta: () => api.get('/saves/meta').then((r) => r.data),
  updateMeta: (fields: Record<string, unknown>) =>
    api.patch('/saves/meta', fields).then((r) => r.data),
  getProtagonist: () => api.get('/saves/protagonist').then((r) => r.data),
  setProtagonist: (charId: number) =>
    api.post('/saves/protagonist', { char_id: charId }).then((r) => r.data),
};

// ============================================================
// 实体 CRUD（通用）
// ============================================================

export const entitiesApi = {
  list: <T>(slug: string, params?: Record<string, unknown>) =>
    api.get<T[]>(`/entities/${slug}`, { params }).then((r) => r.data),
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
};

// ============================================================
// 世界（事件 + 时间推进）
// ============================================================

export const worldApi = {
  status: () => api.get('/world/status').then((r) => r.data),
  events: (params?: { limit?: number; event_type?: string }) =>
    api.get('/world/events', { params }).then((r) => r.data),
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
// LLM 管线（agent）
// ============================================================

export const agentApi = {
  // 管线
  tick: (seconds: number = 60, maxActors: number = 5) =>
    api.post('/agent/tick', { seconds, max_actors: maxActors }).then((r) => r.data),
  timeJump: (seconds: number) =>
    api.post('/agent/time_jump', { seconds }).then((r) => r.data),
  callSkill: (name: string, body: Record<string, unknown>) =>
    api.post(`/agent/skills/${name}/call`, body).then((r) => r.data),

  // Skills
  listSkills: () =>
    api.get('/agent/skills').then((r) => r.data),
  getSkill: (name: string) =>
    api.get(`/agent/skills/${name}`).then((r) => r.data),
  listSkillVersions: (name: string) =>
    api.get(`/agent/skills/${name}/versions`).then((r) => r.data),
  getSkillVersion: (name: string, version: string) =>
    api.get(`/agent/skills/${name}/versions/${version}`).then((r) => r.data),
  createSkillVersion: (name: string, body: { new_version: string; from_version?: string; skill_md?: string }) =>
    api.post(`/agent/skills/${name}/versions`, body).then((r) => r.data),
  updateSkillVersion: (name: string, version: string, body: { skill_md?: string }) =>
    api.put(`/agent/skills/${name}/versions/${version}`, body).then((r) => r.data),
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

  // Variables
  variables: () =>
    api.get('/agent/variables').then((r) => r.data),
};
