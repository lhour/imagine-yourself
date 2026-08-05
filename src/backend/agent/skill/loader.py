"""src.backend.agent.skill.loader — Skill 加载与执行。

Skill = 系统提示词（skill.md）+ 可用工具集合 + 参数。
支持多版本管理：list / get / create(copytree) / update / set_active。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.backend.env import BACKEND_DIR

SKILLS_DIR = BACKEND_DIR / "agent" / "conf" / "skills"


class SkillVersion:
    def __init__(self, version_dir: Path, version: str):
        self.version_dir = version_dir
        self.version = version
        self.skill_md = ""
        sm = version_dir / "skill.md"
        if sm.is_file():
            self.skill_md = sm.read_text(encoding="utf-8")
        # 兼容旧字段 system_prompt.md
        if not self.skill_md:
            sp = version_dir / "system_prompt.md"
            if sp.is_file():
                self.skill_md = sp.read_text(encoding="utf-8")


class FileSkill:
    """单个 skill 配置（多版本）。"""

    def __init__(self, skill_dir: Path):
        self.skill_dir = skill_dir
        self.name = skill_dir.name
        config_path = skill_dir / "config.json"
        self.config: Dict[str, Any] = {}
        if config_path.is_file():
            # utf-8-sig 兼容带 BOM 的文件（PowerShell Set-Content 会加 BOM）
            self.config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        self.default_version = self.config.get("default_version", "v0")
        self.description = self.config.get("description", "")
        self.tools: List[str] = self.config.get("tools", [])
        self.params: Dict[str, Any] = self.config.get("params", {})
        self.versions: Dict[str, SkillVersion] = {}
        for sub in sorted(skill_dir.iterdir()):
            if sub.is_dir() and sub.name.startswith("v") and sub.name[1:].isdigit():
                self.versions[sub.name] = SkillVersion(sub, sub.name)
        # 兼容旧 flat 布局
        if not self.versions and (skill_dir / "skill.md").is_file():
            self.versions["v0"] = SkillVersion(skill_dir, "v0")

    def get_version(self, version: Optional[str] = None) -> SkillVersion:
        v = version or self.default_version
        if v not in self.versions:
            if not self.versions:
                raise FileNotFoundError(f"skill {self.name} 无任何版本")
            v = next(iter(self.versions))
        return self.versions[v]

    def render(self, variables: Dict[str, Any], version: Optional[str] = None) -> str:
        from src.backend.agent.prompt.loader import _inject
        sv = self.get_version(version)
        return _inject(sv.skill_md, variables)


_skills_cache: Dict[str, FileSkill] = {}


def list_skills() -> List[str]:
    if not SKILLS_DIR.exists():
        return []
    return sorted(p.name for p in SKILLS_DIR.iterdir() if p.is_dir())


def get_skill(name: str) -> Optional[FileSkill]:
    if name in _skills_cache:
        return _skills_cache[name]
    p = SKILLS_DIR / name
    if not p.is_dir():
        return None
    fs = FileSkill(p)
    _skills_cache[name] = fs
    return fs


def render_skill(name: str, variables: Dict[str, Any], version: Optional[str] = None) -> str:
    fs = get_skill(name)
    if not fs:
        raise FileNotFoundError(f"skill {name} 不存在")
    return fs.render(variables, version)


# ============================================================
# 版本管理 API（供 HTTP 路由调用）
# ============================================================

def _clear_cache(name: Optional[str] = None) -> None:
    """清缓存，使下次 get_skill 重新读盘。"""
    if name is None:
        _skills_cache.clear()
    else:
        _skills_cache.pop(name, None)


def list_skill_versions(name: str) -> List[str]:
    """返回某 skill 的所有版本号（已排序）。"""
    fs = get_skill(name)
    if not fs:
        raise FileNotFoundError(f"skill {name} 不存在")
    return list(fs.versions.keys())


def get_skill_version_detail(name: str, version: str) -> Dict[str, Any]:
    """取某版本详情。API 字段名为 system_prompt（保留 LLM 通用术语）。"""
    fs = get_skill(name)
    if not fs:
        raise FileNotFoundError(f"skill {name} 不存在")
    if version not in fs.versions:
        raise FileNotFoundError(f"版本 {version} 不存在")
    sv = fs.versions[version]
    return {
        "name": name,
        "version": version,
        "system_prompt": sv.skill_md,  # API 字段名遵循 LLM 通用术语
        "skill_md": sv.skill_md,       # 同时暴露文件字段名，便于前端显示
    }


def create_skill_version(
    name: str,
    new_version: str,
    from_version: Optional[str] = None,
    skill_md: Optional[str] = None,
) -> Dict[str, Any]:
    """新建 skill 版本（基于 from_version 的 copytree，可覆盖 skill_md）。

    new_version 形如 'v1' / 'v2'。
    """
    fs = get_skill(name)
    if not fs:
        raise FileNotFoundError(f"skill {name} 不存在")

    # 校验版本号格式
    if not (new_version.startswith("v") and new_version[1:].isdigit()):
        raise ValueError(f"非法版本号 {new_version}（应为 v0/v1/...）")

    target_dir = fs.skill_dir / new_version
    if target_dir.exists():
        raise FileExistsError(f"版本 {new_version} 已存在")

    # 拷贝源版本目录
    if from_version:
        if from_version not in fs.versions:
            raise FileNotFoundError(f"源版本 {from_version} 不存在")
        src_dir = fs.versions[from_version].version_dir
        shutil.copytree(src_dir, target_dir)
    else:
        target_dir.mkdir(parents=True)
        # 兜底写一个空 skill.md
        (target_dir / "skill.md").write_text("", encoding="utf-8")

    # 若指定了 skill_md，覆盖
    if skill_md is not None:
        (target_dir / "skill.md").write_text(skill_md, encoding="utf-8")

    _clear_cache(name)
    return {"name": name, "version": new_version, "created": True}


def update_skill_version(
    name: str,
    version: str,
    skill_md: Optional[str] = None,
) -> Dict[str, Any]:
    """更新某版本的 skill.md 内容。"""
    fs = get_skill(name)
    if not fs:
        raise FileNotFoundError(f"skill {name} 不存在")
    if version not in fs.versions:
        raise FileNotFoundError(f"版本 {version} 不存在")

    sv = fs.versions[version]
    if skill_md is not None:
        (sv.version_dir / "skill.md").write_text(skill_md, encoding="utf-8")

    _clear_cache(name)
    return {"name": name, "version": version, "updated": True}


def set_skill_active_version(name: str, version: str) -> Dict[str, Any]:
    """设置激活版本（重写 config.json 的 default_version）。"""
    fs = get_skill(name)
    if not fs:
        raise FileNotFoundError(f"skill {name} 不存在")
    if version not in fs.versions:
        raise FileNotFoundError(f"版本 {version} 不存在")

    config_path = fs.skill_dir / "config.json"
    config = fs.config.copy()
    config["default_version"] = version
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    _clear_cache(name)
    return {"name": name, "active_version": version}


def delete_skill_version(name: str, version: str) -> Dict[str, Any]:
    """删除某个版本目录。
    规则：
    - 至少保留一个版本（删除最后一个会抛 ValueError）
    - 如果被删的版本是 default_version，先把 default_version 切换到另一个版本
    """
    fs = get_skill(name)
    if not fs:
        raise FileNotFoundError(f"skill {name} 不存在")
    if version not in fs.versions:
        raise FileNotFoundError(f"版本 {version} 不存在")
    if len(fs.versions) <= 1:
        raise ValueError("至少保留一个版本，禁止删除")

    # 切 active 到另一个版本（如果需要）
    if fs.default_version == version:
        # 取剩余版本中第一个（按字典序）
        remaining = [v for v in fs.versions.keys() if v != version]
        new_active = sorted(remaining)[0]
        config_path = fs.skill_dir / "config.json"
        config = fs.config.copy()
        config["default_version"] = new_active
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    # 删除目录
    shutil.rmtree(str(fs.versions[version].version_dir), ignore_errors=True)
    _clear_cache(name)
    return {"name": name, "deleted_version": version}
