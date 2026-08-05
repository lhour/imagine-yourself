"""后端环境变量统一加载。

加载优先级：
1. src/backend/.env（主路径）
2. 项目根 .env（兼容过渡期）
3. find_dotenv() 兜底
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    _HAS_DOTENV = True
except ImportError:
    _HAS_DOTENV = False

# 路径常量
BACKEND_DIR = Path(__file__).resolve().parent                  # src/backend
PROJECT_ROOT = BACKEND_DIR.parent.parent                         # d:/Desktop/projecct
BACKEND_ENV = BACKEND_DIR / ".env"
ROOT_ENV = PROJECT_ROOT / ".env"

_loaded = False


def load_backend_env() -> None:
    """加载 .env 到 os.environ。幂等：重复调用不会覆盖已存在的环境变量。"""
    global _loaded
    if _loaded:
        return

    if _HAS_DOTENV:
        # 优先级 1: src/backend/.env
        if BACKEND_ENV.is_file():
            load_dotenv(BACKEND_ENV, override=False)
        # 优先级 2: 项目根 .env
        elif ROOT_ENV.is_file():
            load_dotenv(ROOT_ENV, override=False)
        # 优先级 3: find_dotenv 兜底
        else:
            from dotenv import find_dotenv
            p = find_dotenv(usecwd=True)
            if p:
                load_dotenv(p, override=False)

    _loaded = True


# 默认值兜底（即使未加载 .env 也能跑）
os.environ.setdefault("HOST", "0.0.0.0")
os.environ.setdefault("PORT", "8000")
os.environ.setdefault("RELOAD", "1")
os.environ.setdefault("LOG_DIR", "logs")
os.environ.setdefault("SAVES_DIR", str(BACKEND_DIR / "saves"))
