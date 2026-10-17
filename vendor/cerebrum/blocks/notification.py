"""Notification Hub Block — One endpoint for Email, Webhook, Slack, MCP."""

import os
import time
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

from vendor.cerebrum.core.universal_base import UniversalBlock
from vendor.cerebrum.core.typed_block import TypedBlock, Schema, ContentType


class NotificationEvent(BaseModel):
    """Event emitted by the notification hub."""
    event_type: str = Field(..., description="Event type: cost_threshold, swarm_complete, capture_done, etc.")
    source_block: str = Field(default="unknown")
    payload: Dict = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


class NotificationHub:
    """Event bus for pub/sub notifications across all blocks."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, callback: Callable):
        """Subscribe to an event type. Callback receives NotificationEvent."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable):
        """Unsubscribe from an event type."""
        if event_type in self._subscribers:
            self._subscribers[event_type] = [cb for cb in self._subscribers[event_type] if cb != callback]

    async def emit(self, event: NotificationEvent):
        """Publish event to all subscribers."""
        subscribers = self._subscribers.get(event.event_type, [])
        for callback in subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception:
                pass  # Non-blocking — don't let one subscriber break others

    async def send_and_emit(self, channel: str, message: str, result: Dict, source: str = "notification"):
        """Emit a delivery event after sending."""
        await self.emit(NotificationEvent(
            event_type=f"notification.{channel}",
            source_block=source,
            payload={"message": message, "result": result},
            timestamp=time.time()
        ))

    def get_subscriber_counts(self) -> Dict[str, int]:
        """Get count of subscribers per event type."""
        return {et: len(subs) for et, subs in self._subscribers.items()}


import asyncio

# Global instance for cross-block pub/sub
notification_hub = NotificationHub()


class NotificationBlock(TypedBlock):
    """Unified notification dispatcher."""

    name = "notification"
    version = "1.0.0"
    description = "Send notifications via Email, Webhook, Slack, or MCP"
    layer = 2
    tags = ["notification", "messaging", "integration", "core"]
    requires = []

    input_schema = Schema(
        content_type=ContentType.JSON,
        required_fields=["channel", "message"],
        optional_fields=["to", "subject", "html", "url", "headers", "payload", "blocks"],
        format_hints={}
    )

    output_schema = Schema(
        content_type=ContentType.JSON,
        required_fields=["status", "channel"],
        optional_fields=["sent", "message_id", "http_status", "response_preview"],
        format_hints={}
    )

    accepted_input_types = ["JSON", "NotificationRequest"]
    produced_output_types = ["JSON", "NotificationResult"]


    async def execute(self, input_data: Any, params: Dict = None) -> Dict:
        params = params or {}
        action = params.get("action") if isinstance(params, dict) else None
        if isinstance(input_data, str):
            input_data = {"message": input_data}
        return await super().execute(input_data, params)

    def validate_input(self, data: Any) -> Dict[str, Any]:
        if isinstance(data, dict) and data.get("action") in {"health", "status", "list", "history", "get", "unschedule", "broadcast", "search", "summarize", "structure", "execute_async"}:
            return {"valid": True, "errors": [], "warnings": [], "data": data}
        return super().validate_input(data)

    default_config = {
        "sendgrid_api_key": os.getenv("SENDGRID_API_KEY", ""),
        "smtp_host": os.getenv("SMTP_HOST", ""),
        "smtp_port": int(os.getenv("SMTP_PORT", "587")),
        "smtp_user": os.getenv("SMTP_USER", ""),
        "smtp_pass": os.getenv("SMTP_PASS", ""),
        "slack_webhook_url": os.getenv("SLACK_WEBHOOK_URL", ""),
        "default_from_email": os.getenv("DEFAULT_FROM_EMAIL", "cerebrum@localhost"),
    }

    ui_schema = {
        "input": {
            "type": "json",
            "accept": None,
            "placeholder": '{"channel": "email", "to": "ops@example.com", "message": "Hello"}',
            "multiline": True,
        },
        "output": {
            "type": "json",
            "fields": [
                {"name": "channel", "type": "text", "label": "Channel"},
                {"name": "sent", "type": "boolean", "label": "Sent"},
                {"name": "message_id", "type": "text", "label": "Message ID"},
            ],
        },
        "params": [
            {
                "name": "action",
                "type": "select",
                "label": "Action",
                "options": ["send", "broadcast", "health"],
                "default": "send",
            },
        ],
        "quick_actions": [
            {"icon": "✉️", "label": "Send Email", "prompt": "Send an email notification"},
            {"icon": "🔗", "label": "Webhook", "prompt": "POST to webhook URL"},
        ],
    }

    async def process(self, input_data: Any, params: Dict = None) -> Dict:
        params = params or {}
        data = input_data if isinstance(input_data, dict) else {}
        action = params.get("action") or data.get("action", "send")

        if action == "send":
            return await self._send(data)
        elif action == "broadcast":
            return await self._broadcast(data)
        elif action == "health":
            return self._health_check()
        else:
            return {"status": "error", "error": f"Unknown action: {action}"}

    # ── Core Send ──────────────────────────────────────────────────────────────

    async def _send(self, data: Dict) -> Dict:
        channel = (data.get("channel") or "").lower()
        if not channel:
            return {
                "status": "error",
                "error": "channel required: one of mcp | email | webhook | slack",
            }
        handlers = {
            "mcp": self._send_mcp,
            "email": self._send_email,
            "webhook": self._send_webhook,
            "slack": self._send_slack,
        }
        handler = handlers.get(channel)
        if not handler:
            return {"status": "error", "error": f"Unknown channel: {channel}"}
        result = await handler(data)

        # Emit event for subscribers (non-blocking)
        if result.get("status") == "success":
            try:
                await notification_hub.send_and_emit(
                    channel=channel,
                    message=data.get("message", ""),
                    result=result,
                    source=self.name,
                )
            except Exception:
                pass

        return result

    async def _broadcast(self, data: Dict) -> Dict:
        """Send to multiple channels at once."""
        channels = data.get("channels") or []
        if not channels:
            return {
                "status": "error",
                "error": "channels required: any of mcp | email | webhook | slack",
            }
        results = []
        for channel in channels:
            result = await self._send({**data, "channel": channel})
            results.append({"channel": channel, **result})
        sent_all = all(r.get("status") == "success" for r in results)
        return {
            "status": "success" if sent_all else "partial",
            "results": results,
        }

    # ── MCP (Model Context Protocol) ───────────────────────────────────────────

    async def _send_mcp(self, data: Dict) -> Dict:
        """Send notification via MCP — calls a block as an MCP tool."""
        import json
        block_name = data.get("block") or data.get("tool")
        payload = data.get("payload") or data.get("message") or data.get("input", {})
        params = data.get("params", {})

        if not block_name:
            return {"status": "error", "error": "block or tool name required for MCP channel"}

        try:
            from vendor.cerebrum.blocks import BLOCK_REGISTRY

            try:
            except ImportError:
                # Standalone/vendored runtime (a factory-built platform):
                # there is no platform wiring, tier gate or memory cache to
                # thread through, and plain construction is exactly what the
                # block adapters themselves do. Inside the Blocks platform
                # the import succeeds and nothing changes.
                def _create_block_instance(block_class, config=None, allow_platform=True):
                    return block_class()

            if block_name not in BLOCK_REGISTRY:
                return {"status": "error", "error": f"Block '{block_name}' not found"}

            block = _create_block_instance(BLOCK_REGISTRY[block_name])
            result = await block.execute(payload, params)
            return {
                "status": "success",
                "channel": "mcp",
                "sent": True,
                "block": block_name,
                "result_preview": json.dumps(result, default=str)[:500],
            }
        except Exception as e:
            return {"status": "error", "error": f"MCP dispatch failed: {e}"}

    # ── Email ──────────────────────────────────────────────────────────────────

    async def _send_email(self, data: Dict) -> Dict:
        import httpx
        to = data.get("to") or data.get("email")
        subject = data.get("subject", "Cerebrum Notification")
        body = data.get("message") or data.get("body", "")
        html = data.get("html", "")

        if not to:
            return {"status": "error", "error": "to (email) required"}

        # Try SendGrid first
        sg_key = self.config.get("sendgrid_api_key")
        if sg_key:
            return await self._send_sendgrid(to, subject, body, html, sg_key)

        # Fallback SMTP
        return await self._send_smtp(to, subject, body, html)

    async def _send_sendgrid(self, to: str, subject: str, body: str, html: str, api_key: str) -> Dict:
        import httpx
        payload = {
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": self.config.get("default_from_email")},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": body},
            ],
        }
        if html:
            payload["content"].append({"type": "text/html", "value": html})

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
                if resp.status_code in (200, 202):
                    return {"status": "success", "channel": "email", "sent": True}
                return {"status": "error", "error": f"SendGrid error: {resp.status_code}"}
        except Exception as e:
            return {"status": "error", "error": f"SendGrid failed: {e}"}

    async def _send_smtp(self, to: str, subject: str, body: str, html: str) -> Dict:
        host = self.config.get("smtp_host")
        port = self.config.get("smtp_port", 587)
        user = self.config.get("smtp_user")
        password = self.config.get("smtp_pass")
        from_email = self.config.get("default_from_email")

        if not host:
            return {"status": "error", "error": "SMTP not configured (set SMTP_HOST or SENDGRID_API_KEY)"}

        try:
            import aiosmtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = from_email
            msg["To"] = to
            msg.attach(MIMEText(body, "plain"))
            if html:
                msg.attach(MIMEText(html, "html"))

            await aiosmtplib.send(
                msg,
                hostname=host,
                port=port,
                username=user,
                password=password,
                start_tls=True if port == 587 else False,
            )
            return {"status": "success", "channel": "email", "sent": True}
        except ImportError:
            return {"status": "error", "error": "aiosmtplib not installed. Run: pip install aiosmtplib"}
        except Exception as e:
            return {"status": "error", "error": f"SMTP failed: {e}"}

    # ── Webhook ────────────────────────────────────────────────────────────────

    async def _send_webhook(self, data: Dict) -> Dict:
        import httpx
        # `to` is the unified recipient field used by every other channel
        # (an email address, a Slack channel). When the caller picks
        # channel=webhook and passes a URL through that field, accept it.
        url = data.get("url") or data.get("webhook_url")
        if not url:
            candidate = data.get("to")
            if isinstance(candidate, str) and candidate.startswith(("http://", "https://")):
                url = candidate
        payload = data.get("payload") or data.get("message") or data.get("body", {})
        headers = data.get("headers", {"Content-Type": "application/json"})
        method = data.get("method", "POST").upper()

        if not url:
            return {"status": "error", "error": "url required (set 'url' or pass an http(s) URL as 'to')"}

        # SSRF guard: a caller-supplied webhook URL must resolve to a public
        # host, or it could read cloud-metadata / internal services (the method
        # is caller-chosen and the response body is returned to the caller).
        from vendor.cerebrum.core.url_guard import validate_public_url, UnsafeURLError
        try:
            url = validate_public_url(url)
        except UnsafeURLError as e:
            return {"status": "error", "error": f"unsafe webhook url: {e}"}

        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
                if method == "GET":
                    resp = await client.get(url, headers=headers, params=payload if isinstance(payload, dict) else {})
                else:
                    json_payload = payload if isinstance(payload, dict) else {"message": str(payload)}
                    resp = await client.request(method, url, headers=headers, json=json_payload)
                return {
                    "status": "success",
                    "channel": "webhook",
                    "sent": True,
                    "http_status": resp.status_code,
                    "response_preview": resp.text[:500],
                }
        except Exception as e:
            return {"status": "error", "error": f"Webhook failed: {e}"}

    # ── Slack ──────────────────────────────────────────────────────────────────

    async def _send_slack(self, data: Dict) -> Dict:
        import httpx
        url = data.get("webhook_url") or self.config.get("slack_webhook_url")
        text = data.get("message") or data.get("text", "")
        blocks = data.get("blocks")

        if not url:
            return {"status": "error", "error": "Slack webhook URL not configured"}

        payload = {"text": text}
        if blocks:
            payload["blocks"] = blocks

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200 and resp.text == "ok":
                    return {"status": "success", "channel": "slack", "sent": True}
                return {"status": "error", "error": f"Slack error: {resp.status_code} {resp.text}"}
        except Exception as e:
            return {"status": "error", "error": f"Slack failed: {e}"}

    # ── Health ─────────────────────────────────────────────────────────────────

    def _health_check(self) -> Dict:
        channels = []
        channels.append("mcp")
        if self.config.get("sendgrid_api_key") or self.config.get("smtp_host"):
            channels.append("email")
        if self.config.get("slack_webhook_url"):
            channels.append("slack")
        channels.append("webhook")
        return {
            "status": "healthy",
            "available_channels": channels,
            "block_id": self.name,
            "version": self.version,
        }
