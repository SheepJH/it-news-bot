"""Sender 팩토리 — 환경변수 SENDER로 채널을 선택한다."""

from __future__ import annotations

import os

from .base import Sender


def get_sender(name: str | None = None) -> Sender:
    name = (name or os.getenv("SENDER", "telegram")).lower().strip()
    # lazy import: slack_sdk / Pillow 한쪽만 설치해도 동작
    if name == "telegram":
        from .telegram import TelegramSender

        return TelegramSender()
    if name == "slack":
        from .slack import SlackSender

        return SlackSender()
    raise ValueError(f"Unknown SENDER: {name!r}")


__all__ = ["Sender", "get_sender"]
