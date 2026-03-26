"""使用 DeepSeek 将 GameTracking commit 上下文总结为简体中文要点。"""

from __future__ import annotations

import logging

import requests

from config import Config

logger = logging.getLogger(__name__)

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"


def summarize_commit_for_notification(context: str) -> str:
    """根据筛选后的 commit 上下文，输出带 ①②③ 编号的更新摘要。"""
    if not Config.DEEPSEEK_API_KEY:
        logger.warning("DEEPSEEK_API_KEY 未配置，无法生成摘要")
        return ""
    if not (context or "").strip():
        return ""

    system = (
        "你是 Counter-Strike 2（CS2）技术更新分析助手。\n"
        "用户会提供 GameTracking-CS2 仓库单次 commit 的机器可读摘要：含提交说明、"
        "按重要度分级的文件列表、以及少量高价值 diff 片段。\n\n"
        "要求：\n"
        "1. 只用简体中文输出。\n"
        "2. 使用圆圈数字编号，每项单独一行，格式严格为：① ② ③ …"
        "（Unicode 圆圈数字，后接全角空格，再写内容）。\n"
        "3. 每条应简洁可读，风格类似游戏更新要点（玩家/对局/工坊/UI/音频/网络/GC 等），"
        "合并相近条目，优先 5～12 条；若变更极少可少于 5 条。\n"
        "4. 只依据材料中可见内容归纳，不要编造材料中不存在的功能名或结论；"
        "对纯字符串表/行号漂移类噪声可用一条概括「大量底层/字符串资源同步」之类。\n"
        "5. 不要输出 Markdown、不要代码围栏、不要前言后记。"
    )

    try:
        resp = requests.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {Config.DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": context},
                ],
                "temperature": 0.35,
            },
            timeout=120,
        )
        resp.raise_for_status()
        result = resp.json()
        choices = result.get("choices") or []
        if not choices:
            logger.warning("DeepSeek 返回空 choices")
            return ""
        text = (choices[0].get("message") or {}).get("content", "") or ""
        text = text.strip()
        if not text:
            logger.warning("DeepSeek 返回空摘要")
            return ""
        logger.info("DeepSeek 摘要完成，输出长度 %d", len(text))
        return text
    except Exception:
        logger.exception("DeepSeek 摘要请求失败")
        return ""
