#!/usr/bin/env python3
"""CS2 Update Watcher — 监听 CS2 更新并即时通知。

数据源：
  - Steam 官方 ISteamNews API（正式更新公告）
  - GitHub SteamTracking/GameTracking-CS2（客户端 dump 提交 → DeepSeek 摘要）

联调（不走 state、不覆盖已记录进度）：
  python main.py --test-notify-once

通知渠道：
  - 邮件 (SMTP)
  - Bark 推送（iOS）
  - 阿里云语音电话（可选）
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
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
from gametracking_watcher import poll_game_tracking
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


def _clear_console() -> None:
    """清屏。仅在交互式终端执行，避免输出重定向时打印乱码。"""
    if not sys.stdout.isatty():
        return
    if os.name == "nt":
        os.system("cls")
    else:
        # ANSI: 2J=清屏, H=光标回左上角
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


def _send_translated_email_async(new_news: list) -> None:
    """在后台线程中翻译并发送完整版邮件，不阻塞轮询主循环。"""
    try:
        translations = _translate_news(new_news)
        subject_full = f"[CS2 更新] {len(new_news)} 条官方公告（含翻译）"
        body_full_text = format_news_text(new_news, translations)
        body_full_html = format_news_html(new_news, translations)
        send_email(subject_full, body_full_text, body_full_html)
    except Exception:
        logger.exception("后台翻译/发送完整邮件失败（不影响主流程）")


def _migrate_state(current_state: dict) -> None:
    """将旧格式 last_news_gid (单个 GID) 迁移到 seen_news_gids (集合)。"""
    if "seen_news_gids" not in current_state and "last_news_gid" in current_state:
        old_gid = current_state.pop("last_news_gid")
        current_state["seen_news_gids"] = [old_gid] if old_gid else []
        logger.info("状态迁移: last_news_gid=%s → seen_news_gids", old_gid)


def poll_once(current_state: dict) -> dict:
    """执行一次完整检查：Steam 新闻 + GameTracking GitHub。"""
    _migrate_state(current_state)

    seen_gids_list = current_state.get("seen_news_gids")
    seen_gids = set(seen_gids_list) if seen_gids_list is not None else None

    current_gids, new_news = check_steam(seen_gids)

    if current_gids and seen_gids is None:
        logger.info(
            "首次运行，记录当前 %d 条公告 GID（不触发通知）",
            len(current_gids),
        )
        current_state["seen_news_gids"] = list(current_gids)
    elif new_news:
        # 先更新状态，确保即使后续通知失败也不会重复
        merged = (seen_gids or set()) | current_gids
        current_state["seen_news_gids"] = list(merged)
        save_state(current_state)

        # 1. 快速提醒（无翻译），第一时间通知
        subject_quick = f"[CS2 更新] 发现 {len(new_news)} 条新公告（快速提醒）"
        body_quick_text = format_quick_alert_text(new_news)
        body_quick_html = format_quick_alert_html(new_news)
        phone_msg = format_phone_summary(news=new_news)
        notify_all(subject_quick, body_quick_text, body_quick_html, phone_msg)

        # 2. 翻译+完整邮件放到后台线程，不阻塞下一轮轮询
        t = threading.Thread(
            target=_send_translated_email_async,
            args=(new_news,),
            daemon=True,
        )
        t.start()
    elif current_gids:
        merged = (seen_gids or set()) | current_gids
        current_state["seen_news_gids"] = list(merged)

    # 防止已见集合无限增长：只保留最近 50 个 GID
    if len(current_state.get("seen_news_gids", [])) > 50:
        current_state["seen_news_gids"] = current_state["seen_news_gids"][-50:]

    current_state = poll_game_tracking(current_state)

    return current_state


def run_test_notify_once() -> None:
    """联调：各走一遍与 `poll_once` 相同的 Steam 通知链 + 当前 GameTracking tip 的 LLM 通知。

    不读不写 `watcher_state.json`，不影响正式运行时的 last_gid / last_gametracking_sha。

    Steam：拉 2 条公告并假设第 2 条已读，则第 1 条会触发快速提醒 + 翻译邮件 + Bark（与 ENABLE_* 一致）。
    GameTracking：拉分支当前 tip，若含游戏路径则摘要并邮件 + Bark（force）。
    """
    from gametracking_commit import fetch_branch_commit_shas, fetch_commit
    from gametracking_watcher import send_game_tracking_notifications_for_commit
    from steam_news_watcher import fetch_latest_news

    logger.info("=" * 60)
    logger.info("联调 --test-notify-once（不修改 state 文件）")
    logger.info("=" * 60)

    news = fetch_latest_news(count=2)
    if len(news) < 2:
        logger.warning(
            "Steam 公告不足 2 条，跳过新闻联调（需至少 2 条才能模拟「仅最新为未读」）"
        )
    else:
        pretend_seen = {news[1].gid}
        _current_gids, new_news = check_steam(pretend_seen)
        if not new_news:
            logger.warning(
                "Steam：以 GID %s 为已读时未识别到新公告，跳过新闻通知",
                news[1].gid,
            )
        else:
            subject_quick = f"[CS2 更新] 发现 {len(new_news)} 条新公告（快速提醒）"
            body_quick_text = format_quick_alert_text(new_news)
            body_quick_html = format_quick_alert_html(new_news)
            phone_msg = format_phone_summary(news=new_news)
            notify_all(subject_quick, body_quick_text, body_quick_html, phone_msg)

            translations = _translate_news(new_news)
            subject_full = f"[CS2 更新] {len(new_news)} 条官方公告（含翻译）"
            body_full_text = format_news_text(new_news, translations)
            body_full_html = format_news_html(new_news, translations)
            send_email(subject_full, body_full_text, body_full_html)
            logger.info(
                "Steam 联调已发送（快速提醒 + 完整邮件），假定已读 GID=%s",
                news[1].gid,
            )

    if not Config.ENABLE_GAMETRACKING:
        logger.info("GameTracking 已关闭（ENABLE_GAMETRACKING），跳过 commit 联调")
    elif not Config.DEEPSEEK_API_KEY:
        logger.warning("未配置 DEEPSEEK_API_KEY，跳过 GameTracking commit 联调")
    else:
        try:
            tip_list = fetch_branch_commit_shas(
                Config.GAMETRACKING_BRANCH, per_page=1
            )
        except Exception:
            logger.exception("拉取 GameTracking tip 失败（检查 GITHUB_TOKEN）")
            tip_list = []
        if not tip_list or not tip_list[0].get("sha"):
            logger.warning("未拿到 GameTracking tip")
        else:
            sha = tip_list[0]["sha"]
            logger.info(
                "GameTracking 联调 tip: %s %s",
                sha[:7],
                tip_list[0].get("message_first_line", ""),
            )
            try:
                data = fetch_commit(sha)
            except Exception:
                logger.exception("拉取 commit 失败")
            else:
                send_game_tracking_notifications_for_commit(data)

    logger.info("联调结束（state 文件未改动）")


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
        f"轮询间隔: {Config.POLL_INTERVAL_SECONDS} 秒（每轮含 Steam 新闻 + GameTracking）\n"
        f"GameTracking: {'开启' if Config.ENABLE_GAMETRACKING else '关闭'} "
        f"({Config.GAMETRACKING_REPO} @ {Config.GAMETRACKING_BRANCH})\n"
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
    logger.info(
        "轮询间隔: %d 秒（每轮顺序：Steam 新闻 → GameTracking GitHub）",
        Config.POLL_INTERVAL_SECONDS,
    )
    logger.info("Steam App ID: %d", Config.STEAM_APP_ID)
    logger.info(
        "GameTracking: %s | %s @ %s",
        "开启" if Config.ENABLE_GAMETRACKING else "关闭",
        Config.GAMETRACKING_REPO,
        Config.GAMETRACKING_BRANCH,
    )
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
            _clear_console()
            logger.info("控制台已清屏（第 %d 次轮询）", poll_count)

        try:
            current_state = poll_once(current_state)
            save_state(current_state)
        except Exception:
            logger.exception("检查周期异常，将在下次重试")

        seen = current_state.get("seen_news_gids", [])
        gid_summary = f"{len(seen)} 条已知" if seen else "无"
        gsha = current_state.get("last_gametracking_sha")
        gtip = (gsha[:7] + "…") if isinstance(gsha, str) and len(gsha) >= 7 else (gsha or "未记录")
        logger.info(
            "第 %d 次轮询完成 | Steam 公告: %s | GameTracking tip: %s",
            poll_count,
            gid_summary,
            gtip,
        )

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
    if "--test-notify-once" in sys.argv:
        run_test_notify_once()
    else:
        main()
