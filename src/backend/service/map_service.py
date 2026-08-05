"""src.backend.service.map_service — 地图与距离计算服务。

提供：
- 距离计算（同地图欧氏距离 + 跨层级递归换算）
- 路径链查找（两地图间的祖先链）
- 要素按层级查询
- 移动地图/要素的位置同步
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional, Tuple

from src.backend.storage import models
from src.backend.storage.connection import default_save_manager


# ============================================================
# 单位换算（用于跨层级/单位显示）
# ============================================================

# 各 scale_unit 转米的系数
UNIT_TO_METER: Dict[str, float] = {
    "m": 1.0,
    "km": 1000.0,
    "step": 0.7,        # 步 ≈ 0.7 米
    "AU": 1.496e11,     # 天文单位
    "ly": 9.461e15,     # 光年
    "custom": 1.0,
}


def to_meters(value: float, unit: str) -> float:
    return value * UNIT_TO_METER.get(unit, 1.0)


def format_distance(meters: float, prefer_unit: str = "auto") -> Tuple[float, str]:
    """把米转成人话。返回 (数值, 单位)。"""
    if prefer_unit != "auto":
        factor = UNIT_TO_METER.get(prefer_unit, 1.0)
        return meters / factor, prefer_unit

    if meters < 1.0:
        return meters * 100.0, "cm"
    if meters < 1000.0:
        return meters, "m"
    if meters < 100_000.0:        # 100 km 内
        return meters / 1000.0, "km"
    if meters < 1.496e11:         # 1 AU 内
        return meters / 1000.0, "km"
    if meters < 9.461e15:         # 1 光年内
        return meters / 1.496e11, "AU"
    return meters / 9.461e15, "ly"


def semantic_distance(meters: float) -> str:
    """生成人话距离（步行 X 分钟 / X 万 km / X AU / X 光年）。"""
    if meters < 1000:
        # 步行分钟（5km/h = 83m/min）
        minutes = max(1, int(meters / 83))
        return f"步行约 {minutes} 分钟"
    if meters < 100_000:
        return f"{meters/1000:.2f} km"
    if meters < 1.496e11:    # < 1 AU
        return f"{meters/1000/10000:.2f} 万 km"
    if meters < 9.461e15:
        return f"{meters/1.496e11:.4f} AU"
    return f"{meters/9.461e15:.4f} 光年"


# ============================================================
# 位置解析：把 character/item/feature/map 统一成 (map_id, x, y, z, unit)
# ============================================================

def resolve_position(ref: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """把任意对象引用解析为统一坐标系。

    ref = {type: 'character|item|feature|map', id: int}

    返回 {map_id, x, y, z, unit, scale_per_unit} 或 None。
    """
    t = ref.get("type")
    i = ref.get("id")
    if t is None or i is None:
        return None

    if t == "character":
        loc = models.CharacterLocation.list(where="char_id = ?", params=[i], limit=1)
        if not loc:
            return None
        loc = loc[0]
        # 优先用 feature_id（如果在要素里）
        if loc.feature_id:
            f = models.MapFeature.get(loc.feature_id)
            if f:
                m = models.Map.get(f.map_id)
                if m:
                    return {
                        "map_id": m.id,
                        "x": f.current_x if f.is_mobile else (f.geometry.get("cx") if f.shape == "circle" else (f.geometry.get("points", [[0,0]])[0][0])),
                        "y": f.current_y if f.is_mobile else (f.geometry.get("cy") if f.shape == "circle" else (f.geometry.get("points", [[0,0]])[0][1])),
                        "z": f.current_z or 0,
                        "unit": m.scale_unit,
                        "scale_per_unit": m.scale_per_unit,
                    }
        if loc.map_id:
            m = models.Map.get(loc.map_id)
            if m:
                return {
                    "map_id": m.id,
                    "x": loc.x or 0,
                    "y": loc.y or 0,
                    "z": loc.z or 0,
                    "unit": m.scale_unit,
                    "scale_per_unit": m.scale_per_unit,
                }
        return None

    if t == "feature":
        f = models.MapFeature.get(i)
        if not f:
            return None
        m = models.Map.get(f.map_id)
        if not m:
            return None
        # 提取要素的位置（不同 shape 不同）
        gx = gy = 0.0
        if f.shape == "circle" and isinstance(f.geometry, dict):
            gx = f.geometry.get("cx", 0)
            gy = f.geometry.get("cy", 0)
        elif f.shape == "point" and isinstance(f.geometry, dict):
            gx = f.geometry.get("x", 0)
            gy = f.geometry.get("y", 0)
        elif isinstance(f.geometry, dict) and f.geometry.get("points"):
            pts = f.geometry["points"]
            gx = sum(p[0] for p in pts) / len(pts)
            gy = sum(p[1] for p in pts) / len(pts)
        # 移动要素用 current_x/y 覆盖
        if f.is_mobile and f.current_x is not None:
            gx = f.current_x
            gy = f.current_y
        return {
            "map_id": m.id,
            "x": gx,
            "y": gy,
            "z": f.current_z or 0,
            "unit": m.scale_unit,
            "scale_per_unit": m.scale_per_unit,
        }

    if t == "map":
        m = models.Map.get(i)
        if not m:
            return None
        # 移动地图用 current_x/y
        if m.is_mobile and m.current_x is not None:
            parent = models.Map.get(m.current_map_id) if m.current_map_id else None
            if parent:
                return {
                    "map_id": parent.id,
                    "x": m.current_x,
                    "y": m.current_y,
                    "z": m.current_z or 0,
                    "unit": parent.scale_unit,
                    "scale_per_unit": parent.scale_per_unit,
                }
        # 静态地图：返回中心
        return {
            "map_id": m.id,
            "x": m.bbox_x + m.bbox_w / 2,
            "y": m.bbox_y + m.bbox_h / 2,
            "z": 0,
            "unit": m.scale_unit,
            "scale_per_unit": m.scale_per_unit,
        }

    if t == "item":
        # 物品通过 item_holds 找到持有者
        holds = models.ItemHold.list(where="item_id = ?", params=[i], limit=1)
        if not holds:
            return None
        h = holds[0]
        if h.holder_type == "character":
            return resolve_position({"type": "character", "id": h.holder_id})
        if h.holder_type == "group":
            return None  # 群体不直接有坐标
        if h.holder_type == "map":
            return resolve_position({"type": "map", "id": h.holder_id})
        return None

    return None


# ============================================================
# 距离计算
# ============================================================

def get_map_ancestors(map_id: int) -> List[int]:
    """返回从顶级到当前 map 的祖先链 [root_id, ..., map_id]。"""
    chain: List[int] = []
    cur = map_id
    seen = set()
    while cur is not None and cur not in seen:
        seen.add(cur)
        chain.append(cur)
        m = models.Map.get(cur)
        if not m or m.parent_map_id is None:
            break
        cur = m.parent_map_id
    chain.reverse()
    return chain


def find_common_ancestor(map_a: int, map_b: int) -> Tuple[Optional[int], List[int], List[int]]:
    """找两地图的共同祖先。

    返回 (ancestor_id, path_a_from_ancestor, path_b_from_ancestor)。
    若无共同祖先返回 (None, [], [])。
    """
    anc_a = get_map_ancestors(map_a)
    anc_b = get_map_ancestors(map_b)
    common = None
    for x in anc_a:
        if x in anc_b:
            common = x
            break
    if common is None:
        return None, [], []
    ia = anc_a.index(common)
    ib = anc_b.index(common)
    return common, anc_a[ia:], anc_b[ib:]


def distance(from_ref: Dict[str, Any], to_ref: Dict[str, Any],
             prefer_unit: str = "auto") -> Dict[str, Any]:
    """计算两对象距离。

    返回 {meters, display, semantic, path: [...], note}。
    """
    p_a = resolve_position(from_ref)
    p_b = resolve_position(to_ref)
    if not p_a or not p_b:
        return {"error": "无法解析位置", "from": from_ref, "to": to_ref}

    if p_a["map_id"] == p_b["map_id"]:
        # 同地图：直接欧氏距离
        dx = p_a["x"] - p_b["x"]
        dy = p_a["y"] - p_b["y"]
        dz = p_a["z"] - p_b["z"]
        eucl = math.sqrt(dx*dx + dy*dy + dz*dz)
        unit = p_a["unit"]
        meters = to_meters(eucl * p_a["scale_per_unit"], unit)
        val, u = format_distance(meters, prefer_unit)
        return {
            "meters": meters,
            "display": f"{val:.4g} {u}",
            "semantic": semantic_distance(meters),
            "path": [p_a["map_id"], p_b["map_id"]],
            "note": "同地图欧氏距离",
        }

    # 跨层级：找共同祖先
    anc, path_a, path_b = find_common_ancestor(p_a["map_id"], p_b["map_id"])
    if anc is None:
        # 完全不同地图树：返回语义距离
        return {
            "meters": None,
            "display": "无法计算（不在同一地图树）",
            "semantic": "位于不同世界/位面",
            "path": [p_a["map_id"], p_b["map_id"]],
            "note": "无共同祖先",
        }

    # 简化：把双方位置投影到共同祖先地图的坐标系（用各 map 的中心点近似）
    # 严格做法需要逐级累计父级 offset，这里用共同祖先的中心点近似
    m_anc = models.Map.get(anc)
    if not m_anc:
        return {"error": "共同祖先地图不存在"}

    # 在共同祖先地图上，把 a 和 b 都映射到（map_id_anc, 中心 x, 中心 y）
    # 这里近似：用子地图的 bbox 中心
    def project_to_ancestor(child_map_id: int, ancestor_id: int) -> Tuple[float, float, str, float]:
        """从 child_map_id 沿祖先链上溯到 ancestor_id，累加中心偏移。"""
        cur = models.Map.get(child_map_id)
        x = cur.bbox_x + cur.bbox_w / 2
        y = cur.bbox_y + cur.bbox_h / 2
        unit = cur.scale_unit
        spu = cur.scale_per_unit
        # 沿祖先链上溯
        while cur and cur.id != ancestor_id and cur.parent_map_id:
            parent = models.Map.get(cur.parent_map_id)
            if not parent:
                break
            # 父地图坐标系下，子地图的中心 ≈ bbox 中心
            x = cur.bbox_x + cur.bbox_w / 2
            y = cur.bbox_y + cur.bbox_h / 2
            unit = parent.scale_unit
            spu = parent.scale_per_unit
            cur = parent
        return x, y, unit, spu

    ax, ay, ua, sa = project_to_ancestor(p_a["map_id"], anc)
    bx, by, ub, sb = project_to_ancestor(p_b["map_id"], anc)

    # 用祖先地图的单位算欧氏距离
    dx = ax - bx
    dy = ay - by
    eucl = math.sqrt(dx*dx + dy*dy)
    meters = to_meters(eucl * sa, ua)
    val, u = format_distance(meters, prefer_unit)
    return {
        "meters": meters,
        "display": f"{val:.4g} {u}",
        "semantic": semantic_distance(meters),
        "path": path_a + list(reversed(path_b[1:])),
        "note": f"通过共同祖先地图 {m_anc.name} 近似计算",
    }


def distance_matrix(ids: List[int], id_type: str = "feature") -> Dict[str, Any]:
    """多对象两两距离。返回 {pairs: [{from, to, meters, display}, ...]}。"""
    refs = [{"type": id_type, "id": i} for i in ids]
    pairs = []
    for i in range(len(refs)):
        for j in range(i+1, len(refs)):
            d = distance(refs[i], refs[j])
            pairs.append({
                "from": ids[i],
                "to": ids[j],
                "meters": d.get("meters"),
                "display": d.get("display"),
                "semantic": d.get("semantic"),
            })
    return {"pairs": pairs}


# ============================================================
# 地图查询
# ============================================================

def list_features(map_id: int, layer_z_min: Optional[int] = None,
                  layer_z_max: Optional[int] = None) -> List[Dict[str, Any]]:
    """取地图的所有要素，可按层级过滤。"""
    where = "map_id = ?"
    params: List[Any] = [map_id]
    if layer_z_min is not None:
        where += " AND layer_z >= ?"
        params.append(layer_z_min)
    if layer_z_max is not None:
        where += " AND layer_z <= ?"
        params.append(layer_z_max)
    feats = models.MapFeature.list(where=where, params=params, order_by="layer_z ASC, id ASC", limit=10000)
    return [f.to_dict() for f in feats]


def list_children(map_id: int) -> List[Dict[str, Any]]:
    """子地图列表。"""
    children = models.Map.list(where="parent_map_id = ?", params=[map_id], limit=1000)
    return [m.to_dict() for m in children]


def list_heatmaps_on_map(map_id: int) -> List[Dict[str, Any]]:
    """该地图上所有群体的热力图数据。"""
    groups = models.Group.list(where="primary_map_id = ?", params=[map_id], limit=1000)
    return [{
        "group_id": g.id,
        "group_name": g.name,
        "heatmap_grid": g.heatmap_grid,
        "heatmap_resolution": g.heatmap_resolution,
        "center_x": g.center_x,
        "center_y": g.center_y,
        "spread_radius": g.spread_radius,
    } for g in groups if g.heatmap_grid]


def refresh_group_heatmap(group_id: int) -> Dict[str, Any]:
    """根据群体成员的 character_locations 重新栅格化热力图。

    简化实现：取所有 char 在群体中且活跃的角色位置，按 16x16 栅格统计密度。
    """
    sm = default_save_manager()
    if not sm._conn:
        raise RuntimeError("无激活存档")
    g = models.Group.get(group_id)
    if not g:
        raise ValueError(f"群体 {group_id} 不存在")
    if not g.primary_map_id:
        raise ValueError(f"群体 {g.name} 未绑定 primary_map_id")

    m = models.Map.get(g.primary_map_id)
    if not m:
        raise ValueError("primary_map_id 无效")

    # 取该群体的所有角色
    rels = models.CharacterGroupRelation.list(
        where="group_id = ? AND leave_tick IS NULL", params=[group_id], limit=10000
    )
    char_ids = [r.char_id for r in rels]

    # 取这些角色的位置（必须在 primary_map_id 上）
    resolution = g.heatmap_resolution or 16
    cells = [[0.0 for _ in range(resolution)] for _ in range(resolution)]
    total = 0
    for cid in char_ids:
        locs = models.CharacterLocation.list(where="char_id = ? AND map_id = ?",
                                              params=[cid, g.primary_map_id], limit=1)
        if not locs:
            continue
        loc = locs[0]
        if loc.x is None or loc.y is None:
            continue
        # 栅格化
        gx = int((loc.x - m.bbox_x) / m.bbox_w * resolution)
        gy = int((loc.y - m.bbox_y) / m.bbox_h * resolution)
        gx = max(0, min(resolution - 1, gx))
        gy = max(0, min(resolution - 1, gy))
        cells[gy][gx] += 1
        total += 1

    # 归一化到 0-1
    if total > 0:
        max_v = max(max(row) for row in cells)
        if max_v > 0:
            cells = [[v / max_v for v in row] for row in cells]

    grid = {
        "bbox": [m.bbox_x, m.bbox_y, m.bbox_w, m.bbox_h],
        "resolution": resolution,
        "cells": cells,
        "unit_hint": m.scale_unit,
    }

    meta = sm.get_meta()
    models.Group.update(group_id, heatmap_grid=grid, heatmap_updated_tick=meta.get("tick_num", 0))
    return {"group_id": group_id, "updated": True, "total_chars": total, "grid_size": resolution}
