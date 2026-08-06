# v3 六项功能改造方案

> 覆盖范围：前端 → 后端接口 → 执行流程 → skill/prompt → 数据库
> 对应需求：①tick 超时修复 ②底部布局优化 ③中栏筛选精简 ④右侧信息增强 ⑤润色解耦 ⑥润色风格配置

---

## 一、现状梳理（已核实）

| 模块 | 现状文件 | 关键点 |
| --- | --- | --- |
| 底部控制 | `src/frontend/src/components/BottomBar.tsx` | 自动/暂停/下一Tick/时间跨越(9键)/行动输入 |
| 时间预设 | `src/frontend/src/store/gameStore.ts` | `TIME_JUMP_PRESETS`、`AUTO_SPEED_PRESETS` |
| 中栏筛选 | `src/frontend/src/components/EventStreamPanel.tsx` | 类型chips+下拉+重要性+角色聚焦+原文+当前tick+刷新 |
| 右栏 | `src/frontend/src/components/RightPanel.tsx` | 5 tab：角色/群体/物品/地图/记忆(占位) |
| 润色UI | `src/frontend/src/components/LeftPanel.tsx` | 润色长度(4档)+血腥+成人+暴力等级 |
| 管线 | `src/backend/agent/pipeline.py` | 7步 tick：meta→衰减→监控→角色决策→世界反应→编码→润色 |
| 润色变量 | `src/backend/agent/pipeline.py:_build_variables` | 从环境变量读 `POLISH_LENGTH/GORE_ENABLED/ADULT_CONTENT_ENABLED`（与 UI 脱节） |
| 润色skill | `src/backend/agent/conf/skills/event_polisher/v0/skill.md` | 基于 `polish_length/gore/adult` 四变量 |
| 配置 | `src/backend/config.json` | `simulation` 下含 `gore/adult/violence/polish_length` |
| 记忆数据 | `storage/models.py` | memories/memory_index/memory_links/character_impressions/character_quests/character_agendas/character_group_relations |
| 记忆接口 | `src/backend/http/routers/memory.py` | `/api/memory/retrieve`、`/impressions/{char_id}` |
| 全局配置 | `src/backend/http/deps.py` + `routers/config.py` | `get_global_config/set_global_config`，深 merge |

**核心问题**：UI 写入 `config.json`，但 `_build_variables` 读环境变量 → 玩家在界面设置的润色偏好根本不会生效。这是需求⑤的根因，也是润色风格(需求⑥)必须走 `config.json` + skill 变量的原因。

---

## 二、需求① tick 超时修复

### 根因
`net::ERR_ABORTED http://localhost:5173/api/agent/tick` 是**客户端主动中止**。tick 管线含 5 次以上 LLM 长调用，远超 axios 默认 30s 超时。

### 已做
`src/frontend/src/api/client.ts` 已为 `agentApi.tick/timeJump` 加 `LLM_TIMEOUT = 600000`（10 分钟）。

### 待补强
1. **前端**：`gameStore.runTickOnce` 在 `isProcessing` 期间禁止 `refreshEvents` 等短请求混用同一超时（它们默认 30s 无碍）。请求期间禁用页面刷新导航（`onBeforeUnload` 提示）。
2. **后端**（可选加固）：`deepseek_client.chat_completion` 增加超时与取消感知；`/agent/tick` 做成异步任务 + 轮询，避免网关/反向代理在长连接时断开。当前直连 Uvicorn 可不做，作为后续可选演进。
3. **验证**：浏览器 Network 面板确认 tick 请求 `Request Timeout` 显示为 10 分钟；点击后无 ERR_ABORTED。

---

## 三、需求② 底部布局优化

### 目标布局（3 行）
- **第 1 行【Tick】**：`秒|分|时` 三个按钮，点击展开二级数值：
  - 秒：10 / 20 / 30 / 40 / 50
  - 分：1 / 5 / 10 / 20 / 30 / 50
  - 时：1 / 2 / 3 / 4 / 5 / 6 / 12
- **第 2 行【时间跨越】**：`天|月|年|百年|千年|万年|纪元`，每个展开 1–10。
- **第 3 行【瞬间动作】**：左侧输入框（提示输入瞬间动作）+ 右侧「发送」。
- **保留**：任务 / 纲领 tab（`GamePage.tsx` 的 `gp-bottom-tabs`）。

### 前端改动
**`src/frontend/src/store/gameStore.ts`**
- 新增 `TIME_UNIT_OPTS`：
  ```ts
  export const TICK_UNITS = {
    second: { factor: 1,   options: [10,20,30,40,50] },
    minute: { factor: 60,  options: [1,5,10,20,30,50] },
    hour:   { factor: 3600,options: [1,2,3,4,5,6,12] },
  };
  export const JUMP_UNITS = {  // 单位秒数
    day:86400, month:86400*30, year:86400*365,
    century:86400*365*100, millennium:86400*365*1000,
    myriayear:86400*365*10000, era:86400*365*100000,
  };
  ```
- 新增 action：`runTick(unit, n)`（组合出 seconds 调 `agentApi.tick`）、`runJump(unit, n)`、`submitAction(text, seconds)`（先写 `player_action` 事件，再带动作推进 tick）。

**`src/frontend/src/components/BottomBar.tsx`** 重写为 3 行栅格，二级按钮用「点击父按钮 → 弹出该单位的数值选项行」。

### 后端接口（新增字段）
**`src/backend/http/routers/agent.py` 的 `TickReq` 扩展**：
```python
class TickReq(BaseModel):
    seconds: int = 60
    max_actors: int = 5
    player_action: Optional[str] = None   # 瞬间动作文本
```
`pipeline.tick_once` 若收到 `player_action`，在 Step 4 前把该动作作为主角预置决策注入。

### 执行流程（带瞬间动作的 tick）
```
tick_once(seconds, player_action)
  1. 若 player_action:
       - 写一条 player_action 事件到 events（world_service.create_event）
       - 把该动作放入 Step4 actor_decide 的主角变量（role_name=主角）
  2. 正常 7 步（衰减/监控/决策/世界反应/编码/润色，受需求⑤⑥控制）
```

### 新增 skill：`player_action`
`src/backend/agent/conf/skills/player_action/v0/skill.md`
```
# player_action
你负责把玩家的瞬间动作转化为该角色的合理行动，并给出本 tick 的决策要点。
输入：玩家动作 ${player_action}、当前时间 ${game_time}、角色 ${role_name}。
输出：主角本 tick 的行动决策 JSON（含 action_summary / 影响范围 / 可选事件）。
```
在 Step 4 中代替 `actor_decide` 调用（主角），或作为额外 user_prompt 段塞进 `actor_decide`。

---

## 四、需求③ 中栏筛选精简

**`src/frontend/src/components/EventStreamPanel.tsx`**：
- **删除**：`eventTypes` 类型 chips 区、`filter.eventType` 下拉、`importanceMin` 重要性输入。
- **保留**：角色聚焦（`charIds` 多选 chips）、「原文」checkbox（`showRaw`）、`当前 Tick` 显示、`⟳ 刷新`按钮。
- `gameStore.eventsFilter` 可保留旧字段（不破坏），前端不再渲染即可。
- 中栏 `filter-summary` 与角色聚焦样式不变。

---

## 五、需求④ 右侧信息增强

### 数据来源（数据库已全部存在）
`character_impressions`（A→B 印象/好感/信任/恐惧）、`memories`（角色记忆）、`memory_index`（索引）、`memory_links`（宫殿关联）、`character_quests`（任务）、`character_agendas`（纲领）、`character_group_relations`（角色-群体关系）、`event_participants`（角色参与事件）。

### 后端新增聚合接口
**`src/backend/http/routers/entities.py`**（或新 `character_profiles.py`）：
```
GET /api/characters/{id}/profile
```
返回角色完整档案：
```json
{
  "character": { ...Character 全字段 },
  "impressions": [ {target_char_id, target_name, impression_polished, favorability, trust, fear, last_update_tick} ],
  "memories": [ {id, memory_polished, depth, correctness, is_false, remember_tick} ],
  "quests": [ {title, status, priority, desc_polished} ],
  "agendas": [ {title, principle_polished, status} ],
  "groups": [ {group_id, group_name, role_raw, importance_in_group} ],
  "recent_events": [ {event_id, tick_num, event_type, content_polished} ],
  "relations": [ {other_char_id, other_name, link_type, weight} ]  // 由 memory_links 聚合
}
```
外层函数组名 `target_name/group_name` 需 join `characters/groups` 表。

### 前端改动
**`src/frontend/src/components/RightPanel.tsx`**
- 角色 tab 反复使用：点击角色卡片 → 打开抽屉/Modal 展示上述档案（复用 `CharacterTab` 增加 `onOpen`）。
- **记忆 tab**：将占位 `MemoryTab` 落地——选主角 → 调 `memoryApi.retrieve(charId)` 展示 `outline`(印象) + `memories` + `expanded`（宫殿）。
- 新增 `src/frontend/src/api/client.ts`：`worldApi`/`entitiesApi` 增加 `characterProfile(id)`。

---

## 六、需求⑤ 润色解耦

### 新配置模型（`config.json` → `simulation`）
```json
"simulation": {
  "polish_mode": "none",        // none | short | long  （删除 gore/adult/violence）
  "polish_style": "default"     // 见需求⑥
}
```
删除 `simulation.gore_enabled / adult_content / violence_level`、`polish_length`。

### 后端改动
**`src/backend/agent/pipeline.py`**
1. `_build_variables` 改为从全局配置读：
   ```python
   from src.backend.http.deps import get_global_config
   cfg = get_global_config().get("simulation", {})
   variables["polish_mode"] = cfg.get("polish_mode", "none")
   variables["polish_style"] = cfg.get("polish_style", "default")
   ```
2. Step 7 **解耦**：
   - `polish_mode == "none"`：**完全跳过** `event_polisher` 调用；`content_polished` 直接写 `content_raw`（或留空），零 LLM 调用。
   - `polish_mode == "short"/"long"`：写完原文后，新增/保留独立节点调用 `event_polisher`，把 `polish_mode` + `polish_style` 注入变量，回填 `content_polished`。
   - 把润色从 Step 5 的 `world_create_event` 内联润色中抽离，统一由 Step 7 负责（**解耦**）。

### 前端改动
**`src/frontend/src/components/LeftPanel.tsx`**
- 润色选项改为三选一：`无润色(none) / 短润色(short) / 长润色(long)`（`select`），删除血腥/成人/暴力三个控件。
- `POLISH_LEN_OPTS` 改为 `POLISH_MODE_OPTS`。
- `patchCfg` 只提交 `{ simulation: { polish_mode, polish_style } }`。

### 新增 skill：润色强规范
**升级 `src/backend/agent/conf/skills/event_polisher/v0/skill.md`**：
```markdown
# event_polisher
你是一个**严格忠于原文**的事件润色器。把 `content_raw` 改写为 `content_polished`。

## 硬性约束（违反即视为不合格）
1. **零新增事实**：不得添加 raw 中不存在的人物、地点、事件、对白、因果。
2. **零删除事实**：不得删除 raw 中已存在的关键信息。
3. **只增强表达**：可丰富句式、意象、感官描写的措辞，但意义不得改变。
4. **角色口径**：不得替角色说出 raw 中未说的话。
5. **长度档**：short=1-2句；long=1段(≤400字)。
6. **风格**：严格遵循风格块 ${polish_style_prompt}；若为 default 则保持中性。

## 输出
仅返回润色后的纯文本，不包含 JSON 包裹。
```
（`polish_style_prompt` 由需求⑥动态注入。）

---

## 七、需求⑥ 润色风格配置

### 后端：风格 JSON 列表文件
**新文件 `src/backend/config/polish_styles.json`**：
```json
{
  "styles": [
    { "key": "default", "name": "默认", "prompt": "保持中性、克制的叙事风格，不刻意修饰。" },
    { "key": "poetic", "name": "诗意", "prompt": "大量使用比喻与意象，语言富有韵律与画面感。示例：原文『他走进森林』→『他踏入雾霭沉沉的林荫，脚步声惊起一片沉睡的露水』。" },
    { "key": "grimdark", "name": "黑暗残酷", "prompt": "冷峻、压抑，突出残酷与绝望的氛围。" }
  ]
}
```
key=风格标识，value=prompt 描述 + 示例。

### 后端：风格管理服务 + 接口
**新 `src/backend/service/polish_style_service.py`**：`list / upsert / delete`（读写 JSON，带锁）。
**`src/backend/http/routers/config.py`（或新 router）**：
```
GET    /api/config/polish_styles          → 全部风格
POST   /api/config/polish_styles          → 新增/覆盖自定义风格 {key,name,prompt}
DELETE /api/config/polish_styles/{key}    → 删除自定义风格
```

### 后端：风格注入执行方案
采用**「skill 变量注入」方案**（推荐，优于动态拼 prompt 的脆弱性）：
1. `_build_variables` 读 `simulation.polish_style` 的 key。
2. 从 `polish_styles.json` 取出该 key 的 `prompt`，写入变量 `polish_style_prompt`。
3. `event_polisher` skill 通过 `${polish_style_prompt}` 使用（见需求⑤ skill 模板）。
   - 若 key 不存在 → 回退 `default`。
   - 若 `polish_mode == none` → 不触发该 skill。

### 前端改动
**`src/frontend/src/components/LeftPanel.tsx`**：内容偏好区新增「润色风格」下拉，选项来自 `GET /api/config/polish_styles`，选中即 `patchCfg({ simulation: { polish_style } })`。

**`src/frontend/src/pages/StartPage.tsx`（首页）**：新增「润色风格」管理卡片：
- 列表现有风格（key/name/prompt）。
- 「添加/编辑」表单：key、name、prompt 描述与示例 → `POST /api/config/polish_styles`。
- 「删除」自定义风格按钮。

**`src/frontend/src/api/client.ts`**：`configApi` 增加 `polishStyles()` / `upsertPolishStyle()` / `deletePolishStyle()`。

---

## 八、数据库改动

**结论：无需新增表**。需求②④⑤⑥全部复用现有表：
- 需求②：`events`（player_action 事件）、`event_participants`。
- 需求④：`character_impressions / memories / memory_index / memory_links / character_quests / character_agendas / character_group_relations / event_participants`。
- 需求⑤⑥：润色配置存 `config.json`（非 DB）；润色结果存 `events.content_polished`、`memories.memory_polished`。

> 若未来需要「每个角色独立润色风格」，可在 `characters.custom_attrs` 加 `polish_style`（JSON 字段，无需迁移）。当前版本用全局 `config.json` 即可。

---

## 九、改动文件清单

| 层 | 文件 | 动作 |
| --- | --- | --- |
| 前端 | `api/client.ts` | 加 `configApi.polishStyles/Upsert/Delete`、`characterProfile` |
| 前端 | `store/gameStore.ts` | 加单位预设、`runTick/runJump/submitAction` |
| 前端 | `components/BottomBar.tsx` | 3 行布局重写 |
| 前端 | `components/EventStreamPanel.tsx` | 删类型/重要性筛选 |
| 前端 | `components/RightPanel.tsx` | 角色档案抽屉 + 记忆 tab 落地 |
| 前端 | `components/LeftPanel.tsx` | 润色三档 + 风格下拉，删血腥/成人/暴力 |
| 前端 | `pages/StartPage.tsx` | 首页风格管理卡片 |
| 后端 | `http/routers/agent.py` | `TickReq` 加 `player_action` |
| 后端 | `agent/pipeline.py` | 读 config 润色配置、Step7 解耦、player_action 注入 |
| 后端 | `agent/conf/skills/event_polisher/v0/skill.md` | 强规范 + 风格变量 |
| 后端 | `agent/conf/skills/player_action/v0/skill.md` | 新建 |
| 后端 | `service/polish_style_service.py` | 新建 |
| 后端 | `http/routers/config.py` | 风格 CRUD 端点 |
| 后端 | `config/polish_styles.json` | 新建 |
| 后端 | `config.json` | `simulation` 改 `polish_mode/polish_style` |
| 后端 | `http/routers/entities.py` | `GET /characters/{id}/profile` |

---

## 十、实施顺序建议

1. **需求①**：验证超时已生效（最小改动）。
2. **需求③**：删中栏筛选（纯前端，最快见效）。
3. **需求⑤**：润色解耦 + 配置改 `polish_mode`（后端 `_build_variables` + 前端 LeftPanel + skill 强规范）。
4. **需求⑥**：风格 JSON + CRUD 接口 + 注入 + 首页管理（依赖⑤的 skill 变量）。
5. **需求④**：角色档案聚合接口 + 右侧抽屉 + 记忆 tab。
6. **需求②**：底部 3 行布局 + `player_action` skill（依赖接口扩展）。