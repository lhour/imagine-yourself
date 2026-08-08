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
import datetime as _dt
import glob
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


def _traces_file_for(date: Optional[_dt.date] = None) -> Path:
    """返回指定日期对应的 trace 文件路径（YYYYMMDD 命名）。"""
    if date is None:
        date = _dt.date.today()
    return LOG_DIR / f"traces_{date.strftime('%Y%m%d')}.jsonl"


def _current_traces_file() -> Path:
    """返回今天的 trace 文件路径。"""
    return _traces_file_for()


def _all_traces_files() -> List[Path]:
    """列出所有日期的 trace 文件（按日期升序）。"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(LOG_DIR.glob("traces_*.jsonl"))


# 兼容旧代码：TRACES_FILE 指向今天的文件
TRACES_FILE = _current_traces_file()

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


def capture_context() -> Dict[str, Any]:
    """捕获当前 ContextVar 上下文快照（字典形式，避免 Context.run 重入报错）。

    用法：
        ctx = trace.capture_context()
        future = executor.submit(trace.run_in_context, ctx, do_work, arg1)
    """
    return {
        "_active_tracer_cv": _active_tracer_cv.get(None),
        "_current": _current.get(None),
    }


def restore_context(ctx: Dict[str, Any]) -> None:
    """在当前线程中恢复所有 ContextVar（返回 token，便于 reset 可回滚）。"""
    tokens: Dict[str, Any] = {}
    if "_active_tracer_cv" in ctx:
        tokens["_active_tracer_cv"] = _active_tracer_cv.set(ctx["_active_tracer_cv"])
    if "_current" in ctx:
        tokens["_current"] = _current.set(ctx["_current"])
    return tokens


def run_in_context(ctx: Dict[str, Any], func: Callable, *args: Any, **kwargs: Any) -> Any:
    """在指定上下文中执行函数（并发线程专用，不走 Context.run 避免重入报错）。"""
    tokens = restore_context(ctx)
    try:
        return func(*args, **kwargs)
    finally:
        # 注意：reset 前判断 token 是否存在；此处不 reset 是为了兼容线程复用（线程池会复用线程，
        # ContextVar 下次 restore 时会覆盖旧值即可，无需严格 reset）。
        # 如果是一次性线程可打开下面的 reset：
        # for k, t in tokens.items():
        #     try:
        #         if k == "_active_tracer_cv":
        #             _active_tracer_cv.reset(t)
        #         elif k == "_current":
        #             _current.reset(t)
        #     except (ValueError, LookupError):
        #         pass
        pass


# ============================================================
# 落盘 + 查询
# ============================================================

def _append_jsonl(d: Dict[str, Any]) -> None:
    """追加一行 trace 到今天的日志文件（追加模式，不覆盖历史）。"""
    try:
        fpath = _current_traces_file()
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(fpath, "a", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def _compute_token_usage(node: Dict[str, Any]) -> Dict[str, Any]:
    """遍历 span 树，为每个节点计算 token_usage。

    - model_call 节点：直接使用 data.usage 中的 token 数据
    - 其他节点：累加所有子节点的 token 消耗
    - 缓存命中字段也向父节点聚合
    """
    children = node.get("children", [])
    direct_prompt = 0
    direct_completion = 0
    direct_total = 0
    direct_cache_hit = 0
    direct_cache_miss = 0

    if node.get("type") == "model_call":
        usage = node.get("data", {}).get("usage", {})
        if usage:
            direct_prompt = usage.get("prompt_tokens", 0) or 0
            direct_completion = usage.get("completion_tokens", 0) or 0
            direct_total = usage.get("total_tokens", 0) or 0
            if not direct_total:
                direct_total = direct_prompt + direct_completion
            direct_cache_hit = usage.get("prompt_cache_hit_tokens", 0) or 0
            direct_cache_miss = usage.get("prompt_cache_miss_tokens", 0) or 0

    child_prompt = 0
    child_completion = 0
    child_total = 0
    child_cache_hit = 0
    child_cache_miss = 0
    for child in children:
        cu = _compute_token_usage(child)
        child_prompt += cu["prompt_tokens"]
        child_completion += cu["completion_tokens"]
        child_total += cu["total_tokens"]
        child_cache_hit += cu.get("cache_hit_tokens", 0)
        child_cache_miss += cu.get("cache_miss_tokens", 0)

    total_prompt = direct_prompt + child_prompt
    total_completion = direct_completion + child_completion
    total_all = direct_total + child_total
    total_cache_hit = direct_cache_hit + child_cache_hit
    total_cache_miss = direct_cache_miss + child_cache_miss

    node["token_usage"] = {
        "prompt_tokens": total_prompt,
        "completion_tokens": total_completion,
        "total_tokens": total_all,
        "cache_hit_tokens": total_cache_hit,
        "cache_miss_tokens": total_cache_miss,
        "direct_prompt_tokens": direct_prompt,
        "direct_completion_tokens": direct_completion,
        "direct_total_tokens": direct_total,
        "direct_cache_hit_tokens": direct_cache_hit,
        "direct_cache_miss_tokens": direct_cache_miss,
        "child_prompt_tokens": child_prompt,
        "child_completion_tokens": child_completion,
        "child_total_tokens": child_total,
        "child_cache_hit_tokens": child_cache_hit,
        "child_cache_miss_tokens": child_cache_miss,
    }
    return node["token_usage"]


def _summarize(d: Dict[str, Any]) -> Dict[str, Any]:
    root = d
    spans = _flatten(d)
    model_rounds = sum(1 for s in spans if s["type"] == "model_call")
    tool_calls = sum(1 for s in spans if s["type"] == "tool_call")
    skills = sum(1 for s in spans if s["type"] == "skill_call")

    # 计算 token 聚合
    token_usage = root.get("token_usage", {})
    total_tokens = token_usage.get("total_tokens", 0)
    prompt_tokens = token_usage.get("prompt_tokens", 0)
    completion_tokens = token_usage.get("completion_tokens", 0)
    cache_hit_tokens = token_usage.get("cache_hit_tokens", 0)
    cache_miss_tokens = token_usage.get("cache_miss_tokens", 0)

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
        "total_tokens": total_tokens,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cache_hit_tokens": cache_hit_tokens,
        "cache_miss_tokens": cache_miss_tokens,
    }


def _flatten(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = [node]
    for c in node.get("children", []):
        out.extend(_flatten(c))
    return out


def _iter_all_lines() -> List[str]:
    """遍历所有日期的 trace 文件，返回所有行（老文件在前，新文件在后）。"""
    out: List[str] = []
    for fpath in _all_traces_files():
        try:
            with open(fpath, encoding="utf-8") as f:
                out.extend(f.readlines())
        except OSError:
            continue
    return out


def list_traces(limit: int = 200) -> List[Dict[str, Any]]:
    """列出最近的 trace 摘要（跨所有日期文件，最新在前）。"""
    lines = _iter_all_lines()
    out: List[Dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            d = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        # 确保 token_usage 已计算（兼容旧日志）
        if "token_usage" not in d:
            _compute_token_usage(d)
        out.append(_summarize(d))
    out.reverse()  # 最新在前
    return out


def get_trace(tid: str) -> Optional[Dict[str, Any]]:
    """按 id 查找单条 trace（跨所有日期文件）。"""
    if not tid:
        return None
    for fpath in _all_traces_files():
        try:
            with open(fpath, encoding="utf-8") as f:
                for line in f:
                    try:
                        d = json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    if d.get("id") == tid:
                        # 确保 token_usage 已计算（兼容旧日志）
                        if "token_usage" not in d:
                            _compute_token_usage(d)
                        return d
        except OSError:
            continue
    return None


def clear_traces() -> int:
    """清空所有日期的 trace 文件，返回被清空的总行数。"""
    n = 0
    for fpath in _all_traces_files():
        try:
            with open(fpath, encoding="utf-8") as f:
                n += sum(1 for _ in f)
            fpath.write_text("", encoding="utf-8")
        except OSError:
            pass
    return n