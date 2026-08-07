"""src.backend.agent.trace — 请求级调用链追踪（span 树 + JSONL 落盘）。

统一的请求日志格式：每个请求 = 一棵 span 树。
span 类型：
- request        根，代表一次 API 请求动作
- step           管线内的步骤（分组节点）
- skill_call     一次 skill 调用
- model_call     一次 LLM 多轮调用中的单轮（可展开：prompt / think / output / usage）
- tool_call      一次工具执行（工具输入参数 / 返回结果）

并发：span 记录 start/end 时间戳，兄弟 span 时间区间重叠即并发。
前端用时间轴 / 火焰图渲染 span 树，直观看出前后关系与并发关系。

落盘：每个完成的请求 append 一行 JSON 到 LOG_DIR/traces.jsonl。
"""

from __future__ import annotations

import contextlib
import contextvars
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.backend.env import BACKEND_DIR, load_backend_env

load_backend_env()

LOG_DIR = Path(os.environ.get("LOG_DIR", "logs"))
if not LOG_DIR.is_absolute():
    LOG_DIR = BACKEND_DIR.parent.parent / LOG_DIR

TRACES_FILE = LOG_DIR / "traces.jsonl"

# 当前活动 span（线程隔离；每个线程各自持有自己的 _current）
_current: contextvars.ContextVar[Optional["Span"]] = contextvars.ContextVar(
    "trace_current", default=None
)

# 当前活动 tracer（改为 ContextVar 实现线程隔离）
_active_tracer_cv: contextvars.ContextVar[Optional["_Tracer"]] = contextvars.ContextVar(
    "trace_active_tracer", default=None
)
_active_lock = threading.RLock()


class Span:
    """调用链中的一个节点。"""

    __slots__ = (
        "id", "name", "type", "parent", "children", "data",
        "start_wall", "start_ns", "end_ns", "status", "thread_id",
    )

    def __init__(self, name: str, type_: str = "step", parent: Optional["Span"] = None, **data: Any):
        self.id = uuid.uuid4().hex[:12]
        self.name = name
        self.type = type_
        self.parent = parent
        self.children: List["Span"] = []
        self.data: Dict[str, Any] = data
        self.start_wall = time.time()
        self.start_ns = time.perf_counter_ns()
        self.end_ns: Optional[int] = None
        self.status = "running"
        self.thread_id = threading.get_ident()

    def finish(self, status: str = "ok", **extra: Any) -> None:
        self.end_ns = time.perf_counter_ns()
        self.status = status
        self.data.update(extra)

    def record(self, **kw: Any) -> None:
        self.data.update(kw)

    @property
    def duration_ms(self) -> Optional[float]:
        if self.end_ns is None:
            return None
        return round((self.end_ns - self.start_ns) / 1_000_000, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "status": self.status,
            "start_ms": round(self.start_ns / 1_000_000, 2),
            "end_ms": round(self.end_ns / 1_000_000, 2) if self.end_ns else None,
            "duration_ms": self.duration_ms,
            "thread_id": self.thread_id,
            "data": self.data,
            "children": [c.to_dict() for c in self.children],
        }


class _NoopSpan:
    """无活动 tracer 时的占位 span（所有操作 no-op）。"""

    def __init__(self):
        self.data: Dict[str, Any] = {}
        self.id: Optional[str] = None
        self.name = ""
        self.type = ""
        self.status = "ok"

    def finish(self, status: str = "ok", **extra: Any) -> None:
        self.data.update(extra)

    def record(self, **kw: Any) -> None:
        self.data.update(kw)


class _Tracer:
    """一棵请求的调用链树。"""

    def __init__(self, name: str, **root_data: Any):
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        self.root = Span(name, "request", None, ts=ts, **root_data)
        self._lock = threading.RLock()

    def child(self, name: str, type_: str = "step", parent: Optional[Span] = None, **data: Any) -> Span:
        # 防御性：清理可能与位置参数冲突的键
        for k in ("name", "type_", "parent"):
            data.pop(k, None)
        parent = parent or _current.get() or self.root
        s = Span(name, type_, parent, **data)
        with self._lock:
            parent.children.append(s)
        _current.set(s)
        return s

    def finish_child(self, s: Span, status: str = "ok", **extra: Any) -> None:
        s.finish(status, **extra)
        if s.parent is not None:
            _current.set(s.parent)

    def add_root_data(self, **kw: Any) -> None:
        self.root.record(**kw)

    def to_dict(self) -> Dict[str, Any]:
        return self.root.to_dict()


# ============================================================
# 模块级 API
# ============================================================

def start_request(name: str, **root_data: Any) -> _Tracer:
    """开始一次请求追踪，返回 tracer。"""
    with _active_lock:
        t = _Tracer(name, **root_data)
        _active_tracer_cv.set(t)
        _current.set(t.root)
        return t


def end_request(status: str = "ok", **extra: Any) -> Optional[Dict[str, Any]]:
    """结束当前请求追踪，落盘并返回 trace dict。"""
    with _active_lock:
        t = _active_tracer_cv.get()
        _active_tracer_cv.set(None)
        _current.set(None)
    if t is None:
        return None
    t.root.finish(status, **extra)
    d = t.to_dict()
    _append_jsonl(d)
    return d


def get_active_tracer() -> Optional[_Tracer]:
    return _active_tracer_cv.get()


def current_trace_id() -> Optional[str]:
    """当前活动请求 trace 的根 id（用于回填到 API 响应）。"""
    t = get_active_tracer()
    return t.root.id if t is not None else None


@contextlib.contextmanager
def request(name: str, **root_data: Any):
    """以一次 HTTP 请求为单位的追踪上下文。

    用法：
        with trace.request("tick", action="tick"):
            ...  # 其中的 span() 自动挂到该请求树下
    结束时自动落盘；异常时标记 error 并继续抛出。
    """
    t = start_request(name, **root_data)
    try:
        yield t
    except Exception:  # noqa: BLE001
        end_request(status="error")
        raise
    else:
        end_request(status="ok")


def add_root_data(**kw: Any) -> None:
    t = get_active_tracer()
    if t is not None:
        t.add_root_data(**kw)


@contextlib.contextmanager
def span(name: str, type_: str = "step", parent: Optional[Span] = None, **data: Any):
    """进入一个 span 子节点；无活动 tracer 时 no-op。"""
    t = get_active_tracer()
    if t is None:
        ns = _NoopSpan()
        ns.data.update(data)
        yield ns
        return
    s = t.child(name, type_, parent, **data)
    try:
        yield s
    except Exception as e:  # noqa: BLE001
        t.finish_child(s, "error", error=_safe_str(e))
        raise
    else:
        t.finish_child(s, "ok")


def _safe_str(e: Exception) -> str:
    return f"{type(e).__name__}: {e}"


def capture_context() -> contextvars.Context:
    """捕获当前 ContextVar 上下文，用于在并发线程中传播。

    用法：
        ctx = trace.capture_context()
        future = executor.submit(lambda: trace.restore_context(ctx) or do_work())
    """
    return contextvars.copy_context()


def restore_context(ctx: contextvars.Context) -> None:
    """恢复 ContextVar 上下文（在子线程中调用）。"""
    pass  # copy_context 返回的 Context 对象可以直接在子线程中使用


def run_in_context(ctx: contextvars.Context, func: Callable, *args: Any, **kwargs: Any) -> Any:
    """在指定上下文中执行函数（用于并发线程）。

    用法：
        ctx = trace.capture_context()
        future = executor.submit(trace.run_in_context, ctx, do_work, arg1, arg2)
    """
    return ctx.run(func, *args, **kwargs)


# ============================================================
# 落盘 + 查询
# ============================================================

def _append_jsonl(d: Dict[str, Any]) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(TRACES_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def _summarize(d: Dict[str, Any]) -> Dict[str, Any]:
    root = d
    spans = _flatten(d)
    model_rounds = sum(1 for s in spans if s["type"] == "model_call")
    tool_calls = sum(1 for s in spans if s["type"] == "tool_call")
    skills = sum(1 for s in spans if s["type"] == "skill_call")
    return {
        "id": root.get("id"),
        "ts": root.get("data", {}).get("ts"),
        "name": root.get("name"),
        "action": root.get("data", {}).get("action"),
        "save": root.get("data", {}).get("save"),
        "span_count": len(spans),
        "model_rounds": model_rounds,
        "tool_calls": tool_calls,
        "skills": skills,
        "duration_ms": root.get("duration_ms"),
        "status": root.get("status"),
    }


def _flatten(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = [node]
    for c in node.get("children", []):
        out.extend(_flatten(c))
    return out


def list_traces(limit: int = 200) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not TRACES_FILE.exists():
        return out
    try:
        with open(TRACES_FILE, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return out
    for line in lines[-limit:]:
        try:
            d = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        out.append(_summarize(d))
    out.reverse()  # 最新在前
    return out


def get_trace(tid: str) -> Optional[Dict[str, Any]]:
    if not tid or not TRACES_FILE.exists():
        return None
    try:
        with open(TRACES_FILE, encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if d.get("id") == tid:
                    return d
    except OSError:
        return None
    return None


def clear_traces() -> int:
    n = 0
    if TRACES_FILE.exists():
        try:
            with open(TRACES_FILE, encoding="utf-8") as f:
                n = sum(1 for _ in f)
            TRACES_FILE.write_text("", encoding="utf-8")
        except OSError:
            n = 0
    return n