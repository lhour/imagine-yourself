"""src.backend — v3 imagine-youself 后端聚合模块。

模块布局：
- env.py            环境变量加载
- storage/          多存档分库 SQLite + Active Record 模型
- service/          业务服务层（剧本/世界/记忆/地图）
- http/             FastAPI 应用与路由
- agent/            LLM 管线（阶段二/三实现）
- conf/             Prompt/Skill/Tool 配置（阶段二/三实现）
- drama/            剧本源文件目录（阶段四实现）
"""

__version__ = "3.0.0"
