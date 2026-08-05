"""src.backend.agent.tool — Tool 系统与工具注册。

import 此包即触发所有工具模块的 @tool 装饰器，
将工具注册到 ToolManager 单例中。

工具分组：
- storage_tools: 存档/元信息/主角管理（9 个）
- entity_tools:  每个实体自动生成 5 个 CRUD（约 25 实体 × 5 = 125 个）
- memory_tools: 记忆系统工具（5 个）
- map_tools:    地图与距离工具（4 个）
- world_tools:  世界事件工具（3 个）
"""

# 顺序导入，触发 @tool 装饰器自动注册
from src.backend.agent.tool import storage_tools  # noqa: F401
from src.backend.agent.tool import entity_tools   # noqa: F401
from src.backend.agent.tool import memory_tools   # noqa: F401
from src.backend.agent.tool import map_tools       # noqa: F401
from src.backend.agent.tool import world_tools    # noqa: F401

from src.backend.agent.tool.base import ToolManager, tool, ToolSpec  # noqa: F401

# 所有工具名清单（供 skill 配置引用）
ALL_TOOL_NAMES = (
    storage_tools.SAVE_TOOLS
    + entity_tools.STORAGE_TOOLS
    + memory_tools.MEMORY_TOOLS
    + map_tools.MAP_TOOLS
    + world_tools.WORLD_TOOLS
)
