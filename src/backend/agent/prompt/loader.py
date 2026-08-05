"""src.backend.agent.prompt.loader — Prompt 模板加载与变量注入。

支持 ${var} 模板变量，从存档元信息或调用上下文动态注入。
支持多版本管理：list / get / create(copytree) / update / set_active。
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.backend.env import BACKEND_DIR

PROMPTS_DIR = BACKEND_DIR / "agent" / "conf" / "prompts"

_VAR_RE = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


class PromptVersion:
    """单个 prompt 版本（v0/v1/...）。"""

    def __init__(self, version_dir: Path, version: str):
        self.version_dir = version_dir
        self.version = version
        self.system_prompt = ""
        self.user_prompt = ""
        sp = version_dir / "system_prompt.md"
        if sp.is_file():
            self.system_prompt = sp.read_text(encoding="utf-8")
        up = version_dir / "user_prompt.md"
        if up.is_file():
            self.user_prompt = up.read_text(encoding="utf-8")


class FilePrompt:
    """单个 prompt 配置（多版本）。"""

    def __init__(self, prompt_dir: Path):
        self.prompt_dir = prompt_dir
        self.name = prompt_dir.name
        config_path = prompt_dir / "config.json"
        self.config: Dict[str, Any] = {}
        if config_path.is_file():
            # utf-8-sig 兼容带 BOM 的文件
            self.config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        self.default_version = self.config.get("default_version", "v0")
        self.versions: Dict[str, PromptVersion] = {}
        # 加载所有版本子目录 v0/v1/...
        for sub in sorted(prompt_dir.iterdir()):
            if sub.is_dir() and sub.name.startswith("v") and sub.name[1:].isdigit():
                self.versions[sub.name] = PromptVersion(sub, sub.name)
        # 兼容旧 flat 布局：prompt 根目录直接有 system_prompt.md
        if not self.versions and (prompt_dir / "system_prompt.md").is_file():
            self.versions["v0"] = PromptVersion(prompt_dir, "v0")

    def get_version(self, version: Optional[str] = None) -> PromptVersion:
        v = version or self.default_version
        if v not in self.versions:
            if not self.versions:
                raise FileNotFoundError(f"prompt {self.name} 无任何版本")
            # 兜底取第一个
            v = next(iter(self.versions))
        return self.versions[v]

    def render(self, variables: Dict[str, Any], version: Optional[str] = None) -> Dict[str, str]:
        """渲染 system + user prompt，注入变量。"""
        pv = self.get_version(version)
        return {
            "system_prompt": _inject(pv.system_prompt, variables),
            "user_prompt": _inject(pv.user_prompt, variables),
        }


def _inject(text: str, variables: Dict[str, Any]) -> str:
    """把 ${var} 替换为变量值。未提供的变量保留原样（开发期可见）。"""
    def repl(m: re.Match) -> str:
        key = m.group(1)
        if key in variables:
            return str(variables[key])
        return m.group(0)
    return _VAR_RE.sub(repl, text)


# ============================================================
# Registry
# ============================================================

_prompts_cache: Dict[str, FilePrompt] = {}


def list_prompts() -> List[str]:
    if not PROMPTS_DIR.exists():
        return []
    return sorted(p.name for p in PROMPTS_DIR.iterdir() if p.is_dir())


def get_prompt(name: str) -> Optional[FilePrompt]:
    if name in _prompts_cache:
        return _prompts_cache[name]
    p = PROMPTS_DIR / name
    if not p.is_dir():
        return None
    fp = FilePrompt(p)
    _prompts_cache[name] = fp
    return fp


def render_prompt(name: str, variables: Dict[str, Any], version: Optional[str] = None) -> Dict[str, str]:
    fp = get_prompt(name)
    if not fp:
        raise FileNotFoundError(f"prompt {name} 不存在")
    return fp.render(variables, version)


# ============================================================
# 版本管理 API（供 HTTP 路由调用）
# ============================================================

def _clear_cache(name: Optional[str] = None) -> None:
    """清缓存，使下次 get_prompt 重新读盘。"""
    if name is None:
        _prompts_cache.clear()
    else:
        _prompts_cache.pop(name, None)


def list_prompt_versions(name: str) -> List[str]:
    """返回某 prompt 的所有版本号（已排序）。"""
    fp = get_prompt(name)
    if not fp:
        raise FileNotFoundError(f"prompt {name} 不存在")
    return list(fp.versions.keys())


def get_prompt_version_detail(name: str, version: str) -> Dict[str, Any]:
    """取某版本详情（含 system_prompt + user_prompt 原文）。"""
    fp = get_prompt(name)
    if not fp:
        raise FileNotFoundError(f"prompt {name} 不存在")
    if version not in fp.versions:
        raise FileNotFoundError(f"版本 {version} 不存在")
    pv = fp.versions[version]
    return {
        "name": name,
        "version": version,
        "system_prompt": pv.system_prompt,
        "user_prompt": pv.user_prompt,
    }


def create_prompt_version(
    name: str,
    new_version: str,
    from_version: Optional[str] = None,
    system_prompt: Optional[str] = None,
    user_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """新建 prompt 版本（基于 from_version 的 copytree，可覆盖 system/user_prompt）。"""
    fp = get_prompt(name)
    if not fp:
        raise FileNotFoundError(f"prompt {name} 不存在")

    if not (new_version.startswith("v") and new_version[1:].isdigit()):
        raise ValueError(f"非法版本号 {new_version}（应为 v0/v1/...）")

    target_dir = fp.prompt_dir / new_version
    if target_dir.exists():
        raise FileExistsError(f"版本 {new_version} 已存在")

    if from_version:
        if from_version not in fp.versions:
            raise FileNotFoundError(f"源版本 {from_version} 不存在")
        src_dir = fp.versions[from_version].version_dir
        shutil.copytree(src_dir, target_dir)
    else:
        target_dir.mkdir(parents=True)

    if system_prompt is not None:
        (target_dir / "system_prompt.md").write_text(system_prompt, encoding="utf-8")
    if user_prompt is not None:
        (target_dir / "user_prompt.md").write_text(user_prompt, encoding="utf-8")

    _clear_cache(name)
    return {"name": name, "version": new_version, "created": True}


def update_prompt_version(
    name: str,
    version: str,
    system_prompt: Optional[str] = None,
    user_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """更新某版本的 system_prompt / user_prompt 内容。"""
    fp = get_prompt(name)
    if not fp:
        raise FileNotFoundError(f"prompt {name} 不存在")
    if version not in fp.versions:
        raise FileNotFoundError(f"版本 {version} 不存在")

    pv = fp.versions[version]
    if system_prompt is not None:
        (pv.version_dir / "system_prompt.md").write_text(system_prompt, encoding="utf-8")
    if user_prompt is not None:
        (pv.version_dir / "user_prompt.md").write_text(user_prompt, encoding="utf-8")

    _clear_cache(name)
    return {"name": name, "version": version, "updated": True}


def set_prompt_active_version(name: str, version: str) -> Dict[str, Any]:
    """设置激活版本（重写 config.json 的 default_version）。"""
    fp = get_prompt(name)
    if not fp:
        raise FileNotFoundError(f"prompt {name} 不存在")
    if version not in fp.versions:
        raise FileNotFoundError(f"版本 {version} 不存在")

    config_path = fp.prompt_dir / "config.json"
    config = fp.config.copy()
    config["default_version"] = version
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    _clear_cache(name)
    return {"name": name, "active_version": version}


def delete_prompt_version(name: str, version: str) -> Dict[str, Any]:
    """删除某个 prompt 版本目录。
    规则同 delete_skill_version：至少保留一个版本，删除激活版本前先切。
    """
    fp = get_prompt(name)
    if not fp:
        raise FileNotFoundError(f"prompt {name} 不存在")
    if version not in fp.versions:
        raise FileNotFoundError(f"版本 {version} 不存在")
    if len(fp.versions) <= 1:
        raise ValueError("至少保留一个版本，禁止删除")

    if fp.default_version == version:
        remaining = [v for v in fp.versions.keys() if v != version]
        new_active = sorted(remaining)[0]
        config_path = fp.prompt_dir / "config.json"
        config = fp.config.copy()
        config["default_version"] = new_active
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    shutil.rmtree(str(fp.versions[version].version_dir), ignore_errors=True)
    _clear_cache(name)
    return {"name": name, "deleted_version": version}
