"""src.backend.agent.tool.web_fetch — 网络资源抓取工具。

仅在用户明确提供 URL 时使用，从网页抓取相关内容供模型参考。
包含 URL 安全检查（只允许 http/https 协议，禁止内网地址）。
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

from src.backend.agent.tool.base import tool, ToolSpec

WEB_FETCH_TOOL_NAMES: List[str] = []

# 安全限制
MAX_URL_LENGTH = 500
MAX_CONTENT_LENGTH = 10000  # 最大抓取内容长度（字符）
REQUEST_TIMEOUT = 10  # 请求超时（秒）

# 禁止的域名/IP 模式
FORBIDDEN_PATTERNS = [
    # 内网地址
    re.compile(r'^https?://(localhost|127\.0\.0\.1|0\.0\.0\.0)'),
    re.compile(r'^https?://10\.\d+\.\d+\.\d+'),
    re.compile(r'^https?://172\.(1[6-9]|2[0-9]|3[0-1])\.\d+\.\d+'),
    re.compile(r'^https?://192\.168\.\d+\.\d+'),
    # 禁止 file:// 协议
    re.compile(r'^file://'),
    # 禁止其他危险协议
    re.compile(r'^(ftp|gopher|telnet|dict)://'),
]


def _is_url_safe(url: str) -> tuple[bool, str]:
    """检查 URL 是否安全。"""
    if not url or len(url) > MAX_URL_LENGTH:
        return False, "URL 长度超限或为空"

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False, f"不支持的协议: {parsed.scheme}"

    for pattern in FORBIDDEN_PATTERNS:
        if pattern.match(url):
            return False, "禁止访问内网或使用危险协议"

    # 禁止本地文件
    if parsed.path.endswith((".py", ".js", ".ts", ".exe", ".sh", ".bat", ".cmd", ".ps1")):
        return False, "禁止执行脚本文件"

    return True, ""


def _extract_text(html_content: str) -> str:
    """从 HTML 中提取纯文本。"""
    import re
    # 移除 script 和 style 标签
    text = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # 移除 HTML 标签
    text = re.sub(r'<[^>]+>', ' ', text)
    # 清理多余空白
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


@tool(
    name="web_fetch",
    desc="从指定 URL 抓取网页内容，提取文本供参考。仅在用户明确提供链接时使用。",
)
def web_fetch(url: str, max_length: int = 5000) -> str:
    """从指定 URL 抓取网页内容，提取文本供参考。

    仅在用户明确提供链接时使用。抓取成功后返回网页的纯文本内容。
    安全限制：不允许访问内网地址或使用危险协议。

    Args:
        url: 目标网页的 URL（必须是 http/https 协议）
        max_length: 返回内容的最大长度（字符），默认 5000

    Returns:
        JSON string with {success: bool, url: str, title: str, content: str, truncated: bool}
    """
    # 1) 安全检查
    safe, reason = _is_url_safe(url)
    if not safe:
        return json.dumps({
            "success": False,
            "url": url,
            "error": f"URL 安全检查失败: {reason}",
        }, ensure_ascii=False)

    try:
        # 2) 发起请求
        headers = {
            "User-Agent": "AetherStoryEngine/1.0 (Web Fetch Tool)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        response.raise_for_status()

        # 3) 获取内容
        content_type = response.headers.get("Content-Type", "")
        raw_content = response.text

        # 如果是 HTML，提取文本
        if "html" in content_type or urlparse(url).path.endswith((".html", ".htm")):
            text_content = _extract_text(raw_content)
        else:
            text_content = raw_content

        # 4) 截断
        truncated = False
        actual_max = min(max_length, MAX_CONTENT_LENGTH)
        if len(text_content) > actual_max:
            text_content = text_content[:actual_max] + "\n...[内容已截断]"
            truncated = True

        # 5) 尝试获取标题
        title = ""
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', raw_content, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).strip()

        return json.dumps({
            "success": True,
            "url": url,
            "title": title,
            "content": text_content,
            "content_length": len(text_content),
            "truncated": truncated,
            "content_type": content_type,
        }, ensure_ascii=False)

    except requests.Timeout:
        return json.dumps({
            "success": False,
            "url": url,
            "error": f"请求超时（{REQUEST_TIMEOUT} 秒）",
        }, ensure_ascii=False)
    except requests.ConnectionError:
        return json.dumps({
            "success": False,
            "url": url,
            "error": "无法连接到目标服务器",
        }, ensure_ascii=False)
    except requests.HTTPError as e:
        return json.dumps({
            "success": False,
            "url": url,
            "error": f"HTTP 错误: {e.response.status_code}",
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "success": False,
            "url": url,
            "error": f"抓取失败: {str(e)}",
        }, ensure_ascii=False)


WEB_FETCH_TOOL_NAMES.append("web_fetch")


@tool(
    name="web_fetch_batch",
    desc="批量抓取多个 URL 的内容（以换行或逗号分隔）。当用户提供多个链接时使用。",
)
def web_fetch_batch(urls: str, max_length_per_url: int = 2000) -> str:
    """批量抓取多个 URL 的内容（以换行或逗号分隔）。

    当用户提供多个链接时使用。

    Args:
        urls: URL 列表（换行或逗号分隔）
        max_length_per_url: 每个 URL 的最大内容长度

    Returns:
        JSON string with {results: [...]}
    """
    # 解析 URL 列表
    url_list = [u.strip() for u in re.split(r'[\n,，]', urls) if u.strip()]
    if not url_list:
        return json.dumps({"success": False, "error": "未提供有效的 URL 列表"}, ensure_ascii=False)

    if len(url_list) > 5:
        url_list = url_list[:5]  # 最多 5 个
        truncated = True
    else:
        truncated = False

    results = []
    for url in url_list:
        result = web_fetch(url, max_length_per_url)
        try:
            result_json = json.loads(result)
            results.append(result_json)
        except json.JSONDecodeError:
            results.append({"success": False, "url": url, "error": "结果解析失败"})

    return json.dumps({
        "results": results,
        "total": len(results),
        "truncated": truncated,
    }, ensure_ascii=False)


WEB_FETCH_TOOL_NAMES.append("web_fetch_batch")


__all__ = [
    "WEB_FETCH_TOOL_NAMES",
    "web_fetch",
    "web_fetch_batch",
]
