"""src.backend.service.drama_service — 剧本管理：扫描 / 读取 / 导入存档 / 校验。

核心函数：
- list_dramas(): 列出 backend/drama/ 下所有剧本目录
- get_drama(name): 剧本详情（meta 信息 + 文件清单）
- validate_drama(name): **严格 9+1 校验**（文件齐全 + 结构 + 引用一致）
- init_drama(name, save_name, overwrite=False):
    1. 先调用 validate_drama 严格校验
    2. 新建或覆盖存档
    3. 读 9+1 文件写入存档（处理 name→ID 引用解析）
- preview(name): 在线预览 9+1 文件内容（前端卡片化预览用）
- patch_drama_file(name, file_name, content): **原子写**（写临时文件 + os.replace）
- export_drama_zip(name): 导出 10 个文件为 zip（内存中打包）
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.backend.env import BACKEND_DIR
from src.backend.storage import models
from src.backend.storage.connection import SaveManager, default_save_manager

DRAMA_DIR = BACKEND_DIR / "drama"

REQUIRED_FILES = [
    "meta.txt",
    "characters.txt",
    "groups.txt",
    "group_hierarchies.txt",
    "items.txt",
    "maps.txt",
    "map_features.txt",
    "events.txt",
    "settings.txt",
    "plot_planning.txt",
]

# 每个 JSONL 文件至少需要的字段（软校验，字段缺失只 warning）
REQUIRED_FIELDS: Dict[str, List[str]] = {
    "characters.txt": ["name"],
    "groups.txt": ["name"],
    "group_hierarchies.txt": [],   # child_group_name / parent_group_name 也可
    "items.txt": ["name"],
    "maps.txt": ["name"],
    "map_features.txt": [],        # feature 可匿名
    "events.txt": ["content_raw"],
    "settings.txt": ["title"],
    "plot_planning.txt": [],       # plot 节点可只含 plot 字段
}

IMPORTANCE_RANGE = (0, 5)


# ============================================================
# 工具函数
# ============================================================

def _now_real_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _load_jsonl(p: Path) -> List[Dict[str, Any]]:
    """读 JSONL 文件，空行跳过，每行都是合法 JSON 对象。"""
    if not p.is_file():
        return []
    out = []
    for i, line in enumerate(p.read_text(encoding="utf-8-sig").splitlines(), 1):
        s = line.strip()
        if not s:
            continue
        try:
            out.append(json.loads(s))
        except json.JSONDecodeError as e:
            raise ValueError(f"JSONL 解析失败：{p.name} 第 {i} 行：{e}") from e
    return out


def _load_json(p: Path) -> Dict[str, Any]:
    if not p.is_file():
        raise FileNotFoundError(f"剧本文件 {p.name} 不存在")
    return json.loads(p.read_text(encoding="utf-8-sig"))


def _importance_clamp(v: Any) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        n = 3
    return max(0, min(5, n))


# ---------- 剧本级玩法配置 ----------

def get_drama_gameplay_options(drama_name: str) -> Dict[str, Any]:
    """读取剧本的玩法配置（不存在则返回默认值）。"""
    from src.backend.storage.gameplay_defaults import get_default_gameplay_options
    drama_path = DRAMA_DIR / drama_name
    if not drama_path.is_dir():
        raise FileNotFoundError(f"剧本 {drama_name} 不存在")
    opts_file = drama_path / "gameplay_options.json"
    defaults = get_default_gameplay_options()
    if opts_file.is_file():
        try:
            raw = json.loads(opts_file.read_text(encoding="utf-8-sig"))
            return _deep_merge_dict(defaults, raw)
        except Exception:
            return defaults
    return defaults


def save_drama_gameplay_options(drama_name: str, options: Dict[str, Any]) -> Dict[str, Any]:
    """保存剧本的玩法配置。"""
    drama_path = DRAMA_DIR / drama_name
    if not drama_path.is_dir():
        raise FileNotFoundError(f"剧本 {drama_name} 不存在")
    opts_file = drama_path / "gameplay_options.json"
    defaults = get_default_gameplay_options()
    merged = _deep_merge_dict(defaults, options)
    opts_file.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return merged


def _deep_merge_dict(base: Dict, override: Dict) -> Dict:
    """深度合并两个 dict：override 覆盖 base，嵌套 dict 也深合并。"""
    import copy
    result = copy.deepcopy(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge_dict(result[key], val)
        else:
            result[key] = copy.deepcopy(val)
    return result


# ============================================================
# 公开 API：扫描 / 详情 / 预览
# ============================================================

def list_dramas() -> List[Dict[str, Any]]:
    """列出所有剧本目录，带 meta 摘要。"""
    if not DRAMA_DIR.exists():
        return []
    out = []
    for p in sorted(DRAMA_DIR.iterdir()):
        if not p.is_dir():
            continue
        meta: Dict[str, Any] = {}
        try:
            meta = _load_json(p / "meta.txt")
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        files = [f.name for f in p.iterdir() if f.is_file()]
        out.append({
            "name": p.name,
            "title": meta.get("name") or p.name,
            "summary": meta.get("summary_raw") or meta.get("summary_polished") or "",
            "protagonist_default": meta.get("protagonist_name_default"),
            "start_game_time": meta.get("start_game_time"),
            "era_name": meta.get("era_name"),
            "files": files,
        })
    return out


def get_drama(name: str) -> Optional[Dict[str, Any]]:
    """剧本详情：meta + 文件清单。"""
    p = DRAMA_DIR / name
    if not p.is_dir():
        return None
    files = {f.name: f.stat().st_size for f in p.iterdir() if f.is_file()}
    meta: Dict[str, Any] = {}
    try:
        meta = _load_json(p / "meta.txt")
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {
        "name": name,
        "path": str(p),
        "meta": meta,
        "files": files,
        "file_count": len(files),
    }


def preview(name: str) -> Dict[str, Any]:
    """在线预览 9+1 文件内容。"""
    p = DRAMA_DIR / name
    if not p.is_dir():
        raise FileNotFoundError(f"剧本 {name} 不存在")
    result: Dict[str, Any] = {}
    for fname in [
        "meta.txt", "characters.txt", "groups.txt", "group_hierarchies.txt",
        "items.txt", "maps.txt", "map_features.txt", "events.txt",
        "settings.txt", "plot_planning.txt",
    ]:
        fp = p / fname
        if not fp.is_file():
            result[fname] = None
            continue
        txt = fp.read_text(encoding="utf-8-sig").rstrip()
        if fname == "meta.txt":
            try:
                result[fname] = json.loads(txt)
            except json.JSONDecodeError:
                result[fname] = txt
        else:
            # JSONL → 数组
            try:
                result[fname] = _load_jsonl(fp)
            except ValueError:
                result[fname] = txt.splitlines()
    return result


def delete_drama(name: str) -> bool:
    """删除剧本目录。"""
    import shutil
    p = DRAMA_DIR / name
    if not p.is_dir():
        return False
    shutil.rmtree(p)
    return True


# ============================================================
# 严格校验：validate_drama — 9+1 文件齐全 + 结构合法 + 引用一致
# ============================================================

def validate_drama(name: str) -> Dict[str, Any]:
    """严格校验剧本：
    返回 { ok, errors: [...], warnings: [...], info: {...} }
    - errors: 阻断导入的严重错误
    - warnings: 不阻断但建议修复
    """
    p = DRAMA_DIR / name
    errors: List[str] = []
    warnings: List[str] = []
    info: Dict[str, Any] = {}

    # --- 1. 目录存在 ---
    if not p.is_dir():
        errors.append(f"剧本目录不存在：{p}")
        return {"ok": False, "errors": errors, "warnings": warnings, "info": info}

    # --- 2. 10 文件齐全 ---
    existing_files = {f.name for f in p.iterdir() if f.is_file()}
    for rf in REQUIRED_FILES:
        if rf not in existing_files:
            errors.append(f"缺少核心文件：{rf}")
    info["missing_files"] = [rf for rf in REQUIRED_FILES if rf not in existing_files]

    # 读取每个文件内容
    data: Dict[str, Any] = {}
    for fname in REQUIRED_FILES:
        fp = p / fname
        if not fp.is_file():
            data[fname] = None
            continue
        try:
            if fname == "meta.txt":
                data[fname] = _load_json(fp)
            else:
                data[fname] = _load_jsonl(fp)
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
            errors.append(f"{fname} 格式错误：{e}")
            data[fname] = None

    # --- 3. meta.txt 校验 ---
    meta = data.get("meta.txt")
    if meta and isinstance(meta, dict):
        if not meta.get("start_game_time"):
            warnings.append("meta.txt 缺少 start_game_time（导入后默认空字符串）")
        if not meta.get("name"):
            warnings.append("meta.txt 缺少 name（将使用目录名）")
        info["title"] = meta.get("name") or name
        info["protagonist_default"] = meta.get("protagonist_name_default")
        info["era_name"] = meta.get("era_name")
    else:
        errors.append("meta.txt 无法解析为 JSON 对象")
        meta = {}

    # --- 4. 行数统计 + 每行字段完整性 ---
    row_counts: Dict[str, int] = {}
    names_by_file: Dict[str, set] = {}
    for fname in REQUIRED_FILES:
        if fname == "meta.txt" or data[fname] is None:
            continue
        rows = data[fname]
        if not isinstance(rows, list):
            errors.append(f"{fname} 解析结果不是数组")
            continue
        row_counts[fname] = len(rows)
        names: set = set()
        for i, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                errors.append(f"{fname} 第{i}行不是 JSON 对象")
                continue
            # 必填字段软校验
            for rfld in REQUIRED_FIELDS.get(fname, []):
                if rfld not in row or row[rfld] in (None, ""):
                    warnings.append(f"{fname} 第{i}行缺少字段 {rfld}")
            # importance 范围
            if "importance" in row:
                try:
                    imp = int(row["importance"])
                except (TypeError, ValueError):
                    warnings.append(f"{fname} 第{i}行 importance 非整数，使用默认3")
                else:
                    if not (IMPORTANCE_RANGE[0] <= imp <= IMPORTANCE_RANGE[1]):
                        warnings.append(
                            f"{fname} 第{i}行 importance={imp} 超出范围 {IMPORTANCE_RANGE}，导入时自动 clamp"
                        )
            # 名称去重
            for nk in ("name", "title", "char_name", "group_name", "map_name", "item_name"):
                if nk in row and isinstance(row[nk], str) and row[nk].strip():
                    nv = row[nk].strip()
                    if nv in names:
                        warnings.append(f"{fname} 第{i}行 {nk}={nv} 与前面行重复，可能导致引用歧义")
                    names.add(nv)
                    break
        names_by_file[fname] = names
    info["row_counts"] = row_counts

    # --- 5. 交叉引用一致性校验 ---
    # 提取各实体名集合
    char_names = names_by_file.get("characters.txt", set())
    group_names = names_by_file.get("groups.txt", set())
    map_names = names_by_file.get("maps.txt", set())
    item_names = names_by_file.get("items.txt", set())

    info["counts"] = {
        "characters": len(char_names),
        "groups": len(group_names),
        "maps": len(map_names),
        "items": len(item_names),
    }

    # protagonist 默认存在
    protag = meta.get("protagonist_name_default") if isinstance(meta, dict) else None
    if protag and protag not in char_names:
        errors.append(f"meta.txt protagonist_name_default={protag} 不在 characters.txt 中")

    # groups.leader_name
    if isinstance(data.get("groups.txt"), list):
        for i, row in enumerate(data["groups.txt"], 1):
            for k in ("leader_name", "leader_id_alias"):
                if row.get(k) and row[k] not in char_names:
                    warnings.append(f"groups.txt 第{i}行 {k}={row[k]} 不在角色列表中（导入时置空）")
            if row.get("primary_map_name") and row["primary_map_name"] not in map_names:
                warnings.append(f"groups.txt 第{i}行 primary_map_name={row['primary_map_name']} 不在地图列表中")

    # group_hierarchies 引用
    if isinstance(data.get("group_hierarchies.txt"), list):
        for i, row in enumerate(data["group_hierarchies.txt"], 1):
            child = row.get("child_group") or row.get("child_group_name")
            parent = row.get("parent_group") or row.get("parent_group_name")
            if child and child not in group_names:
                warnings.append(f"group_hierarchies.txt 第{i}行 child_group={child} 不在群体列表中，将跳过")
            if parent and parent not in group_names:
                warnings.append(f"group_hierarchies.txt 第{i}行 parent_group={parent} 不在群体列表中，将跳过")

    # maps.parent_map_name / current_map_name
    if isinstance(data.get("maps.txt"), list):
        for i, row in enumerate(data["maps.txt"], 1):
            for refk, target_set in [
                ("parent_map_name", map_names),
                ("current_map_name", map_names),
                ("carrier_char_name", char_names),
                ("carrier_item_name", item_names),
            ]:
                if row.get(refk) and row[refk] not in target_set:
                    warnings.append(f"maps.txt 第{i}行 {refk}={row[refk]} 引用不存在（导入时置空）")

    # map_features.map_name / child_map_name / carrier_*
    if isinstance(data.get("map_features.txt"), list):
        for i, row in enumerate(data["map_features.txt"], 1):
            if row.get("map_name") and row["map_name"] not in map_names:
                warnings.append(f"map_features.txt 第{i}行 map_name={row['map_name']} 引用不存在")
            if row.get("child_map_name") and row["child_map_name"] not in map_names:
                warnings.append(f"map_features.txt 第{i}行 child_map_name={row['child_map_name']} 引用不存在")
            ct = row.get("carrier_type")
            cn = row.get("carrier_char_name") or row.get("carrier_name")
            in_ = row.get("carrier_item_name") or row.get("carrier_name")
            if ct == "character" and cn and cn not in char_names:
                warnings.append(f"map_features.txt 第{i}行 carrier_char_name={cn} 不在角色列表中")
            if ct == "item" and in_ and in_ not in item_names:
                warnings.append(f"map_features.txt 第{i}行 carrier_item_name={in_} 不在物品列表中")

    # characters.location_map_name / groups_member
    if isinstance(data.get("characters.txt"), list):
        for i, row in enumerate(data["characters.txt"], 1):
            if row.get("location_map_name") and row["location_map_name"] not in map_names:
                warnings.append(f"characters.txt 第{i}行 location_map_name={row['location_map_name']} 引用不存在")
            for mem in row.get("groups_member") or []:
                gname = mem.get("group_name") if isinstance(mem, dict) else None
                if gname and gname not in group_names:
                    warnings.append(f"characters.txt 第{i}行 groups_member.group_name={gname} 引用不存在")

    # items.holder_name
    if isinstance(data.get("items.txt"), list):
        for i, row in enumerate(data["items.txt"], 1):
            holder = row.get("holder_name") or row.get("owner_name")
            if holder and holder not in char_names:
                warnings.append(f"items.txt 第{i}行 holder_name={holder} 不在角色列表中（导入时不创建持有关系）")

    # events.location_map_name / participants
    if isinstance(data.get("events.txt"), list):
        for i, row in enumerate(data["events.txt"], 1):
            if row.get("location_map_name") and row["location_map_name"] not in map_names:
                warnings.append(f"events.txt 第{i}行 location_map_name={row['location_map_name']} 引用不存在")
            for p in row.get("participants") or []:
                if not isinstance(p, dict):
                    continue
                pt = p.get("participant_type", "character")
                pname = p.get("participant_name") or p.get("name")
                target = {
                    "character": char_names,
                    "group": group_names,
                    "item": item_names,
                    "map": map_names,
                }.get(pt, set())
                if pname and pname not in target:
                    warnings.append(
                        f"events.txt 第{i}行 participant {pt}:{pname} 引用不存在"
                    )

    # plot_planning 存在即可（只写入主角 quest，不强校验）
    pp = data.get("plot_planning.txt")
    if isinstance(pp, list):
        info["counts"]["plot_planning"] = len(pp)
        if len(pp) > 0 and not protag:
            warnings.append("plot_planning.txt 有内容但 meta.txt 未指定 protagonist_name_default（写入时将跳过）")

    ok = len(errors) == 0
    info["ok"] = ok
    return {
        "ok": ok,
        "errors": errors,
        "warnings": warnings,
        "info": info,
    }


def patch_drama_file(name: str, file_name: str, content: str) -> bool:
    """**原子写** 单个剧本文件内容：
    1. 写临时文件（同目录 .{file_name}.tmpXXXX）
    2. os.replace 原子替换
    保证失败时原文件内容不变
    """
    allowed = {
        "meta.txt", "characters.txt", "groups.txt", "group_hierarchies.txt",
        "items.txt", "maps.txt", "map_features.txt", "events.txt",
        "settings.txt", "plot_planning.txt",
    }
    if file_name not in allowed:
        raise ValueError(f"不允许编辑文件 {file_name}")
    p = DRAMA_DIR / name / file_name
    p.parent.mkdir(parents=True, exist_ok=True)
    dir_path = str(p.parent)
    final_path = str(p)
    # 在同目录创建临时文件，确保同卷（os.replace 要求同卷）
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{file_name}.tmp",
        dir=dir_path,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content.rstrip() + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, final_path)
    except Exception:
        # 清理临时文件
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    return True


def export_drama_zip(name: str) -> bytes:
    """将剧本 10 个核心文件打包为 zip（内存中构建，返回 bytes）。"""
    p = DRAMA_DIR / name
    if not p.is_dir():
        raise FileNotFoundError(f"剧本 {name} 不存在")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in REQUIRED_FILES:
            fp = p / fname
            if fp.is_file():
                zf.write(str(fp), arcname=f"{name}/{fname}")
            else:
                # 空文件占位（带注释）
                zf.writestr(f"{name}/{fname}", f"# （{fname} 缺失）\n")
    return buf.getvalue()


# ============================================================
# 核心：init_drama — 把 9+1 文件写入新存档
# ============================================================

def init_drama(
    name: str,
    save_name: str,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """将剧本写入存档。

    流程：
    1. 读取所有 JSONL/JSON 文件
    2. 用 SaveManager.create_save 新建或覆盖激活
    3. 按写入顺序依次批量 create：
       meta → maps → map_features → characters → groups →
       group_hierarchies → character_group_relations →
       items → item_holds → character_locations →
       settings → events → event_participants →
       memories/memory_index/memory_links →
       quests/agendas/quest_steps → plot_planning
    4. 处理所有 name→ID 引用：parent_map_name/child_map_name/map_name/
       location_map_name/participant_name/carrier_name/char_name/item_name 等
    5. 最后写入 world_meta，并根据 protagonist_name_default 设置主角
    """
    drama_path = DRAMA_DIR / name
    if not drama_path.is_dir():
        raise FileNotFoundError(f"剧本 {name} 不存在")

    # --- 0. 严格校验（errors 阻断 / warnings 只记录在返回值 stats.validation 中）---
    vr = validate_drama(name)
    if not vr["ok"]:
        raise ValueError(
            "剧本校验失败（严重错误）：\n" + "\n".join(f"- {e}" for e in vr["errors"])
        )

    meta = _load_json(drama_path / "meta.txt")
    characters_rows = _load_jsonl(drama_path / "characters.txt")
    groups_rows = _load_jsonl(drama_path / "groups.txt")
    hierarchies_rows = _load_jsonl(drama_path / "group_hierarchies.txt")
    items_rows = _load_jsonl(drama_path / "items.txt")
    maps_rows = _load_jsonl(drama_path / "maps.txt")
    map_features_rows = _load_jsonl(drama_path / "map_features.txt")
    events_rows = _load_jsonl(drama_path / "events.txt")
    settings_rows = _load_jsonl(drama_path / "settings.txt")
    plot_rows = _load_jsonl(drama_path / "plot_planning.txt")

    # ---------- 1. 创建 / 切换存档 ----------
    sm = SaveManager()
    all_saves = sm.list_saves()
    if save_name in all_saves:
        if overwrite:
            sm.delete_save(save_name)
        else:
            raise FileExistsError(f"存档 {save_name} 已存在")
    sm.create_save(save_name)
    sm.switch_save(save_name)

    # 统计用
    stats: Dict[str, int] = {}

    # ---------- 2. maps ----------
    # 第一轮先 create 所有 map，建立 name→id 映射
    map_name_to_id: Dict[str, int] = {}
    for row in maps_rows:
        r = dict(row)
        # parent_map_name → parent_map_id
        if "parent_map_name" in r and r["parent_map_name"]:
            # 先占位，第二轮 resolve（因为 parent 可能在后面出现）
            pass
        # carrier_char_name → carrier_char_id（等 characters create 后再写）
        # carrier_item_name → carrier_item_id
        # current_map_name → current_map_id（等当前 maps 全部建完再写）
        create_fields = {
            "name": r["name"],
            "desc_raw": r.get("desc_raw") or "",
            "desc_polished": r.get("desc_polished"),
            "map_type": r.get("map_type", "region"),
            "coord_system": r.get("coord_system", "cartesian_2d"),
            "scale_unit": r.get("scale_unit", "m"),
            "scale_per_unit": r.get("scale_per_unit", 1.0),
            "bbox_x": r.get("bbox_x", 0),
            "bbox_y": r.get("bbox_y", 0),
            "bbox_w": r.get("bbox_w", 1000),
            "bbox_h": r.get("bbox_h", 1000),
            "bbox_d": r.get("bbox_d"),
            "default_zoom": r.get("default_zoom", 1.0),
            "default_center_x": r.get("default_center_x"),
            "default_center_y": r.get("default_center_y"),
            "is_mobile": r.get("is_mobile", 0),
            "importance": _importance_clamp(r.get("importance", 3)),
            "custom_attrs": r.get("custom_attrs", {}),
        }
        created = models.Map.create(**create_fields)
        map_name_to_id[r["name"]] = created.id
        # 临时存原始 row 用于后续 resolve
        r["$id"] = created.id
    stats["maps"] = len(maps_rows)

    # maps 第二轮：resolve parent_map_id / current_map_id
    char_name_to_id: Dict[str, int] = {}  # 先占位，等下面 create characters
    item_name_to_id: Dict[str, int] = {}

    for row in maps_rows:
        if "$id" not in row:
            continue
        updates: Dict[str, Any] = {}
        if row.get("parent_map_name") and row["parent_map_name"] in map_name_to_id:
            updates["parent_map_id"] = map_name_to_id[row["parent_map_name"]]
        if row.get("current_map_name") and row["current_map_name"] in map_name_to_id:
            updates["current_map_id"] = map_name_to_id[row["current_map_name"]]
        if row.get("current_x") is not None:
            updates["current_x"] = row["current_x"]
        if row.get("current_y") is not None:
            updates["current_y"] = row["current_y"]
        if row.get("current_z") is not None:
            updates["current_z"] = row["current_z"]
        if updates:
            models.Map.update(row["$id"], **updates)

    # ---------- 3. characters ----------
    for row in characters_rows:
        created = models.Character.create(
            name=row["name"],
            appearance_raw=row.get("appearance_raw") or "",
            appearance_polished=row.get("appearance_polished"),
            personality_raw=row.get("personality_raw") or "",
            personality_polished=row.get("personality_polished"),
            gender=row.get("gender"),
            age=row.get("age"),
            status=row.get("status", ""),
            importance=_importance_clamp(row.get("importance", 3)),
            custom_attrs=row.get("custom_attrs", {}),
            created_at_tick=row.get("created_at_tick", 0),
            dead_at_tick=row.get("dead_at_tick"),
        )
        char_name_to_id[row["name"]] = created.id
    stats["characters"] = len(characters_rows)

    # ---------- 4. groups ----------
    group_name_to_id: Dict[str, int] = {}
    for row in groups_rows:
        r = dict(row)
        leader_id = None
        leader_name = r.get("leader_name") or r.get("leader_id_alias")
        if leader_name and leader_name in char_name_to_id:
            leader_id = char_name_to_id[leader_name]
        primary_map_id = None
        if r.get("primary_map_name") and r["primary_map_name"] in map_name_to_id:
            primary_map_id = map_name_to_id[r["primary_map_name"]]
        created = models.Group.create(
            name=r["name"],
            desc_raw=r.get("desc_raw") or "",
            desc_polished=r.get("desc_polished"),
            group_type=r.get("group_type", "generic"),
            leader_id=leader_id,
            importance=_importance_clamp(r.get("importance", 3)),
            primary_map_id=primary_map_id,
            center_x=r.get("center_x"),
            center_y=r.get("center_y"),
            spread_radius=r.get("spread_radius", 50),
            distribution_raw=r.get("distribution_raw"),
            heatmap_grid=r.get("heatmap_grid"),
            heatmap_resolution=r.get("heatmap_resolution", 16),
            heatmap_updated_tick=r.get("heatmap_updated_tick"),
            custom_attrs=r.get("custom_attrs", {}),
        )
        group_name_to_id[r["name"]] = created.id
    stats["groups"] = len(groups_rows)

    # ---------- 5. group_hierarchies ----------
    for row in hierarchies_rows:
        child_name = row.get("child_group") or row.get("child_group_name")
        parent_name = row.get("parent_group") or row.get("parent_group_name")
        if child_name not in group_name_to_id or parent_name not in group_name_to_id:
            continue
        models.GroupHierarchy.create(
            child_group_id=group_name_to_id[child_name],
            parent_group_id=group_name_to_id[parent_name],
            relation_raw=row.get("relation_raw", "subset"),
            weight=row.get("weight", 1.0),
        )
    stats["group_hierarchies"] = len(hierarchies_rows)

    # ---------- 6. character_group_relations（从 groups/characters 的成员字段或默认全员加入主群体） ----------
    cgr_count = 0
    # 支持：characters 行里 groups_member 列表 [{group_name, role}]
    # 或：groups 行里 members 列表 [{char_name, role}]
    for row in characters_rows:
        cname = row["name"]
        if cname not in char_name_to_id:
            continue
        cid = char_name_to_id[cname]
        for mem in row.get("groups_member") or []:
            gname = mem.get("group_name")
            if gname in group_name_to_id:
                models.CharacterGroupRelation.create(
                    char_id=cid,
                    group_id=group_name_to_id[gname],
                    role_raw=mem.get("role_raw", "member"),
                    join_tick=mem.get("join_tick", 0),
                    importance_in_group=mem.get("importance_in_group", 3),
                )
                cgr_count += 1
    for row in groups_rows:
        gname = row["name"]
        if gname not in group_name_to_id:
            continue
        gid = group_name_to_id[gname]
        for mem in row.get("members") or []:
            cname = mem.get("char_name")
            if cname in char_name_to_id:
                models.CharacterGroupRelation.create(
                    char_id=char_name_to_id[cname],
                    group_id=gid,
                    role_raw=mem.get("role_raw", "member"),
                    join_tick=mem.get("join_tick", 0),
                    importance_in_group=mem.get("importance_in_group", 3),
                )
                cgr_count += 1
    stats["character_group_relations"] = cgr_count

    # ---------- 7. items ----------
    for row in items_rows:
        created = models.Item.create(
            name=row["name"],
            desc_raw=row.get("desc_raw") or "",
            desc_polished=row.get("desc_polished"),
            item_type=row.get("item_type", "generic"),
            rarity=row.get("rarity", 1),
            importance=_importance_clamp(row.get("importance", 2)),
            is_stackable=row.get("is_stackable", 0),
            stack_size=row.get("stack_size", 1),
            custom_attrs=row.get("custom_attrs", {}),
            created_at_tick=row.get("created_at_tick", 0),
        )
        item_name_to_id[row["name"]] = created.id
    stats["items"] = len(items_rows)

    # ---------- 8. item_holds（items 行的 holder_name / characters 行 items_in_inventory） ----------
    item_holds_count = 0
    for row in items_rows:
        iname = row["name"]
        if iname not in item_name_to_id:
            continue
        iid = item_name_to_id[iname]
        holder = row.get("holder_name") or row.get("owner_name")
        if holder and holder in char_name_to_id:
            models.ItemHold.create(
                item_id=iid,
                quantity=row.get("quantity", 1),
                holder_type="character",
                holder_id=char_name_to_id[holder],
                acquired_tick=row.get("acquired_tick", 0),
                use_times=row.get("use_times", 0),
            )
            item_holds_count += 1
    stats["item_holds"] = item_holds_count

    # ---------- 9. maps 第三轮补 carrier_* 依赖 ----------
    for row in maps_rows:
        if "$id" not in row:
            continue
        updates: Dict[str, Any] = {}
        cn = row.get("carrier_char_name")
        if cn and cn in char_name_to_id:
            updates["carrier_char_id"] = char_name_to_id[cn]
        in_ = row.get("carrier_item_name")
        if in_ and in_ in item_name_to_id:
            updates["carrier_item_id"] = item_name_to_id[in_]
        if updates:
            models.Map.update(row["$id"], **updates)

    # ---------- 10. map_features ----------
    for row in map_features_rows:
        r = dict(row)
        map_id = None
        mn = r.get("map_name")
        if mn and mn in map_name_to_id:
            map_id = map_name_to_id[mn]
        child_map_id = None
        cmn = r.get("child_map_name")
        if cmn and cmn in map_name_to_id:
            child_map_id = map_name_to_id[cmn]
        carrier_id = None
        carrier_type = r.get("carrier_type")
        if carrier_type == "character":
            cn2 = r.get("carrier_char_name") or r.get("carrier_name")
            if cn2 and cn2 in char_name_to_id:
                carrier_id = char_name_to_id[cn2]
        elif carrier_type == "item":
            in2 = r.get("carrier_item_name") or r.get("carrier_name")
            if in2 and in2 in item_name_to_id:
                carrier_id = item_name_to_id[in2]
        models.MapFeature.create(
            map_id=map_id,
            name=r.get("name") or r.get("feature_name") or "",
            feature_type=r.get("feature_type", "generic"),
            shape=r.get("shape", "point"),
            geometry=r.get("geometry", {}),
            layer_z=r.get("layer_z", 0),
            color_hint=r.get("color_hint"),
            visual_raw=r.get("visual_raw"),
            child_map_id=child_map_id,
            is_obstacle=r.get("is_obstacle", 0),
            is_mobile=r.get("is_mobile", 0),
            carrier_type=carrier_type,
            carrier_id=carrier_id,
            size_value=r.get("size_value"),
            size_unit_override=r.get("size_unit_override"),
        )
    stats["map_features"] = len(map_features_rows)

    # ---------- 11. character_locations（characters 行 location_map_name/x/y/z / feature_name） ----------
    cl_count = 0
    for row in characters_rows:
        cname = row["name"]
        if cname not in char_name_to_id:
            continue
        cid = char_name_to_id[cname]
        map_n = row.get("location_map_name")
        if map_n and map_n in map_name_to_id:
            mid = map_name_to_id[map_n]
            # feature_name → feature_id（若提供）
            feat_id = None
            fn = row.get("feature_name") or row.get("location_feature_name")
            if fn:
                # 简单查该 map 下第一个同名 feature
                for mf in map_features_rows:
                    if (
                        mf.get("map_name") == map_n
                        and (mf.get("name") == fn or mf.get("feature_name") == fn)
                    ):
                        features = models.MapFeature.list(
                            where="map_id = ? AND name = ?",
                            params=[mid, fn], limit=1,
                        )
                        if features:
                            feat_id = features[0].id
                        break
            models.CharacterLocation.create(
                char_id=cid,
                map_id=mid,
                feature_id=feat_id,
                x=row.get("x"),
                y=row.get("y"),
                z=row.get("z"),
                location_detail_raw=row.get("location_detail_raw"),
                last_update_tick=row.get("last_update_tick", 0),
            )
            cl_count += 1
    stats["character_locations"] = cl_count

    # ---------- 12. settings ----------
    for row in settings_rows:
        models.Setting.create(
            category=row.get("category", "world"),
            title=row["title"],
            desc_raw=row.get("desc_raw") or "",
            desc_polished=row.get("desc_polished"),
            setting_type=row.get("setting_type", "essential"),
            importance=_importance_clamp(row.get("importance", 3)),
            custom_attrs=row.get("custom_attrs", {}),
        )
    stats["settings"] = len(settings_rows)

    # ---------- 13. events + event_participants ----------
    for row in events_rows:
        r = dict(row)
        mid = None
        mname = r.get("location_map_name")
        if mname and mname in map_name_to_id:
            mid = map_name_to_id[mname]
        e = models.Event.create(
            tick_num=r.get("tick_num", 0),
            game_time=r.get("game_time") or meta.get("start_game_time") or "",
            event_type=r.get("event_type", "narrative"),
            content_raw=r.get("content_raw") or "",
            content_polished=r.get("content_polished"),
            location_map_id=mid,
            location_detail_raw=r.get("location_detail_raw"),
            importance=_importance_clamp(r.get("importance", 3)),
            custom_attrs=r.get("custom_attrs", {}),
        )
        # participants
        for p in r.get("participants") or []:
            ptype = p.get("participant_type", "character")
            pname = p.get("participant_name") or p.get("name")
            pid = None
            if ptype == "character" and pname and pname in char_name_to_id:
                pid = char_name_to_id[pname]
            elif ptype == "group" and pname and pname in group_name_to_id:
                pid = group_name_to_id[pname]
            elif ptype == "item" and pname and pname in item_name_to_id:
                pid = item_name_to_id[pname]
            if pid is not None:
                models.EventParticipant.create(
                    event_id=e.id,
                    participant_type=ptype,
                    participant_id=pid,
                    role_raw=p.get("role_raw", "witness"),
                    perception_raw=p.get("perception_raw"),
                )
    stats["events"] = len(events_rows)

    # ---------- 14. world_meta + 继承剧本玩法配置 ----------
    protagonist_name_default = meta.get("protagonist_name_default")
    protag_id = None
    if protagonist_name_default and protagonist_name_default in char_name_to_id:
        protag_id = char_name_to_id[protagonist_name_default]
    start_tick = 0
    # 如果 events 有负 tick，设置 meta 为 events 中最大 tick 或 0
    if events_rows:
        max_tick = max(int(r.get("tick_num", 0)) for r in events_rows)
        start_tick = max(start_tick, max_tick)

    # 继承剧本级玩法配置到存档
    try:
        drama_gopts = get_drama_gameplay_options(name)
        import json
        sm.update_meta(
            tick_num=start_tick,
            game_time=meta.get("start_game_time") or "",
            era_name=meta.get("era_name"),
            script_name=name,
            protagonist_id=protag_id,
            real_time=_now_real_time(),
            description=meta.get("description") or meta.get("summary_raw"),
            world_background_raw=meta.get("world_background_raw"),
            world_background_polished=meta.get("world_background_polished"),
            civilization_summary=meta.get("civilization_summary"),
            stable_context_version=meta.get("stable_context_version", 1),
            gameplay_options=json.dumps(drama_gopts, ensure_ascii=False),
        )
    except Exception:
        sm.update_meta(
            tick_num=start_tick,
            game_time=meta.get("start_game_time") or "",
            era_name=meta.get("era_name"),
            script_name=name,
            protagonist_id=protag_id,
            real_time=_now_real_time(),
            description=meta.get("description") or meta.get("summary_raw"),
            world_background_raw=meta.get("world_background_raw"),
            world_background_polished=meta.get("world_background_polished"),
            civilization_summary=meta.get("civilization_summary"),
            stable_context_version=meta.get("stable_context_version", 1),
        )
    stats["protagonist"] = protagonist_name_default if protag_id else None
    stats["start_tick"] = start_tick

    # ---------- 15. plot_planning（写入 CharacterQuest 表作主线记录，便于后续管线读取） ----------
    plot_count = 0
    if protagonist_name_default and protagonist_name_default in char_name_to_id:
        pid = char_name_to_id[protagonist_name_default]
        for row in plot_rows:
            models.CharacterQuest.create(
                char_id=pid,
                title=row.get("title") or f"主线节点 tick_{row.get('tick_num',0)}",
                desc_raw=row.get("plot_raw") or row.get("plot") or "",
                desc_polished=row.get("plot_polished"),
                quest_type="main_plot",
                status="in_progress",
                priority=_importance_clamp(row.get("importance", 4)),
                start_tick=row.get("tick_num", 0),
                success_condition_raw=row.get("success_condition_raw"),
                custom_attrs={
                    "estimated_time_raw": row.get("estimated_time_raw"),
                    "is_completed": row.get("is_completed", 0),
                },
            )
            plot_count += 1
    stats["plot_planning"] = plot_count

    # 记录校验 warnings 供前端提示用户
    stats["validation"] = {
        "warning_count": len(vr["warnings"]),
        "warnings": vr["warnings"][:50],  # 最多返回前 50 条
    }

    # 返回前释放活动连接，避免 Windows 上其他 SaveManager 无法删除该 db 文件
    sm.close_active()

    return {
        "ok": True,
        "drama": name,
        "save": save_name,
        "meta": meta,
        "stats": stats,
    }
