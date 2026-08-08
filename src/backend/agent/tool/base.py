"""src.backend.agent.tool.base — @tool 装饰器与 ToolManager。

用法：
    @tool(name="hello", desc="打招呼")
    def hello(name: str) -> dict:
        return {"msg": f"hello {name}"}

ToolManager 自动收集注册的工具，并提供 OpenAI function-calling schema。

工具描述可通过 agent/conf/tools/tool_descriptions.json 覆盖（前端编辑会落盘到此文件）。
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, get_type_hints

from src.backend.env import BACKEND_DIR


# JSON Schema 类型映射
_PY_TO_JSON_SCHEMA = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


_TOOL_DESCRIPTIONS_PATH = BACKEND_DIR / "agent" / "conf" / "tools" / "tool_descriptions.json"


def _load_description_overrides() -> Dict[str, str]:
    if not _TOOL_DESCRIPTIONS_PATH.is_file():
        return {}
    try:
        return json.loads(_TOOL_DESCRIPTIONS_PATH.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _save_description_overrides(data: Dict[str, str]) -> None:
    _TOOL_DESCRIPTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _TOOL_DESCRIPTIONS_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


class ToolSpec:
    """单个工具的元数据 + 函数。"""

    def __init__(
        self,
        func: Callable,
        name: str,
        desc: str,
        params: Optional[Dict[str, Any]] = None,
    ):
        self.func = func
        self.name = name
        self.desc = desc
        self.params = params or self._infer_params(func)

    def _infer_params(self, func: Callable) -> Dict[str, Any]:
        """从函数签名推断 OpenAI function-calling 参数 schema。"""
        sig = inspect.signature(func)
        hints = get_type_hints(func) if hasattr(func, "__annotations__") else {}
        properties: Dict[str, Any] = {}
        required: List[str] = []
        for pname, p in sig.parameters.items():
            if pname in ("self", "cls"):
                continue
            ptype = hints.get(pname, str)
            json_type = _PY_TO_JSON_SCHEMA.get(ptype, "string")
            properties[pname] = {
                "type": json_type,
                "description": getattr(p.annotation, "__doc__", "") or "",
            }
            if p.default is inspect.Parameter.empty:
                required.append(pname)
        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    def to_openai_schema(self) -> Dict[str, Any]:
        # 每次生成 schema 时检查覆盖，确保前端编辑后立即生效
        overrides = _load_description_overrides()
        desc = overrides.get(self.name, self.desc)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": desc,
                "parameters": self.params,
            },
        }

    def call(self, **kwargs) -> Any:
        return self.func(**kwargs)


def tool(name: str, desc: str, params: Optional[Dict[str, Any]] = None):
    """装饰器：把函数注册为工具。"""
    def decorator(func: Callable) -> Callable:
        spec = ToolSpec(func, name=name, desc=desc, params=params)
        ToolManager.register(spec)
        func.__tool_spec__ = spec  # type: ignore[attr-defined]
        return func
    return decorator


class _ToolManager:
    """工具注册中心。"""

    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def list_names(self) -> List[str]:
        return sorted(self._tools.keys())

    def list_with_descriptions(self) -> List[Dict[str, Any]]:
        overrides = _load_description_overrides()
        out: List[Dict[str, Any]] = []
        for name in sorted(self._tools.keys()):
            spec = self._tools[name]
            out.append({
                "name": name,
                "desc": overrides.get(name, spec.desc),
                "base_desc": spec.desc,
                "overridden": name in overrides,
            })
        return out

    def all_schemas(self) -> List[Dict[str, Any]]:
        return [spec.to_openai_schema() for spec in self._tools.values()]

    def schemas_for(self, names: List[str]) -> List[Dict[str, Any]]:
        return [self._tools[n].to_openai_schema() for n in names if n in self._tools]

    def execute(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        spec = self.get(name)
        if not spec:
            return {"error": f"未知工具: {name}"}
        try:
            result = spec.call(**arguments)
            return {"result": result} if not isinstance(result, dict) or "error" not in result else result
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    @staticmethod
    def update_description(name: str, desc: str) -> Optional[str]:
        """更新某工具的描述（写入 tool_descriptions.json）。
        返回旧描述；工具不存在时返回 None。
        """
        spec = ToolManager.get(name)
        if not spec:
            return None
        overrides = _load_description_overrides()
        overrides[name] = desc
        _save_description_overrides(overrides)
        return overrides.get(name)


# 单例
ToolManager = _ToolManager()
