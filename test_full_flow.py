#!/usr/bin/env python3
"""模拟一次完整的更新检测流程。

原理：拉取最新 2 条公告，假装只知道第 2 条（旧的），
这样第 1 条（最新的）就会被当成"新更新"，触发完整通知。
"""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("test-flow")

from formatter import format_news_html, format_news_text, format_phone_summary
from notifier import notify_all
from steam_news_watcher import fetch_latest_news


def main():
    logger.info("=== 模拟完整更新检测流程 ===")

    logger.info("Step 1: 拉取最新 2 条公告...")
    news = fetch_latest_news(count=2)
    if len(news) < 2:
        logger.error("公告数量不足，无法模拟")
        sys.exit(1)

    latest = news[0]
    previous = news[1]
    logger.info("最新公告: [GID=%s] %s", latest.gid, latest.title)
    logger.info("上一条:   [GID=%s] %s", previous.gid, previous.title)

    logger.info("Step 2: 假装上次记录的是 GID=%s，发现 1 条新公告", previous.gid)
    new_news = [latest]

    logger.info("Step 3: 格式化内容（含翻译）...")
    subject = f"[CS2 更新] {len(new_news)} 条官方公告"
    body_text = format_news_text(new_news)
    body_html = format_news_html(new_news)
    phone_msg = format_phone_summary(news=new_news)

    logger.info("Step 4: 发送所有通知...")
    results = notify_all(subject, body_text, body_html, phone_msg)

    logger.info("=== 测试完成 ===")
    for channel, ok in results.items():
        status = "成功" if ok else "跳过/失败"
        logger.info("  %s: %s", channel, status)


if __name__ == "__main__":
    main()
