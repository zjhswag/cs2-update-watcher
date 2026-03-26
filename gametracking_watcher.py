"""轮询 SteamTracking/GameTracking-CS2：新提交且含游戏 dump 时 LLM 摘要并邮件 + Bark。"""

from __future__ import annotations

import html as html_module
import logging
import re

from config import Config
from gametracking_commit import (
    build_llm_context,
    commit_includes_cs2_game_content,
    extract_steamdb_urls,
    fetch_branch_commit_shas,
    fetch_commit,
)
from gametracking_llm import summarize_commit_for_notification
from notifier import send_bark, send_email

logger = logging.getLogger(__name__)

_STATE_KEY = "last_gametracking_sha"


def poll_game_tracking(state: dict) -> dict:
    """在 state 上更新 last_gametracking_sha；对新增且含 CS2 内容的提交发邮件与 Bark。"""
    if not Config.ENABLE_GAMETRACKING:
        return state

    if not Config.DEEPSEEK_API_KEY:
        logger.debug("未配置 DEEPSEEK_API_KEY，跳过 GameTracking 轮询")
        return state

    if not Config.GITHUB_TOKEN:
        logger.warning("建议配置 GITHUB_TOKEN，否则 GitHub API 额度较低")

    try:
        recent = fetch_branch_commit_shas(
            Config.GAMETRACKING_BRANCH,
            per_page=Config.GAMETRACKING_COMMITS_PER_POLL,
        )
    except Exception:
        logger.exception("拉取 GameTracking 提交列表失败")
        return state

    if not recent or not recent[0].get("sha"):
        logger.warning("GameTracking 提交列表为空")
        return state

    tip_sha = recent[0]["sha"]
    last = state.get(_STATE_KEY)

    if last is None:
        logger.info(
            "首次 GameTracking 监听，记录当前 tip=%s（不触发历史通知）",
            tip_sha[:7],
        )
        state[_STATE_KEY] = tip_sha
        return state

    if tip_sha == last:
        return state

    new_items: list[dict] = []
    for item in recent:
        sha = item.get("sha") or ""
        if sha == last:
            break
        new_items.append(item)
    new_items.reverse()

    logger.info(
        "GameTracking 发现 %d 条新提交（tip %s → %s）",
        len(new_items),
        last[:7],
        tip_sha[:7],
    )

    for item in new_items:
        sha = item.get("sha") or ""
        if not sha:
            continue
        line = item.get("message_first_line") or ""
        try:
            data = fetch_commit(sha)
        except Exception:
            logger.exception("拉取 commit %s 失败", sha[:7])
            continue

        is_game, reason = commit_includes_cs2_game_content(data)
        if not is_game:
            logger.info("跳过非游戏内容提交 %s: %s", sha[:7], reason)
            continue

        msg = (data.get("commit") or {}).get("message") or ""
        html_url = data.get("html_url") or ""
        first_line = (
            msg.split("\n", 1)[0].strip() if isinstance(msg, str) else ""
        )

        ctx = build_llm_context(data)
        steam_urls = extract_steamdb_urls(msg if isinstance(msg, str) else "")
        if steam_urls:
            ctx += "\n\n## 备注\nSteamDB patch（仅链接）\n" + "\n".join(steam_urls)

        try:
            summary = summarize_commit_for_notification(ctx)
        except Exception:
            logger.exception("DeepSeek 摘要失败 %s", sha[:7])
            continue

        if not summary:
            logger.warning("摘要为空，跳过通知 %s", sha[:7])
            continue

        safe_line = re.sub(r"[\r\n]+", " ", first_line).strip()
        subject = f"[CS2 GameTracking] {sha[:7]} {safe_line[:60]}"
        footer = "\n".join(
            [
                f"Commit: {sha[:7]}",
                f"链接: {html_url}",
                f"过滤: {reason}",
                f"说明: {first_line}",
            ]
        )
        body_text = summary + "\n\n---\n" + footer
        body_html = (
            '<pre style="white-space:pre-wrap;font-family:system-ui,sans-serif;">'
            f"{html_module.escape(summary)}"
            '</pre><hr/><pre style="font-size:12px;">'
            f"{html_module.escape(footer)}"
            "</pre>"
        )

        send_email(subject, body_text, body_html)
        bark_body = summary[:3500] + ("\n…" if len(summary) > 3500 else "")
        ok = send_bark(subject, bark_body, force=True)
        if not ok and not Config.BARK_URL:
            logger.warning("Bark 未配置或失败（commit %s）", sha[:7])
        logger.info("已通知 GameTracking 游戏提交 %s", sha[:7])

    state[_STATE_KEY] = tip_sha
    return state
