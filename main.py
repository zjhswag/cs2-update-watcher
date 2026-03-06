#!/usr/bin/env python3
"""CS2 Update Watcher — 监听 CS2 更新并即时通知。

数据源：
  Steam 官方 ISteamNews API（正式更新公告）

通知渠道：
  - 邮件 (SMTP)
  - Bark 推送（iOS）
  - 阿里云语音电话（可选）
"""

from __future__ import annotations

import logging
import os
import signal
import time
from datetime import datetime, timedelta, timezone

from config import Config
from formatter import (
    _translate_news,
    format_news_html,
    format_news_text,
    format_phone_summary,
    format_quick_alert_html,
    format_quick_alert_text,
)
from notifier import notify_all, send_email
from state import load_state, save_state
from steam_news_watcher import check_for_news as check_steam

CST = timezone(timedelta(hours=8))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cs2-watcher")

_running = True


def _handle_signal(sig, _frame):
    global _running
    logger.info("收到信号 %s，准备退出...", signal.Signals(sig).name)
    _running = False


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


def poll_once(current_state: dict) -> dict:
    """执行一次完整的检查周期。"""
    last_gid = current_state.get("last_news_gid")

    new_gid, new_news = check_steam(last_gid)

    if new_gid and last_gid is None:
        logger.info("首次运行，记录当前最新公告 GID: %s（不触发通知）", new_gid)
        current_state["last_news_gid"] = new_gid
        return current_state

    if not new_news:
        return current_state

    # 1. 先发快速提醒（无翻译），第一时间通知
    subject_quick = f"[CS2 更新] 发现 {len(new_news)} 条新公告（快速提醒）"
    body_quick_text = format_quick_alert_text(new_news)
    body_quick_html = format_quick_alert_html(new_news)
    phone_msg = format_phone_summary(news=new_news)
    notify_all(subject_quick, body_quick_text, body_quick_html, phone_msg)

    # 2. 翻译后发送带翻译的完整版邮件
    translations = _translate_news(new_news)
    subject_full = f"[CS2 更新] {len(new_news)} 条官方公告（含翻译）"
    body_full_text = format_news_text(new_news, translations)
    body_full_html = format_news_html(new_news, translations)
    send_email(subject_full, body_full_text, body_full_html)

    current_state["last_news_gid"] = new_gid

    return current_state


def _check_heartbeat(last_heartbeat_date: str | None) -> str | None:
    """每天中午 12:00 发送一封心跳邮件，确认程序运行正常。"""
    now = datetime.now(tz=CST)
    today_str = now.strftime("%Y-%m-%d")

    if now.hour < 12:
        return last_heartbeat_date

    if last_heartbeat_date == today_str:
        return last_heartbeat_date

    subject = f"[CS2 Watcher] 运行正常 — {today_str}"
    body = (
        f"CS2 Update Watcher 运行状态报告\n"
        f"{'=' * 40}\n\n"
        f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')} CST\n"
        f"轮询间隔: {Config.POLL_INTERVAL_SECONDS} 秒\n"
        f"邮件通知: 开启\n"
        f"Bark 推送: {'开启' if Config.ENABLE_BARK else '关闭'}\n\n"
        f"程序运行正常，持续监听 CS2 更新中。\n\n"
        f"By 周佳和"
    )
    send_email(subject, body)
    logger.info("心跳邮件已发送")
    return today_str


def main():
    logger.info("=" * 60)
    logger.info("CS2 Update Watcher 启动")
    logger.info("轮询间隔: %d 秒", Config.POLL_INTERVAL_SECONDS)
    logger.info("Steam App ID: %d", Config.STEAM_APP_ID)
    logger.info("邮件通知: %s", "开启" if Config.ENABLE_EMAIL else "关闭")
    logger.info("Bark 推送: %s", "开启" if Config.ENABLE_BARK else "关闭")
    logger.info("电话通知: %s", "开启" if Config.ENABLE_PHONE else "关闭")
    logger.info("每日心跳: 12:00 CST")
    logger.info("=" * 60)

    current_state = load_state()
    last_heartbeat = current_state.get("last_heartbeat_date")
    poll_count = 0

    while _running:
        poll_count += 1

        if poll_count % 100 == 0:
            os.system("cls" if os.name == "nt" else "clear")
            logger.info("控制台已清屏（第 %d 次轮询）", poll_count)

        try:
            current_state = poll_once(current_state)
            save_state(current_state)
        except Exception:
            logger.exception("检查周期异常，将在下次重试")

        gid = current_state.get("last_news_gid", "无")
        logger.info("第 %d 次轮询完成 | 最新公告 GID: %s", poll_count, gid)

        try:
            last_heartbeat = _check_heartbeat(last_heartbeat)
            current_state["last_heartbeat_date"] = last_heartbeat
            save_state(current_state)
        except Exception:
            logger.exception("心跳邮件发送异常")

        for _ in range(Config.POLL_INTERVAL_SECONDS):
            if not _running:
                break
            time.sleep(1)

    logger.info("CS2 Update Watcher 已停止（共轮询 %d 次）", poll_count)


if __name__ == "__main__":
    main()
