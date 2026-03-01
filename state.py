"""持久化运行状态，避免重启后重复通知。"""

import json
import logging
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
    try:
        _state_path().write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        logger.exception("保存状态文件失败")
