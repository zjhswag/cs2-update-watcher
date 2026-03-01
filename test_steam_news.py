"""测试 ISteamNews API —— 拉取 CS2 最近的官方公告并输出完整内容。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

from config import Config
from steam_news_watcher import OFFICIAL_FEED, STEAM_NEWS_URL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("test-steam-news")


def fetch_full_news(count: int = 5) -> list[dict]:
    """不截断内容，拉取完整公告（maxlength=0 表示不限长度）。"""
    params = {
        "appid": Config.STEAM_APP_ID,
        "count": count,
        "maxlength": 0,
        "format": "json",
        "feeds": OFFICIAL_FEED,
    }
    resp = requests.get(STEAM_NEWS_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("appnews", {}).get("newsitems", [])


def main():
    logger.info("正在请求 ISteamNews API (完整内容, feeds=%s) ...", OFFICIAL_FEED)
    news = fetch_full_news(count=5)

    if not news:
        logger.warning("未获取到任何新闻，请检查网络或 API 状态")
        return

    logger.info("成功获取 %d 条官方公告\n", len(news))

    for i, n in enumerate(news, 1):
        ts = datetime.fromtimestamp(n["date"], tz=timezone.utc)
        print("=" * 60)
        print(f"[{i}/{len(news)}] {n['title']}")
        print(f"时间:  {ts.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"GID:   {n['gid']}")
        print(f"来源:  {n['feedlabel']}")
        print(f"链接:  {n['url']}")
        print("-" * 60)
        print(n["contents"])
        print()


if __name__ == "__main__":
    main()
