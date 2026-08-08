"""src.backend.http.app — FastAPI 应用工厂。"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.backend.env import load_backend_env
from src.backend.http.routers import (
    agent, anchors, character_profiles, config, dramas, entities, groups, knowledge, maps, memory, propagation, saves, scheduled_events, traces, v5, world
)

load_backend_env()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Aether Story Engine",
        description="AI 驱动的叙事游戏引擎后端 — 数据库简化重构版",
        version="3.0.0",
    )

    # CORS（开发期全开）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 路由注册
    app.include_router(config.router)
    app.include_router(saves.router)
    app.include_router(entities.router)
    app.include_router(character_profiles.router)
    app.include_router(memory.router)
    app.include_router(maps.router)
    app.include_router(groups.router)
    app.include_router(world.router)
    app.include_router(anchors.router)
    app.include_router(scheduled_events.router)
    app.include_router(propagation.router)
    app.include_router(dramas.router)
    app.include_router(agent.router)
    app.include_router(traces.router)
    # v5 新功能路由
    app.include_router(v5.router)
    app.include_router(knowledge.router)

    @app.get("/api/health", tags=["system"])
    def health():
        return {"status": "ok", "version": "3.0.0"}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    import os
    uvicorn.run(
        "src.backend.http.app:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        reload=bool(int(os.environ.get("RELOAD", "1"))),
    )
