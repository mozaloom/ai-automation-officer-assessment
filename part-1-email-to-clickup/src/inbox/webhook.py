"""Microsoft Graph change notifications: keep one inbox subscription alive and decide whether an incoming call is genuine.

A notification only says "something new arrived". It is never trusted for content: a genuine one (matching clientState) just starts the normal
sync, which reads the mailbox itself. Everything else stays in the normal pipeline, so the webhook adds no new decision logic.
"""

from __future__ import annotations

import hmac
import re
import secrets
from datetime import timedelta
from typing import Any, Optional

from .adapters.base import AdapterError
from .store import iso, utcnow

MINUTES = 4200  # Graph allows at most 4230 minutes (about 70 hours) for mail subscriptions
_TOKEN = re.compile(r"^[\x20-\x7e]{1,1024}$")  # printable ASCII only: the validation token is echoed back as text/plain


def valid_validation_token(token: Optional[str]) -> bool:
    return bool(token) and bool(_TOKEN.fullmatch(token))


class Webhooks:
    def __init__(self, store: Any, mail: Any):
        self.store, self.mail = store, mail

    def ensure(self, notification_url: str) -> dict:
        """Create the subscription, or renew it. Called by the hourly schedule, so a lost subscription heals itself within the hour."""
        meta = self.store.get_meta("webhook") or {}
        if meta.get("subscription_id") and meta.get("url") == notification_url and meta.get("client_state"):
            try:
                self.mail.renew_subscription(meta["subscription_id"], MINUTES)
                return self._save({**meta, "state": "active", "error": None})
            except AdapterError as err:
                if err.code != "graph_404":  # the subscription still exists: a temporary problem, try again next hour
                    self._save({**meta, "state": "error", "error": err.code})
                    raise
        for old in self.mail.list_subscriptions():  # never leave a stale subscription of ours behind
            if old.get("notificationUrl") == notification_url:
                self.mail.delete_subscription(old["id"])
        client_state = secrets.token_urlsafe(32)
        self._save({"state": "creating", "url": notification_url, "client_state": client_state, "subscription_id": None})  # before Graph can call us
        try:
            sub = self.mail.create_subscription(notification_url, client_state, MINUTES)
        except AdapterError as err:
            self._save({"state": "error", "url": notification_url, "client_state": client_state, "subscription_id": None, "error": err.code})
            raise
        return self._save({"state": "active", "url": notification_url, "client_state": client_state, "subscription_id": sub.get("id"), "error": None,
                           "expires_at": sub.get("expirationDateTime")})

    def _save(self, meta: dict) -> dict:
        meta = {**meta, "renewed_at": iso(utcnow())}
        self.store.put_meta("webhook", meta)
        return meta

    def genuine(self, payload: Any) -> bool:
        """True when at least one notification carries our secret clientState. Constant-time comparison."""
        expected = (self.store.get_meta("webhook") or {}).get("client_state")
        if not expected or not isinstance(payload, dict):
            return False
        return any(isinstance(n, dict) and isinstance(n.get("clientState"), str) and hmac.compare_digest(n["clientState"].encode(), expected.encode())
                   for n in payload.get("value", []) if isinstance(payload.get("value"), list))

    def status(self) -> dict:
        meta = self.store.get_meta("webhook") or {}
        return {"supported": bool(getattr(self.mail, "supports_webhooks", False)), "state": meta.get("state", "off"), "expires_at": meta.get("expires_at"),
                "renewed_at": meta.get("renewed_at"), "error": meta.get("error")}
