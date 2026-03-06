"""将更新信息格式化为可读的通知内容。"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING

from translator import translate_to_chinese

if TYPE_CHECKING:
    from steam_news_watcher import SteamNewsItem

logger = logging.getLogger(__name__)

CST = timezone(timedelta(hours=8))


def _translate_news(news: list[SteamNewsItem]) -> dict[str, str]:
    """统一翻译所有新闻内容，返回 {gid: 翻译文本} 映射。每条只翻译一次。"""
    translations = {}
    for n in news:
        clean_text = _strip_steam_markup(n.contents)
        translated = translate_to_chinese(clean_text)
        translations[n.gid] = _strip_steam_markup(translated) if translated else ""
    return translations


def format_news_text(news: list[SteamNewsItem], translations: dict[str, str] | None = None) -> str:
    if translations is None:
        translations = _translate_news(news)

    now = datetime.now(tz=CST).strftime("%Y-%m-%d %H:%M")
    lines = [f"CS2（{now}）更新内容：", "=" * 50, ""]
    for n in news:
        ts = datetime.fromtimestamp(n.date, tz=CST).strftime("%Y-%m-%d %H:%M")
        clean_text = _strip_steam_markup(n.contents)
        lines.append(f"{n.title}")
        lines.append(f"  时间: {ts}")
        lines.append(f"  链接: {n.url}")
        lines.append("")
        lines.append(clean_text)
        lines.append("")

        translated = translations.get(n.gid, "")
        if translated:
            lines.append("— 翻译如下 —")
            lines.append("")
            lines.append(translated)
            lines.append("")

        lines.append("-" * 50)
        lines.append("")
    lines.append("By 周佳和")
    return "\n".join(lines)


def format_news_html(news: list[SteamNewsItem], translations: dict[str, str] | None = None) -> str:
    if translations is None:
        translations = _translate_news(news)

    now = datetime.now(tz=CST).strftime("%Y-%m-%d %H:%M")
    items = []
    for n in news:
        ts = datetime.fromtimestamp(n.date, tz=CST).strftime("%Y-%m-%d %H:%M")
        content_html = _steam_markup_to_html(_esc(n.contents))

        translated = translations.get(n.gid, "")
        translated_html = ""
        if translated:
            translated_html = (
                '<hr style="border:none;border-top:1px dashed #ccc;margin:16px 0">'
                '<p style="color:#e67e22;font-weight:bold;margin:8px 0">翻译如下</p>'
                f'<div style="line-height:1.6">{_esc(translated).replace(chr(10), "<br>")}</div>'
            )

        items.append(
            f'<div style="margin-bottom:20px;padding:16px;border:1px solid #ddd;border-radius:8px">'
            f'<h3 style="margin:0 0 8px"><a href="{n.url}">{_esc(n.title)}</a></h3>'
            f'<small style="color:#666">{ts}</small>'
            f'<div style="margin-top:12px;line-height:1.6">{content_html}</div>'
            f'{translated_html}'
            f'</div>'
        )
    return (
        f'<h2>CS2（{now}）更新内容：</h2>'
        + "".join(items)
        + '<p style="margin-top:24px;color:#888;text-align:right;font-size:14px">By 周佳和</p>'
    )


def format_quick_alert_text(news: list[SteamNewsItem]) -> str:
    """生成快速提醒的纯文本（无翻译），用于第一时间通知。"""
    now = datetime.now(tz=CST).strftime("%Y-%m-%d %H:%M")
    lines = [
        f"[CS2 更新] 发现 {len(news)} 条新公告",
        "=" * 50,
        "",
        f"检测时间: {now}",
        "",
        "公告列表：",
        "",
    ]
    for n in news:
        ts = datetime.fromtimestamp(n.date, tz=CST).strftime("%Y-%m-%d %H:%M")
        lines.append(f"• {n.title}")
        lines.append(f"  时间: {ts}")
        lines.append(f"  链接: {n.url}")
        lines.append("")
    lines.append("翻译版邮件正在生成，稍后发送。")
    lines.append("")
    lines.append("By 周佳和")
    return "\n".join(lines)


def format_quick_alert_html(news: list[SteamNewsItem]) -> str:
    """生成快速提醒的 HTML（无翻译），用于第一时间通知。"""
    now = datetime.now(tz=CST).strftime("%Y-%m-%d %H:%M")
    items = []
    for n in news:
        ts = datetime.fromtimestamp(n.date, tz=CST).strftime("%Y-%m-%d %H:%M")
        items.append(
            f'<div style="margin-bottom:12px;padding:12px;border:1px solid #ddd;border-radius:6px">'
            f'<h3 style="margin:0 0 4px"><a href="{n.url}">{_esc(n.title)}</a></h3>'
            f'<small style="color:#666">{ts}</small>'
            f'</div>'
        )
    return (
        f'<h2>CS2 更新提醒 — 发现 {len(news)} 条新公告</h2>'
        f'<p style="color:#666">检测时间: {now}</p>'
        + "".join(items)
        + '<p style="margin-top:16px;color:#e67e22">翻译版邮件正在生成，稍后发送。</p>'
        + '<p style="margin-top:24px;color:#888;text-align:right;font-size:14px">By 周佳和</p>'
    )


def format_phone_summary(news: list[SteamNewsItem] | None = None) -> str:
    """生成简短的电话语音摘要（TTS 用）。"""
    parts = ["CS2 更新提醒。"]
    if news:
        parts.append(f"Steam发布了{len(news)}条新公告，标题：{news[0].title[:40]}。")
    parts.append("请尽快查看邮件了解详情。")
    return "".join(parts)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _steam_markup_to_html(text: str) -> str:
    """将 Steam BBCode 风格标记转为 HTML。"""
    text = re.sub(r'\[h1\](.*?)\[/h1\]', r'<h2>\1</h2>', text, flags=re.DOTALL)
    text = re.sub(r'\[h2\](.*?)\[/h2\]', r'<h3>\1</h3>', text, flags=re.DOTALL)
    text = re.sub(r'\[h3\](.*?)\[/h3\]', r'<h4>\1</h4>', text, flags=re.DOTALL)
    text = re.sub(r'\[b\](.*?)\[/b\]', r'<strong>\1</strong>', text, flags=re.DOTALL)
    text = re.sub(r'\[i\](.*?)\[/i\]', r'<em>\1</em>', text, flags=re.DOTALL)
    text = re.sub(r'\[u\](.*?)\[/u\]', r'<u>\1</u>', text, flags=re.DOTALL)
    text = re.sub(r'\[url=(.*?)\](.*?)\[/url\]', r'<a href="\1">\2</a>', text, flags=re.DOTALL)
    text = re.sub(r'\[img\](.*?)\[/img\]', r'<img src="\1" style="max-width:100%">', text)
    text = re.sub(r'\[p\](.*?)\[/p\]', r'<p>\1</p>', text, flags=re.DOTALL)
    text = text.replace('[list]', '<ul>').replace('[/list]', '</ul>')
    text = re.sub(r'\[\*\](.*?)\[/\*\]', r'<li>\1</li>', text, flags=re.DOTALL)
    text = re.sub(r'\[\*\](.*?)(?=\[\*\]|</ul>|\Z)', r'<li>\1</li>', text, flags=re.DOTALL)

    text = re.sub(r'\[/?[^\]]*\]', '', text)

    text = text.replace('\n', '<br>')
    return text


def _strip_steam_markup(text: str) -> str:
    """移除所有 Steam BBCode 标记，只保留纯文本。"""
    text = re.sub(r'\[url=(.*?)\](.*?)\[/url\]', r'\2', text, flags=re.DOTALL)
    text = re.sub(r'\[/?[^\]]*\]', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
