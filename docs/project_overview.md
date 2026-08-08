# Aether Story Engine — 项目介绍文档

> **版本**：v5.0.0（v4 数据库 + v5 增强方案融合实施版）
> **日期**：2026-08-08
> **状态**：活跃开发中

---

## 目录

- [一、项目概述与设计理念](#一项目概述与设计理念)
- [二、整体架构总览](#二整体架构总览)
- [三、数据库设计（三库分工）](#三数据库设计三库分工)
- [四、核心流程——五节点管线](#四核心流程五节点管线)
- [五、模型与工具系统](#五模型与工具系统)
- [六、API 接口设计](#六api-接口设计)
- [七、前端架构](#七前端架构)
- [八、关键特性](#八关键特性)
- [九、部署与运维](#九部署与运维)
- [十、目录结构总览](#十目录结构总览)

---

## 一、项目概述与设计理念

### 1.1 项目是什么

**Aether Story Engine** 是一个基于 **DeepSeek LLM** 的叙事游戏引擎。它能够：

- **剧本驱动**：通过 JSONL 格式剧本一键初始化完整世界（角色、群体、地图、设定、剧情规划等）
- **Agent 编排**：以 Skill/工具系统组织 LLM 调用，实现多角色并发决策与事件生成
- **多存档隔离**：每个存档独立 SQLite + KuzuDB + 向量库，支持快照/恢复
- **Web 控制台**：React + PixiJS + Three.js 混合渲染，提供完整的世界编辑与游玩界面

### 1.2 设计理念

| 理念 | 说明 |
|------|------|
| **客观/主观分离** | 事件是客观事实，感知是主观记忆。事件不存 perception，主观感知仅进入记忆库 |
| **三库分工** | 关系库（SQLite）+ 图库（KuzuDB）+ 向量库（sqlite-vec），各司其职 |
| **反应式决策** | 角色同时输出 proactive_option + reactive_strategy，解决「对峙中 B 等 A 出招」 |
| **锚点剧情** | 人工/模型可写入「希望未来发生的剧情」，带 0-5 必然性档位 |
| **并发优先** | 角色决策、角色更新均并发执行，最大化吞吐量 |
| **上下文分层** | 恒定前缀 + 恒定中段 + 动态尾段，适配 LLM 前缀缓存 |
| **动态实体配额** | 新角色/群体/设定有三档配额（per_tick / per_100tick / max_total） |
| **本地离线知识库** | 使用本地向量模型，不依赖云端 embedding |

### 1.3 技术栈

| 层 | 技术 |
|----|------|
| 语言 | Python 3.12 · TypeScript |
| 后端框架 | FastAPI（REST API） |
| 关系数据库 | SQLite（嵌入式） |
| 图数据库 | KuzuDB（嵌入式，Cypher 查询） |
| 向量数据库 | sqlite-vec（SQLite 扩展，FLOAT[768]） |
| LLM | DeepSeek（OpenAI SDK 兼容，支持 mock 模式） |
| 前端框架 | React 18 · Vite 5 |
| 渲染引擎 | PixiJS（2D）+ Three.js（3D）混合渲染 |
| 状态管理 | Zustand |
| 测试 | pytest（后端 38+ 用例 + E2E 验证） |

---

## 二、整体架构总览

```
┌───────────────────────────────────────────────────────────────────────┐
│                           Aether Story Engine                          │
├───────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                      前端（React + PixiJS）                     │  │
│  │  StartPage · SavesPage · GamePage · ModelPage · KnowledgePage  │  │
│  │  SettingsPage · RequestLogPage · WorldSchedulePage · ...       │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                              │ HTTP / REST                             │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                    后端（FastAPI + Agent 管线）                  │  │
│  │                                                                 │  │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │  │
│  │  │ HTTP 路由层  │    │  Agent 管线 │    │   Skill / Prompt     │  │  │
│  │  │ (14 routers) │───▶│ (5 节点)    │───▶│   (30+ skills)      │  │  │
│  │  └─────────────┘    └─────────────┘    └─────────────────────┘  │  │
│  │         │                    │                     │             │  │
│  │  ┌──────┴──────┐    ┌────────┴────────┐    ┌────────┴────────┐  │  │
│  │  │  服务层      │    │   工具系统       │    │   LLM 客户端     │  │  │
│  │  │ (7 services) │    │   (60+ tools)   │    │   (DeepSeek)     │  │  │
│  │  └─────────────┘    └─────────────────┘    └─────────────────┘  │  │
│  │         │                    │                     │             │  │
│  │  ┌──────┴───────────────────┴─────────────────────┴────────┐   │  │
│  │  │                      存储层（三库）                       │   │  │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────────────────────┐ │   │  │
│  │  │  │  SQLite  │  │  KuzuDB  │  │    sqlite-vec（向量）     │ │   │  │
│  │  │  │ 关系库    │  │ 图库     │  │    虚拟表挂主库           │ │   │  │
│  │  │  └──────────┘  └──────────┘  └──────────────────────────┘ │   │  │
│  │  └──────────────────────────────────────────────────────────┘   │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 三、数据库设计（三库分工）

### 3.1 三库架构

每个存档由三个数据库文件组成，切换存档时三库一同切换：

| 数据库 | 技术 | 文件 | 职责 |
|--------|------|------|------|
| **关系库** | SQLite | `{save}.db` | 元信息、客观实体、事件流、锚点剧情、任务/纲领、向量元数据 |
| **图数据库** | KuzuDB | `{save}.kuzu` | 所有实体间关系：角色关系、群体从属、记忆宫殿关联、事件参与图谱 |
| **向量库** | sqlite-vec | 虚拟表挂主 SQLite | 记忆/事件/设定的语义向量 + ANN 检索 |

### 3.2 三大模块归属

```
┌─────────────────────────────────────────────────────────────────┐
│  模块一：元信息层（关系库）                                      │
│  world_meta（tick/game_time/era/protagonist/gameplay_options）  │
└─────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│  模块二：客观层                                                  │
│  关系库：characters / groups / items / maps / map_features /    │
│           character_locations / events / event_participants /   │
│           settings                                              │
│  图库：客观关系边（MemberOf / Leads / SubordinateTo /           │
│        ParticipatedIn / Holds）                                 │
└─────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│  模块三：主观层                                                  │
│  关系库：memories / character_quests / character_agendas /      │
│           quest_steps / character_impressions_cache             │
│  图库：主观关系边（ViewsAs / ViewsGroupAs / MemoryLink）         │
│  向量库：vec_memories / vec_events / vec_settings 虚拟表        │
└─────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│  横切：锚点剧情表（关系库，跨客观/主观）                          │
│  anchor_plots（人工/模型写入，0-5 必然性）                       │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 核心表清单

#### 元信息层

| 表 | 说明 |
|----|------|
| `world_meta` | 单例元信息（tick/game_time/era/protagonist/gameplay_options/world_background） |

#### 客观层

| 表 | 说明 |
|----|------|
| `characters` | 角色（含客观能力 ability_raw/polished、双轨叙事文本） |
| `groups` | 群体（含热力图字段） |
| `character_group_relations` | 角色-群体关系 |
| `group_hierarchies` | 群体从属关系 |
| `items` | 物品 |
| `item_holds` | 物品持有（多态） |
| `maps` | 地图容器（支持层级嵌套 + 移动地图） |
| `map_features` | 地形要素（高楼/山川/河流/星球/飞船） |
| `character_locations` | 角色位置 |
| `events` | 客观事件流（核心主角，含 anchor_id 回链 + plot_arc） |
| `event_participants` | 事件参与人（纯客观 role，无 perception） |
| `settings` | 世界观设定 |

#### 主观层

| 表 | 说明 |
|----|------|
| `memories` | 记忆基本表（含 person_ids/location_ids JSON 索引 + vector_id） |
| `character_impressions_cache` | 印象缓存（图库 ViewsAs 边的快查镜像） |
| `character_quests` | 角色任务（含 deadline_game_time 截止时间） |
| `character_agendas` | 角色行动纲领（含 review_game_time 回顾时间点） |
| `quest_steps` | 任务大纲步骤 |

#### 横切

| 表 | 说明 |
|----|------|
| `anchor_plots` | 锚点剧情表（0-5 必然性 + 状态生命周期） |
| `scheduled_events` | 周期/计划事件调度 |
| `event_dissemination` | 定向传播触达追踪 |
| `public_knowledge` | 媒体报道广播通道 |
| `operation_log` | 操作审计日志 |

### 3.4 图数据库设计（KuzuDB）

#### 节点表

| 节点类型 | 说明 |
|----------|------|
| `CharacterNode` | 角色节点 |
| `GroupNode` | 群体节点 |
| `ItemNode` | 物品节点 |
| `MapNode` | 地图节点 |
| `EventNode` | 事件节点 |
| `MemoryNode` | 记忆节点 |

#### 边表

**客观关系边：**

| 边 | 说明 |
|----|------|
| `MemberOf` | 角色与群体的从属关系（含 role/join_tick/leave_tick） |
| `Leads` | 角色领导群体 |
| `SubordinateTo` | 群体从属 |
| `ParticipatedIn` | 角色参与事件（含 role/depth_hint） |
| `Holds` | 角色持有物品 |

**主观关系边：**

| 边 | 说明 |
|----|------|
| `ViewsAs` | A 对 B 的主观看法（有向！含 favorability/trust/fear） |
| `ViewsGroupAs` | A 对群体的主观看法 |
| `MemoryLink` | 记忆宫殿关联（同场景/因果/情感） |

### 3.5 向量数据库设计

| 虚拟表 | 维度 | 说明 |
|--------|------|------|
| `vec_memories` | FLOAT[768] | 记忆语义向量 |
| `vec_events` | FLOAT[768] | 事件语义向量 |
| `vec_settings` | FLOAT[768] | 设定语义向量 |
| `vec_knowledge` | FLOAT[768] | 知识库条目向量 |

**检索能力：**
- 语义召回 top N + 深度加权排序
- 混合检索（语义 + 精确 person_id/location_id 过滤）
- 取代旧的 memory_index 倒排索引

### 3.6 锚点剧情表设计

**必然性档位（inevitability 0-5）：**

| 档位 | 含义 | 注入方式 |
|------|------|----------|
| 0 | 纯引导灵感 | 作为「可选灵感」注入 |
| 1-2 | 软引导 | 提示「剧本希望…」 |
| 3-4 | 强引导 | 注入 task brief，尽量安排 |
| 5 | 硬约束 | 必须实现，否则打回重生成 |

**状态生命周期：**
```
pending → active → fulfilled / expired / abandoned
```

---

## 四、核心流程——五节点管线

### 4.1 管线总览

```
用户输入(推进事件/时间/动作)
        │
        ▼
┌─────────────────────────────────────────────────┐
│ 节点0：辅助节点                                  │
│  0.6 任务/纲领监控                               │
│  0.7 周期事件调度                                │
└─────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────┐
│ 节点1：前置分析 pre_analyzer                    │
│  · 推演动作时长（失败回退60秒）                 │
│  · 拉取 active 锚点剧情                         │
│  · 生成 task_brief（总结性指导话术）            │
│  · 推进 tick/game_time                          │
└─────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────┐
│ 节点2：角色并发推演 actor_decide（并发）         │
│  每个活跃角色输出 actor_proposal:               │
│  { intent, action, speech,                      │
│    depends_on[], is_reactive,                  │
│    proactive_option, reactive_strategy,         │
│    wait_willingness }                          │
└─────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────┐
│ 节点3：统筹校验 coordinator（核心）              │
│  · 构建动作依赖图 + 拓扑排序                    │
│  · 检测循环依赖 = 同步对峙                       │
│  · 合法性校验（物理/因果/一致性）                │
│  · 不合法打回重生成（上限3轮）                  │
│  · 锚点检查（高必然性是否实现）                 │
│  · 合成完整剧情叙事 + 事件流                    │
└─────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────┐
│ 节点3.5：动态实体创建 world_react_v2             │
│  · 识别剧情中的新实体（角色/群体/设定等）        │
│  · 配额检查（三档制）                           │
│  · 创建新实体 + 写入操作日志                    │
└─────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────┐
│ 节点4：角色更新 character_updater（并发）        │
│  · 记忆编码（关系库 + 向量库双写）              │
│  · 印象更新（图库 ViewsAs + 缓存表双写）        │
│  · 性格/状态/任务变更                           │
└─────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────┐
│ 节点5：全局更新 global_updater                  │
│  · 地形/地图/世界观/文明/科技变更               │
│  · 锚点状态更新                                 │
│  · 消息传播推进                                 │
└─────────────────────────────────────────────────┘
        │
        ▼
   (可选)润色节点 polish_mode != none
```

### 4.2 反应式决策

这是解决「角色 A 与 B 对峙，B 在等 A 出招再决定怎么行动」的核心机制：

1. **节点2** 要求每角色同时输出：
   - `proactive_option`：主动想做什么
   - `reactive_strategy`：若对方先动我怎么反应
   - `wait_willingness`（0-5）：愿意等多久
   - `depends_on[]`：依赖哪些角色先动

2. **节点3** 据此裁决：
   - A.wait=0, B.wait=2 → A 先动，B 用 `reactive_strategy`
   - A.wait=0, B.wait=0 → 同步并发
   - A.wait=2, B.wait=2 → 僵持

**优势**：多数对峙场景用两次交互搞定，无需多轮对话。

### 4.3 打回循环

统筹节点 `coordinator` 的合法性校验支持打回机制：
- 非法动作（物理/因果/性格不一致）被打回，附带 `rejection_reason`
- 仅打回非法的角色决策（非全部），定点重生成
- 上限 3 轮防止死循环

### 4.4 时间模型

| 时间类型 | 说明 |
|----------|------|
| **正常 tick** | 推进固定秒数（10s~86400s），触发五节点管线 |
| **时间跨越** | 跨越较大时间跨度（3天~10000年），走 `time_jump_pipeline`，触发全局更新（地形/文明/年龄等） |

---

## 五、模型与工具系统

### 5.1 Skill（技能）系统

Skill = 系统提示词（skill.md）+ 可用工具集合 + 版本管理。

**Skill 清单（30+ 个）：**

| Skill | 用途 | 所属节点 |
|-------|------|----------|
| `pre_analyzer` | 前置分析（场景摘要 + task_brief） | 节点1 |
| `actor_decide_v2` | 角色决策（含 proactive/reactive） | 节点2 |
| `coordinator` | 统筹校验（合法性 + 锚点检查 + 剧情合成） | 节点3 |
| `character_updater` | 角色更新（记忆/印象/性格/状态） | 节点4 |
| `global_updater` | 全局更新（地形/世界观/文明） | 节点5 |
| `world_react_v2` | 动态实体创建 | 节点3.5 |
| `memory_encoder` | 记忆编码（已并入 character_updater） | — |
| `memory_retriever` | 记忆召回（向量语义检索） | — |
| `memory_decayer` | 记忆衰减 | 节点4后 |
| `quest_monitor` | 任务监控（deadline_game_time） | 节点0.6 |
| `agenda_monitor` | 纲领监控（review_game_time） | 节点0.6 |
| `scheduled_event_dispatcher` | 周期事件调度 | 节点0.7 |
| `rumor_propagator` | 消息传播失真 | 节点5.5 |
| `drama_generator` | 剧本生成（10步管线） | 剧本初始化 |
| `event_polisher` | 事件润色 | 可选后置 |
| `polish_style_selector` | 润色风格选择 | 可选 |
| `prompt_expander` | 剧本预设补全 | 剧本生成 |
| `drama_evaluator` | 剧本合理性评估 + 打回 | 剧本生成 |

**版本管理：**
- 每个 skill 存放在 `agent/conf/skills/{name}/` 目录
- 支持多版本（`v0/skill.md`、`v1/skill.md`）
- API 支持 list/get/create(copytree)/update/set_active

### 5.2 Tool（工具）系统

工具分为以下分组，供 Skill 按需引用：

| 分组 | 工具 | 说明 |
|------|------|------|
| **meta_tools** | 存档/元信息/主角管理 | storage_list_saves / storage_create_save / storage_switch_save 等 |
| **objective_tools** | 客观实体 CRUD + 地图 + 世界事件 | character_filter / character_bulk_create / map_distance 等 |
| **subjective_tools** | 记忆/印象/任务专用 | memory_create / impression_update / quest_bulk_update 等 |
| **graph_tools** | 图库关系查询与写入 | relation_query / relation_upsert / memory_palace_expand 等 |
| **anchor_tools** | 锚点剧情管理 | anchor_list / anchor_create / anchor_fulfill 等 |
| **dynamic_tools** | 动态实体创建 + 配额检查 | entity_quota_check / character_create_dynamic 等 |
| **knowledge_tools** | 知识库检索与管理 | kb_search / kb_add / kb_update 等 |
| **web_fetch_tools** | 网络资源抓取 | web_fetch（含 url_guard 安全检查） |

**工具总量**：约 60-70 个（精简后，移除主观实体的通用 CRUD，专用工具替代）。

### 5.3 LLM 客户端

**核心特性：**
- 基于 OpenAI SDK 的 DeepSeek 客户端
- **Mock 模式**：无 API Key 时自动进入 mock 模式，返回模拟数据
- **Prompt 前缀缓存**：利用 DeepSeek 的前缀缓存机制，记录 system_prompt 的 hash 以命中缓存
- **多轮工具调用**：支持最多 5 轮 tool_call 循环
- **并发支持**：通过 `ContextVar` + `ThreadPoolExecutor` 实现线程隔离的并发 LLM 调用

### 5.4 Trace（追踪）系统

**调用链追踪：**
- 每个 API 请求生成一棵 span 树
- span 类型：`request` / `step` / `skill_call` / `model_call` / `tool_call`
- 并发：兄弟 span 时间区间重叠即并发
- 落盘：`logs/traces_YYYYMMDD.jsonl`（每请求一行 JSON）

---

## 六、API 接口设计

### 6.1 路由总览

| 路由 | 路径 | 说明 |
|------|------|------|
| `config` | `/api/config` | 全局配置读写 |
| `saves` | `/api/saves` | 存档管理（CRUD + 切换 + 快照） |
| `entities` | `/api/entities` | 通用实体 CRUD（按 slug） |
| `character_profiles` | `/api/characters/{id}/profile` | 角色完整档案聚合 |
| `memory` | `/api/memory` | 记忆操作（创建/召回/衰减） |
| `maps` | `/api/maps` | 地图操作（创建/查询/导航） |
| `groups` | `/api/groups` | 群体操作 |
| `world` | `/api/world` | 世界事件（创建/润色/查询） |
| `anchors` | `/api/anchors` | 锚点剧情管理（含状态流转） |
| `scheduled_events` | `/api/scheduled-events` | 周期事件调度 |
| `propagation` | `/api/propagation` | 消息传播追踪 |
| `dramas` | `/api/dramas` | 剧本管理（导入/生成/评估） |
| `agent` | `/api/agent` | Agent 操作（tick/advance/time_jump/call_skill） |
| `traces` | `/api/traces` | 请求日志查询 |
| `v5` | `/api/v5` | v5 新功能（玩法选项/动态实体） |
| `knowledge` | `/api/knowledge` | 知识库管理 |

### 6.2 核心 API

#### 存档管理
```
GET    /api/saves              列出所有存档
POST   /api/saves              创建存档（name）
DELETE /api/saves/{name}       删除存档
POST   /api/saves/{name}/switch 切换当前存档
GET    /api/saves/{name}/meta  获取存档元信息
PUT    /api/saves/{name}/meta  更新元信息
POST   /api/saves/{name}/snapshot 创建快照
```

#### 实体 CRUD（通用）
```
GET    /api/entities/{slug}          列表查询
POST   /api/entities/{slug}          创建（批量）
PUT    /api/entities/{slug}/{id}     更新
DELETE /api/entities/{slug}/{id}     删除
GET    /api/entities/{slug}/count    计数
```

#### Agent 核心操作
```
POST   /api/agent/tick              推进一个 tick
POST   /api/agent/advance           推进指定秒数
POST   /api/agent/time_jump         时间跨越
POST   /api/agent/call_skill        直接调用 skill
```

#### 锚点剧情
```
GET    /api/anchors                 列表（支持 status/inevitability/plot_arc 过滤）
POST   /api/anchors                 创建（human/model 均走此入口）
GET    /api/anchors/{id}            获取详情
PUT    /api/anchors/{id}            更新
DELETE /api/anchors/{id}            删除
POST   /api/anchors/{id}/fulfill   标记已实现（关联 event_id）
POST   /api/anchors/{id}/abandon   放弃锚点
```

#### 角色档案聚合
```
GET    /api/characters/{id}/profile 聚合返回：
  · 客观信息（character）
  · 印象缓存（impressions_cache）
  · 主观关系（图库 ViewsAs）
  · 最近记忆
  · 任务/纲领
  · 相关锚点
  · 参与事件
```

#### 记忆语义检索
```
GET    /api/memory/{char_id}/search?q={自然语言}&limit=10
    语义召回 + 深度加权排序
GET    /api/memory/{char_id}/by_index?person_id=&location_id=
    精确索引查询
```

#### 关系/图查询
```
GET    /api/relations?from={char_id}&type=views_as&depth=2
    代理图库查询，返回关系链
POST   /api/graph/query
    直传 Cypher（受白名单限制，仅查询）
```

#### 请求日志
```
GET    /api/traces                  列表摘要
GET    /api/traces/{id}            完整 span 树
DELETE /api/traces                  清空所有日志
```

---

## 七、前端架构

### 7.1 技术栈

- **React 18** + **TypeScript**
- **Vite 5**（构建工具）
- **PixiJS**（2D 渲染引擎）
- **Three.js**（3D 渲染引擎）
- **Zustand**（状态管理）
- **React Router**（路由）

### 7.2 页面结构

| 页面 | 路径 | 说明 |
|------|------|------|
| 开始页 | `/` | 首页入口（显示功能卡片） |
| 存档管理 | `/saves` | 存档列表、创建、切换 |
| 剧本管理 | `/dramas` | 剧本导入、生成、评估 |
| 模型配置 | `/model` | Skill/Prompt/Tool 编辑 |
| 系统设置 | `/settings` | 全局配置 |
| 请求日志 | `/traces` | 请求日志查看（时间轴火焰图 + 树形视图） |
| 玩法设置 | `/gameplay` | 动态实体配额、上下文预算、世界管理 |
| 世界调度 | `/world-schedule` | 周期事件管理 |
| 操作日志 | `/operations` | 动态实体创建记录 |
| 知识库 | `/knowledge` | 知识库检索与管理 |
| **游戏主界面** | `/play` | 核心游玩界面 |

### 7.3 游戏主界面（GamePage）

```
┌─────────────────────────────────────────────────────────────┐
│                        TopBar（顶栏）                        │
├──────────┬──────────────────────────────────┬───────────────┤
│ LeftPanel│     EventStreamPanel（事件流）    │  RightPanel   │
│ 左侧面板 │                                  │  右侧面板     │
│ · 角色   │                                  │  · 角色档案    │
│ · 群体   │                                  │  · 任务/纲领    │
│ · 物品   │                                  │  · 锚点       │
│ · 地图   │                                  │  · 记忆       │
│          │                                  │               │
├──────────┴──────────────────────────────────┴───────────────┤
│                    BottomBar（底栏）                          │
│  · 玩家动作输入  · 任务/纲领切换  · 推进按钮                  │
├─────────────────────────────────────────────────────────────┤
│                  MapBrowser（地图浏览器）                    │
│  · PixiJS/Three.js 混合渲染  · 三层 Canvas（静态/动态/效果）│
│  · 角色移动动画（travel_progress 插值）                      │
│  · 环境事件可视化（地震波纹圈、火山灰云等）                   │
└─────────────────────────────────────────────────────────────┘
```

### 7.4 关键特性

- **可拖拽布局**：聊天对话框与右侧面板宽度可拖拽调整
- **独立滚动**：各内容区域独立滚动，互不影响
- **地图三层架构**：静态层 / 动态层 / 效果层 Canvas 分离渲染
- **角色移动动画**：基于 `travel_progress` 插值实现平滑过渡
- **环境事件可视化**：地震红色波纹圈、火山灰云等动态效果
- **JSON 自动格式化**：右侧 JSON 内容格式化展示，嵌套对象自动解析
- **Toast 通知**：错误与通知自动消失

---

## 八、关键特性

### 8.1 三库协同

每个存档的三个数据库（SQLite + KuzuDB + 向量库）在创建/切换时同步初始化：
- SQLite schema（含 `vec_*` 虚拟表）
- KuzuDB 图库（建节点/边表）
- 向量库初始化标记

### 8.2 动态实体配额

所有动态实体（角色/群体/设定/地图/地图要素/物品）受三档配额约束：
- **1 tick 上限**：`per_tick`（单次 tick 新增数）
- **100 tick 上限**：`per_100tick`（最近 100 tick 累计）
- **总量上限**：`max_total`（存档全局累计）

超配额时在 `operation_log` 中记录 `rejected_creations`，防止 prompt 无限膨胀。

### 8.3 上下文分层打包

`context_packager` 将上下文分为三层：
- **恒定前缀 A**：系统身份、全局规则、文明/科技/时代背景
- **恒定中段 B**：主角能力、世界观核心设定（essential settings）
- **动态尾段 C**：当前 tick 场景、在场角色、活跃锚点、玩家动作

`context_budget` 控制动态实体注入量，超预算时按 `recency+importance` 截断。

### 8.4 玩法选项加工

`option_processor` 将玩家选项翻译成具体写作指令，而非明文拼接：
- `writing_style` → 直白/隐晦/写意/克制的具体指令
- `death_likelihood` → 归一化为概率区间
- `favorability_bias`/`luck_bias`/`challenge_bias` → 叙事倾向指令
- `player_sexuality` → 叙事视角指令

### 8.5 网络抓取安全

`web_fetch` 工具的严格安全策略：
- 仅当用户主动提供网页链接时才调用
- `url_guard` 阻断本地/内网地址（防 SSRF）
- 限长（默认 8000 字符）
- 工具描述明确「仅当用户提供链接时使用」

### 8.6 独立知识库

引擎级知识库（与存档无关）：
- 独立 SQLite 存储（`knowledge.db`）
- 本地离线向量检索（bge-small-zh 或 text2vec）
- 分类管理 + 标签检索 + 分页/随机输出
- 支持脚本批量导入（JSONL 格式）

### 8.7 周期事件调度

`scheduled_events` 支持：
- 周期事件（daily/weekly/monthly/yearly/custom）
- 一次性事件（one_shot）
- 触发条件 + 过期条件
- 作用范围（character/group/map 等）
- 事件模板 JSON

### 8.8 消息传播系统

支持三种传播通道：
- **定向传播**：口头/书信/电话/网络 → `event_dissemination`（追踪失真路径）
- **广播通道**：媒体报道/官方公告 → `public_knowledge`（按 reach_tags 判断触达）
- **传播失真**：`rumor_propagator` skill 生成失真记忆

---

## 九、部署与运维

### 9.1 快速开始

```bash
# 1. 安装后端依赖
pip install -r src/backend/requirements.txt
copy src\backend\.env.example src\backend\.env
# 编辑 .env 填入 DEEPSEEK_API_KEY

# 2. 构建前端
cd src/frontend
npm install
npm run build

# 3. 启动后端
uvicorn src.backend.http.app:app --host 0.0.0.0 --port 8000 --reload-dir src/backend

# 打开 http://localhost:8000 访问 Web 控制台
```

### 9.2 环境配置

**关键环境变量（`.env`）：**

| 变量 | 说明 | 默认 |
|------|------|------|
| `DEEPSEEK_API_KEY` | LLM API Key | —（未设则进入 mock 模式） |
| `DEEPSEEK_BASE_URL` | API Base URL | `https://api.deepseek.com` |
| `HOST` | 绑定地址 | `0.0.0.0` |
| `PORT` | 绑定端口 | `8000` |
| `RELOAD` | 热重载开关 | `1` |
| `LOG_DIR` | 日志目录 | `logs/` |
| `SAVES_DIR` | 存档目录 | `backend/saves/` |
| `KNOWLEDGE_DIR` | 知识库目录 | `backend/knowledge/` |

### 9.3 依赖清单

**后端（`backend/requirements.txt`）：**
- FastAPI
- uvicorn
- pydantic
- openai（SDK 兼容）
- kuzu==0.11.3（图库）
- sqlite-vec==0.1.9（向量库）
- httpx（网络抓取）

**前端（`frontend/package.json`）：**
- React 18
- TypeScript
- Vite 5
- Zustand（状态管理）
- PixiJS（2D 渲染）
- Three.js（3D 渲染）
- react-router-dom

### 9.4 运行模式

| 模式 | 说明 |
|------|------|
| **Mock 模式** | 无 API Key 时自动开启，所有 LLM 调用返回模拟数据 |
| **正式模式** | 配置 DEEPSEEK_API_KEY 后使用真实 LLM |
| **前端热开发** | `cd src/frontend && npm run dev`，访问 http://localhost:5173 |
| **后端热重载** | `--reload-dir src/backend`，仅监控后端源码变更 |

### 9.5 测试

```bash
cd src/backend
pytest tests/
# 或运行指定测试
pytest tests/test_agent.py      # Agent 管线测试
pytest tests/test_api.py        # API 接口测试
pytest tests/test_drama_import.py # 剧本导入测试
pytest tests/e2e_verify.py      # E2E 验证
```

### 9.6 日志与追踪

- **请求日志**：`logs/traces_YYYYMMDD.jsonl`（每日期分文件，追加模式）
- **运行日志**：`logs/agent_YYYY-MM-DD.log`（按日期命名）
- **API 文档**：`http://localhost:8000/docs`（Swagger UI）
- **健康检查**：`GET /api/health`

---

## 十、目录结构总览

```
projecct/
├── docs/                          # 项目文档
│   └── project_overview.md       # 本文档
├── scripts/                       # 工具脚本
│   ├── start_backend.bat         # 后端启动
│   ├── start_frontend.bat        # 前端启动
│   ├── test_tick.py              # Tick 测试
│   ├── test_llm_e2e.py           # LLM E2E 测试
│   └── ...
├── src/
│   ├── backend/
│   │   ├── agent/                # Agent 核心
│   │   │   ├── conf/
│   │   │   │   ├── prompts/      # Prompt 模板（7 类）
│   │   │   │   ├── skills/       # Skill 定义（30+）
│   │   │   │   ├── tools/        # Tool 实现（11 个模块）
│   │   │   │   └── variables.json
│   │   │   ├── prompt/loader.py  # Prompt 加载器
│   │   │   ├── skill/loader.py   # Skill 加载器
│   │   │   ├── trace.py          # 追踪系统
│   │   │   ├── context_packager.py # 上下文分层打包
│   │   │   ├── option_processor.py # 选项处理器
│   │   │   ├── entity_quota.py   # 实体配额检查
│   │   │   ├── pipeline_v4.py    # v4 五节点管线
│   │   │   ├── pipeline.py       # 兼容旧管线
│   │   │   ├── advance_pipeline.py
│   │   │   ├── time_jump_pipeline.py
│   │   │   └── pipeline_orchestrator.py
│   │   ├── drama/                # 剧本源文件
│   │   │   └── urban_fantasy/    # 都市异能剧本
│   │   ├── http/                 # HTTP 层
│   │   │   ├── routers/          # 14 个路由模块
│   │   │   ├── app.py            # FastAPI 应用工厂
│   │   │   └── deps.py           # 依赖注入
│   │   ├── knowledge/            # 独立知识库
│   │   │   ├── store.py          # 知识库存储
│   │   │   ├── tool.py           # 知识库工具
│   │   │   └── init_sample_data.py
│   │   ├── service/              # 业务逻辑层
│   │   │   ├── drama_service.py
│   │   │   ├── drama_generator.py
│   │   │   ├── memory_service.py
│   │   │   ├── world_service.py
│   │   │   ├── map_service.py
│   │   │   ├── game_time_utils.py
│   │   │   └── propagation_estimator.py
│   │   ├── storage/              # 存储层
│   │   │   ├── models.py        # Active Record 模型（25+ 实体）
│   │   │   ├── connection.py    # SaveManager + Schema 迁移
│   │   │   ├── graph_store.py   # KuzuDB 图库封装
│   │   │   ├── vector_store.py  # sqlite-vec 向量库封装
│   │   │   └── gameplay_defaults.py
│   │   ├── tests/                # 测试
│   │   ├── deepseek_client.py    # LLM 客户端
│   │   ├── env.py                # 环境变量加载
│   │   ├── config.json           # 后端配置
│   │   └── requirements.txt
│   └── frontend/
│       ├── src/
│       │   ├── api/              # API 客户端
│       │   ├── components/       # UI 组件
│       │   │   ├── map/          # 地图渲染组件
│       │   │   ├── TopBar.tsx
│       │   │   ├── LeftPanel.tsx
│       │   │   ├── RightPanel.tsx
│       │   │   ├── BottomBar.tsx
│       │   │   ├── EventStreamPanel.tsx
│       │   │   └── ...
│       │   ├── pages/            # 页面
│       │   │   ├── GamePage.tsx
│       │   │   ├── SavesPage.tsx
│       │   │   ├── DramasPage.tsx
│       │   │   ├── ModelPage.tsx
│       │   │   ├── KnowledgePage.tsx
│       │   │   ├── RequestLogPage.tsx
│       │   │   └── ...
│       │   ├── store/gameStore.ts # Zustand 状态管理
│       │   ├── styles/           # 样式
│       │   ├── App.tsx
│       │   └── main.tsx
│       ├── index.html
│       ├── package.json
│       └── vite.config.ts
├── knowledge_template.md         # 知识库模板
└── .gitignore
```

---

## 附录：版本演进

| 版本 | 核心特性 |
|------|----------|
| **v3** | 19 张表单一 SQLite、7 步顺序管线、基础 Agent 编排 |
| **v4** | 三库分工（SQLite+KuzuDB+向量）、五节点管线、反应式决策、锚点剧情、图库关系、语义检索 |
| **v5** | 动态实体配额、上下文分层打包、玩法选项加工、独立知识库、网络抓取、消息传播、周期调度、剧本一键生成 |

---

*文档生成时间：2026-08-08 · 基于当前代码库分析*
