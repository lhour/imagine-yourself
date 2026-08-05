<a id="v3-top"></a>

# 「设身处地」v3 完整系统重新设计规格书

> 基于客观事实 / 主观记忆双轨制叙事引擎

*版本*：v3.0.0 *日期*：2026-08-05 *状态*：设计稿

---

## 目录

- [一、设计总览](#s1-overview)
  - [1.1 核心理念](#s1-1)
  - [1.2 架构分层](#s1-2)
  - [1.3 「关键文本 + 润色文案」双字段约定](#s1-3)
- [二、数据库设计](#s2-database)
  - [2.1 命名与存储概览](#s2-1)
  - [2.2 元信息表（单例）](#s2-2)
  - [2.3 客观表](#s2-3-objects)
    - [2.3.1 角色表 `characters`](#s2-3-1)
    - [2.3.2 群体表 `groups`](#s2-3-2)
    - [2.3.3 角色-群体关系表 `character_group_relations`](#s2-3-3)
    - [2.3.4 群体从属表 `group_hierarchies`](#s2-3-4)
    - [2.3.5 物品表 `items`](#s2-3-5)
    - [2.3.6 物品持有表 `item_holds`](#s2-3-6)
    - [2.3.7 地图表 `maps`](#s2-3-7)
    - [2.3.8 角色位置表 `character_locations`](#s2-3-8)
    - [2.3.9 事件表 `events`](#s2-3-9)
    - [2.3.10 事件参与表 `event_participants`](#s2-3-10)
    - [2.3.11 设定表 `settings`](#s2-3-11)
  - [2.4 主观记忆系统（核心创新）](#s2-4-memory)
    - [2.4.1 记忆基本表 `memories`](#s2-4-1)
    - [2.4.2 记忆索引表 `memory_index`](#s2-4-2)
    - [2.4.3 记忆宫殿（关联图谱）`memory_links`](#s2-4-3)
    - [2.4.4 角色印象表 `character_impressions`](#s2-4-4)
  - [2.5 任务与纲领系统表](#s2-5-quests)
    - [2.5.1 角色任务表 `character_quests`](#s2-5-1)
    - [2.5.2 角色行动纲领表 `character_agendas`](#s2-5-2)
    - [2.5.3 任务大纲步骤表 `quest_steps`](#s2-5-3)
  - [2.6 快照与迁移策略](#s2-6)
- [三、后端接口层](#s3-api)
  - [3.1 通用 CRUD 与高级查询规范](#s3-1)
  - [3.2 存档管理 `/api/saves`](#s3-2)
  - [3.3 记忆专用端点 `/api/memory`（核心）](#s3-3)
  - [3.4 事件与时间推进 `/api/world`](#s3-4)
  - [3.5 剧本管理 `/api/dramas`](#s3-5)
  - [3.6 模型配置 `/api/agent`](#s3-6)
  - [3.7 全局配置 `/api/config`](#s3-7)
- [四、模型层（LLM 管线）](#s4-model)
  - [4.1 Prompt / Skill / Tools 模块化配置](#s4-1)
  - [4.2 正常推进管线（Normal Tick）](#s4-2)
  - [4.3 时间跨越管线（Time Jump）](#s4-3)
  - [4.4 记忆加载管线（Memory Retriever）](#s4-4)
  - [4.5 任务推进与失败检测](#s4-5)
  - [4.6 事件润色管线（Polish）](#s4-6)
- [五、前端交互层（游戏页面）](#s5-frontend-gameplay)
  - [5.1 整体布局](#s5-1)
  - [5.2 左设置栏](#s5-2)
  - [5.3 主事件流区（核心页面）](#s5-3)
  - [5.4 时间控制条](#s5-4)
  - [5.5 玩家动作与任务纲领面板](#s5-5)
  - [5.6 菜单栏（实体浏览）](#s5-6)
- [六、前端管理页面](#s6-admin)
  - [6.1 开始游戏（首页）](#s6-1)
  - [6.2 读取存档](#s6-2)
  - [6.3 模型管理（Prompt / Skill 版本管理）](#s6-3)
  - [6.4 剧本管理（一键生成 + 编辑 + 删除）](#s6-4)
  - [6.5 全局设置](#s6-5)
- [七、剧本源文件格式](#s7-drama-format)
  - [7.1 剧本目录结构](#s7-1)
  - [7.2 各文件 JSONL 字段规范](#s7-2)
  - [7.3 一键生成剧本流程](#s7-3)
- [八、工程约定与硬约束](#s8-conventions)

---

<a id="s1-overview"></a>

## 一、设计总览

<a id="s1-1"></a>

### 1.1 核心理念

v3 是一次从数据库→接口→管线→前端的整体重新设计，围绕两个核心主张：

1. **客观/主观双轨制**
   - **客观层（Objective）：上帝视角下的世界事实——角色外貌/位置/事件真实发生的事，存于**客观表**。
   - **主观层（Subjective）：每个角色各自的感知与记忆，因视角偏差、信息缺失、记忆失真而各不相同，存于**主观记忆系统**。
2. **关键文本 + 润色文案**双字段：所有需人类阅读的文本一律存两份：
   - `raw（关键文本，简短、结构化、LLM友好、可索引可过滤）
   - `polished`（润色后优美的叙事文案，供前端展示，可重复润色）
3. **时间的主角是事件**：游戏的推进的推进的本质是**事件流**，所有角色/物品/位置变化都附着在事件上，事件是一切的主角。
4. **记忆宫殿与按需加载**：不把所有记忆一次性塞进 Prompt，而是按深度→索引→宫殿关联→逐层加载，实现真正智能的上下文管理。

<a id="s1-2"></a>

### 1.2 架构分层

```
┌────────────────────────────────────────────────────────────────┐
│                       前端 Frontend (React + Vite + TS)            │
│  ┌──────────┐ ┌───────────────┐ ┌────────────┐ ┌──────────────┐ │
│  │ 管理页 │ │   游戏页面   │ │  菜单栏   │ │  设置面板     │ │
│  └────┬─────┘ └───────┬───────┘ └─────┬──────┘ └──────┬───────┘ │
└───────┼───────────────┼───────────────┼───────────────┼───────────┘
        │               │               │               │  HTTP / REST
┌───────┴───────────────┴───────────────┴───────────────┴───────────┐
│                    FastAPI Backend                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────┐   │
│  │  Router 层   │  │  Service 层   │  │  Agent Harness LLM 管线  │   │
│  │ (REST 路由)   │  │(业务/剧本)    │  │ + Skill/Tool/PromptMgr  │   │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬────────────┘   │
└─────────┼─────────────────────┼────────────────────────┼────────────────┘
          │                     │                        │
┌─────────┴─────────────────────┴────────────────────────┴────────────────┐
│                        存储 Storage (SQLite · 多存档分库)                        │
│  ┌────────────────┐  ┌──────────────────────┐  ┌──────────────────┐    │
│  │  客观表组   │  │   主观记忆系统组    │  │  任务/元信息表组    │    │
│  └────────────────┘  └──────────────────────┘  └──────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

<a id="s1-3"></a>

### 1.3 「关键文本 + 润色文案」双字段约定

贯穿 v3 全库的统一字段命名：

| 字段名 | 含义 | 示例 |
|--------|------|------|
| `raw` | 关键文本，极简结构化，LLM 友好，可索引可过滤 | "角色A 拥抱 角色B，地点 酒馆 |
| `polished` | 润色后叙事文本，可重新生成 | "沈默伸出臂膀，将对方轻轻拥入怀中，酒香与她发丝的气息在酒馆中萦绕..." |

所有面向玩家的前端展示优先显示 `polished`；LLM 在做推理/索引/过滤时一律用 `raw`。`polished` 可通过 `event_polisher` skill 独立再次生成（可控制长度/风格/血腥度等配置）。

---

<a id="s2-database"></a>

## 二、数据库设计

<a id="s2-1"></a>

### 2.1 命名与存储概览

- **多存档分库**：每个存档一个独立 `.db` 文件，存放在 `saves/{存档名}.db`。
- **快照目录**：`saves/{存档名}.snapshots/round_{N:04d}_{YYYYMMDD_HHMMSS}.db`。
- **元信息单例表**：`world_meta`（每个 db 内只有 1 行）。
- **重要字段硬约束**：
  - `importance` 一律 0–5（默认 3）。
  - 游戏时间格式：`{纪元}{年}年{月}月{日}日{时}时{分}分{秒}秒`（可表示范围/估计）。
  - 所有状态字段一律为字符串（`status`），如 `健康/受伤/暴怒`。
  - 所有可扩展属性一律 `custom_attrs` JSON TEXT。

客观表 7 张 + 关联表 4 张 + 记忆系统 4 张 + 任务系统 3 张 + 元信息 1 张 = **19 张**。

<a id="s2-2"></a>

### 2.2 元信息表（单例） `world_meta`

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK 主键自增 | 永远为 1 |
| tick_num | INTEGER | NOT NULL DEFAULT 1 | 当前推进轮次（替代 round_num），每 tick+1 |
| game_time | TEXT | NOT NULL | 当前游戏内时间 |
| era_name | TEXT | 可空 | 纪元名，便于显示："源石纪元" / "灵气纪元" |
| script_name | TEXT | 可空 | 剧本名 |
| protagonist_id | INTEGER | FK → characters.id | 主角角色 ID |
| real_time | TEXT | NOT NULL | 上一次保存的真实世界时间戳 |
| description | TEXT | 可空 | 存档简介 |
| custom_attrs | TEXT(JSON) | DEFAULT '{}' | 自定义属性 |

<a id="s2-3-objects"></a>

### 2.3 客观表

<a id="s2-3-1"></a>

#### 2.3.1 角色表 `characters`

> 上帝视角下的客观角色信息。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK |  |
| name | TEXT | NOT NULL | 角色姓名 |
| appearance_raw | TEXT | NOT NULL | 外貌关键文本 |
| appearance_polished | TEXT | 可空 | 外貌润色 |
| personality_raw | TEXT | NOT NULL | 性格关键文本（如"外冷内热/理性/多疑"） |
| personality_polished | TEXT | 可空 | 性格润色描述 |
| gender | TEXT | 可空 | 性别 |
| age | INTEGER | 可空 | 年龄 |
| status | TEXT | DEFAULT '' | 客观状态（健康/受伤/暴怒/死亡…可用 `/` 分隔多维 |
| importance | INTEGER | DEFAULT 3 | 0–5 |
| custom_attrs | TEXT(JSON) | DEFAULT '{}' | 自定义客观属性（职业/异能等级/种族…） |
| created_at_tick | INTEGER | DEFAULT 0 | 创建时 tick |
| dead_at_tick | INTEGER | 可空 | 死亡 tick（可空=存活） |

索引：`idx_char_name(name)`、`idx_char_status(status)`、`idx_char_importance(importance)`。

<a id="s2-3-2"></a>

#### 2.3.2 群体表 `groups`

> 一个群体 = 任一可被视为整体的人/物集合。支持层级从属（通过 `group_hierarchies` 表）。
> **每个群体绑定一个「主要活动地图」+ 一张「分布热力图」**，前端可在地图上以热力图层可视化群体的空间分布。

例：长安城居民、酒馆酒客、森林魔物团、某军队军团。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK |  |
| name | TEXT | NOT NULL | 群体名称 |
| desc_raw | TEXT | NOT NULL | 群体是什么 |
| desc_polished | TEXT | 可空 | 润色 |
| group_type | TEXT | NOT NULL | 枚举：`residence`(居民) / `military`(军队) / `organization`(组织) / `monster`(魔物) / `crowd`(人群) / `custom` |
| leader_id | INTEGER | FK → characters.id 可空 | 领导人角色 ID |
| importance | INTEGER | DEFAULT 3 | 0–5 |
| **primary_map_id** | INTEGER | FK → maps.id 可空 | **主要活动地图**（热力图绑定到此地图坐标系） |
| **center_x** | REAL | 可空 | 群体分布中心 X（在 primary_map 坐标系内） |
| **center_y** | REAL | 可空 | 群体分布中心 Y |
| **spread_radius** | REAL | DEFAULT 0.0 | 分布半径（0=点状集中；越大越分散） |
| **distribution_raw** | TEXT | 可空 | 分布关键文本（"集中在东区贫民窟/沿河两岸散布"） |
| **heatmap_grid** | TEXT(JSON) | 可空 | **热力图栅格数据**（见下方格式） |
| **heatmap_resolution** | INTEGER | DEFAULT 16 | 热力图分辨率（每边格子数，默认 16×16） |
| **heatmap_updated_tick** | INTEGER | 可空 | 热力图最后更新 tick |
| custom_attrs | TEXT(JSON) | DEFAULT '{}' | 扩展：成员规模、据点、宗旨等 |
| created_at_tick | INTEGER | DEFAULT 0 | 创建 tick |

索引：`idx_group_name(name)`、`idx_group_type(group_type)`、`idx_group_map(primary_map_id)`。

##### `heatmap_grid` JSON 格式

把 `primary_map` 划成 `heatmap_resolution × heatmap_resolution` 个格子，每格一个 0–1 的密度值。前端渲染成热力图叠加在地图 Canvas 上。

```json
{
  "resolution": 16,
  "bbox": {"x": 0.0, "y": 0.0, "w": 100.0, "h": 80.0},
  "cells": [
    [0.0, 0.1, 0.3, 0.8, 1.0, 0.7, 0.2, ...],
    [0.0, 0.2, 0.5, 0.9, 0.8, 0.4, 0.1, ...],
    ...
  ],
  "min_density": 0.0,
  "max_density": 1.0,
  "unit_hint": "人口密度/兵力密度/魔物出没频率"
}
```

- `bbox`：热力图覆盖的区域（在 primary_map 坐标系内），通常等于地图的 `width × height`。
- `cells`：二维数组，`cells[row][col]` 为该格子密度（0=无，1=最密集）。
- `unit_hint`：人能读的单位说明（前端 tooltip 用）。
- 若群体是点状分布（如单个酒馆全员聚集），可只填 `center_x/center_y` 而不存 `heatmap_grid`，前端用 spread_radius 画一个高斯晕染圆。

##### 热力图更新策略

- **手动更新**：管理员模式 / 剧本初始化时由 `drama_generator` 写入。
- **自动更新**：`memory_decayer` 同期或独立一个 `group_heatmap_refresher` skill，每 N tick 根据成员（通过 `character_group_relations` + 各自 `character_locations`）重新统计栅格。
- **时间跨越后**：`time_skip_summarizer` 必须重新生成所有群体的 `heatmap_grid`（文明兴衰后群体分布会大变）。

<a id="s2-3-3"></a>

#### 2.3.3 角色-群体关系表 `character_group_relations`

> 一个角色可同时属多个群体。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK |  |
| char_id | INTEGER | FK → characters.id |  |
| group_id | INTEGER | FK → groups.id |  |
| role_raw | TEXT | DEFAULT 'member' | 在群体中的身份关键文本（"member/owner/leader/guest…） |
| join_tick | INTEGER | DEFAULT 0 | 加入时的 tick |
| leave_tick | INTEGER | 可空 | 离开 tick，可空=仍在 |
| importance_in_group | INTEGER | DEFAULT 3 | 群体内重要性 0–5 |

索引：`idx_cgr_char(char_id)`、`idx_cgr_group(group_id)`。

<a id="s2-3-4"></a>

#### 2.3.4 群体从属表 `group_hierarchies`

> 表达群体层级：酒馆酒客 ⊂ 城市居民 ⊂ 国家公民。允许多父多子（通过关联表），也可只做森林 A 属势力 A 同时属势力 B）。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK |  |
| child_group_id | INTEGER | FK → groups.id | 子群体 |
| parent_group_id | INTEGER | FK → groups.id | 父群体 |
| relation_raw | TEXT | DEFAULT 'subset' | 从属关系关键文本 |
| weight | REAL | DEFAULT 1.0 | 从属程度/比例 0–1 |

索引：`idx_gh_child`、`idx_gh_parent`。

<a id="s2-3-5"></a>

#### 2.3.5 物品表 `items`

> 所有客观存在的无思想实体：一件衣、甲、剑、药、花、钱。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK |  |
| name | TEXT | NOT NULL | 物品名 |
| desc_raw | TEXT | NOT NULL | 物品关键文本 |
| desc_polished | TEXT | 可空 | 润色 |
| item_type | TEXT | NOT NULL | `weapon`/`armor`/`consumable`/`clothes`/`money`/`plant`/`tool`/`material`/`custom` |
| rarity | INTEGER | DEFAULT 1 | 稀有度 0–5 |
| importance | INTEGER | DEFAULT 3 | 0–5 |
| is_stackable | INTEGER | DEFAULT 0 | 0/1 是否可堆叠 |
| stack_size | INTEGER | DEFAULT 1 | 堆叠数（如一捆箭 100 支=100） |
| custom_attrs | TEXT(JSON) | DEFAULT '{}' | 伤害/防御/特效/面额 |
| created_at_tick | INTEGER | DEFAULT 0 |  |

索引：`idx_item_name`、`idx_item_type`。

<a id="s2-3-6"></a>

#### 2.3.6 物品持有表 `item_holds`

> 物品在哪里：人身上 / 地上 / 银行 / 箱子里 / 商店里。**持有的「位置+容器」。用多态外键表达：
`holder_type + holder_id`。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK |  |
| item_id | INTEGER | FK → items.id |  |
| quantity | INTEGER | DEFAULT 1 | 持有数量 |
| holder_type | TEXT | NOT NULL | `character` / `map_location` / `group` / `storage`(银行/仓库) / `item`(嵌套容器) |
| holder_id | INTEGER | NOT NULL | 对应表的 ID |
| holder_detail | TEXT | 可空 | 具体子位置："背后剑鞘"/"宝箱底层" |
| acquired_tick | INTEGER | DEFAULT 0 | 获得时 tick |
| use_times | INTEGER | DEFAULT -1 | 使用次数（-1=无限） |

索引：`idx_ih_item`、`idx_ih_holder(holder_type, holder_id)`。

<a id="s2-3-7"></a>

#### 2.3.7 地图表 `maps`（v3 重新设计）

> **设计目标**：完整绘制地图地形（城市高楼/宇宙星球/山川河流/飞船），不需形象但要按层级画出位置关系，并能描述任意两对象间的距离。
> **核心改动**：
> 1. 统一坐标系字段（去掉 2D/3D/球面互斥分支），统一存 `bbox` + `unit`。
> 2. **拆分「地图容器」与「地形要素」**：地图本身只是容器/坐标系，具体的山/楼/河/星球放到独立 `map_features` 表。
> 3. 支持**移动地图节点**（飞船/马车），关联载体角色/物品，每 tick 自动更新位置。
> 4. 内置**比例尺与单位**，自动计算两点距离。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK |  |
| name | TEXT | NOT NULL | 地图/区域名（"长安城"/"猎户座旋臂"/"沈默的飞船"） |
| desc_raw | TEXT | NOT NULL | 关键描述 |
| desc_polished | TEXT | 可空 | 润色描述 |
| parent_map_id | INTEGER | FK → maps.id 可空 | 父地图（可空=顶级；飞船这类移动地图也可指向当前所在的大地图） |
| map_type | TEXT | NOT NULL | `universe`/`galaxy`/`star_system`/`planet`/`continent`/`country`/`city`/`district`(街区)/`building`/`room`/`vehicle`(飞船/车船等移动载体内部)/`plane`/`region`/`custom` |
| coord_system | TEXT | DEFAULT 'cartesian_2d' | `cartesian_2d`（平面）/ `cartesian_3d`（空间，星系/宇宙）/ `spherical`（星球表面） |
| **scale_unit** | TEXT | DEFAULT 'm' | **比例尺单位**：`m`(米)/`km`(千米)/`AU`(天文单位)/`ly`(光年)/`step`(步)/`custom` |
| **scale_per_unit** | REAL | DEFAULT 1.0 | 1 个单位 = 多少 scale_unit（例 100 表示坐标系单位 1 = 100 米） |
| bbox_x | REAL | DEFAULT 0.0 | 地图左上角 X（坐标系原点） |
| bbox_y | REAL | DEFAULT 0.0 | 左上角 Y |
| bbox_w | REAL | NOT NULL | 地图宽度（单位与 scale_unit 一致） |
| bbox_h | REAL | NOT NULL | 地图高度 |
| bbox_d | REAL | 可空 | 深度（仅 cartesian_3d 用，星球/星系/宇宙） |
| **default_zoom** | REAL | DEFAULT 1.0 | 前端默认缩放倍率 |
| **default_center_x** | REAL | 可空 | 默认视图中心 X |
| **default_center_y** | REAL | 可空 | 默认视图中心 Y |
| **is_mobile** | INTEGER | DEFAULT 0 | 0/1 是否是移动地图（飞船/车/船） |
| **carrier_char_id** | INTEGER | FK → characters.id 可空 | 移动地图的载体角色（如飞船的舰长） |
| **carrier_item_id** | INTEGER | FK → items.id 可空 | 移动地图的载体物品（如马车本身是一件物品） |
| **current_x** | REAL | 可空 | 移动地图当前在父地图中的 X 坐标（每 tick 更新） |
| **current_y** | REAL | 可空 |  |
| **current_z** | REAL | 可空 | 3D 用 |
| **current_map_id** | INTEGER | FK → maps.id 可空 | 移动地图当前所在的父地图 ID（飞船此刻在城市A上空） |
| importance | INTEGER | DEFAULT 3 | 0–5 |
| custom_attrs | TEXT(JSON) | DEFAULT '{}' | 扩展（天气/危险度/所属势力/星球重力等） |
| created_at_tick | INTEGER | DEFAULT 0 |  |

索引：`idx_map_parent(parent_map_id)`、`idx_map_type(map_type)`、`idx_map_mobile(is_mobile)`、`idx_map_current(current_map_id)`。

##### 地图层级示例

```
cartesian_3d, unit=ly（光年）
└── 银河系 (map)
    └── 猎户座旋臂 (map, 父=银河系)
        └── 太阳系 (map, 父=猎户座旋臂)
            └── 地球 (map, spherical, 父=太阳系)
                └── 东亚大陆 (map, 父=地球)
                    └── 长安城 (map, cartesian_2d, unit=m)
                        └── 东市街区 (map, 父=长安城)
                            └── 沈默的酒馆 (map, 父=东市街区)
                                └── 酒馆大堂 (map, 父=酒馆)
                        └── 沈默的飞船 (map, is_mobile=1, current_map_id=长安城, current_x=... )
                            └── 飞船驾驶舱 (map, 父=飞船)
```

---

<a id="s2-3-7-features"></a>

#### 2.3.7-bis 地形要素表 `map_features`（v3 核心新增）

> 一张地图只是空容器，**所有可见的地形对象都是 feature**：高楼、山、河、湖、森林、道路、星球、恒星、小行星带、星云、飞船、家具、植被……每个 feature 是地图上的一个可绘制对象，可被点击、可被寻路、可承载子地图（点高楼→进入楼内平面图）。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK |  |
| map_id | INTEGER | FK → maps.id NOT NULL | 所属地图 |
| name | TEXT | NOT NULL | 要素名（"沈默酒馆"/"中央高楼"/"长江"/"火星"） |
| desc_raw | TEXT | 可空 | 关键描述 |
| desc_polished | TEXT | 可空 | 润色描述 |
| feature_type | TEXT | NOT NULL | `building`(高楼建筑)/`mountain`(山)/`river`(河)/`lake`(湖)/`forest`(森林)/`road`(道路)/`bridge`(桥)/`wall`(墙)/`vegetation`(植被)/`furniture`(家具)/`star`(恒星)/`planet`(星球)/`moon`(卫星)/`asteroid`(小行星)/`asteroid_belt`(小行星带)/`nebula`(星云)/`starship`(飞船)/`station`(空间站)/`region`(区域填充)/`custom` |
| shape | TEXT | NOT NULL | `point`(点：一棵树/一颗星)/`line`(线：河流/道路)/`polygon`(多边形：建筑轮廓/森林)/`circle`(圆：星球/小行星)/`volume`(体：3D 星云/建筑高度) |
| **geometry** | TEXT(JSON) | NOT NULL | **几何数据**，见下方格式 |
| size_value | REAL | 可空 | 主尺寸（半径/长度/高度，单位与所属 map 的 scale_unit 一致） |
| size_unit_override | TEXT | 可空 | 单位覆盖（若与地图单位不同） |
| **layer_z** | INTEGER | DEFAULT 0 | **绘制层级深度**（小→大，先画的在下层；例：地形0/道路1/建筑2/家具3/角色4） |
| **color_hint** | TEXT | 可空 | 颜色提示（"灰白/赤红/碧蓝"），前端按 type+hint 渲染 |
| **icon_hint** | TEXT | 可空 | 图标提示（用于点状要素的图标选择） |
| visual_raw | TEXT | 可空 | **视觉关键文本**（"30层玻璃幕墙高楼，顶部有直升机停机坪"）— LLM 用于生成绘制 |
| visual_polished | TEXT | 可空 | 视觉润色文本 |
| **is_obstacle** | INTEGER | DEFAULT 0 | 0/1 是否是障碍物（影响寻路） |
| **is_mobile** | INTEGER | DEFAULT 0 | 0/1 是否会动（飞船/马车 feature 本身会动） |
| **carrier_id** | INTEGER | 可空 | 移动要素的载体 ID（character 或 item）+ carrier_type |
| carrier_type | TEXT | 可空 | `character`/`item`/`map`（关联一个移动地图） |
| **current_x** | REAL | 可空 | 移动要素的当前 X（每 tick 更新） |
| current_y | REAL | 可空 |  |
| current_z | REAL | 可空 | 3D 用 |
| **child_map_id** | INTEGER | FK → maps.id 可空 | **点击此要素时进入的子地图**（"进入高楼"→楼内平面图；"登陆火星"→火星表面地图） |
| parent_feature_id | INTEGER | FK → 本表可空 | 要素嵌套（高楼里的电梯/房间里的家具） |
| importance | INTEGER | DEFAULT 3 | 0–5 |
| custom_attrs | TEXT(JSON) | DEFAULT '{}' | 扩展（楼层/材质/建造年代等） |
| created_at_tick | INTEGER | DEFAULT 0 |  |

索引：`idx_mf_map(map_id)`、`idx_mf_type(feature_type)`、`idx_mf_layer(map_id, layer_z)`、`idx_mf_child(child_map_id)`、`idx_mf_mobile(is_mobile)`。

##### `geometry` JSON 格式（按 shape 不同）

```json
// shape=point：一棵树/一颗星球
{ "x": 50.0, "y": 30.0, "z": null }

// shape=line：一条河/一条路
{ "points": [[0,10],[20,15],[50,12],[80,30]], "width": 2.0 }

// shape=polygon：一栋高楼/一片森林的轮廓
{ "points": [[10,10],[30,10],[30,25],[10,25]], "holes": [] }

// shape=circle：星球/小行星
{ "cx": 0, "cy": 0, "r": 6371.0 }

// shape=volume：3D 星云/带高度的建筑
{ "points": [[10,10],[30,10],[30,25],[10,25]], "z_min": 0, "z_max": 120.0 }
```

##### 要素 → 子地图跳转链

地形要素可关联一个 child_map_id：
- 高楼 feature → child_map_id 指向"楼内平面图"地图
- 星球 feature → child_map_id 指向"星球表面地图"
- 飞船 feature → child_map_id 指向"飞船内部地图"
- 酒馆 feature → child_map_id 指向"酒馆内部地图"

前端点击要素 → 若有 child_map_id → 平滑过渡到子地图视图（面包屑导航记录路径）。

##### 移动要素与移动地图的关系

| 场景 | 数据怎么存 |
|------|-----------|
| 一艘飞船（既是地图也是要素） | `maps` 表存一条 is_mobile=1 的飞船地图；同时 `map_features` 存一条 feature_type=starship 的要素，geometry 指向飞船当前位置；`map_features.child_map_id` 指向飞船地图 ID；`map_features.is_mobile=1`，每 tick 同步两者坐标 |
| 一匹马（只是要素不是地图） | 只存 `map_features`（feature_type=custom, is_mobile=1），无 child_map_id；角色骑马时 character_locations.feature_id 指向马 |
| 一栋静止的高楼 | 只存 `map_features`（feature_type=building），child_map_id 指向楼内地图，is_mobile=0 |

---

<a id="s2-3-7-distance"></a>

#### 2.3.7-ter 距离系统（v3 新增）

> 后端按地图的 scale_unit + 坐标自动计算任意两对象距离，并生成人话表达。

**距离计算规则**：

1. **同地图内两 feature**：欧氏距离 `sqrt(dx²+dy²+dz²) × scale_per_unit`，单位用 scale_unit。
2. **同地图内两角色**：用各自 character_locations 的 x/y/z，同上。
3. **跨层级**（角色A在酒馆、角色B在城市另一街区）：递归把双方位置换算到共同祖先地图的坐标系，再算欧氏距离。
   - 例：A 在"酒馆大堂"(0.5, 0.5) → 酒馆在"东市街区"(20, 30) → 东市在"长安城"(100, 200)；B 在长安城(105, 195)；最终距离 ≈ 5×scale。
4. **完全不在同一地图树**（角色A在地球，角色B在火星）：返回语义距离（"约 5500 万 km / 0.37 AU"），不做精确计算。

**距离 API**：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/maps/distance` | 请求体：`{from: {type, id}, to: {type, id}, via_map_id?: ..., prefer_unit?: 'auto'}`；type ∈ `character/group/item/feature/map`。返回：`{meters, display:"3.2 km", path: [地图链], semantic:"步行约 40 分钟"}` |
| GET | `/api/maps/{id}/distance_matrix?ids=1,2,3` | 一次性算多个要素两两距离（地图浏览器测距工具用） |
| GET | `/api/characters/{id}/distance_to?target_type=character&target_id=5` | 角色到目标的距离快捷端点 |

**语义距离生成**：根据 scale_unit + scale_per_unit 自动选合适的展示：
- < 1 km → "步行 X 分钟"（按 5 km/h 估算）
- 1–100 km → "X.Y km"
- 100 km – 1 AU → "X 万 km"
- 行星尺度 → "X 地球周长"
- 0.1–100 AU → "X AU"
- > 100 AU → "X 光年" / "X 千秒差距"

<a id="s2-3-8"></a>

#### 2.3.8 角色位置表 `character_locations`

> 角色当下坐标。v3 增加 `feature_id` 字段：角色可以"在某要素里"（骑马/在飞船上/在高楼内），feature_id 优先于 x/y/z 作为定位语义。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK |  |
| char_id | INTEGER | FK → characters.id UNIQUE | 每个角色一个当前位置 |
| map_id | INTEGER | FK → maps.id 可空 | 所在地图 |
| **feature_id** | INTEGER | FK → map_features.id 可空 | **所在要素**（骑马=马要素/在飞船=飞船要素/在高楼=楼要素）。若要素 is_mobile=1，角色随要素移动，x/y/z 可不填 |
| x | REAL | 可空 | 精确 X 坐标（小区域不填） |
| y | REAL | 可空 | 精确 Y |
| z | REAL | 可空 | 精确 Z |
| location_detail_raw | TEXT | 可空 | 关键文本（"酒馆二楼靠窗"） |
| last_update_tick | INTEGER | DEFAULT 0 | 最后移动 tick |

索引：`idx_cl_char(char_id)`、`idx_cl_map(map_id)`、`idx_cl_feature(feature_id)`。

> **跟随逻辑**：若 `feature_id` 指向一个 is_mobile=1 的要素（如马/飞船），角色的实际位置 = 要素位置 + 角色相对偏移；查询角色位置时后端自动 join feature.current_x/y。

<a id="s2-3-9"></a>

#### 2.3.9 事件表 `events`（核心主角）

> 客观事件是世界的第一公民。一切变化都附着事件（时间点/地点/参与人/内容）。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK |  |
| tick_num | INTEGER | NOT NULL | 发生在第几 tick |
| game_time | TEXT | NOT NULL | 游戏内时间字符串 |
| event_type | TEXT | NOT NULL | 事件类型枚举：`social`(社交) / `combat`(战斗) / `move`(移动) / `item_transfer`(物品) / `environment`(环境) / `dialog`(对话) / `quest`(任务) / `system`(系统) / `custom` |
| location_map_id | INTEGER | FK → maps.id 可空 | 发生地点地图 ID |
| location_detail_raw | TEXT | 可空 | 子位置关键文本 |
| content_raw | TEXT | NOT NULL | **事件关键文本（极简） |
| content_polished | TEXT | 可空 | **润色后的叙事文本（展示用） |
| importance | INTEGER | DEFAULT 3 | 0–5 事件重要度 |
| visibility | TEXT | DEFAULT 'public' | `public`/`private`/`secret` |
| source_event_id | INTEGER | FK → events.id 可空 | 若由哪个事件引发（链条追踪） |
| custom_attrs | TEXT(JSON) | DEFAULT '{}' | 扩展（伤害值/金钱变化/情绪强度等） |

索引：`idx_event_tick(tick_num)`、`idx_event_map(location_map_id)`、`idx_event_type(event_type)`、`idx_event_importance(importance)`。

> 参与人用关联表存（一对多）。

<a id="s2-3-10"></a>

#### 2.3.10 事件参与表 `event_participants`

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK |  |
| event_id | INTEGER | FK → events.id |  |
| participant_type | TEXT | NOT NULL | `character` / `group` / `item` / `map`(环境作为"旁观者"） |
| participant_id | INTEGER | NOT NULL | 对应 ID |
| role_raw | TEXT | NOT NULL | 参与角色：`protagonist`(主视角主角) / `secondary`(配角) / `bystander`(旁观者/第三者) / `victim`(受害者) / `initiator`(发起者) |
| perception_raw | TEXT | 可空 | 该参与者在本事件中**客观上**做了啥（关键文本） |

索引：`idx_ep_event`、`idx_ep_participant`。

> 注意：事件参与表是客观谁参与了；而**主观上每个参与者的感知、记忆、看法不同，那是记忆系统层（下面）。

<a id="s2-3-11"></a>

#### 2.3.11 设定表 `settings`

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK |  |
| category | TEXT | NOT NULL | 分类：`world`(世界观) / `era`(时代/科技) / `culture`(文化) / `tech`(科技) / `supernatural`(特异功能/灵气) / `traffic`(交通) / `economy`(经济) / `custom` |
| title | TEXT | NOT NULL | 设定标题（如“青铜文明末期） |
| desc_raw | TEXT | NOT NULL | 关键描述 |
| desc_polished | TEXT | 可空 | 润色 |
| setting_type | TEXT | DEFAULT 'essential' | `essential`(默认必加载) / `supplementary`(按需) |
| importance | INTEGER | DEFAULT 3 | 0–5 |
| custom_attrs | TEXT(JSON) | DEFAULT '{}' |  |

索引：`idx_setting_category`。

---

<a id="s2-4-memory"></a>

### 2.4 主观记忆系统（核心创新）

> **设计思想**：事件客观一致 → 每个参与者基于自己的感知形成主观记忆。

一个事件 → 每条记忆关联到**记忆宫殿链；可深度分层；可失真；可遗忘；可按深度/时间/地点/人物 4 维度索引；可按需加载。

记忆生成在**事件发生之后**由 `memory_encoder` skill 为每个在场参与者（非死即忘）生成各自的记忆条目。每条记忆有**深度 0-5 / 正确性 0-100 / 视角 bias。

记忆加载由 `memory_retriever` 管线按：深度 → 时间 → 关联链，按需步进加载。

<a id="s2-4-1"></a>

#### 2.4.1 记忆基本表 `memories`

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK |  |
| char_id | INTEGER | FK → characters.id | **谁的**记忆 |
| source_event_id | INTEGER | FK → events.id 可空 | 源于哪条客观事件（可空=非事件源记忆，如"我觉得他很坏"的印象） |
| memory_raw | TEXT | NOT NULL | **该角色**记忆的关键文本（**他自己的版本**） |
| memory_polished | TEXT | 可空 | 润色成的内心独白式描述 |
| depth | INTEGER | DEFAULT 3 | 深度 0–5：0=很快忘；5=永不忘 |
| correctness | INTEGER | DEFAULT 100 | 正确性 0–100：100=和客观一致，0=完全记错 |
| perspective_bias_raw | TEXT | 可空 | 视角偏差描述关键文本（"只看到背影以为是仇人"） |
| mood | TEXT | 可空 | 当时的情绪标签（`angry/happy/...） |
| remember_tick | INTEGER | NOT NULL | 记住的 tick（通常等于事件 tick + 偏差 lag） |
| last_recall_tick | INTEGER | 可空 | 上一次被回想起的 tick |
| recall_count | INTEGER | DEFAULT 0 | 回想次数（回想会强化深度） |
| forget_prob | REAL | DEFAULT 0.0 | 当前遗忘概率 0-1，动态衰减值 |
| is_false | INTEGER | DEFAULT 0 | 0/1 是否是**虚假记忆**（模型主动植入/篡改） |
| custom_attrs | TEXT(JSON) | DEFAULT '{}' | 扩展：被谁篡改、来源阴谋等 |

索引：
- `idx_mem_char(char_id)`
- `idx_mem_depth(char_id, depth)` （深度优先用）
- `idx_mem_event(source_event_id)`
- `idx_mem_correct(correctness)`
- `idx_mem_tick(remember_tick)`

<a id="s2-4-2"></a>

#### 2.4.2 记忆索引表 `memory_index`

> 每条记忆按**时间 / 地点 / 人物 / 物品** 4 维度建立可空外键索引，支持多维过滤快速拉取记忆。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK |  |
| memory_id | INTEGER | FK → memories.id |  |
| char_id | INTEGER | FK → characters.id | 冗余，便于联表 |
| index_type | TEXT | NOT NULL | `time` / `location` / `person` / `item` / `keyword` |
| index_key | TEXT | NOT NULL | 索引键值：`person→人名/地点→地图 ID/时间→tick 字符串/物品→物品名/关键词 |
| index_value | TEXT | 可空 | 额外索引值 |

索引：`idx_mi_mem(memory_id)`、`idx_mi_lookup(char_id, index_type, index_key)`（最常用的多维查询）。

**示例**：记忆 = 小红在酒馆亲了小明。为小刚的记忆建 3 条索引：
- `time` → `tick=1231`
- `location` → `map_id=5`
- `person` → `小红`
- `person` → `小明`

这样模型查："我对小红有什么记忆？" → 按 `index_type=person,index_key=小红 → 拉到这条。

<a id="s2-4-3"></a>

#### 2.4.3 记忆宫殿（关联图谱）`memory_links`

> 记忆宫殿：每条记忆和其他记忆的关联。形成**关联链**。加载一条会联想相邻。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK |  |
| char_id | INTEGER | FK → characters.id | 冗余 |
| memory_a_id | INTEGER | FK → memories.id |  |
| memory_b_id | INTEGER | FK → memories.id |  |
| link_type | TEXT | NOT NULL | `same_person` / `same_place` / `causal`（因果）/ `emotional`（情感相关）/ `time_sequence（时间先后）/ `custom` |
| link_strength | REAL | DEFAULT 0.8 | 关联强度 0–1：越高越容易被联动加载 |
| weight | REAL | DEFAULT 1.0 | 动态权重（会被强化/衰减 |

索引：`idx_ml_char_a(char_id, memory_a_id)`、`idx_ml_char_b(char_id, memory_b_id)`。

<a id="s2-4-4"></a>

#### 2.4.4 角色印象表 `character_impressions`

> "A 对 B 的整体印象"是记忆的**顶层摘要**。每次加载记忆时先加载印象，决定要不要进一步深挖。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK |  |
| observer_char_id | INTEGER | FK → characters.id | 观察者 A |
| target_char_id | INTEGER | FK → characters.id | 被观察者 B |
| impression_raw | TEXT | NOT NULL | A 对 B 的总体印象关键文本 |
| impression_polished | TEXT | 可空 | 润色 |
| favorability | INTEGER | DEFAULT 50 | 好感度 0–100 |
| trust | INTEGER | DEFAULT 50 | 信任度 0–100 |
| fear | INTEGER | DEFAULT 0 | 惧怕度 0–100 |
| last_update_tick | INTEGER | DEFAULT 0 | 最后修改 tick |

索引：`idx_ci_pair(observer_char_id, target_char_id)` UNIQUE。

> 按需加载记忆的顺序：
> 1. 先拉印象（顶层摘要）
> 2. 按 depth=4–5 的记忆（必加载）
> 3. 再按 query 的关键词（人/时间/地点）从索引拉相关记忆
> 4. 通过 memory_links 宫殿关联链展开
> 5. 最后 0–3 浅度记忆随机采样
> 6. 受 forget_prob 动态遗忘跳过

---

<a id="s2-5-quests"></a>

### 2.5 任务与纲领系统表

> 区别：
- **任务 quest**：有具体完成条件。例"把信送到"、"保护她" — 有目标有终局。
- **纲领 agenda**：长期行为准则 / 策略。例"一切都优先保护小红" — 每 tick 自动决策的指导原则。可被阻碍才中断。
- **大纲步骤 quest_steps**：任务自动拆解的分步执行计划。

<a id="s2-5-1"></a>

#### 2.5.1 角色任务表 `character_quests`

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK |  |
| char_id | INTEGER | FK → characters.id |  |
| title | TEXT | NOT NULL | 任务名 |
| desc_raw | TEXT | NOT NULL | 任务关键描述 |
| desc_polished | TEXT | 可空 | 润色 |
| quest_type | TEXT | DEFAULT 'side' | `main`/`side`/`routine`/`personal`/`emergency` |
| status | TEXT | DEFAULT 'planned' | `planned`/`in_progress`/`completed`/`paused`/`terminated`/`failed` |
| priority | INTEGER | DEFAULT 3 | 0–5 |
| start_tick | INTEGER | NOT NULL | 起始 tick |
| estimated_ticks | INTEGER | 可空 | 预计 tick |
| success_condition_raw | TEXT | NOT NULL | 完成条件关键文本 |
| fail_condition_raw | TEXT | 可空 | 失败条件关键文本 |
| assigned_by | TEXT | DEFAULT 'player' | `player`/`system`/`self`/`other_char_id` |
| parent_quest_id | INTEGER | FK → 本表可空 | 父任务 |
| completion_summary_raw | TEXT | 可空 | 完成时摘要 |
| blocked_reason_raw | TEXT | 可空 | 被阻碍的原因（失败检测时填） |
| custom_attrs | TEXT(JSON) | DEFAULT '{}' | 奖励、关联物品等 |

索引：`idx_cq_char_status(char_id, status)`。

<a id="s2-5-2"></a>

#### 2.5.2 角色行动纲领表 `character_agendas`

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK |  |
| char_id | INTEGER | FK → characters.id |  |
| title | TEXT | NOT NULL | 纲领名 |
| principle_raw | TEXT | NOT NULL | 行为准则关键文本（例"每回合都保护小红，小红遇到危险就挡在前面。"） |
| principle_polished | TEXT | 可空 | 润色 |
| status | TEXT | DEFAULT 'active' | `active`/`paused`/`terminated` |
| priority | INTEGER | DEFAULT 3 | 0–5 |
| start_tick | INTEGER | NOT NULL |  |
| end_tick | INTEGER | 可空 | 结束/作废 |
| conflict_with | TEXT | 可空 | 阻碍原因 |
| blocked_reason_raw | TEXT | 可空 | 被阻碍无法继续原因 |

索引：`idx_ca_char(char_id, status)`。

<a id="s2-5-3"></a>

#### 2.5.3 任务大纲步骤表 `quest_steps`

> 大任务由 `outline_planner` skill 拆解成步。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK |  |
| quest_id | INTEGER | FK → character_quests.id |  |
| step_no | INTEGER | NOT NULL | 第几步 |
| action_raw | TEXT | NOT NULL | 本步要做什么关键文本 |
| status | TEXT | DEFAULT 'pending' | `pending`/`in_progress`/`done`/`skipped`/`failed` |
| done_tick | INTEGER | 可空 | 完成 tick |
| condition_raw | TEXT | 可空 | 进入下一步的条件 |

---

<a id="s2-6"></a>

### 2.6 快照与迁移策略

- 快照：`SaveManager.create_snapshot` → VACUUM INTO `saves/{name}.snapshots/round_{tick:04d}_{YYYYMMDD_HHMMSS}.db`。
- 迁移：`storage/connection.py::_init_schema` 用 `PRAGMA table_info({table}` 检测缺列，`ALTER TABLE ADD COLUMN`，旧存档自动升级。幂等。

---

<a id="s3-api"></a>

## 三、后端接口层

> Base path: `/api`

<a id="s3-1"></a>

### 3.1 通用 CRUD 与高级查询规范

所有 12 类实体（character / group / item / map / event / setting / memory / quest / agenda / quest_step / impression / item_hold）共用一套端点。

#### 统一的查询参数 `GET /api/entities/{slug}`

| 参数 | 类型 | 说明 |
|------|------|------|
| `filter` | JSON | 精确匹配 `{"status":"active","char_id":5}` |
| `like` | JSON | 模糊 `{"name":"%小%","raw":"%酒馆%"}` |
| `sort` | STRING | 列名，前加 `-` 降序：`-importance,tick_num` |
| `limit` | INT | 默认 50 |
| `offset` | INT | 默认 0 |
| `fields` | STRING CSV | 只返回某些字段：`id,name,raw` 节省带宽 |

端点清单：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/entities/_slugs` | 列出可用 slug |
| GET | `/api/entities/{slug}` | 查询（支持 filter/like/sort/limit/offset/fields） |
| POST | `/api/entities/{slug}` | 创建 1 条 |
| GET | `/api/entities/{slug}/count` | COUNT（也支持 filter/like） |
| GET | `/api/entities/{slug}/_bulk_create` | 批量创建 |
| POST | `/api/entities/{slug}/_bulk_update` | 按 ID 批量更新 |
| POST | `/api/entities/{slug}/_bulk_delete` | 按 ID 批量删除 |
| GET | `/api/entities/{slug}/{id}` | 单条 |
| PATCH | `/api/entities/{slug}/{id}` | 按 ID 更新 |
| DELETE | `/api/entities/{slug}/{id}` | 按 ID 删除 |

<a id="s3-2"></a>

### 3.2 存档管理 `/api/saves`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/saves` | 列表 |
| POST | `/api/saves` | 创建（重名直接**报错**，不覆盖 |
| DELETE | `/api/saves/{name}` | 删除 + 删快照目录 |
| POST | `/api/saves/{name}/switch` | 切换激活存档，触发迁移逻辑 |
| GET | `/api/saves/active` | 当前激活名 |
| GET | `/api/saves/meta` | world_meta |
| PATCH | `/api/saves/meta` | 更新（tick/game_time/protagonist） |
| GET | `/api/saves/protagonist` | 主角 |
| POST | `/api/saves/protagonist` | 设置主角 |
| POST | `/api/saves/snapshots` | 创建快照 |
| GET | `/api/saves/snapshots` | 列表 |
| POST | `/api/saves/snapshots/restore` | 回档 |
| DELETE | `/api/saves/snapshots/{file}` | 删除 |

<a id="s3-3"></a>

### 3.3 记忆专用端点 `/api/memory`（核心创新 API）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/memory/retrieve` | **核心按需加载**（POST JSON 查询拉记忆** — 见下方请求体 |
| POST | `/api/memory/{char_id}/impression` | A→B 的印象 |
| POST | `/api/memory/{char_id}/impressions` | 该角色对所有人印象列表 |
| POST | `/api/memory/decay` | **遗忘衰减（tick 推进调一次 |
| POST | `/api/memory/distort` | 按规则随机篡改/植入（GM/指定篡改，接口 |
| POST | `/api/memory/palace/{mem_id}` | **记忆宫殿展开**：返回关联链，按 link_strength 排序 |
| POST | `/api/memory/encode_event` | 为一个 event 的所有参与者从 event → 生成记忆（管线内部调） |

**请求 `/api/memory/retrieve 请求体：**
```json
{
  "char_id": 5,
  "query": {
    "person": ["小红",
    "location": 12,
    "time_range": [100, 200],
    "keyword": ["刺杀,
    "min_depth": 2
  },
  "loading_strategy": "hierarchical",
  "palace_depth": 2,
  "limit_total": 50
}
```

返回：
```json
{
  "impressions": [{observer对被观察对象},
  "core": [depth>=4 的记忆],
  "index_hits": [按索引匹配到的记忆],
  "palace_expanded": [从核心记忆沿 memory_links 展开 palace_depth 层的记忆链],
  "shallow_sample": [随机抽样 depth=0-3 的浅记忆],
  "skipped_due_to_forget": 3
}
```

<a id="s3-4"></a>

### 3.4 事件与时间推进 `/api/world`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/world/meta` | 取 world_meta + 主角信息 + 统计 |
| GET | `/api/world/events` | **事件流查询**（支持按角色/地点/类型/时间/importance 筛选）见下 |
| POST | `/api/world/tick_once` | **正常推进 1 tick**（返回生成的事件列表+润色后） |
| POST | `/api/world/time_jump` | **时间跨越**：`{delta_ticks:..., delta_game_time_str:"...", span:"3天"}`，返回跨越摘要+里程碑事件 |
| POST | `/api/world/player_action` | **玩家动作**：`{char_id, action_raw:"拥抱小明", target_id...}`，执行+推进1tick |
| POST | `/api/world/polish_event/{event_id}` | 重新润色一条事件的 content_polished（按当前全局风格配置） |

**`/api/world/events` 查询参数：**
- `char_ids[]`：多角色过滤（参与过的事件）
- `map_ids[]`：多地点过滤
- `event_types[]`：social/combat...
- `tick_from / tick_to`
- `importance_min`
- `view`：`raw` / `polished`（默认 polished）

<a id="s3-5"></a>

### 3.5 剧本管理 `/api/dramas`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/dramas` | 扫描 `backend/drama/` 列出所有剧本 |
| GET | `/api/dramas/{name}` | 详情 |
| POST | `/api/dramas/{name}/init` | **导入数据库**（新建存档，写入所有初始数据） |
| POST | `/api/dramas/_generate` | **一键生成剧本**：`{prompt, name, style_options...}` → 返回进度 task_id |
| GET | `/api/dramas/_generate/{task_id}` | 生成进度 |
| PATCH | `/api/dramas/{name}` | 修改剧本源文件（文件级保存） |
| DELETE | `/api/dramas/{name}` | 删除整目录 |
| GET | `/api/dramas/{name}/preview` | **在线预览 8 个 txt |

<a id="s3-6"></a>

### 3.6 模型配置 `/api/agent`

#### Prompts：
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/agent/prompts` | 列表 |
| GET | `/api/agent/prompts/{name}` | 取当前激活版本内容 |
| GET | `/api/agent/prompts/{name}/versions` | 所有版本 |
| POST | `/api/agent/prompts/{name}/versions` | 建新版本（copytree） |
| PUT | `/api/agent/prompts/{name}/versions/{v}` | 修改 |
| PUT | `/api/agent/prompts/{name}/active` | 设激活版本（改 config.json default_version） |

#### Skills：同 prompts，skill 文件是 skill.md，API 字段仍叫 system_prompt。路径 `/api/agent/skills/{name}/...`

#### Tools：
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/agent/tools` | 列表所有工具描述 |
| GET | `/api/agent/tools/_slugs` | 实体 CRUD 工具的 slug |
| GET | `/api/agent/variables` | Prompt/Skill 可用模板变量说明（读 `agent/conf/variables.json`） |

<a id="s3-7"></a>

### 3.7 全局配置 `/api/config`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/config` | 读当前全局设置（不含 API key 不返回真实值，仅占位） |
| PATCH | `/api/config` | 修改 → 写 `backend/.env` + `backend/custom_config.json` |
| POST | `/api/config/_test_llm` | 用当前 key + 模型发一条测试消息 |

---

<a id="s4-model"></a>

## 四、模型层（LLM 管线）

<a id="s4-1"></a>

### 4.1 Prompt / Skill / Tools 模块化配置

文件结构：
```
backend/agent/conf/
├── prompts/{name}/config.json
│                   v0/system_prompt.md
│                   v0/user_prompt.md
│                   v1/...
├── skills/{name}/config.json        ← default_version
│                  v0/skill.md
│                  v1/...
├── tools/{entity_slug}.json   (13 张实体 × 1 张 basic + 1 张 storage
└── variables.json              ← 模板变量 ${xxx} 含义说明
```

Skill 清单（v3）：

| Skill 名 | 作用 |
|----------|------|
| `memory_encoder` | 事件 → 为每个参与者编码各自主观记忆（视角偏差/深度/正确性） |
| `memory_retriever` | 按 query / 深度 / 索引 / 宫殿链，按层加载记忆 |
| `memory_decayer` | 每个 tick：forget_prob 衰减，depth 递减，触发 forget/decay/distort |
| `actor_decide` | 每个角色 tick 决策：意图→具体要做啥 |
| `world_react` | 世界对玩家动作反应 + NPC 间互动 |
| `outline_planner` | 把任务拆解成大纲步骤 |
| `quest_monitor` | 每个 tick 检查任务完成/失败/阻碍检测 |
| `agenda_monitor` | 纲领阻碍检测 |
| `event_polisher` | 把 raw 润成 polished（长度/血腥/成人 配置生效） |
| `time_skip_summarizer` | 时间跨越（>1tick：史诗摘要 + 里程碑事件 |
| `drama_generator` | 一键生成剧本 8 文件 |

<a id="s4-2"></a>

### 4.2 正常推进管线（Normal Tick `POST /api/world/tick_once`）

```
Step 0  黑词过滤
    │
Step 1  ┌──────────────────┐ 记忆衰减 & 遗忘  │
       │ memory_decayer    │ → 降 depth/forget_prob → 删低 depth 记  │
       └──────────────────┘                                    │
Step 2  ┌──────────────────┐ 任务 & 纲领检测 │
       │ quest_monitor     │  每个 in_progress 任务判定 success/fail/blocked│
       │ agenda_monitor  │  纲领阻碍检测                                │
       └──────────────────┘                                    │
Step 3  ┌──────────────────┐ NPC 决策         │
       │ memory_retriever│ 拉每个 actor 的 core memory │
       │ actor_decide      │ → 生成 actor 这 tick 的意图/行动 raw      │
       └──────────────────┘                                    │
Step 4  ┌──────────────────┐ 世界反应        │
       │ world_react    │ 汇总所有 actor 行动 + 玩家行动 + 环境│
       │                   │ 合成「事件草案 events」列表          │
       └──────────────────┘                                    │
Step 5  ┌──────────────────┐ 事件写入+编码 │
       │ 写 events + event_participants│                         │
       │ memory_encoder    │ 每个参与者 → 记忆        │
       └──────────────────┘                                    │
Step 6  ┌──────────────────┐ 润色展示        │
       │ event_polisher  │ raw → polished（长度/风格/血腥度）        │
       └──────────────────┘                                    │
Step 7  tick_num++，返回事件列表给前端                         │
```

<a id="s4-3"></a>

### 4.3 时间跨越管线（Time Jump `POST /api/world/time_jump`）

场景：一次跳 3 天 / 7 天 / 30 天 / 100 天 / 1 年 / 3 年 / 10 年 / 100 年 / 1000 年 / 10000 年。

不逐 tick 模拟（否则 10000 年 = 无限 token）：

```
Step 1 计算最终 game_time（divmod 年月日时分秒）
Step 2 ┌─────────────────────┐
      │ time_skip_summarizer │ 按跨度分层：                           │
      │                     │ • 短期（<1 年）→ 事件摘要 + 3-5 里程碑       │
      │                     │ • 中期（1-100年）→ 代际变迁 + 10 里程碑       │
      │                     │ • 长期（100-1万年）→ 文明兴衰 + 人物生卒       │
      │                     │ • 超长期（>1万年）→ 地质/宇宙级   │
      └─────────────────────┘
Step 3 写入一批里程碑事件 events（每个都是低逐）
Step 4 批量更新：角色死亡/衰老/物品磨损/地图变化/群体兴衰/任务完成
Step 5 memory_encoder 批量为存活角色编码"大事件的各自"记忆
Step 6 event_polisher 润色里程碑
Step 7 返回史诗式 summary + 里程碑事件列表
```

<a id="s4-4"></a>

### 4.4 记忆加载管线（`memory_retriever` 管线内部调用）

调用链：
1. 先从 character_impressions 加载顶层摘要（顶层概览
2. `depth ≥ 4 的 core（必加载）
3. 根据检索维度索引表 memory_index 按 person/time/location/keyword 查命中
4. 沿 memory_links 展开 palace_depth 层的关联链
5. depth 0-3 的 sample 比例抽几条
6. 按 forget_prob 做伯努利抽样跳过（模拟没记起来）
7. 返回分 block 返回结构

<a id="s4-5"></a>

### 4.5 任务与纲领推进

- **Quest：每 tick 结束执行 `quest_monitor`：
  - 当前完成条件：LLM 判当前状态是否满足 success_condition_raw → 完成→ 设 completed + 写 completion_summary_raw
  - 失败条件：同理 → failed
  - 阻碍：连续 3 tick 无进展 → 写 blocked_reason_raw → 前端提示玩家
- **Agenda**：`agenda_monitor`：
  - LLM 判断「纲领原则在当前世界状态是否冲突 → 终止 + conflict_with + blocked_reason_raw
  - 没冲突 → actor_decide 时把 principle_raw 注入系统提示词引导

<a id="s4-6"></a>

### 4.6 事件润色管线

- Skill: event_polisher 输入：
  - events.content_raw + 全局配置：
    - gore：开启血腥
    - adult_content：开启成人
    - polish_length：short（50字）/medium（200）/long（500）/epic（2000+）
    - style：叙事风/古风/科幻/写实
- 输出：content_polished，更新 events.content_polished
- 前端点「重润色」按钮调用 `/api/world/polish_event/{id}` → 重新生成

---

<a id="s5-frontend-gameplay"></a>

## 五、前端交互层（游戏页面）

<a id="s5-1"></a>

### 5.1 整体布局（三栏 + 顶部控制条 + 底部操作条）

```
┌───┬─────────────────────────────────────────────┬──────┐
│ S │  顶部：Tick/时间/保存/加载     │ MENU │
│ E ├─────────────────────────────────────────────┤ 右栏： │
│ T │                                             │ 角色清单  │
│ T │              事件流主区（timeline）│ 物品清单 │
│ I │                                             │ 地图展示 │
│ N │                                             │ 记忆宫殿│
│ G │                                             │ │
│ G │                                             │ │
│ S ├─────────────────────────────────────────────┤──────┤
│   │ 底：时间控制条（正常/跨越+速度） + 玩家动作栏 │      │
└───┴─────────────────────────────────────────────┴──────┘
```

<a id="s5-2"></a>

### 5.2 左设置栏（可折叠）

| 元素 | 作用 |
|------|------|
| 当前 tick | 显示 + 手动编辑跳转（GM 模式） |
| 当前 game_time | 显示 + 编辑 |
| 纪元名 | 显示 |
| 主角 | 显示下拉切 |
| 存档名 | 显示 +「保存」按钮 |
| 保存 / 另存为 / 回档 / 快照列表 |  |
| 全局开关：血腥 / 成人 / 润色长度 | 临时覆盖 |
| 折叠按钮 | 折叠/展开整栏 |

<a id="s5-3"></a>

### 5.3 主事件流区（核心）

- 时间线展示：自上而下按 tick 分组，一 tick 一组卡片，卡片内多条事件
- 事件卡片：默认展示 content_polished（可切换 raw / polished）
- 筛选：
  - 参与人 chip 多选（多角色聚焦：点角色头像 chip + 地点 chip
  - 事件类型（社交/战斗/移动/物品）
  - importance 滑块
  - tick 范围滑块
- 聚焦：选中某人时，只有他参与的事件高亮，其余灰
- 点击事件卡 → 弹层显示参与人、位置、importance、关联记忆（若视角=主角）
- 悬停事件 → 浮层显示**该事件的被哪些角色记得 / 哪些忘

<a id="s5-4"></a>

### 5.4 时间控制条（底部）

两种模式切换：**正常流逝 + 时间跨越

#### 正常流逝按钮组（Auto 模式，真实时间间隔）：
- `10s / 1m / 5m / 30m / 1h / 4h / 1d`（真实等待间隔，每到间隔自动调一次 `tick_once`
- `⏸ 暂停 / ▶ 开始
- 手动 `⏭ 下一 tick`

#### 时间跨越（Jump 模式，游戏内跨度）：
按钮组（按游戏内时间）：
- 短期：`3天` `7天` `30天` `100天`
- 中期：`1年` `3年` `10年` `100年`
- 长期：`1000年` `10000年`
- 点按钮 → 确认弹窗（"将跨越 100 年，是否继续？" → `time_jump` → 返回史诗摘要全屏弹窗展示。

<a id="s5-5"></a>

### 5.5 玩家动作与任务纲领面板（右侧或右下或弹出）

#### 玩家动作（Action Row）
- 文本输入框："我要 亲吻小红"
- 快捷动作 chip：`亲近`/`攻击`/`对话`/`移动到`/`使用物品` → 选 chip → 选目标
- 提交 → `player_action` → 推进 tick → 返回事件流刷新

#### 任务 & 纲领
- 任务列表 Tab：列主角的任务（进行中/已完成/失败，可「设优先级 / 中止 / 新建任务」弹窗
- 纲领 Tab：列主角的纲领（激活/暂停，可新建/编辑）
- 新建任务：标题 / 描述 / 类型 / 完成条件 / 失败条件 / 优先级
- 新建纲领：原则关键文本 + 优先级

<a id="s5-6"></a>

### 5.6 菜单栏（右上抽屉/弹出

菜单）

| 菜单项 | 内容 |
|--------|------|
| 🧍 角色 | 全部角色卡（点击→详情：属性/位置/任务/对他的印象）|
| 👥 群体 | 群体树（层级）+ **每群体热力图预览缩略图**（点击→详情见下方"群体热力图浏览器"）|
| 🗺 地图 | **地图浏览器（地形要素绘制 + 群体热力图层 + 距离测距）** — 见下方"地图浏览器渲染规范" |
| 🎒 物品 | 物品（筛选：类型/稀有度/持有者）|
| 📜 设定 | 按分类：世界/时代/文化/超自然 浏览设定 |
| 🧠 记忆宫殿**（主角视角）** | 我的记忆：深度分层树 + 关联链可视化 |
| ⚙ 管理员模式 | 全局配置临时修改时间 |

##### 地图浏览器渲染规范

地图浏览器 v3 采用 **PixiJS（2D 主渲染器）+ Three.js（3D 切换渲染器）** 混合方案，五层图层架构。

###### 渲染器选型

| 场景 | 渲染器 | 触发条件 |
|------|--------|---------|
| **城市/街区/建筑/室内平面图**（90% 场景） | **PixiJS v8 + @pixi/react** | `map.coord_system == 'cartesian_2d'` 或 `'spherical'` |
| **星系/宇宙/3D 空间** | **Three.js + @react-three/fiber** | `map.coord_system == 'cartesian_3d'` |

切换逻辑：进入子地图时根据其 `coord_system` 字段自动挂载对应渲染器组件，整个 `<MapRenderer>` 容器内通过条件渲染切换：

```tsx
function MapRenderer({ mapId }: { mapId: number }) {
  const map = useMap(mapId);
  if (map.coord_system === 'cartesian_3d') {
    return <ThreeMapRenderer map={map} />;
  }
  return <PixiMapRenderer map={map} />;
}
```

> **起步策略**：阶段一/二只实现 PixiJS 渲染器，3D 场景暂时用 `volume` shape 的假透视顶替；等核心玩法跑通后再实现 Three.js 渲染器（阶段三或 v4）。

###### PixiJS 五层 Container 设计

`<PixiMapRenderer>` 用 5 个 `Container` 自下而上叠放，对应 v3 的五层架构。每个 Container 设置 `zIndex` 保证顺序：

```tsx
import { Container, withApplication } from '@pixi/react';
import { Application, Container as PixiContainer } from 'pixi.js';

function PixiMapRenderer({ map, features, characters, heatmaps }) {
  return (
    <Stage width={800} height={600} options={{ backgroundColor: 0x0a0a0a }}>
      {/* 静态层 zIndex=0：bbox 边界/网格/比例尺（缓存到 RenderTexture，只画一次） */}
      <StaticLayer map={map} zIndex={0} />
      {/* 要素层 zIndex=1：所有 map_features 按 layer_z 排序 */}
      <FeatureLayer features={features} zIndex={1} />
      {/* 动态层 zIndex=2：角色头像/事件标记/移动要素实时位置（每帧重绘） */}
      <DynamicLayer characters={characters} tick={tick} zIndex={2} />
      {/* 特效层 zIndex=3：地震波纹/火山灰/天气 */}
      <EffectLayer effects={effects} zIndex={3} />
      {/* 热力图层 zIndex=4：群体热力图叠加（WebGL shader） */}
      <HeatmapLayer heatmaps={heatmaps} map={map} zIndex={4} />
      {/* UI 覆盖层（DOM）：面包屑/工具栏/比例尺/tooltip — 用 PixiJS event mode + DOM 浮层 */}
      <UIOverlay map={map} />
    </Stage>
  );
}
```

**性能关键策略**：

1. **静态层缓存**：bbox/网格/比例尺只画一次，渲染到 `RenderTexture`，每帧直接贴图，不重绘。
2. **要素层分级缓存**：按 `layer_z` 分组，同一 layer_z 的要素合并到一个 `Container`，整体缓存为 RenderTexture。只有 `is_mobile=1` 的要素才每帧重绘。
3. **批量绘制**：同种 `feature_type` 的要素用同一个 `Graphics` + 批量 draw call，PixiJS 自动合并。
4. **视锥剔除**：根据当前缩放/平移只画可见 bbox 内的要素（PixiJS `cull` 插件）。
5. **纹理图集**：`point` shape 的图标用 `Spritesheet` 打包，1 个 draw call 画几千个图标。

###### 地形要素绘制规则

每个 `map_features` 按 `layer_z` 升序绘制。按 `shape` 不同：

| shape | PixiJS 实现 | 性能要点 |
|-------|------------|---------|
| `point` | `Sprite` + `Spritesheet`，按 `feature_type`+`icon_hint` 选图标 | 几千个点用 `ParticleContainer` 批量 |
| `line` | `Graphics.drawPolygon(points)` 连线，lineWidth=`geometry.width` | 同色同宽合并为一个 Graphics |
| `polygon` | `Graphics.drawPolygon()` + `beginFill(color, 0.3)` 半透明填充 | 轮廓和填充分开 batch |
| `circle` | `Graphics.drawCircle(cx, cy, r)` | 同上 |
| `volume`（假 3D 透视） | 底面 `drawPolygon` + 顶部偏移 `polygon`（按 `z_max` 计算 y 偏移）+ 侧面四边形 | 模拟高度，星系场景才换 Three.js |

- `color_hint` 缺失时按 feature_type 默认色：`building=0x8a7a6a` / `mountain=0xc8a878` / `river=0x3a7ad8` / `forest=0x2a6a3a` / `star=0xffd700` / `starship=0xa0a0b0`。
- 要素标注名：用 `Text` 组件，但用户可全局关闭（性能优化）。
- **移动要素**（is_mobile=1）：每 tick 更新 `x/y`，留尾迹用 `ParticleContainer` 存最近 N 帧位置淡出。

###### 热力图 WebGL Shader 实现

热力图层用自定义 `Filter` + fragment shader，一次性绘制整张栅格，比逐格 `fillRect` 快几十倍：

```glsl
// heatmap.frag —— fragment shader 骨架
precision mediump float;
uniform sampler2D u_density;   // 群体密度栅格纹理
uniform vec3 u_color_stops[5]; // 蓝→绿→黄→红 5 个色阶
varying vec2 v_uv;
void main() {
  float d = texture2D(u_density, v_uv).r;
  // 5 色阶插值
  vec3 color = mix(u_color_stops[0], u_color_stops[1], clamp(d * 4.0, 0.0, 1.0));
  color = mix(color, u_color_stops[2], clamp((d - 0.25) * 4.0, 0.0, 1.0));
  color = mix(color, u_color_stops[3], clamp((d - 0.5) * 4.0, 0.0, 1.0));
  color = mix(color, u_color_stops[4], clamp((d - 0.75) * 4.0, 0.0, 1.0));
  gl_FragColor = vec4(color, d * 0.7); // alpha 由密度决定
}
```

- `u_density` 纹理：把 `heatmap_grid.cells` 二维数组转成 `Uint8Array`，用 `PIXI.Texture.fromBuffer()` 一次创建。
- 多个群体叠加：用 `filter` 的 `blendMode = 'add'` 自然叠加，重合区域颜色变亮（蓝+红=品红，表示两个群体都密集）。
- 鼠标悬停某格：用 `extract.pixels()` 反查该像素的累积密度，做 tooltip。

###### Three.js 3D 渲染器（阶段三）

仅用于 `coord_system == 'cartesian_3d'` 的星系/宇宙场景。骨架：

```tsx
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Stars } from '@react-three/drei';

function ThreeMapRenderer({ map, features }) {
  return (
    <Canvas camera={{ position: [0, 0, 100], fov: 50 }}>
      <ambientLight intensity={0.5} />
      <Stars radius={300} depth={50} count={5000} factor={4} />
      <OrbitControls />
      {/* 要素映射到 3D 对象 */}
      {features.map(f => <Feature3D key={f.id} feature={f} />)}
      {/* 移动要素（飞船）每 tick 更新 position */}
      <MovingShips tick={tick} />
    </Canvas>
  );
}

function Feature3D({ feature }) {
  if (feature.shape === 'circle' && feature.feature_type === 'star') {
    return <mesh position={[feature.geometry.cx, feature.geometry.cy, 0]}>
      <sphereGeometry args={[feature.geometry.r, 32, 32]} />
      <meshBasicMaterial color={feature.color_hint || '#ffd700'} />
    </mesh>;
  }
  if (feature.shape === 'circle' && feature.feature_type === 'planet') {
    return <PlanetMesh feature={feature} />; // 含轨道动画
  }
  // ... 其他类型
}
```

特性：星球自转动画 / 飞船轨道运动 / 行星之间真实距离感 / 滚轮缩放光年级别 / 鼠标拖动旋转视角。

###### 交互规则

- **悬停要素**：PixiJS `eventMode = 'static'` + `cursor = 'pointer'`，触发 `pointermove` → 显示 DOM tooltip。
- **点击要素**：若有 `child_map_id` → 触发 `onEnterChildMap(mapId)`，父组件切换地图；否则 → 弹出要素详情卡。
- **双击要素**：弹出编辑器（管理员模式）/ 详情只读（玩家模式）。
- **面包屑导航**（顶部 DOM 层）：当前地图路径 `宇宙 › 银河系 › 太阳系 › 地球 › 长安城`，点任一段回上层。
- **比例尺**（左下角 DOM 层）：根据当前 PixiJS `stage.scale` 实时计算 `1 格 = X 米/km/光年`。
- **测距工具**：工具栏切换"测距模式" → 点两个要素/角色 → 画虚线 + 显示 `display` 距离 + 调 `/api/maps/distance` 拿语义文本。

###### 缩放与跨层级

- 鼠标滚轮缩放（PixiJS `stage.scale` 在 bbox 范围内 clamp）。
- 缩放到极限（看到整个 map）→ 出现"返回父地图"按钮 → 切到 `parent_map_id` 视图。
- 点要素进入子地图 → 用 `default_zoom`/`default_center_x/y` 作为初始视图参数。
- 跨渲染器过渡：2D→3D 切换时用 200ms 渐变 + 缩放动画，避免突兀。

##### 群体热力图叠加

群体热力图作为第 5 层（heatmap-layer）叠加在要素层之上。规则见前文"群体表"小节。多个群体叠加时颜色变亮表示重合。可在工具栏开关显隐。

##### 前端依赖清单（v3 新增）

```json
{
  "dependencies": {
    "pixi.js": "^8.1.0",
    "@pixi/react": "^8.0.0",
    "@react-three/fiber": "^8.16.0",
    "@react-three/drei": "^9.108.0",
    "three": "^0.165.0",
    "zustand": "^4.5.0"
  }
}
```

> Zustand 用于地图浏览器状态管理（当前 map_id / 缩放 / 平移 / 选中要素 / 测距模式），跨 PixiJS 与 DOM 浮层共享。

##### 地图相关 API

在通用 CRUD 之外追加：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/maps/{id}/features` | 取该地图的所有要素（按 layer_z 排序） |
| GET | `/api/maps/{id}/features?layer_z_min=0&layer_z_max=2` | 按层级过滤要素 |
| GET | `/api/maps/{id}/children` | 子地图列表 |
| GET | `/api/maps/{id}/path_to?target_map_id=12` | 两地图间的祖先链路径 |
| POST | `/api/maps/distance` | **两对象距离**（角色/物品/要素/地图） |
| GET | `/api/maps/{id}/distance_matrix?ids=1,2,3` | 多对象两两距离矩阵 |
| GET | `/api/characters/{id}/distance_to?target_type=character&target_id=5` | 角色到目标距离快捷 |
| GET | `/api/groups/{id}/heatmap` | 单独取某群体的 heatmap_grid |
| POST | `/api/groups/{id}/refresh_heatmap` | 触发重新统计 |
| GET | `/api/maps/{id}/heatmaps` | 该地图所有群体热力图 |

---

<a id="s6-admin"></a>

## 六、前端管理页面（顶部导航：首页 / 剧本 / 模型 / 配置 / 进入游戏

<a id="s6-1"></a>

### 6.1 开始游戏（首页）

路径 `/`（未选存档时进入此页，进入游戏后是游戏页）。

区块：
- 大标题「设身处地 v3
- 「📜 剧本卡片区：横向滚动所有剧本（封面+名+摘要+主角建议年龄）
- 点剧本 → 「▶ 开始新游戏」→ 选存档名 → `POST /api/dramas/{name}/init + 设置主角
- 「📂 读取最近存档」tiles：最近 5 个存档，点进入
- 「+ 新建空白世界（从 0 开始无剧本）

<a id="s6-2"></a>

### 6.2 读取存档页 `/saves`

- 表格：存档名 / 剧本 / tick / 游戏时间 / 主角 / 最后保存 / 操作
- 操作：▶ 进入 / 📋 复制 / 🗑 删除 / 🕒 快照列表 / ↩ 回档
- 快照列表模态框：时间+ 点击回

<a id="s6-3"></a>

### 6.3 模型管理 `/model`

三个 Tab：Prompts / Skills / Variables

#### **Prompts Tab
- 左：列表 prompt 名列表 + 当前激活版本徽标
- 中：版本时间线（v0 → v1 → v2），点版本可切换（历史对比
- 右：双栏编辑器（左 system_prompt.md / 右 user_prompt.md
- 底部：`+ 建新版本（当前版本 → v{n+1}，从当前激活）
- 操作：「设为激活版本」/「重命名」/「删版本」/「导出版本」

#### 同上，编辑器改为 `skill.md` 单文件编辑 + config.json 编辑器。

#### 配置 Tab：只读展示 variables.json 定义的变量字典表格列表；

<a id="s6-4"></a>

### 6.4 剧本管理 `/dramas`

|区块
- 顶部：「✨ 一键生成剧本」大按钮 → 弹模态：
  - 提示词输入框（textarea："都市异能，主角沈默，上海市，白银时代
  - 风格选择：古风/科幻/都市/西幻/仙侠/自定义
  - 规模：小型（5 角色）/中型（15）/大型（30）
  - 「开始生成」→ POST `/api/dramas/_generate → 进度条
  - 生成完：「查看/编辑/导入
- 剧本列表卡片：封面 / 规模 / 生成时间 → 详情编辑 / 删除 / 初始化进游戏预览（8 分屏展示

<a id="s6-5"></a>

### 6.5 全局设置 `/settings`

分组表单：

| 分组 | 字段 |
|------|------|
| 🔑 模型 | API Key（密文输入 · 测试连接按钮 |
| 模型名称 | 选模型 / 温度 / TopP / 最大 Token 轮次限制（每步 max_llm_calls_per_tick）|
| 润色 | 润色长度 short/medium/long/epic |
| 内容分级 | 血腥描写开关、成人描写开关（开关）/暴力等级 0-5） |
| 日志 | LOG_DIR / 日志等级 |
| 存档 | 默认快照策略（手动/自动/自动间隔 tick） |

---

<a id="s7-drama-format"></a>

## 七、剧本源文件格式（8+1 文件，JSONL / JSON Lines + 1 个 meta.txt）

### 7.1 剧本目录

```
backend/drama/{剧本名}/
├── meta.txt                    ← 单行 JSON（不是 JSONL）
├── characters.txt          ← JSONL
├── groups.txt
├── group_hierarchies.txt
├── items.txt
├── maps.txt                     ← 地图容器（v3 新增 scale_unit/coord_system/is_mobile 等）
├── map_features.txt       ← ★ v3 新增：地形要素（楼/河/山/星球/飞船…）
├── events.txt                ← 初始历史事件（剧情的剧情）
├── settings.txt
└── plot_planning.txt       ← 剧情规划（主线脉络
```

### 7.2 各文件字段规范

**`meta.txt`（JSON）
```json
{
  "name": "白银时代协奏曲",
  "protagonist_name_default": "沈默",
  "start_game_time": "灵气纪元 214 年 3 月 15 日 08 时 00 分 00 秒",
  "era_name": "灵气纪元",
  "summary_raw": "沈默在上海市灵气复苏前夜觉醒异能。",
  "summary_polished": "城市上空，沈默..."
}
```

**`characters.txt`（JSONL，每一行一个角色）：
```json
{
  "name": "沈默",
  "appearance_raw": "身高 180/黑发/银瞳",
  "appearance_polished": "...",
  "personality_raw": "外冷内热/理性",
  "gender": "男",
  "age": 23,
  "importance": 5,
  "custom_attrs": {"异能等级": "S"}
}
```

**`groups.txt`**（每一行一个群体）：
```json
{ "name": "长安城居民", "desc_raw": "长安城所有常住人口", "group_type": "residence", "leader_id": null, "importance": 3 }
```

**`group_hierarchies.txt`**：
```json
{ "child_group": "酒馆酒客", "parent_group": "长安城居民", "relation_raw": "subset", "weight": 1.0 }
```

**`items.txt`**：
```json
{ "name": "100 元", "desc_raw": "人民币 100 元", "item_type": "money", "rarity": 1, "importance": 1 }
```

**`maps.txt`**（v3：支持 parent_map_name / scale_unit / coord_system / is_mobile 等字段）：
```json
{ "name": "太阳系", "desc_raw": "G2型恒星系", "map_type": "star_system", "parent_map_name": "猎户座旋臂", "coord_system": "cartesian_3d", "scale_unit": "AU", "scale_per_unit": 1.0, "bbox_w": 100, "bbox_h": 100, "bbox_d": 100 }
{ "name": "长安城", "desc_raw": "唐都", "map_type": "city", "parent_map_name": "东亚大陆", "coord_system": "cartesian_2d", "scale_unit": "m", "scale_per_unit": 1.0, "bbox_w": 12000, "bbox_h": 8000 }
{ "name": "沈默的飞船", "desc_raw": "中型探索舰", "map_type": "vehicle", "coord_system": "cartesian_2d", "scale_unit": "m", "is_mobile": 1, "carrier_char_name": "沈默", "current_map_name": "长安城", "current_x": 5000, "current_y": 3000 }
```

**`map_features.txt`**（v3 新增：地形要素）：
```json
{ "map_name": "太阳系", "name": "太阳", "feature_type": "star", "shape": "circle", "geometry": {"cx":50,"cy":50,"r":0.5}, "size_value": 696000, "size_unit_override": "km", "layer_z": 0, "color_hint": "金黄", "visual_raw": "G2型恒星/表面温度5800K" }
{ "map_name": "太阳系", "name": "地球", "feature_type": "planet", "shape": "circle", "geometry": {"cx":62,"cy":48,"r":0.0001}, "size_value": 6371, "size_unit_override": "km", "layer_z": 1, "child_map_name": "地球表面", "color_hint": "碧蓝" }
{ "map_name": "长安城", "name": "中央高楼", "feature_type": "building", "shape": "polygon", "geometry": {"points":[[6000,4000],[6050,4000],[6050,4030],[6000,4030]]}, "layer_z": 2, "color_hint": "灰白", "visual_raw": "30层玻璃幕墙高楼/顶部直升机停机坪", "child_map_name": "中央高楼内部", "is_obstacle": 1 }
{ "map_name": "长安城", "name": "渭河", "feature_type": "river", "shape": "line", "geometry": {"points":[[0,4000],[3000,4200],[6000,4100],[9000,4300],[12000,4500]],"width":80}, "layer_z": 1, "color_hint": "碧蓝" }
{ "map_name": "长安城", "name": "沈默的飞船", "feature_type": "starship", "shape": "polygon", "geometry": {"points":[[4990,2990],[5010,2990],[5010,3010],[4990,3010]]}, "layer_z": 3, "color_hint": "银灰", "is_mobile": 1, "carrier_type": "character", "carrier_name": "沈默", "child_map_name": "沈默的飞船" }
```

> 解析规则：`map_name` / `parent_map_name` / `child_map_name` / `carrier_name` 都用名字字符串引用，由 `drama_service.init_drama` 在写入时解析为 ID 外键。

**`events.txt`**（初始历史事件）：
```json
{
  "tick_num": -5,
  "game_time": "灵气纪元 214 年 3 月 10 日",
  "event_type": "social",
  "location_map_name": "长安酒馆",
  "content_raw": "沈默和小红初次见面",
  "content_polished": "雨声里，沈默推门而入...",
  "importance": 4,
  "participants": [
    {"participant_type":"character", "participant_name":"沈默","role_raw":"initiator"},
    {"participant_type":"character", "participant_name":"小红", "role_raw":"secondary"}
  ]
}
```

**`settings.txt`**：
```json
{ "category": "supernatural", "title": "灵气复苏", "desc_raw": "214 年灵气复苏", "setting_type": "essential", "importance": 5 }
```

**`plot_planning.txt`**：
```json
{
  "tick_num": 0,
  "plot_raw": "沈默觉醒 → 加入异能局 → 对抗反派",
  "estimated_time_raw": "3 个月内",
  "importance": 5,
  "is_completed": 0
}
```

<a id="s7-3"></a>

### 7.3 一键生成剧本流程（drama_generator skill）

输入：用户 prompt + 风格 + 规模参数

输出：9+1 文件逐一生成：
1. 先 meta（确定主角/时间/基调）
2. settings（世界观/时代/文化/超自然）
3. maps（从大到小，宇宙→星球→城市→建筑→房间；含移动地图如飞船）
4. **map_features（v3 新增：为每张地图生成地形要素 — 山川河流/高楼建筑/星球恒星/飞船等）**
5. characters（核心→次要→路人）
6. groups + group_hierarchies（含 primary_map_id + 热力图初始数据）
7. items（核心物品/货币）
8. 初始历史 events（过去发生的事使世界有历史）
9. plot_plannings（主线/支线脉络）

生成完写入 `backend/drama/{name}/` 目录。可 9 分屏查看修改。

---

<a id="s8-conventions"></a>

## 八、工程约定与硬约束（继承 v2 + 新增）

### 硬约束
1. 所有 JSON 格式配置。
2. 工具配置 JSON 存 `agent/conf/tools/`。
3. 快照目录：`saves/{存档名}.snapshots/round_{N:04d}_{YYYYMMDD_HHMMSS}.db`
4. importance 一律 0-5，默认 3。
5. 游戏时间格式：`{纪元}{年}年{月}月{日}日{时}时{分}分{秒}秒`。
6. 状态字段 status 为字符串 `/` 多维。
7. 剧情规划 1 个 plot 字段 + estimated_time。
8. 日志：`LOG_DIR` env，文件名 `agent_YYYY-MM-DD.log`。
9. 剧本文件 `backend/drama/`。
10. `.env` / `.env.example` / `requirements.txt` 全放 `backend/`。
11. CharacterExperience / GroupExperience 的 status：`in_progress`/`completed`/`paused`/`terminated`。
12. BaseSetting.setting_type：`essential`/`supplementary`。
13. 同存重名报错（不可覆盖创建）。
14. maps.parent_map_id（层级）。
15. 所有玩家可见字段：每句都是 `_raw` + `_polished` 双字段 v3 全局约定。

### 工程约定
1. 工具命名：`{entity_slug}_{action}`。
2. Prompt：`agent/conf/prompts/{name}/config.json`（version 字段）+ `v{n}/ 版本文案。
3. Skill：`agent/conf/skills/{name}/config.json`（default_version）+ `v{n}/skill.md`。
4. 存储模型 Active Record：`storage/models.py`。
5. 迁移 `_init_schema`（create_save / switch_save 都触发）。
6. 前端 JSON 内容必须换行缩进展示；custom_attrs 自动解析成结构化。
7. 事件流页面聊天+右侧栏拖拽可调。
8. 三层 Canvas 地图渲染（静态/动态/效果）。

---

*文档结束。v3_redesign_spec.md*
