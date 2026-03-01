"""持久化运行状态，避免重启后重复通知。"""

import json
import logging
import os
from pathlib import Path

from config import Config

logger = logging.getLogger(__name__)


def _state_path() -> Path:
    return Path(Config.STATE_FILE)


def load_state() -> dict:
    p = _state_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("状态文件损坏，将重新初始化")
        return {}


def save_state(data: dict) -> None:
    """原子写入：先写临时文件，再 rename 覆盖，防止写入中途崩溃导致状态丢失。"""
    p = _state_path()
    tmp = p.with_suffix(".json.tmp")
    try:
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(str(tmp), str(p))
    except OSError:
        logger.exception("保存状态文件失败")
