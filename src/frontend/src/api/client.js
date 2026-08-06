// v3 API 客户端 — 与 src.backend.http 路由对应
import axios from 'axios';
export const api = axios.create({
    baseURL: '/api',
    timeout: 30000,
    headers: { 'Content-Type': 'application/json' },
});
// 重型 LLM 管线（tick / 时间跨越）耗时远超普通请求，
// 单独放宽超时，避免 30s 默认超时导致 net::ERR_ABORTED。
const LLM_TIMEOUT = 600000; // 10 分钟
// ============================================================
// 存档管理
// ============================================================
export const savesApi = {
    list: () => api.get('/saves').then((r) => r.data.saves),
    create: (name) => api.post('/saves', { name }).then((r) => r.data),
    switch: (name) => api.post(`/saves/${name}/switch`).then((r) => r.data),
    delete: (name) => api.delete(`/saves/${name}`).then((r) => r.data),
    getMeta: () => api.get('/saves/meta').then((r) => r.data),
    updateMeta: (fields) => api.patch('/saves/meta', fields).then((r) => r.data),
    getProtagonist: () => api.get('/saves/protagonist').then((r) => r.data),
    setProtagonist: (charId) => api.post('/saves/protagonist', { char_id: charId }).then((r) => r.data),
    // 快照
    listSnapshots: () => api.get('/saves/snapshots').then((r) => r.data),
    createSnapshot: () => api.post('/saves/snapshots').then((r) => r.data),
    restoreSnapshot: (snapshotFile) => api.post('/saves/snapshots/restore', null, { params: { snapshot_file: snapshotFile } }).then((r) => r.data),
    deleteSnapshot: (snapshotFile) => api.delete(`/saves/snapshots/${snapshotFile}`).then((r) => r.data),
};
// ============================================================
// 实体 CRUD（通用）
// ============================================================
export const entitiesApi = {
    list: (slug, params) => api.get(`/entities/${slug}`, { params })
        .then((r) => r.data.items),
    get: (slug, id) => api.get(`/entities/${slug}/${id}`).then((r) => r.data),
    create: (slug, body) => api.post(`/entities/${slug}`, body).then((r) => r.data),
    update: (slug, id, body) => api.patch(`/entities/${slug}/${id}`, body).then((r) => r.data),
    delete: (slug, id) => api.delete(`/entities/${slug}/${id}`).then((r) => r.data),
    slugs: () => api.get('/entities/_slugs').then((r) => r.data),
    // 角色完整档案
    characterProfile: (charId) => api.get(`/characters/${charId}/profile`).then((r) => r.data),
};
// ============================================================
// 世界（事件 + 时间推进）
// ============================================================
export const worldApi = {
    status: () => api.get('/world/status').then((r) => r.data),
    events: (params) => api.get('/world/events', { params }).then((r) => r.data),
    getEvent: (eventId) => api.get(`/world/events/${eventId}`).then((r) => r.data),
    createEvent: (body) => api.post('/world/events', body).then((r) => r.data),
    tick: (seconds, maxActors = 5) => api.post('/world/tick', { seconds, max_actors: maxActors }).then((r) => r.data),
    timeJump: (seconds) => api.post('/world/time_jump', { seconds }).then((r) => r.data),
};
// ============================================================
// 记忆系统
// ============================================================
export const memoryApi = {
    retrieve: (charId, opts) => api.post('/memory/retrieve', { char_id: charId, ...opts }).then((r) => r.data),
    encodeEvent: (eventId) => api.post(`/memory/encode_event/${eventId}`).then((r) => r.data),
    palace: (memoryId, depth = 2) => api.get(`/memory/palace/${memoryId}`, { params: { depth } }).then((r) => r.data),
};
// ============================================================
// 地图与距离
// ============================================================
export const mapsApi = {
    features: (mapId, opts) => api.get(`/maps/${mapId}/features`, { params: opts }).then((r) => r.data),
    children: (mapId) => api.get(`/maps/${mapId}/children`).then((r) => r.data),
    heatmaps: (mapId) => api.get(`/maps/${mapId}/heatmaps`).then((r) => r.data),
    distance: (from, to) => api.post('/maps/distance', { from, to }).then((r) => r.data),
    distanceMatrix: (mapId, ids, idType = 'feature') => api.get(`/maps/${mapId}/distance_matrix`, { params: { ids: ids.join(','), id_type: idType } }).then((r) => r.data),
    pathTo: (fromMapId, targetMapId) => api.get('/maps/path_to', { params: { from_map_id: fromMapId, target_map_id: targetMapId } }).then((r) => r.data),
};
// ============================================================
// 群体热力图
// ============================================================
export const groupsApi = {
    heatmap: (groupId) => api.get(`/groups/${groupId}/heatmap`).then((r) => r.data),
    refreshHeatmap: (groupId) => api.post(`/groups/${groupId}/refresh_heatmap`).then((r) => r.data),
};
// ============================================================
// LLM 管线（agent）
// ============================================================
export const agentApi = {
    // 管线
    tick: (seconds = 60, maxActors = 5, playerAction) => api.post('/agent/tick', { seconds, max_actors: maxActors, player_action: playerAction }, { timeout: LLM_TIMEOUT }).then((r) => r.data),
    timeJump: (seconds) => api.post('/agent/time_jump', { seconds }, { timeout: LLM_TIMEOUT }).then((r) => r.data),
    // 统一时间推进：按跨度自动选择 tick/time_jump
    advance: (seconds, opts) => api.post('/agent/advance', { seconds, player_action: opts?.player_action }, { timeout: LLM_TIMEOUT }).then((r) => r.data),
    callSkill: (name, body) => api.post(`/agent/skills/${name}/call`, body).then((r) => r.data),
    testConnection: (body) => api.post('/agent/_test_connection', body ?? {}).then((r) => r.data),
    // Skills
    listSkills: () => api.get('/agent/skills').then((r) => r.data),
    getSkill: (name) => api.get(`/agent/skills/${name}`).then((r) => r.data),
    listSkillVersions: (name) => api.get(`/agent/skills/${name}/versions`).then((r) => r.data),
    getSkillVersion: (name, version) => api.get(`/agent/skills/${name}/versions/${version}`).then((r) => r.data),
    createSkillVersion: (name, body) => api.post(`/agent/skills/${name}/versions`, body).then((r) => r.data),
    updateSkillVersion: (name, version, body) => api.put(`/agent/skills/${name}/versions/${version}`, body).then((r) => r.data),
    deleteSkillVersion: (name, version) => api.delete(`/agent/skills/${name}/versions/${version}`).then((r) => r.data),
    setSkillActive: (name, version) => api.put(`/agent/skills/${name}/active`, { version }).then((r) => r.data),
    renderSkill: (name) => api.get(`/agent/skills/${name}/render`).then((r) => r.data),
    // Prompts
    listPrompts: () => api.get('/agent/prompts').then((r) => r.data),
    // Tools
    listTools: () => api.get('/agent/tools').then((r) => r.data),
    toolSlugs: () => api.get('/agent/tools/_slugs').then((r) => r.data),
    getTool: (name) => api.get(`/agent/tools/${name}`).then((r) => r.data),
    // Variables
    variables: () => api.get('/agent/variables').then((r) => r.data),
    // Prompts 版本管理
    listPromptVersions: (name) => api.get(`/agent/prompts/${name}/versions`).then((r) => r.data),
    getPromptVersion: (name, version) => api.get(`/agent/prompts/${name}/versions/${version}`).then((r) => r.data),
    createPromptVersion: (name, body) => api.post(`/agent/prompts/${name}/versions`, body).then((r) => r.data),
    updatePromptVersion: (name, version, body) => api.put(`/agent/prompts/${name}/versions/${version}`, body).then((r) => r.data),
    deletePromptVersion: (name, version) => api.delete(`/agent/prompts/${name}/versions/${version}`).then((r) => r.data),
    setPromptActive: (name, version) => api.put(`/agent/prompts/${name}/active`, { version }).then((r) => r.data),
    renderPrompt: (name) => api.get(`/agent/prompts/${name}/render`).then((r) => r.data),
};
// ============================================================
// 剧本管理
// ============================================================
export const dramasApi = {
    list: () => api.get('/dramas').then((r) => r.data.items),
    get: (name) => api.get(`/dramas/${name}`).then((r) => r.data),
    validate: (name) => api.get(`/dramas/${name}/validate`).then((r) => r.data),
    preview: (name) => api.get(`/dramas/${name}/preview`).then((r) => r.data),
    init: (name, saveName, overwrite = false) => api.post(`/dramas/${name}/init`, { save_name: saveName, overwrite }).then((r) => r.data),
    patchFile: (name, fileName, content) => api.patch(`/dramas/${name}`, { file_name: fileName, content }).then((r) => r.data),
    delete: (name) => api.delete(`/dramas/${name}`).then((r) => r.data),
    generate: (prompt, name, opts) => api.post('/dramas/_generate', { prompt, name, ...(opts ?? {}) }).then((r) => r.data),
    generateStep: (name, step) => api.post(`/dramas/${name}/_generate_step`, { step }).then((r) => r.data),
    generateStatus: (name) => api.get(`/dramas/${name}/_generate_status`).then((r) => r.data),
    exportZip: (name) => api.get(`/dramas/${name}/export`, { responseType: 'blob' }).then((r) => r.data),
};
// ============================================================
// 全局配置
// ============================================================
export const configApi = {
    get: () => api.get('/config').then((r) => r.data),
    patch: (body) => api.patch('/config', body).then((r) => r.data),
    reset: () => api.post('/config/_reset').then((r) => r.data),
};
