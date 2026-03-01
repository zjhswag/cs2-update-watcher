"""监听 Steam 官方 ISteamNews API 获取 CS2 更新公告。

这是对 GitHub commit 监控的补充：commit 反映代码级变更，
Steam News 则包含 Valve 发布的正式更新日志和补丁说明。
"""

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
    except requests.RequestException:
        logger.exception("Steam News API 请求失败")
        return []

    data = resp.json()
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


def check_for_news(last_gid: str | None) -> tuple[str | None, list[SteamNewsItem]]:
    """主入口：检查是否有新的 Steam 新闻。

    返回 (最新 GID, 新新闻列表)。
    如果没有更新，返回 (None, [])。
    """
    news = fetch_latest_news()
    if not news:
        return None, []

    if last_gid is None:
        latest = news[0]
        logger.info("首次运行，记录最新新闻 GID: %s", latest.gid)
        return latest.gid, []

    new_items: list[SteamNewsItem] = []
    for item in news:
        if item.gid == last_gid:
            break
        new_items.append(item)

    if not new_items:
        return None, []

    latest_gid = new_items[0].gid
    logger.info("发现 %d 条新的 Steam 新闻, 最新: %s", len(new_items), new_items[0].title)
    return latest_gid, new_items
