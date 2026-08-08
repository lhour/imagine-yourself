"""src.backend.service.game_time_utils — 游戏时间工具层（10.0 公共前置基础设施）。

游戏时间格式（项目硬约束）：'{纪元}{年}年{月}月{日}日{时}时{分}分{秒}秒'
示例：'源石纪元13年9月1日08时00分00秒'
支持范围与估计格式的容错解析。

本模块为 10.1（消息传播延迟）/ 10.2（任务纲领时间）/ 10.3（周期事件 cron）的公共前置，
纯代码无 LLM。

简化约定（虚构历法）：
- 30 天/月、365 天/年（进位换算，非真实历法）
- 跨纪元比较按 era 字典序（单存档通常单纪元，跨纪元场景罕见）
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


# 游戏时间正则：纪元(任意非数字前缀) + 年月日时分秒
_GT_RE = re.compile(
    r"^(?P<era>[^\d]+?)(?P<year>\d+)年(?P<month>\d+)月(?P<day>\d+)日"
    r"(?P<hour>\d+)时(?P<minute>\d+)分(?P<second>\d+)秒$"
)


@dataclass
class GameTime:
    era: str
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int

    def __str__(self) -> str:
        return format_game_time(self)


@dataclass
class Duration:
    """时间段。days/months/years 可任意组合，add 时按 30 天/月、365 天/年简化换算。"""
    days: float = 0.0
    months: float = 0.0
    years: float = 0.0

    def total_days(self) -> float:
        return self.days + self.months * 30.0 + self.years * 365.0

    def total_seconds(self) -> float:
        return self.total_days() * 86400.0


def parse_game_time(s: str) -> Optional[GameTime]:
    """解析游戏时间字符串。失败返回 None（容错，支持降级解析年月日）。"""
    if not s:
        return None
    s = s.strip()
    m = _GT_RE.match(s)
    if m:
        return GameTime(
            era=m.group("era"),
            year=int(m.group("year")),
            month=int(m.group("month")),
            day=int(m.group("day")),
            hour=int(m.group("hour")),
            minute=int(m.group("minute")),
            second=int(m.group("second")),
        )
    # 降级：仅年月日（默认 00:00:00）
    m2 = re.match(r"^(?P<era>[^\d]+?)(?P<year>\d+)年(?P<month>\d+)月(?P<day>\d+)日", s)
    if m2:
        return GameTime(
            era=m2.group("era"),
            year=int(m2.group("year")),
            month=int(m2.group("month")),
            day=int(m2.group("day")),
            hour=0, minute=0, second=0,
        )
    return None


def format_game_time(gt: GameTime) -> str:
    return f"{gt.era}{gt.year}年{gt.month}月{gt.day}日{gt.hour:02d}时{gt.minute:02d}分{gt.second:02d}秒"


def compare(a: GameTime, b: GameTime) -> int:
    """a < b → -1；a == b → 0；a > b → 1。同纪元内按数值比较；跨纪元按 era 字典序（简化）。"""
    if a.era != b.era:
        return -1 if a.era < b.era else 1
    for x, y in ((a.year, b.year), (a.month, b.month), (a.day, b.day),
                 (a.hour, b.hour), (a.minute, b.minute), (a.second, b.second)):
        if x != y:
            return -1 if x < y else 1
    return 0


def delta(a: GameTime, b: GameTime) -> Duration:
    """a - b → Duration（天数为主，简化：不处理跨纪元）。"""
    if a.era != b.era:
        return Duration()  # 跨纪元无法精确
    def to_days(gt: GameTime) -> float:
        return (gt.year * 365 + gt.month * 30 + gt.day
                + gt.hour / 24.0 + gt.minute / 1440.0 + gt.second / 86400.0)
    return Duration(days=to_days(a) - to_days(b))


def add(gt: GameTime, dur: Duration) -> GameTime:
    """GameTime + Duration → GameTime。按 30 天/月、365 天/年简化进位。"""
    total_sec = (gt.hour * 3600 + gt.minute * 60 + gt.second
                 + dur.total_seconds())
    extra_days = total_sec // 86400.0
    rem_sec = int(total_sec % 86400.0)
    hour = rem_sec // 3600
    minute = (rem_sec % 3600) // 60
    second = rem_sec % 60

    total_days = gt.year * 365 + gt.month * 30 + gt.day + int(extra_days)
    year = total_days // 365
    rem = total_days % 365
    month = rem // 30
    day = rem % 30
    if month == 0:
        month = 1
        day = max(1, day)
    if month > 12:
        year += month // 12
        month = month % 12 or 12
    return GameTime(gt.era, year, month, max(1, day), hour, minute, second)


def parse_duration(raw: str) -> Optional[Duration]:
    """解析自然语言时长：'约3天'/'半天'/'半年'/'数年'/'2个月'。失败返回 None。"""
    if not raw:
        return None
    s = raw.strip()
    # 半年 / 半天（先于通用年/天匹配，避免误判）
    if "半年" in s:
        return Duration(months=6)
    if "半天" in s:
        return Duration(days=0.5)
    # 终身 / 长期
    if "终身" in s or "终生" in s or "长期" in s:
        return Duration(years=100)
    # N个月（先于 N年，因"个月"含"月"不含"年"；但"1年3个月"会先命中年）
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:个?月|个月)", s)
    if m and "年" not in s:
        return Duration(months=float(m.group(1)))
    # N年
    m = re.search(r"(\d+(?:\.\d+)?)\s*年", s)
    if m:
        return Duration(years=float(m.group(1)))
    # N天
    m = re.search(r"(\d+(?:\.\d+)?)\s*天", s)
    if m:
        return Duration(days=float(m.group(1)))
    # N小时
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:小时|时)", s)
    if m:
        return Duration(days=float(m.group(1)) / 24.0)
    # 模糊量词
    if re.search(r"[数几]\s*年", s):
        return Duration(years=3)
    if re.search(r"[数几]\s*月", s):
        return Duration(months=3)
    if re.search(r"[数几]\s*天", s):
        return Duration(days=3)
    return None


def next_cron(gt: GameTime, pattern: str, detail: str = "") -> Optional[GameTime]:
    """推进到下一周期。

    pattern: daily / weekly / monthly / yearly / custom
    detail: 自定义描述（custom 时尽力用 parse_duration 解析）。
    """
    pattern = (pattern or "").lower()
    if pattern == "daily":
        return add(gt, Duration(days=1))
    if pattern == "weekly":
        return add(gt, Duration(days=7))
    if pattern == "monthly":
        return add(gt, Duration(months=1))
    if pattern == "yearly":
        return add(gt, Duration(years=1))
    if pattern == "custom":
        d = parse_duration(detail)
        if d:
            return add(gt, d)
        return add(gt, Duration(days=1))
    return None


def to_sortable(s: str) -> int:
    """游戏时间字符串 → 可比较整数（用于 SQL 排序/过滤）。

    编码：year*1e10 + month*1e8 + day*1e6 + hour*1e4 + minute*100 + second。
    跨纪元不参与（单存档通常单纪元）；解析失败返回 0。
    """
    gt = parse_game_time(s)
    if not gt:
        return 0
    return (gt.year * 10_000_000_000
            + gt.month * 100_000_000
            + gt.day * 1_000_000
            + gt.hour * 10_000
            + gt.minute * 100
            + gt.second)
