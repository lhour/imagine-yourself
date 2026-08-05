#!/usr/bin/env python3
"""
环境一键检查脚本 · imagine youself
=========================================================
检查所有前置依赖是否就绪，输出清晰的结果和修复建议。

用法:
    python scripts/check_env.py

退出码:
    0 = 全部就绪
    1 = 有缺失项
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

# 项目根目录（本文件位于 scripts/check_env.py，上溯 1 层）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "src" / "backend"
FRONTEND_DIR = PROJECT_ROOT / "src" / "frontend"

# 颜色（Windows 10+ 支持 ANSI）
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RESET = "\033[0m"
BOLD = "\033[1m"

# 启用 Windows ANSI 颜色支持
if sys.platform == "win32":
    os.system("")


def ok(msg: str, detail: str = ""):
    print(f"  {GREEN}✅ {msg}{RESET}" + (f"  {CYAN}({detail}){RESET}" if detail else ""))


def fail(msg: str, hint: str = ""):
    print(f"  {RED}❌ {msg}{RESET}")
    if hint:
        for line in hint.split("\n"):
            print(f"     {YELLOW}💡 {line}{RESET}")


def warn(msg: str, detail: str = ""):
    print(f"  {YELLOW}⚠️  {msg}{RESET}" + (f"  {CYAN}({detail}){RESET}" if detail else ""))


def section(title: str):
    print(f"\n{BOLD}── {title} ──{RESET}")


def run_cmd(cmd: list, timeout: int = 10) -> tuple:
    """运行命令，返回 (returncode, stdout, stderr)。失败返回 (1, '', 'error')"""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 1, "", ""


def parse_version(version_str: str) -> tuple:
    """从 'v22.23.2' 或 'Python 3.12.3' 中提取版本元组 (major, minor, patch)"""
    import re
    nums = re.findall(r"\d+", version_str)
    return tuple(int(n) for n in nums[:3]) if len(nums) >= 2 else (0, 0, 0)


# ============================================================
# 检查项
# ============================================================

results = []  # (passed, name)


def check_python():
    section("Python 运行时")
    code, out, err = run_cmd([sys.executable, "--version"])
    version = out or err
    if code == 0 and version:
        ver = parse_version(version)
        if ver >= (3, 10):
            ok(f"Python {version}")
            results.append((True, "python"))
        else:
            fail(f"Python 版本过低: {version}", "需要 3.10+，请从 https://python.org 下载新版本")
            results.append((False, "python"))
    else:
        fail("Python 未安装", "请从 https://python.org 下载安装，安装时勾选 Add to PATH")
        results.append((False, "python"))


def check_git():
    section("Git 版本控制")
    git_path = shutil.which("git")
    if git_path:
        code, out, _ = run_cmd(["git", "--version"])
        ok(out or "git 已安装", f"路径: {git_path}")
        results.append((True, "git"))
    else:
        fail("Git 未安装", "请从 https://git-scm.com/download/win 下载安装")
        results.append((False, "git"))


def check_node():
    section("Node.js 运行时")

    # 方式 1：直接在 PATH 中找 node
    node_path = shutil.which("node")
    npm_path = shutil.which("npm")

    # 方式 2：如果 PATH 没有，检查 fnm 安装的 Node
    if not node_path:
        fnm_dir = Path.home() / ".fnm"
        if fnm_dir.is_dir():
            node_versions = fnm_dir / "node-versions"
            if node_versions.is_dir():
                versions = sorted([d.name for d in node_versions.iterdir() if d.name.startswith("v")])
                for v in versions:
                    install_dir = node_versions / v / "installation"
                    node_exe = install_dir / "node.exe"
                    if node_exe.is_file():
                        node_path = str(node_exe)
                        npm_path = str(install_dir / "npm.cmd")
                        break

    if node_path:
        code, out, _ = run_cmd([node_path, "--version"])
        version = out
        ver = parse_version(version)
        if ver >= (20, 0):
            ok(f"Node.js {version}", f"路径: {node_path}")
            results.append((True, "node"))
        else:
            fail(f"Node.js 版本过低: {version}", "需要 20+，建议用 fnm install 22")
            results.append((False, "node"))
    else:
        fail("Node.js 未安装", "请参考 docs/setup.md 第四章安装 Node.js 22 LTS")
        results.append((False, "node"))

    # npm
    if npm_path:
        code, out, _ = run_cmd([npm_path, "--version"], timeout=15)
        if code == 0 and out:
            ok(f"npm {out}")
            results.append((True, "npm"))
        else:
            warn("npm 命令执行失败")
            results.append((False, "npm"))
    else:
        fail("npm 未找到", "npm 随 Node.js 一起安装，请检查 Node 安装是否完整")
        results.append((False, "npm"))


def check_backend_deps():
    section("后端 Python 依赖")
    deps = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn[standard]"),
        ("openai", "openai"),
        ("dotenv", "python-dotenv"),
        ("yaml", "pyyaml"),
        ("httpx", "httpx"),
    ]
    all_ok = True
    for module, package in deps:
        code, _, _ = run_cmd([sys.executable, "-c", f"import {module}"])
        if code == 0:
            ok(package)
        else:
            fail(package, f"pip install {package}")
            all_ok = False
    results.append((all_ok, "backend_deps"))


def check_frontend_deps():
    section("前端依赖")
    node_modules = FRONTEND_DIR / "node_modules"
    if node_modules.is_dir() and (node_modules / "vite").is_dir():
        ok("node_modules 已安装", f"{FRONTEND_DIR}\\node_modules")
        results.append((True, "frontend_deps"))
    else:
        fail("前端依赖未安装", "cd src\\frontend && npm install")
        results.append((False, "frontend_deps"))


def check_env_file():
    section("环境变量配置")
    env_file = BACKEND_DIR / ".env"
    if not env_file.is_file():
        fail("src/backend/.env 不存在", "copy src\\backend\\.env.example src\\backend\\.env 并填入 DEEPSEEK_API_KEY")
        results.append((False, "env_file"))
        return

    content = env_file.read_text(encoding="utf-8")
    has_key = False
    key_is_placeholder = True
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("DEEPSEEK_API_KEY="):
            key = line.split("=", 1)[1].strip()
            if key and key != "your_api_key_here" and key.startswith("sk-"):
                has_key = True
                key_is_placeholder = False
            elif key:
                has_key = True
                key_is_placeholder = True
            break

    if has_key and not key_is_placeholder:
        ok("DEEPSEEK_API_KEY 已配置")
        results.append((True, "env_file"))
    elif has_key and key_is_placeholder:
        warn("DEEPSEEK_API_KEY 还是占位符", "请编辑 src/backend/.env 填入真实 API Key")
        results.append((False, "env_file"))
    else:
        fail("DEEPSEEK_API_KEY 未配置", "请编辑 src/backend/.env 填入 sk-xxx")
        results.append((False, "env_file"))


def check_drama():
    section("剧本文件")
    drama_dir = BACKEND_DIR / "drama"
    if not drama_dir.is_dir():
        fail("src/backend/drama/ 目录不存在")
        results.append((False, "drama"))
        return

    dramas = [d for d in drama_dir.iterdir() if d.is_dir()]
    if not dramas:
        warn("src/backend/drama/ 下没有剧本", "至少需要一个剧本目录才能初始化存档")
        results.append((False, "drama"))
        return

    # v3 剧本格式：9+1 文件（meta.txt 是 JSON，其余 9 个是 JSONL）
    required = [
        "meta.txt", "characters.txt", "groups.txt", "group_hierarchies.txt",
        "items.txt", "maps.txt", "map_features.txt", "events.txt",
        "settings.txt", "plot_planning.txt",
    ]
    for drama in dramas:
        missing = [f for f in required if not (drama / f).is_file()]
        if missing:
            fail(f"{drama.name} 缺少文件", f"缺少: {', '.join(missing)}")
            results.append((False, "drama"))
        else:
            ok(f"剧本 {drama.name} 完整（9+1 文件齐全）")
            results.append((True, "drama"))


def print_summary():
    section("检查结果汇总")
    passed = sum(1 for p, _ in results if p)
    total = len(results)
    failed = [name for p, name in results if not p]

    print()
    if not failed:
        print(f"  {GREEN}{BOLD}🎉 全部就绪！({passed}/{total}){RESET}")
        print(f"  {GREEN}可以启动项目了：{RESET}")
        print(f"  {CYAN}uvicorn src.backend.http.app:app --port 8000 --reload{RESET}")
        print()
        sys.exit(0)
    else:
        print(f"  {RED}{BOLD}有 {len(failed)} 项未就绪：{RESET}")
        for name in failed:
            print(f"  {RED}  - {name}{RESET}")
        print()
        print(f"  {YELLOW}请参考 docs/setup.md 修复以上问题{RESET}")
        sys.exit(1)


# ============================================================
# 主流程
# ============================================================

def main():
    print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{CYAN}║  imagine youself · 环境一键检查                  ║{RESET}")
    print(f"{BOLD}{CYAN}║  imagine youself · 环境检查                      ║{RESET}")
    print(f"{BOLD}{CYAN}╚══════════════════════════════════════════════════╝{RESET}")
    print(f"  项目路径: {PROJECT_ROOT}")

    check_python()
    check_git()
    check_node()
    check_backend_deps()
    check_frontend_deps()
    check_env_file()
    check_drama()

    print_summary()


if __name__ == "__main__":
    main()
