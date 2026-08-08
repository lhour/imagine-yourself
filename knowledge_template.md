# 知识库条目模板

## 格式说明
知识库条目使用 JSON 格式，包含以下字段：
- `title`: 条目标题（必填）
- `content`: 条目详细内容（必填）
- `category_name`: 分类名称（必填，可选分类见下方）
- `keywords`: 关键词列表（用于检索）
- `tags`: 标签列表
- `source`: 来源（manual/script/import）
- `importance`: 重要度 1-5

## 支持的分类
- 武器法宝
- 武功武学
- 人物外貌
- 人物性格
- 种族生物
- 势力组织
- 场景地点
- 物品道具
- 剧情套路
- 其他设定

## 示例（JSON 格式）
```json
{
  "title": "墨渊剑",
  "content": "上古神剑，剑身漆黑如墨，蕴含深渊之力。使用者需以心神为引，否则易被剑意反噬。",
  "category_name": "武器法宝",
  "keywords": ["神剑", "上古", "墨"],
  "tags": ["武器", "剑"],
  "source": "manual",
  "importance": 5
}
```

## 批量导入格式
每行一个 JSON 对象（JSONL 格式），可一次性导入多条。
