"""拉取 GameTracking-CS2 的 GitHub commit，并按重要程度筛选用于 LLM 的上下文。"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

import requests

from config import Config

logger = logging.getLogger(__name__)

Tier = Literal["high", "medium", "low"]

STEAMDB_PATCHNOTE_RE = re.compile(
    r"https://steamdb\.info/patchnotes/\d+/?",
    re.IGNORECASE,
)
# 例：2000749 | 45 files | M DumpSource2/convars.txt, ...
_GAMETRACKING_BOT_COMMIT_RE = re.compile(
    r"\b\d{6,}\b\s*\|\s*\d+\s+files\s*\|",
    re.IGNORECASE,
)


@dataclass
class CommitFileInfo:
    filename: str
    status: str
    additions: int
    deletions: int
    patch: str | None


def extract_steamdb_urls(message: str) -> list[str]:
    return list(dict.fromkeys(STEAMDB_PATCHNOTE_RE.findall(message or "")))


def is_cs2_game_content_path(path: str) -> bool:
    """是否为 GameTracking-CS2 仓库内「客户端 / 逆向 dump」路径（非 .github、README 等维护文件）。"""
    if not path or not str(path).strip():
        return False
    pl = path.replace("\\", "/").lower()
    # 仅维护性目录：整份提交若只动这些，不通知
    if pl.startswith(".github/"):
        return False
    return (
        pl.startswith("game/")
        or pl.startswith("content/")
        or pl.startswith("protobufs/")
        or pl.startswith("dumpsource2/")
    )


def commit_includes_cs2_game_content(data: dict[str, Any]) -> tuple[bool, str]:
    """根据变更文件路径判断是否包含 CS2 游戏侧 dump，排除纯仓库维护提交。"""
    raw = data.get("files") or []
    if not raw:
        msg = (data.get("commit") or {}).get("message") or ""
        if isinstance(msg, str) and _GAMETRACKING_BOT_COMMIT_RE.search(msg):
            return True, "files 未列出，但提交说明符合 GameTracking 自动提交格式"
        return False, "无 files 列表（且提交说明不像常规资源同步）"

    all_names: list[str] = []
    game_names: list[str] = []
    for item in raw:
        fn = item.get("filename") or ""
        all_names.append(fn)
        if is_cs2_game_content_path(fn):
            game_names.append(fn)

    if game_names:
        return True, f"游戏相关文件 {len(game_names)}/{len(all_names)}"

    sample = ", ".join(all_names[:5])
    more = "…" if len(all_names) > 5 else ""
    return False, f"无 game/content/protobufs/dumpsource2 变更（示例: {sample}{more}）"


def classify_path(path: str) -> Tier:
    p = path.replace("\\", "/")
    pl = p.lower()

    if "_strings.txt" in pl:
        return "low"
    if "rendersystemvulkan_strings" in pl:
        return "low"

    if pl.endswith(".proto") or "/protobufs/" in pl:
        return "high"
    if pl.endswith("dumpsource2/convars.txt"):
        return "high"
    if "/game/csgo/cfg/" in pl and pl.endswith(".cfg"):
        return "high"
    if "/built_from_cl.txt" in pl:
        return "high"
    if "/steam.inf" in pl and pl.endswith("steam.inf"):
        return "high"
    if "weapons.vdata" in pl:
        return "high"
    if "items_game.txt" in pl:
        return "high"
    if "workshop_cvar_whitelist.txt" in pl:
        return "high"

    if ".stringsignore" in pl:
        return "medium"
    # 注意路径可能没有前导 “/”，用包含判断即可匹配 DumpSource2/schemas/…
    if "dumpsource2/schemas/" in pl:
        return "medium"
    if "/panorama/" in pl and pl.endswith((".js", ".xml", ".css")):
        return "medium"
    if "/annotations/official/" in pl:
        return "medium"
    if "/pak01_dir/resource/" in pl and pl.endswith(".txt"):
        return "medium"

    return "low"


def _github_headers() -> dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if Config.GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {Config.GITHUB_TOKEN}"
    return h


def fetch_commit(sha: str) -> dict[str, Any]:
    owner_repo = Config.GAMETRACKING_REPO.strip().strip("/")
    url = f"https://api.github.com/repos/{owner_repo}/commits/{sha}"
    resp = requests.get(url, headers=_github_headers(), timeout=60)
    resp.raise_for_status()
    return resp.json()


def fetch_branch_commit_shas(branch: str | None = None, *, per_page: int = 15) -> list[dict[str, Any]]:
    """获取分支上最近若干条提交的 sha / message / html_url（不含完整 files）。"""
    owner_repo = Config.GAMETRACKING_REPO.strip().strip("/")
    br = (branch or Config.GAMETRACKING_BRANCH).strip() or "master"
    url = (
        f"https://api.github.com/repos/{owner_repo}/commits"
        f"?sha={br}&per_page={max(1, min(per_page, 50))}"
    )
    resp = requests.get(url, headers=_github_headers(), timeout=60)
    resp.raise_for_status()
    body = resp.json()
    if not isinstance(body, list):
        return []
    out: list[dict[str, Any]] = []
    for item in body:
        if not isinstance(item, dict):
            continue
        c = item.get("commit") or {}
        msg = c.get("message") or ""
        first = msg.split("\n", 1)[0].strip() if isinstance(msg, str) else ""
        out.append(
            {
                "sha": item.get("sha") or "",
                "html_url": item.get("html_url") or "",
                "message_first_line": first,
            }
        )
    return out


def _parse_files(data: dict[str, Any]) -> list[CommitFileInfo]:
    out: list[CommitFileInfo] = []
    for f in data.get("files") or []:
        out.append(
            CommitFileInfo(
                filename=f.get("filename") or "",
                status=f.get("status") or "",
                additions=int(f.get("additions") or 0),
                deletions=int(f.get("deletions") or 0),
                patch=f.get("patch"),
            )
        )
    return out


def build_llm_context(
    data: dict[str, Any],
    *,
    max_total_chars: int = 56000,
    max_patch_chars_high: int = 12000,
    max_patch_chars_medium: int = 6000,
    schema_patch_max_change: int = 120,
) -> str:
    """拼接给 DeepSeek 的说明性文本（非完整仓库，仅筛选后的列表与补丁片段）。"""
    sha = data.get("sha") or ""
    html_url = data.get("html_url") or ""
    commit = data.get("commit") or {}
    msg = commit.get("message") or ""
    if not isinstance(msg, str):
        msg = str(msg)

    files = _parse_files(data)
    by_tier: dict[Tier, list[CommitFileInfo]] = {"high": [], "medium": [], "low": []}
    for fi in files:
        by_tier[classify_path(fi.filename)].append(fi)

    lines: list[str] = [
        "## Commit",
        f"SHA: {sha}",
        f"URL: {html_url}",
        "",
        "## message",
        msg.strip(),
        "",
    ]
    steam_urls = extract_steamdb_urls(msg)
    if steam_urls:
        lines.extend(["## SteamDB", *steam_urls, ""])

    lines.append("## 文件（按重要度）")
    for tier in ("high", "medium", "low"):
        subset = by_tier[tier]
        if not subset:
            continue
        lines.append(f"### {tier} ({len(subset)})")
        for fi in sorted(subset, key=lambda x: x.filename):
            lines.append(
                f"- [{fi.status}] {fi.filename}  +{fi.additions}/-{fi.deletions}"
            )
        lines.append("")

    lines.append("## 补丁片段（已截断；仅 high / 部分 medium）")
    parts: list[str] = []

    def one_patch(label: str, fi: CommitFileInfo, limit: int) -> str | None:
        if not fi.patch:
            return None
        chunk = fi.patch
        if len(chunk) > limit:
            chunk = chunk[:limit] + "\n... [patch truncated] ..."
        return f"### {label}: {fi.filename}\n```diff\n{chunk}\n```\n"

    for fi in sorted(by_tier["high"], key=lambda x: x.filename):
        b = one_patch("high", fi, max_patch_chars_high)
        if b:
            parts.append(b)

    schema_count = sum(
        1 for f in by_tier["medium"] if "/schemas/" in f.filename.lower()
    )
    for fi in sorted(by_tier["medium"], key=lambda x: x.filename):
        churn = fi.additions + fi.deletions
        path_low = fi.filename.replace("\\", "/").lower()
        if "dumpsource2/schemas/" in path_low:
            if schema_count > 35 and churn > schema_patch_max_change:
                continue
        lim = max_patch_chars_medium
        if churn > 400 and "/panorama/" in path_low:
            lim = min(lim, 4000)
        b = one_patch("medium", fi, lim)
        if b:
            parts.append(b)

    ctx = "\n".join(lines) + "\n" + "\n".join(parts)
    if len(ctx) > max_total_chars:
        ctx = ctx[: max_total_chars - 60] + "\n... [total context truncated] ...\n"
    logger.info(
        "LLM 上下文: %d 字符, high=%d medium=%d low=%d",
        len(ctx),
        len(by_tier["high"]),
        len(by_tier["medium"]),
        len(by_tier["low"]),
    )
    return ctx
