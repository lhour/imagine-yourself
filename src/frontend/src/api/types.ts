// v3 API 类型定义

export interface WorldMeta {
  id: number;
  tick_num: number;
  game_time: string;
  era_name: string | null;
  script_name: string | null;
  protagonist_id: number | null;
  real_time: string;
  description: string | null;
  custom_attrs: Record<string, unknown>;
}

export interface Character {
  id: number;
  name: string;
  appearance_raw: string;
  appearance_polished: string | null;
  personality_raw: string;
  personality_polished: string | null;
  gender: string | null;
  age: number | null;
  status: string;
  importance: number;
  custom_attrs: Record<string, unknown>;
  created_at_tick: number;
  dead_at_tick: number | null;
}

export interface Group {
  id: number;
  name: string;
  desc_raw: string;
  desc_polished: string | null;
  group_type: string;
  leader_id: number | null;
  importance: number;
  primary_map_id: number | null;
  center_x: number | null;
  center_y: number | null;
  spread_radius: number;
  distribution_raw: string | null;
  heatmap_grid: HeatmapGrid | null;
  heatmap_resolution: number;
  heatmap_updated_tick: number | null;
  custom_attrs: Record<string, unknown>;
}

export interface HeatmapGrid {
  resolution: number;
  bbox: { x: number; y: number; w: number; h: number };
  cells: number[][];
  min_density: number;
  max_density: number;
  unit_hint: string;
}

export interface MapRecord {
  id: number;
  name: string;
  desc_raw: string;
  desc_polished: string | null;
  parent_map_id: number | null;
  map_type: string;
  coord_system: string;
  scale_unit: string;
  scale_per_unit: number;
  bbox_x: number;
  bbox_y: number;
  bbox_w: number;
  bbox_h: number;
  bbox_d: number | null;
  default_zoom: number;
  default_center_x: number | null;
  default_center_y: number | null;
  is_mobile: number;
  carrier_char_id: number | null;
  carrier_item_id: number | null;
  current_x: number | null;
  current_y: number | null;
  current_z: number | null;
  current_map_id: number | null;
  importance: number;
  custom_attrs: Record<string, unknown>;
}

export interface MapFeature {
  id: number;
  map_id: number;
  name: string;
  feature_type: string;
  shape: string;
  geometry: Record<string, unknown>;
  layer_z: number;
  color_hint: string | null;
  visual_raw: string | null;
  child_map_id: number | null;
  is_obstacle: number;
  is_mobile: number;
  carrier_type: string | null;
  carrier_id: number | null;
  size_value: number | null;
  size_unit_override: string | null;
}

export interface Item {
  id: number;
  name: string;
  desc_raw: string;
  desc_polished: string | null;
  item_type: string;
  rarity: number;
  importance: number;
  is_stackable: number;
  stack_size: number;
  custom_attrs: Record<string, unknown>;
}

export interface EventParticipant {
  id: number;
  event_id: number;
  participant_type: 'character' | 'group' | 'item' | 'map';
  participant_id: number;
  role_raw: string;
  perception_raw: string | null;
  name: string;
}

export interface MemorySight {
  char_id: number;
  char_name: string;
  depth: number;
  correctness: number;
  forget_prob: number;
  is_false: boolean;
}

export interface LinkedMemory extends MemorySight {
  id: number;
  memory_raw: string;
  memory_polished: string | null;
  remember_tick: number;
}

export interface EventRecord {
  id: number;
  tick_num: number;
  game_time: string;
  event_type: string;
  content_raw: string;
  content_polished: string | null;
  location_map_id: number | null;
  location_detail_raw: string | null;
  importance: number;
  custom_attrs: Record<string, unknown>;
  created_at: string;
  participants: EventParticipant[];
  remembered_by: MemorySight[];
  forgotten_by: MemorySight[];
  linked_memories?: LinkedMemory[];
}

export interface CharacterQuest {
  id: number;
  char_id: number;
  title: string;
  desc_raw: string;
  desc_polished: string | null;
  quest_type: string;
  status: 'open' | 'in_progress' | 'done' | 'failed' | 'blocked';
  priority: number;
  start_tick: number;
  estimated_ticks: number | null;
  success_condition_raw: string | null;
  fail_condition_raw: string | null;
  assigned_by: string | null;
  parent_quest_id: number | null;
  completion_summary_raw: string | null;
  blocked_reason_raw: string | null;
  custom_attrs: Record<string, unknown>;
}

export interface CharacterAgenda {
  id: number;
  char_id: number;
  title: string;
  principle_raw: string;
  principle_polished: string | null;
  status: 'active' | 'blocked' | 'completed' | 'archived';
  priority: number;
  start_tick: number;
  end_tick: number | null;
  conflict_with: string | null;
  blocked_reason_raw: string | null;
}

export interface Memory {
  id: number;
  char_id: number;
  memory_raw: string;
  memory_polished: string | null;
  depth: number;
  correctness: number;
  forget_prob: number;
  perspective_bias: string | null;
  remember_tick: number;
  source_event_id: number | null;
  custom_attrs: Record<string, unknown>;
}

export interface SaveInfo {
  name: string;
  created_at: string | null;
  size_kb: number | null;
}

// Tick 管线响应
export interface TickTraceStep {
  step: number | string;
  name: string;
  [key: string]: unknown;
}

export interface TickResponse {
  tick: number;
  game_time: string;
  trace: TickTraceStep[];
  events_created: number[];
  decisions: Array<{ char_id: number; char_name: string; decision: unknown }>;
  mock_mode: boolean;
  /** v4: coordinator 合成的连贯剧情文本（narrative 为主展示，events 可展开） */
  narrative?: string;
  /** 推进的实际秒数（advance 返回） */
  seconds?: number;
  /** advance 模式：tick / jump */
  advance_mode?: 'tick' | 'jump';
  /** C 阶段：是否走 orchestrator（v4 + 编排层） */
  orchestrated?: boolean;
  /** C 阶段：编排层摘要（概率事件 / 规划 / 反思 / 锚点校验 / 配额使用） */
  orchestration?: OrchestrationSummary;
  /** narrative 是否被反思重写 */
  narrative_rewritten?: boolean;
}

/** C 阶段编排层摘要 */
export interface OrchestrationSummary {
  probability_events: {
    hard_hint: string;
    sampled: boolean;
    triggers?: string[];
    params?: { death_likelihood: number; luck_bias: number; challenge_bias: number };
  };
  plan: {
    skip_nodes: string[];
    skip_reasons: Record<string, string>;
    mock?: boolean;
  };
  reflection: {
    passed: boolean;
    final_narrative: string;
    conflicts: Array<{ type: string; severity: string; description: string }>;
    retries: number;
    anchors_fulfilled?: Array<{ anchor_id: number; evidence: string }>;
  };
  anchor_check: {
    checked?: number;
    fulfilled?: Array<{ anchor_id: number; title?: string; evidence?: string; fulfilled_event_id?: number }>;
    expired?: Array<{ anchor_id: number; reason?: string }>;
    unchanged?: Array<{ anchor_id: number; reason?: string }>;
    skipped?: boolean;
  };
  quota_used: Record<string, number>;
}

export interface TimeJumpResponse {
  from_tick: number;
  to_tick: number;
  from_time: string;
  to_time: string;
  seconds: number;
  span_type: 'short' | 'medium' | 'long' | 'ultra_long' | 'epochal';
  span_label: string;
  summary: string;
  events_created: number[];
  milestone_count: number;
  mock_mode: boolean;
  usage?: Record<string, number>;
}

// Skill / Tool / Variable
export interface SkillInfo {
  name: string;
  description: string;
  default_version: string;
  tools: string[];
  versions: string[];
}

export interface SkillVersionDetail {
  name: string;
  version: string;
  system_prompt: string;
  skill_md: string;
}

// ============================================================
// 锚点剧情（v4）
// ============================================================

export type AnchorStatus = 'pending' | 'active' | 'fulfilled' | 'expired' | 'abandoned';

export interface AnchorPlot {
  id: number;
  title: string;
  desc_raw: string;
  desc_polished: string | null;
  inevitability: number;          // 0-5：0=灵感，1-2=软引导，3-4=强引导，5=硬约束
  status: AnchorStatus;
  trigger_condition_raw: string;
  target_tick: number | null;
  created_tick: number;
  fulfilled_tick: number | null;
  fulfilled_event_id: number | null;
  created_by: string;             // human | model | system
  priority: number;               // 1-5
  plot_arc: string;
  tags: string[];
  custom_attrs: Record<string, unknown>;
}

export interface ToolSlug {
  slug: string;
  table: string;
  tools: string[];
}

// 通用响应
export interface ListResponse<T> {
  items: T[];
  count: number;
}

export interface SlugsResponse {
  slugs: ToolSlug[];
  count: number;
}

export interface VariablesResponse {
  variables: Record<string, { description: string; source: string }>;
}
