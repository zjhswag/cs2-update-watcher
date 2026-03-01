"""通知模块：支持邮件 (SMTP)、Bark 推送（iOS）、阿里云语音电话。"""

from __future__ import annotations

import json
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from config import Config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 邮件 (SMTP)
# ---------------------------------------------------------------------------

def send_email(subject: str, body_text: str, body_html: str | None = None) -> bool:
    """通过 SMTP 发送邮件通知。"""
    if not Config.ENABLE_EMAIL:
        logger.debug("邮件通知已关闭")
        return False

    if not all([Config.SMTP_USER, Config.SMTP_PASSWORD, Config.NOTIFY_EMAIL]):
        logger.warning("邮件配置不完整，跳过邮件通知")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = Config.SMTP_USER
    msg["To"] = Config.NOTIFY_EMAIL

    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        if Config.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(Config.SMTP_HOST, Config.SMTP_PORT, timeout=30) as server:
                server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
                server.sendmail(Config.SMTP_USER, Config.NOTIFY_EMAIL, msg.as_string())
        else:
            with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=30) as server:
                server.starttls()
                server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
                server.sendmail(Config.SMTP_USER, Config.NOTIFY_EMAIL, msg.as_string())
        logger.info("邮件发送成功: %s", subject)
        return True
    except Exception:
        logger.exception("邮件发送失败")
        return False


# ---------------------------------------------------------------------------
# Bark 推送（iOS）
# ---------------------------------------------------------------------------

def send_bark(title: str, body: str) -> bool:
    """通过 Bark 推送通知到 iPhone。

    Bark 地址格式: https://api.day.app/你的Key
    """
    if not Config.ENABLE_BARK:
        logger.debug("Bark 推送已关闭")
        return False

    if not Config.BARK_URL:
        logger.warning("BARK_URL 未配置，跳过 Bark 推送")
        return False

    url = Config.BARK_URL.rstrip("/")

    payload = {
        "title": title,
        "body": body[:4000],
        "sound": Config.BARK_SOUND,
        "group": "CS2",
        "isArchive": "1",
        "level": "critical",
        "call": "1",
        "volume": "5",
    }

    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 200:
            logger.info("Bark 推送成功: %s", title)
            return True
        logger.warning("Bark 推送返回异常: %s", data)
        return False
    except Exception:
        logger.exception("Bark 推送失败")
        return False


# ---------------------------------------------------------------------------
# 阿里云语音电话
# ---------------------------------------------------------------------------

def make_phone_call(message: str) -> bool:
    """通过阿里云语音服务拨打电话通知。"""
    if not Config.ENABLE_PHONE:
        logger.debug("电话通知已关闭")
        return False

    if not all([
        Config.ALIYUN_ACCESS_KEY_ID,
        Config.ALIYUN_ACCESS_KEY_SECRET,
        Config.ALIYUN_TTS_CODE,
        Config.ALIYUN_CALLED_NUMBER,
    ]):
        logger.warning("阿里云语音配置不完整，跳过电话通知")
        return False

    try:
        from alibabacloud_dyvmsapi20170525.client import Client
        from alibabacloud_dyvmsapi20170525.models import SingleCallByTtsRequest
        from alibabacloud_tea_openapi.models import Config as AliConfig
    except ImportError:
        logger.error(
            "阿里云语音 SDK 未安装，请运行: "
            "pip install alibabacloud-dyvmsapi20170525"
        )
        return False

    try:
        ali_config = AliConfig(
            access_key_id=Config.ALIYUN_ACCESS_KEY_ID,
            access_key_secret=Config.ALIYUN_ACCESS_KEY_SECRET,
            endpoint="dyvmsapi.aliyuncs.com",
        )
        client = Client(ali_config)

        tts_param = json.dumps({"content": message[:200]}, ensure_ascii=False)

        request = SingleCallByTtsRequest(
            called_number=Config.ALIYUN_CALLED_NUMBER,
            called_show_number=Config.ALIYUN_SHOW_NUMBER or None,
            tts_code=Config.ALIYUN_TTS_CODE,
            tts_param=tts_param,
        )
        response = client.single_call_by_tts(request)
        body = response.body
        if body.code == "OK":
            logger.info("阿里云语音呼叫成功, CallId: %s", body.call_id)
            return True
        logger.warning("阿里云语音呼叫返回异常: Code=%s, Message=%s", body.code, body.message)
        return False
    except Exception:
        logger.exception("阿里云语音呼叫失败")
        return False


# ---------------------------------------------------------------------------
# 统一入口
# ---------------------------------------------------------------------------

def notify_all(
    subject: str,
    body_text: str,
    body_html: str | None = None,
    phone_message: str | None = None,
):
    """同时触发所有已启用的通知渠道。"""
    results = {}
    results["email"] = send_email(subject, body_text, body_html)
    results["bark"] = send_bark(subject, phone_message or subject)
    results["phone"] = make_phone_call(phone_message or subject)

    succeeded = [k for k, v in results.items() if v]
    failed = [k for k, v in results.items() if not v]
    if succeeded:
        logger.info("通知成功: %s", ", ".join(succeeded))
    if failed:
        logger.debug("通知跳过/失败: %s", ", ".join(failed))

    return results
