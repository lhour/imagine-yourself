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
}

export interface EventParticipant {
  id: number;
  event_id: number;
  participant_type: string;
  participant_id: number;
  role_raw: string;
  perception: string | null;
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
