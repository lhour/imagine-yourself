"""src.backend.agent.tool — Tool 系统与工具注册。

v5 工具分组：
- storage_tools: 存档/元信息/主角管理（meta_tools）
- entity_tools:  每个实体自动生成 5 个 CRUD（约 25 实体 × 5 = 125 个）
- memory_tools:  记忆系统工具（5 个）→ 重构为 subjective_tools 子集
- map_tools:     地图与距离工具（4 个）
- world_tools:   世界事件工具（3 个）
- anchor_tools:  v4 新增：锚点剧情管理（4 个）
- graph_tools:   v4 新增：图库关系查询与写入（6 个）
- vector_tools:  v4 新增：向量语义检索（规划中，暂以 memory_retrieve 兼代）
- dynamic_tools: v5 新增：动态实体创建 + 配额检查 + 设定追加
- knowledge_tools: v5 新增：知识库检索与管理
- web_fetch_tools: v5 新增：网络资源抓取
"""

# 顺序导入，触发 @tool 装饰器自动注册
from src.backend.agent.tool import storage_tools  # noqa: F401
from src.backend.agent.tool import entity_tools   # noqa: F401
from src.backend.agent.tool import memory_tools   # noqa: F401
from src.backend.agent.tool import map_tools       # noqa: F401
from src.backend.agent.tool import world_tools    # noqa: F401
from src.backend.agent.tool import anchor_tools   # v4 新增  # noqa: F401
from src.backend.agent.tool import graph_tools    # v4 新增  # noqa: F401
from src.backend.agent.tool import scheduled_event_tools  # 10.3 新增  # noqa: F401
from src.backend.agent.tool import dynamic_tools  # v5 新增  # noqa: F401
from src.backend.agent.tool import web_fetch_tools  # v5 新增  # noqa: F401
from src.backend.knowledge.tool import KNOWLEDGE_TOOL_NAMES  # v5 新增  # noqa: F401

from src.backend.agent.tool.base import ToolManager, tool, ToolSpec  # noqa: F401

# 所有工具名清单（供 skill 配置引用）
ALL_TOOL_NAMES = (
    storage_tools.SAVE_TOOLS
    + entity_tools.STORAGE_TOOLS
    + memory_tools.MEMORY_TOOLS
    + map_tools.MAP_TOOLS
    + world_tools.WORLD_TOOLS
    + anchor_tools.ANCHOR_TOOLS
    + graph_tools.GRAPH_TOOLS
    + scheduled_event_tools.SCHEDULED_EVENT_TOOLS
    + dynamic_tools.DYNAMIC_TOOL_NAMES
    + web_fetch_tools.WEB_FETCH_TOOL_NAMES
    + KNOWLEDGE_TOOL_NAMES
)

# v5 语义分组（供 Skill/Agent 按模块选用）
TOOL_GROUPS = {
    "meta_tools": storage_tools.SAVE_TOOLS,
    "objective_tools": entity_tools.STORAGE_TOOLS + map_tools.MAP_TOOLS + world_tools.WORLD_TOOLS,
    "subjective_tools": memory_tools.MEMORY_TOOLS + graph_tools.GRAPH_TOOLS,
    "graph_tools": graph_tools.GRAPH_TOOLS,
    "vector_tools": [memory_tools.MEMORY_TOOLS[0]],  # memory_retrieve 内部已接入向量召回
    "anchor_tools": anchor_tools.ANCHOR_TOOLS,
    "scheduled_event_tools": scheduled_event_tools.SCHEDULED_EVENT_TOOLS,
    "map_tools": map_tools.MAP_TOOLS,
    "world_tools": world_tools.WORLD_TOOLS,
    # v5 新增
    "dynamic_tools": dynamic_tools.DYNAMIC_TOOL_NAMES,
    "entity_quota_tools": [dynamic_tools.DYNAMIC_TOOL_NAMES[0]],  # entity_quota_check
    "entity_create_tools": dynamic_tools.DYNAMIC_TOOL_NAMES[1:7],  # 6 个创建工具
    "setting_append_tools": dynamic_tools.DYNAMIC_TOOL_NAMES[7:],  # setting_append + world_meta_append
    "knowledge_tools": KNOWLEDGE_TOOL_NAMES,  # 知识库检索与管理
    "web_fetch_tools": web_fetch_tools.WEB_FETCH_TOOL_NAMES,  # 网络资源抓取
}
