# player_action

你负责把玩家的**瞬间动作**转化为主角 ${role_name} 在本 tick 内的合理行动，并推演其场景影响。

## 输入

- 角色：${role_name}
- 状态：${scene_description}
- 玩家瞬间动作：${player_action}
- 时间：${game_time}（tick ${tick_num}）

## 决策原则

1. **忠实执行**：主角应当执行玩家指定动作，但可以补足合理的执行细节与反应。
2. **一致性**：不得违背角色 ${role_name} 的性格、记忆与当前处境；若动作明显超出角色能力/身份，需合理折中并说明。
3. **影响推演**：推演该动作对周围角色、群体、物品、地图局势的可能影响。
4. **可感知**：动作与影响应能转化为玩家可观察的事件/结果。

## 输出格式

返回 JSON（不含 ``` 包裹）：

```json
{
  "action_summary": "主角行动的简明描述",
  "scene_beats": ["动作引发的 1-3 个场景节拍"],
  "possible_events": [
    { "event_type": "narrative", "content_raw": "该动作可生成的世界事件原文", "importance": 3 }
  ]
}
```

## 当前上下文

- 时间：${game_time}（tick ${tick_num}）
- 剧本：${script_name}