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


def send_game_tracking_notifications_for_commit(data: dict) -> bool:
    """对已拉取的单个 commit 做路径过滤、LLM 摘要，并发送邮件 + Bark（force）。成功进入发送流程返回 True。"""
    sha = (data.get("sha") or "")[:7] or "?"
    is_game, reason = commit_includes_cs2_game_content(data)
    if not is_game:
        logger.info("跳过非游戏内容提交 %s: %s", sha, reason)
        return False

    msg = (data.get("commit") or {}).get("message") or ""
    html_url = data.get("html_url") or ""
    first_line = msg.split("\n", 1)[0].strip() if isinstance(msg, str) else ""
    full_sha = data.get("sha") or sha

    ctx = build_llm_context(data)
    steam_urls = extract_steamdb_urls(msg if isinstance(msg, str) else "")
    if steam_urls:
        ctx += "\n\n## 备注\nSteamDB patch（仅链接）\n" + "\n".join(steam_urls)

    try:
        summary = summarize_commit_for_notification(ctx)
    except Exception:
        logger.exception("DeepSeek 摘要失败 %s", full_sha[:7])
        return False

    if not summary:
        logger.warning("摘要为空，跳过通知 %s", full_sha[:7])
        return False

    safe_line = re.sub(r"[\r\n]+", " ", first_line).strip()
    subject = f"[CS2 GameTracking] {full_sha[:7]} {safe_line[:60]}"
    footer = "\n".join(
        [
            f"Commit: {full_sha[:7]}",
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
        logger.warning("Bark 未配置或失败（commit %s）", full_sha[:7])
    logger.info("已通知 GameTracking 游戏提交 %s", full_sha[:7])
    return True


_SEEN_KEY = "seen_gametracking_shas"


def poll_game_tracking(state: dict) -> dict:
    """在 state 上更新已见 SHA 集合；对新增且含 CS2 内容的提交发邮件与 Bark。"""
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
    current_shas = {item.get("sha") for item in recent if item.get("sha")}
    seen_list = state.get(_SEEN_KEY)
    seen_shas = set(seen_list) if seen_list is not None else None

    # 兼容旧状态：如果存在旧的 _STATE_KEY 但没有 _SEEN_KEY，做一次迁移
    if seen_shas is None and state.get(_STATE_KEY):
        old_last = state[_STATE_KEY]
        logger.info("从旧格式迁移 GameTracking 状态，旧 tip=%s", old_last[:7])
        seen_shas = set()
        for item in recent:
            seen_shas.add(item.get("sha", ""))
            if item.get("sha") == old_last:
                break
        state[_SEEN_KEY] = list(seen_shas)
        state[_STATE_KEY] = tip_sha
        return state

    if seen_shas is None:
        logger.info(
            "首次 GameTracking 监听，记录当前 %d 个 SHA（不触发历史通知）",
            len(current_shas),
        )
        state[_SEEN_KEY] = list(current_shas)
        state[_STATE_KEY] = tip_sha
        return state

    new_items = [item for item in recent if item.get("sha") and item["sha"] not in seen_shas]

    if not new_items:
        merged = seen_shas | current_shas
        state[_SEEN_KEY] = list(merged)
        state[_STATE_KEY] = tip_sha
        return state

    new_items.reverse()

    logger.info(
        "GameTracking 发现 %d 条新提交（tip → %s）",
        len(new_items),
        tip_sha[:7],
    )

    # 先更新状态，防止通知失败导致重复
    merged = seen_shas | current_shas
    # 只保留最近 100 个 SHA，防止无限增长
    state[_SEEN_KEY] = list(merged)[-100:]
    state[_STATE_KEY] = tip_sha

    for item in new_items:
        sha = item.get("sha") or ""
        if not sha:
            continue
        try:
            data = fetch_commit(sha)
        except Exception:
            logger.exception("拉取 commit %s 失败", sha[:7])
            continue

        send_game_tracking_notifications_for_commit(data)

    return state
