#!/usr/bin/env python3
"""测试：指定 GameTracking commit →（仅游戏 dump 变更时）DeepSeek 摘要 → 邮件 + Bark。

逻辑：
  1. 变更路径必须落在 `game/`、`content/`、`Protobufs/`、`DumpSource2/` 之一，否则视为仓库维护提交，默认不跑 LLM、不通知。
  2. 符合条件的提交：LLM 摘要后发邮件，并对 Bark 使用 `force=True`（仍需配置 BARK_URL）。
  3. `--force-notify`：即使判定为维护提交也照样摘要并通知（调试用）。

用法示例：
  export DEEPSEEK_API_KEY=...
  export GITHUB_TOKEN=...          # 强烈建议，否则 GitHub 易限流
  # 无新推送时，直接测「当前分支最新一条」：
  python3 test_commit_ai_summary.py --latest --no-notify
  python3 test_commit_ai_summary.py --latest
  # 指定 SHA：
  python3 test_commit_ai_summary.py --sha 5d9ac5f --no-notify
"""

from __future__ import annotations

import argparse
import html as html_module
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("test-commit-ai")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GameTracking commit AI 摘要测试（仅 CS2 dump 变更触发通知）"
    )
    parser.add_argument(
        "--sha",
        default="783074f",
        help="commit SHA（完整或短 SHA）；与 --latest 二选一，同时给定时以 --latest 为准",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help=(
            "使用 Config 中 GAMETRACKING_BRANCH（默认 master）的 **当前最新一条** 提交，"
            "等同「刚推送」效果，便于仓库暂无新 commit 时联调邮件与 Bark"
        ),
    )
    parser.add_argument(
        "--no-notify",
        action="store_true",
        help="只打印摘要，不发送邮件 / Bark",
    )
    parser.add_argument(
        "--force-notify",
        action="store_true",
        help="忽略路径过滤，仍生成摘要并通知（维护提交调试用）",
    )
    args = parser.parse_args()

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

    if not Config.DEEPSEEK_API_KEY:
        logger.error("请设置环境变量 DEEPSEEK_API_KEY")
        sys.exit(1)

    target_sha = args.sha
    if args.latest:
        try:
            tip = fetch_branch_commit_shas(
                Config.GAMETRACKING_BRANCH, per_page=1
            )
        except Exception:
            logger.exception(
                "获取分支 %s 最新提交失败（是否未设置 GITHUB_TOKEN 导致限流？）",
                Config.GAMETRACKING_BRANCH,
            )
            sys.exit(1)
        if not tip or not tip[0].get("sha"):
            logger.error("分支 %s 无可用提交", Config.GAMETRACKING_BRANCH)
            sys.exit(1)
        target_sha = tip[0]["sha"]
        logger.info(
            "使用分支 %s 当前 tip: %s %s",
            Config.GAMETRACKING_BRANCH,
            target_sha[:7],
            tip[0].get("message_first_line", ""),
        )

    logger.info("拉取 commit %s ...", target_sha)
    data = fetch_commit(target_sha)
    sha_full = data.get("sha") or target_sha
    html_url = data.get("html_url") or ""
    msg = (data.get("commit") or {}).get("message") or ""
    first_line = msg.split("\n", 1)[0].strip() if isinstance(msg, str) else ""

    is_game, filter_reason = commit_includes_cs2_game_content(data)
    if args.force_notify:
        is_game = True
        filter_reason = "已 --force-notify，跳过路径过滤"

    print("\n" + "=" * 60)
    print("是否 CS2 游戏 dump 变更")
    print("=" * 60)
    print(f"  include: {is_game}")
    print(f"  说明: {filter_reason}")
    print("=" * 60 + "\n")

    if not is_game:
        logger.info("非游戏内容提交，跳过 LLM 与通知（可用 --force-notify）")
        return

    steam_urls = extract_steamdb_urls(msg if isinstance(msg, str) else "")
    patch_url = steam_urls[0] if steam_urls else None

    ctx = build_llm_context(data)
    if patch_url:
        ctx += (
            "\n\n## 备注\ncommit 含 SteamDB patch 链接（未爬取）\n"
            + patch_url
            + "\n"
        )

    logger.info("调用 DeepSeek 生成摘要...")
    summary = summarize_commit_for_notification(ctx)

    if not summary:
        logger.error("摘要为空，退出")
        sys.exit(2)

    print("\n" + "=" * 60)
    print(summary)
    print("=" * 60 + "\n")

    footer_lines = [
        f"Commit: {sha_full[:7]}",
        f"链接: {html_url}",
        "提交说明首行: " + first_line,
        f"路径过滤: {filter_reason}",
    ]
    if patch_url:
        footer_lines.append("SteamDB（仅链接）: " + patch_url)

    footer = "\n".join(footer_lines)

    if args.no_notify:
        logger.info("已跳过通知（--no-notify）")
        return

    subject = f"[CS2 GameTracking] {sha_full[:7]} AI 更新摘要"
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
        logger.warning("Bark 未发送：未配置 BARK_URL")

    logger.info("邮件已尝试发送（受 ENABLE_EMAIL 与 SMTP 配置影响）")


if __name__ == "__main__":
    main()
