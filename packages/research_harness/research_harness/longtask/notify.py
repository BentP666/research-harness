"""Chat notification adapters for LongTask gate payloads.

Adapters are pure payload builders by default.  Actual webhook delivery is a
separate explicit action so local dogfooding never posts to third-party systems
by accident.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlparse

Provider = Literal["generic", "feishu", "slack"]


@dataclass(frozen=True)
class NotificationDeliveryResult:
    provider: Provider
    sent: bool
    status_code: int | None
    payload: dict[str, Any]
    message: str


def build_chat_notification(
    notification: dict[str, Any],
    *,
    provider: Provider = "generic",
) -> dict[str, Any]:
    """Convert a LongTask gate notification into a chat-provider payload."""
    if provider == "generic":
        return dict(notification)
    if provider == "feishu":
        return _build_feishu_card(notification)
    if provider == "slack":
        return _build_slack_message(notification)
    raise ValueError(f"unsupported notification provider: {provider}")


def deliver_chat_notification(
    notification: dict[str, Any],
    *,
    provider: Provider,
    webhook_url: str | None,
    send: bool = False,
    timeout_seconds: int = 10,
) -> NotificationDeliveryResult:
    """Dry-run or explicitly send a chat notification to a webhook."""
    payload = build_chat_notification(notification, provider=provider)
    if not send:
        return NotificationDeliveryResult(
            provider=provider,
            sent=False,
            status_code=None,
            payload=payload,
            message="dry-run: notification payload built but not sent",
        )
    if not webhook_url:
        return NotificationDeliveryResult(
            provider=provider,
            sent=False,
            status_code=None,
            payload=payload,
            message="webhook_url is required when send=true",
        )
    parsed = urlparse(webhook_url)
    if parsed.scheme != "https":
        return NotificationDeliveryResult(
            provider=provider,
            sent=False,
            status_code=None,
            payload=payload,
            message="webhook_url must use https when send=true",
        )
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        status_code = int(response.status)
    return NotificationDeliveryResult(
        provider=provider,
        sent=True,
        status_code=status_code,
        payload=payload,
        message=f"sent: HTTP {status_code}",
    )


def _build_feishu_card(notification: dict[str, Any]) -> dict[str, Any]:
    title = str(notification.get("title") or "LongTask approval")
    status = str(notification.get("status") or "pending")
    gate_type = str(notification.get("gate_type") or "gate")
    actions = dict(notification.get("actions") or {})
    buttons = []
    for key, action in actions.items():
        if not isinstance(action, dict) or not action.get("url"):
            continue
        buttons.append(
            {
                "tag": "button",
                "text": {
                    "tag": "plain_text",
                    "content": str(action.get("label") or key),
                },
                "type": "primary" if key == "approve" else "default",
                "url": str(action["url"]),
            }
        )
    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "blue",
                "title": {"tag": "plain_text", "content": title},
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**Status:** {status}\\n**Gate:** {gate_type}",
                    },
                },
                {"tag": "action", "actions": buttons},
            ],
        },
    }


def _build_slack_message(notification: dict[str, Any]) -> dict[str, Any]:
    title = str(notification.get("title") or "LongTask approval")
    status = str(notification.get("status") or "pending")
    gate_type = str(notification.get("gate_type") or "gate")
    actions = dict(notification.get("actions") or {})
    buttons = []
    for key, action in actions.items():
        if not isinstance(action, dict) or not action.get("url"):
            continue
        buttons.append(
            {
                "type": "button",
                "text": {"type": "plain_text", "text": str(action.get("label") or key)},
                "url": str(action["url"]),
                "style": "primary"
                if key == "approve"
                else "danger"
                if key == "reject"
                else None,
            }
        )
    for button in buttons:
        if button.get("style") is None:
            button.pop("style", None)
    return {
        "text": title,
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": title}},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Status:* {status}\\n*Gate:* {gate_type}",
                },
            },
            {"type": "actions", "elements": buttons},
        ],
    }
