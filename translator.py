"""调用 DeepSeek API 将英文文本翻译为中文。"""

from __future__ import annotations

import logging

import requests

from config import Config

logger = logging.getLogger(__name__)

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"


def translate_to_chinese(text: str) -> str:
    """将英文文本翻译成中文，保留原有格式标记。失败时返回空字符串。"""
    if not Config.DEEPSEEK_API_KEY:
        logger.warning("DEEPSEEK_API_KEY 未配置，跳过翻译")
        return ""

    if not text.strip():
        return ""

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
                    {
                        "role": "system",
                        "content": (
                            "你是一个专业的游戏翻译。请将以下 CS2（Counter-Strike 2）"
                            "更新日志从英文翻译成简体中文。\n"
                            "要求：\n"
                            "1. 用纯文本输出，不要使用任何标记语言（不要用BBCode如[b][*]等，"
                            "也不要用Markdown如**、-等）\n"
                            "2. 保持原文的层级结构，用换行和缩进表示\n"
                            "3. 只翻译文字内容，不要添加任何解释\n"
                            "4. 代码、变量名、函数名保持英文原样不翻译"
                        ),
                    },
                    {"role": "user", "content": text},
                ],
                "temperature": 0.3,
            },
            timeout=60,
        )
        resp.raise_for_status()
        result = resp.json()
        translated = result["choices"][0]["message"]["content"]
        logger.info("DeepSeek 翻译完成，原文 %d 字 → 译文 %d 字", len(text), len(translated))
        return translated
    except Exception:
        logger.exception("DeepSeek 翻译请求失败")
        return ""
