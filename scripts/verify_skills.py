"""验证 11 个 skill 加载。"""
import sys, os
sys.path.insert(0, os.path.abspath('.'))
from src.backend.agent.skill.loader import list_skills, get_skill

skills = list_skills()
print(f"Skills found: {len(skills)}")
for name in skills:
    fs = get_skill(name)
    if fs:
        v = fs.get_version()
        print(f"  {name:25s}  v={v.version}  tools={len(fs.tools)}  desc={fs.description[:50]}")
