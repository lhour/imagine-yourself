"""src.backend.http.routers.saves — 存档管理路由。"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.backend.http.deps import get_save_manager, require_active_save
from src.backend.storage.connection import SaveManager

router = APIRouter(prefix="/api/saves", tags=["saves"])


class CreateSaveReq(BaseModel):
    name: str


class SwitchReq(BaseModel):
    pass


class UpdateMetaReq(BaseModel):
    tick_num: Optional[int] = None
    game_time: Optional[str] = None
    era_name: Optional[str] = None
    script_name: Optional[str] = None
    description: Optional[str] = None
    protagonist_id: Optional[int] = None
    custom_attrs: Optional[Dict[str, Any]] = None


@router.get("")
def list_saves(sm: SaveManager = Depends(get_save_manager)):
    return {"saves": sm.list_saves()}


@router.post("")
def create_save(req: CreateSaveReq, sm: SaveManager = Depends(get_save_manager)):
    try:
        name = sm.create_save(req.name)
    except (ValueError, FileExistsError) as e:
        raise HTTPException(400, str(e))
    return {"created": name, "active": name}


@router.delete("/{name}")
def delete_save(name: str, sm: SaveManager = Depends(get_save_manager)):
    try:
        sm.delete_save(name)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    return {"deleted": name}


@router.post("/{name}/switch")
def switch_save(name: str, sm: SaveManager = Depends(get_save_manager)):
    try:
        sm.switch_save(name)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    return {"active": name}


@router.get("/active")
def get_active(sm: SaveManager = Depends(get_save_manager)):
    return {"active_save": sm.active_save}


@router.get("/meta")
def get_meta(sm: SaveManager = Depends(require_active_save)):
    return sm.get_meta()


@router.patch("/meta")
def update_meta(req: UpdateMetaReq, sm: SaveManager = Depends(require_active_save)):
    fields = req.dict(exclude_none=True)
    if not fields:
        raise HTTPException(400, "无字段可更新")
    return sm.update_meta(**fields)


@router.get("/protagonist")
def get_protagonist(sm: SaveManager = Depends(require_active_save)):
    p = sm.get_protagonist()
    if not p:
        return {"protagonist": None}
    return {"protagonist": p}


@router.post("/protagonist")
def set_protagonist(char_id: int, sm: SaveManager = Depends(require_active_save)):
    return sm.set_protagonist(char_id)


@router.get("/snapshots")
def list_snapshots(sm: SaveManager = Depends(require_active_save)):
    snaps = sm.list_snapshots(sm.active_save)
    return {"snapshots": snaps, "save": sm.active_save}


@router.post("/snapshots")
def create_snapshot(sm: SaveManager = Depends(require_active_save)):
    try:
        fname = sm.create_snapshot()
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    return {"created": fname}


@router.post("/snapshots/restore")
def restore_snapshot(snapshot_file: str, sm: SaveManager = Depends(require_active_save)):
    try:
        name = sm.restore_snapshot(snapshot_file)
    except (FileNotFoundError, RuntimeError) as e:
        raise HTTPException(404, str(e))
    return {"restored": name, "snapshot": snapshot_file}


@router.delete("/snapshots/{snapshot_file}")
def delete_snapshot(snapshot_file: str, sm: SaveManager = Depends(require_active_save)):
    sm.delete_snapshot(snapshot_file)
    return {"deleted": snapshot_file}
