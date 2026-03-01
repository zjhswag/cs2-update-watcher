#!/usr/bin/env python3
"""测试脚本：拉取最近一条 CS2 Steam 新闻，发送到邮箱。

用法：
  1. 先在 .env 中填好 QQ 邮箱的 SMTP 配置
  2. python test_send_news.py
"""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("test-send")

from config import Config
from formatter import format_news_html, format_news_text
from notifier import send_email
from steam_news_watcher import fetch_latest_news


def main():
    logger.info("正在从 Steam API 拉取最新新闻...")
    news = fetch_latest_news(count=1)

    if not news:
        logger.error("未能获取到任何新闻，请检查网络或 STEAM_API_KEY")
        sys.exit(1)

    item = news[0]
    logger.info("获取到新闻: %s", item.title)

    subject = f"[CS2 更新测试] {item.title}"
    body_text = format_news_text(news)
    body_html = format_news_html(news)

    logger.info("SMTP: %s:%d, 发件人: %s, 收件人: %s",
                Config.SMTP_HOST, Config.SMTP_PORT, Config.SMTP_USER, Config.NOTIFY_EMAIL)

    ok = send_email(subject, body_text, body_html)
    if ok:
        logger.info("邮件发送成功！请检查你的 QQ 邮箱收件箱（或垃圾箱）")
    else:
        logger.error("邮件发送失败，请检查 .env 中的 SMTP 配置")
        sys.exit(1)


if __name__ == "__main__":
    main()
