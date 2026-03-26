import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # --- 轮询间隔（秒）---
    POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))

    # --- DeepSeek API（翻译）---
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

    # --- Steam Web API ---
    STEAM_API_KEY = os.getenv("STEAM_API_KEY", "")
    STEAM_APP_ID = int(os.getenv("STEAM_APP_ID", "730"))

    # --- 邮件通知 (SMTP) ---
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.qq.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "")

    # --- Bark 推送（iOS）---
    BARK_URL = os.getenv("BARK_URL", "")
    BARK_SOUND = os.getenv("BARK_SOUND", "alarm")

    # --- 阿里云语音通知 ---
    ALIYUN_ACCESS_KEY_ID = os.getenv("ALIYUN_ACCESS_KEY_ID", "")
    ALIYUN_ACCESS_KEY_SECRET = os.getenv("ALIYUN_ACCESS_KEY_SECRET", "")
    ALIYUN_TTS_CODE = os.getenv("ALIYUN_TTS_CODE", "")
    ALIYUN_CALLED_NUMBER = os.getenv("ALIYUN_CALLED_NUMBER", "")
    ALIYUN_SHOW_NUMBER = os.getenv("ALIYUN_SHOW_NUMBER", "")

    # --- 通知开关 ---
    ENABLE_EMAIL = os.getenv("ENABLE_EMAIL", "true").lower() == "true"
    ENABLE_BARK = os.getenv("ENABLE_BARK", "false").lower() == "true"
    ENABLE_PHONE = os.getenv("ENABLE_PHONE", "false").lower() == "true"

    # --- GitHub（GameTracking commit 监听 + LLM 摘要）---
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
    GAMETRACKING_REPO = os.getenv("GAMETRACKING_REPO", "SteamTracking/GameTracking-CS2")
    GAMETRACKING_BRANCH = os.getenv("GAMETRACKING_BRANCH", "master")
    GAMETRACKING_COMMITS_PER_POLL = int(os.getenv("GAMETRACKING_COMMITS_PER_POLL", "15"))
    ENABLE_GAMETRACKING = os.getenv("ENABLE_GAMETRACKING", "true").lower() == "true"

    # --- 持久化 ---
    STATE_FILE = os.getenv("STATE_FILE", "watcher_state.json")
