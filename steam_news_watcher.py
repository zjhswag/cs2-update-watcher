"""监听 Steam 官方 ISteamNews API 获取 CS2 更新公告。"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

from config import Config

logger = logging.getLogger(__name__)

STEAM_NEWS_URL = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v0002/"
OFFICIAL_FEED = "steam_community_announcements"


@dataclass
class SteamNewsItem:
    gid: str
    title: str
    contents: str
    url: str
    date: int  # unix timestamp
    feed_label: str


def fetch_latest_news(count: int = 5) -> list[SteamNewsItem]:
    """从 Steam API 获取最新的 CS2 新闻。"""
    params = {
        "appid": Config.STEAM_APP_ID,
        "count": count,
        "maxlength": 0,
        "format": "json",
        "feeds": OFFICIAL_FEED,
    }
    if Config.STEAM_API_KEY:
        params["key"] = Config.STEAM_API_KEY

    try:
        resp = requests.get(STEAM_NEWS_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        logger.exception("Steam News API 请求失败")
        return []

    news_items = data.get("appnews", {}).get("newsitems", [])

    return [
        SteamNewsItem(
            gid=str(item.get("gid", "")),
            title=item.get("title", ""),
            contents=item.get("contents", ""),
            url=item.get("url", ""),
            date=item.get("date", 0),
            feed_label=item.get("feedlabel", ""),
        )
        for item in news_items
    ]


def check_for_news(
    seen_gids: set[str] | None,
) -> tuple[set[str], list[SteamNewsItem]]:
    """检查是否有新的 Steam 新闻。

    使用已见 GID 集合（而非单个 GID）来判断新旧，
    避免 API 返回顺序不稳定时 GID 交替导致重复通知。

    返回 (当前页面所有 GID 的集合, 新新闻列表)。
    若无数据返回 (set(), [])。
    """
    news = fetch_latest_news()
    if not news:
        return set(), []

    current_gids = {item.gid for item in news}

    if seen_gids is None:
        logger.info(
            "首次运行，记录当前 %d 条新闻 GID（不触发通知）",
            len(current_gids),
        )
        return current_gids, []

    new_items = [item for item in news if item.gid not in seen_gids]

    if not new_items:
        return set(), []

    new_items.sort(key=lambda x: x.date)

    logger.info(
        "发现 %d 条新的 Steam 新闻, 最新: %s",
        len(new_items),
        new_items[-1].title,
    )
    return current_gids, new_items
