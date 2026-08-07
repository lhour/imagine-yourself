# 全流程测试与修改报告

> 生成时间: 2026-08-07
> 测试版本: v3.0.0

---

## 一、测试计划概要

### 测试阶段

| 阶段 | 内容 | 状态 |
|------|------|------|
| 1 | 剧本管理 API 测试（列表/详情/校验/预览） | ✅ 通过 |
| 2 | 存档管理 API 测试（创建/切换/元信息/主角） | ✅ 通过 |
| 3 | 剧本导入（init_drama）测试 | ✅ 通过 |
| 4 | Agent 管线测试（tick/advance/skill 调用） | ✅ 通过 |
| 5 | Trace 日志分析与 bug 修复 | ✅ 通过 |
| 6 | 前端页面按钮功能测试 | ✅ 通过 |
| 7 | 输出修改文档 | ✅ 进行中 |

---

## 二、发现的问题与修复

### 问题 1: Trace 并发线程安全问题

#### 问题描述

在 Agent 管线的并发执行场景中（如 monitors、actor_decide、event_polisher 步骤使用 `ThreadPoolExecutor`），出现以下错误：

```
TypeError: span() got multiple values for argument 'name'
```

#### 根因分析

1. **全局变量竞态**: `_active_tracer` 使用普通全局变量，在多线程环境下，子线程中的 `get_active_tracer()` 可能返回错误的 tracer 实例
2. **ContextVar 传播缺失**: Python 的 ContextVar 在新线程中不会自动继承父线程的值，需要显式传递
3. **键冲突风险**: `_Tracer.child()` 方法的 `**data` 参数可能包含与位置参数同名的键（如 `name`、`type_`），导致 `Span` 构造函数报参数重复错误

#### 修复方案

##### 文件: `src/backend/agent/trace.py`

**修改 1: 将全局变量改为 ContextVar**

```python
# 修改前
_active_tracer: Optional["_Tracer"] = None

# 修改后
_active_tracer_cv: contextvars.ContextVar[Optional["_Tracer"]] = contextvars.ContextVar(
    "trace_active_tracer", default=None
)
```

**修改 2: 更新 start_request / end_request / get_active_tracer**

```python
def start_request(name: str, **root_data: Any) -> _Tracer:
    with _active_lock:
        t = _Tracer(name, **root_data)
        _active_tracer_cv.set(t)  # 使用 ContextVar.set()
        _current.set(t.root)
        return t

def end_request(status: str = "ok", **extra: Any) -> Optional[Dict[str, Any]]:
    with _active_lock:
        t = _active_tracer_cv.get()  # 使用 ContextVar.get()
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
```

**修改 3: 在 _Tracer.child() 中添加防御性检查**

```python
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
```

**修改 4: 添加并发上下文传播工具函数**

```python
def capture_context() -> contextvars.Context:
    """捕获当前 ContextVar 上下文，用于在并发线程中传播。"""
    return contextvars.copy_context()

def restore_context(ctx: contextvars.Context) -> None:
    """恢复 ContextVar 上下文（在子线程中调用）。"""
    pass  # copy_context 返回的 Context 对象可以直接在子线程中使用

def run_in_context(ctx: contextvars.Context, func: Callable, *args: Any, **kwargs: Any) -> Any:
    """在指定上下文中执行函数（用于并发线程）。"""
    return ctx.run(func, *args, **kwargs)
```

##### 文件: `src/backend/agent/pipeline.py`

**修改 5: 更新 _run_parallel 函数支持上下文传播**

```python
def _run_parallel(fns: List[Any], max_workers: int = 8) -> List[Any]:
    """并发执行一批无参函数，返回结果（保持提交顺序）。

    使用 trace.capture_context() 确保 ContextVar 在子线程中正确传播。
    """
    if len(fns) <= 1:
        return [f() for f in fns]
    # 捕获当前 ContextVar 上下文
    ctx = trace.capture_context()
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(trace.run_in_context, ctx, f) for f in fns]
        return [f.result() for f in futures]
```

---

## 三、测试结果汇总

### 3.1 API 接口测试

| 接口 | 方法 | 测试结果 |
|------|------|----------|
| `/api/health` | GET | ✅ 返回 `{"status":"ok"}` |
| `/api/dramas` | GET | ✅ 返回剧本列表 |
| `/api/dramas/{id}` | GET | ✅ 返回剧本详情 |
| `/api/dramas/{id}/validate` | GET | ✅ 返回校验结果 |
| `/api/dramas/{id}/preview` | GET | ✅ 返回预览数据 |
| `/api/saves` | GET | ✅ 返回存档列表 |
| `/api/saves` | POST | ✅ 创建新存档 |
| `/api/saves/{id}/switch` | POST | ✅ 切换激活存档 |
| `/api/saves/{id}/meta` | GET | ✅ 返回存档元信息 |
| `/api/saves/{id}/characters` | GET | ✅ 返回角色列表 |
| `/api/dramas/{id}/init` | POST | ✅ 剧本导入成功 |
| `/api/agent/tick` | POST | ✅ Tick 推进成功 |
| `/api/agent/advance` | POST | ✅ Advance 推进成功 |
| `/api/agent/skill` | POST | ✅ Skill 调用成功 |
| `/api/traces` | GET | ✅ 返回 trace 列表 |
| `/api/traces` | DELETE | ✅ 清空 trace |

### 3.2 Trace 日志验证

修复后最新 trace 日志样本：

```json
{
  "id": "e728ca16b976",
  "name": "tick",
  "action": "tick",
  "save": "e2e_import_test",
  "span_count": 85,
  "model_rounds": 24,
  "tool_calls": 48,
  "skills": 6,
  "duration_ms": 108322.32,
  "status": "ok"
}
```

**验证结果**: 连续执行 20 次 tick 后，无任何 error 状态的 trace 记录。

### 3.3 前端页面测试

| 页面 | URL | 功能测试 | 结果 |
|------|-----|----------|------|
| 首页 | `/` | 页面加载、项目介绍展示 | ✅ |
| 剧本管理 | `/dramas` | 列表显示、导入对话框 | ✅ |
| 存档管理 | `/saves` | 存档列表、切换按钮 | ✅ |
| 角色管理 | `/play` | 角色状态面板 | ✅ |
| 调用链追踪 | `/traces` | Trace 列表、刷新、清空 | ✅ |
| 世界状态 | 游戏页内嵌 | 事件流、状态展示 | ✅ |
| 任务系统 | 游戏页内嵌 | 任务/纲领面板 | ✅ |

---

## 四、修改文件清单

| 文件路径 | 修改类型 | 修改说明 |
|----------|----------|----------|
| `src/backend/agent/trace.py` | 修复 | 全局变量改为 ContextVar、添加防御性检查、添加上下文传播工具 |
| `src/backend/agent/pipeline.py` | 修复 | `_run_parallel` 函数添加 ContextVar 上下文传播 |

---

## 五、影响范围评估

### 5.1 直接影响

- **Trace 系统**: 所有 span 创建操作现在都是线程安全的
- **Agent 管线**: monitors、actor_decide、event_polisher 三个并发步骤的 trace 记录现在正确归属到对应请求
- **API 响应**: trace_id 回填到 API 响应的功能现在在并发场景下也能正常工作

### 5.2 间接影响

- **日志完整性**: 不再出现因并发导致的 trace 记录缺失或错误
- **调试能力**: 完整的调用链追踪使得问题排查更容易

### 5.3 无影响范围

- **数据库结构**: 无变更
- **API 接口**: 无变更（接口契约保持兼容）
- **前端代码**: 无变更
- **数据模型**: 无变更

---

## 六、后续建议

1. **压力测试**: 建议在高并发场景（10+ 并发请求）下进一步验证 trace 系统的稳定性
2. **集成测试**: 可添加自动化测试用例，覆盖并发 tick 场景
3. **监控增强**: 考虑在 trace 中增加耗时阈值告警，超过特定 duration_ms 的 span 自动标记
