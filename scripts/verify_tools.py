"""验证 tool 注册。"""
import sys, os
sys.path.insert(0, os.path.abspath('.'))
from src.backend.agent.tool.base import ToolManager
from src.backend.agent.tool import storage_tools, entity_tools, map_tools, memory_tools, world_tools

print(f"Registered tools: {len(ToolManager.list_names())}")
print(f"  storage: {len(storage_tools.SAVE_TOOLS)}")
print(f"  entity:  {len(entity_tools.ENTITY_TOOL_NAMES)}  (19 实体 x 5 工具 = 95)")
print(f"  map:     {len(map_tools.MAP_TOOLS)}")
print(f"  memory:  {len(memory_tools.MEMORY_TOOLS)}")
print(f"  world:   {len(world_tools.WORLD_TOOLS)}")
total = len(storage_tools.SAVE_TOOLS) + len(entity_tools.ENTITY_TOOL_NAMES) + len(map_tools.MAP_TOOLS) + len(memory_tools.MEMORY_TOOLS) + len(world_tools.WORLD_TOOLS)
print(f"Total expected: {total}")
assert len(ToolManager.list_names()) == total, "工具数不匹配"
print("OK")
