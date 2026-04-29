"""Telegram Bot API로 카드 묶음 + 원문 링크 버튼을 전송한다."""

from __future__ import annotations

import json
import os
from io import BytesIO

import requests

API_BASE = "https://api.telegram.org"


def _token() -> str:
    return os.environ["TELEGRAM_BOT_TOKEN"]


def _chat_id() -> str:
    return os.environ["TELEGRAM_CHAT_ID"]


def send_media_group(images: list[BytesIO], caption: str | None = None) -> None:
    """카드 이미지(메모리 버퍼) 여러 장을 한 묶음으로 전송 (스와이프 가능)."""
    url = f"{API_BASE}/bot{_token()}/sendMediaGroup"

    media = []
    files = {}
    for i, buf in enumerate(images):
        key = f"photo{i}"
        item = {"type": "photo", "media": f"attach://{key}"}
        # 첫 장에만 캡션 달 수 있음
        if i == 0 and caption:
            item["caption"] = caption
            item["parse_mode"] = "HTML"
        media.append(item)
        buf.seek(0)
        filename = getattr(buf, "name", f"{key}.png")
        files[key] = (filename, buf, "image/png")

    data = {"chat_id": _chat_id(), "media": json.dumps(media)}
    response = requests.post(url, data=data, files=files, timeout=30)
    response.raise_for_status()


def send_link_button(article_url: str) -> None:
    """원문 보기 인라인 버튼만 달린 짧은 메시지."""
    url = f"{API_BASE}/bot{_token()}/sendMessage"

    payload = {
        "chat_id": _chat_id(),
        "text": "📖 원문이 궁금하다면 👇",
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": json.dumps(
            {
                "inline_keyboard": [
                    [{"text": "📖 원문 보기", "url": article_url}]
                ]
            }
        ),
    }
    response = requests.post(url, data=payload, timeout=30)
    response.raise_for_status()
