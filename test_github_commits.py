"""查看 GameTracking-CS2 最近的 commit 详细时间。

GitHub commit 有两个时间：
  - author date: 作者创建 commit 的时间
  - committer date: commit 被提交/推送的时间
两者通常几乎相同，但在 rebase/cherry-pick 场景下可能不同。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

from config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("test-github")

REPO = Config.GITHUB_REPO  # SteamDatabase/GameTracking-CS2
API_BASE = "https://api.github.com"


def fetch_commits(count: int = 15) -> list[dict]:
    url = f"{API_BASE}/repos/{REPO}/commits"
    headers = {"Accept": "application/vnd.github+json"}
    if Config.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {Config.GITHUB_TOKEN}"

    resp = requests.get(url, headers=headers, params={"per_page": count}, timeout=30)

    remaining = resp.headers.get("X-RateLimit-Remaining", "?")
    reset_ts = resp.headers.get("X-RateLimit-Reset", "")
    reset_str = ""
    if reset_ts:
        reset_time = datetime.fromtimestamp(int(reset_ts), tz=timezone.utc)
        reset_str = reset_time.strftime("%H:%M:%S UTC")

    logger.info("GitHub API 状态: %s | 剩余配额: %s | 重置时间: %s",
                resp.status_code, remaining, reset_str)

    if resp.status_code == 403:
        logger.error("API 限流，请配置 GITHUB_TOKEN 后重试")
        return []

    resp.raise_for_status()
    return resp.json()


def main():
    logger.info("仓库: %s", REPO)
    logger.info("Token: %s", "已配置" if Config.GITHUB_TOKEN else "未配置（匿名，60次/小时）")
    print()

    commits = fetch_commits(count=15)
    if not commits:
        return

    print()
    print(f"{'SHA':10s} | {'Author Date (UTC)':24s} | {'Committer Date (UTC)':24s} | {'差值':8s} | 文件数 | 编号")
    print("=" * 110)

    for c in commits:
        sha = c["sha"][:8]
        commit_data = c["commit"]

        author_date_str = commit_data["author"]["date"]
        committer_date_str = commit_data["committer"]["date"]

        author_dt = datetime.fromisoformat(author_date_str.replace("Z", "+00:00"))
        committer_dt = datetime.fromisoformat(committer_date_str.replace("Z", "+00:00"))

        diff = abs((committer_dt - author_dt).total_seconds())
        diff_str = f"{int(diff)}s" if diff > 0 else "0s"

        msg_parts = commit_data["message"].split("|")
        build_num = msg_parts[0].strip() if msg_parts else "?"
        file_count = msg_parts[1].strip() if len(msg_parts) >= 2 else "?"

        print(
            f"{sha:10s} | "
            f"{author_dt.strftime('%Y-%m-%d %H:%M:%S UTC'):24s} | "
            f"{committer_dt.strftime('%Y-%m-%d %H:%M:%S UTC'):24s} | "
            f"{diff_str:8s} | "
            f"{file_count:6s} | "
            f"{build_num}"
        )

    print()
    logger.info("以上时间均为 UTC，北京时间 = UTC + 8 小时")


if __name__ == "__main__":
    main()
