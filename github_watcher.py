"""监听 SteamDatabase/GameTracking-CS2 仓库的新 commit。

策略：轮询 GitHub REST API /repos/{owner}/{repo}/commits，
比较上次记录的最新 commit SHA，发现新 commit 时返回变更详情。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import requests

from config import Config

logger = logging.getLogger(__name__)

API_BASE = "https://api.github.com"


@dataclass
class CommitInfo:
    sha: str
    message: str
    author: str
    date: str
    url: str
    files_changed: list[str] = field(default_factory=list)


def _headers() -> dict[str, str]:
    h = {"Accept": "application/vnd.github+json"}
    if Config.GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {Config.GITHUB_TOKEN}"
    return h


def fetch_latest_commits(since_sha: str | None, per_page: int = 10) -> list[CommitInfo]:
    """获取仓库最新 commit 列表。

    如果 since_sha 不为空，只返回比它更新的 commit。
    """
    url = f"{API_BASE}/repos/{Config.GITHUB_REPO}/commits"
    params = {"per_page": per_page}

    try:
        resp = requests.get(url, headers=_headers(), params=params, timeout=30)
        resp.raise_for_status()
    except requests.RequestException:
        logger.exception("GitHub API 请求失败")
        return []

    commits_json = resp.json()
    if not isinstance(commits_json, list):
        logger.error("GitHub API 返回格式异常: %s", type(commits_json))
        return []

    results: list[CommitInfo] = []
    for item in commits_json:
        sha = item["sha"]
        if sha == since_sha:
            break
        commit_data = item.get("commit", {})
        author_info = commit_data.get("author", {})
        results.append(CommitInfo(
            sha=sha,
            message=commit_data.get("message", ""),
            author=author_info.get("name", "unknown"),
            date=author_info.get("date", ""),
            url=item.get("html_url", ""),
        ))

    return results


def fetch_commit_files(sha: str) -> list[str]:
    """获取某个 commit 修改的文件列表。"""
    url = f"{API_BASE}/repos/{Config.GITHUB_REPO}/commits/{sha}"
    try:
        resp = requests.get(url, headers=_headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return [f["filename"] for f in data.get("files", [])]
    except requests.RequestException:
        logger.exception("获取 commit 文件列表失败: %s", sha)
        return []


def check_for_updates(last_sha: str | None) -> tuple[str | None, list[CommitInfo]]:
    """主入口：检查是否有新 commit。

    返回 (最新 SHA, 新 commit 列表)。
    如果没有更新，返回 (None, [])。
    """
    new_commits = fetch_latest_commits(last_sha)
    if not new_commits:
        return None, []

    for commit in new_commits[:3]:
        commit.files_changed = fetch_commit_files(commit.sha)

    latest_sha = new_commits[0].sha
    logger.info("发现 %d 个新 commit, 最新: %s", len(new_commits), latest_sha[:8])
    return latest_sha, new_commits
