"""Microsoft Graph (Outlook) adapter: delegated OAuth for one mailbox, minimum permissions.

Scopes: Mail.ReadWrite (read, create reply drafts), Mail.Send (send an approved reply), offline_access (refresh token), User.Read.
The refresh token lives only in AWS Secrets Manager (rotated here when Microsoft issues a new one); access tokens stay in memory.
Nothing secret is ever logged or put in an error message.
"""

from __future__ import annotations

import html
import re
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Callable, Optional, Protocol

from ..models import Email
from .base import AdapterError, HttpFn, http_form, http_json

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPE = "Mail.ReadWrite Mail.Send offline_access User.Read"
SELECT = "id,internetMessageId,subject,from,toRecipients,receivedDateTime,body,conversationId,hasAttachments"


class SecretBox(Protocol):
    def read(self) -> dict: ...
    def write(self, value: dict) -> None: ...


def _text(content: str, content_type: str) -> str:
    if content_type.lower() == "html":
        content = re.sub(r"(?is)<(script|style).*?</\1>", " ", content)
        content = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", content)
        content = html.unescape(re.sub(r"<[^>]+>", " ", content))
    content = re.sub(r"[ \t]+", " ", content)
    return re.sub(r"\n\s*\n+", "\n\n", re.sub(r"[ \t]*\n[ \t]*", "\n", content)).strip()


def _expiry(now: float, minutes: int) -> str:
    return datetime.fromtimestamp(now + minutes * 60, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


class GraphAdapter:
    mode = "graph"
    supports_webhooks = True

    def __init__(self, secret: SecretBox, http: HttpFn = http_json, form: Callable = http_form, clock: Callable[[], float] = time.time):
        self._secret, self._http, self._form, self._clock = secret, http, form, clock
        self._access: Optional[str] = None
        self._expires = 0.0
        self._ids: dict[str, str] = {}

    # ------------------------------------------------------------------ OAuth (refresh-token grant)

    def _token(self) -> str:
        if self._access and self._clock() < self._expires - 60:
            return self._access
        cfg = self._secret.read()
        if not all(cfg.get(k) for k in ("tenant_id", "client_id", "refresh_token")):
            raise AdapterError("graph_not_connected", "Outlook is not connected: run connect_outlook.sh to sign in as the mailbox")
        status, body = self._form(f"https://login.microsoftonline.com/{cfg['tenant_id']}/oauth2/v2.0/token",
                                  {"grant_type": "refresh_token", "client_id": cfg["client_id"], "refresh_token": cfg["refresh_token"], "scope": SCOPE})
        if status != 200 or "access_token" not in body:
            reason = body.get("error", "unknown") if isinstance(body, dict) else "unknown"
            raise AdapterError("graph_auth", f"Microsoft refused the sign-in ({reason}); reconnect the mailbox", retryable=status >= 500)
        self._access, self._expires = body["access_token"], self._clock() + int(body.get("expires_in", 3600))
        if body.get("refresh_token") and body["refresh_token"] != cfg["refresh_token"]:
            self._secret.write({**cfg, "refresh_token": body["refresh_token"]})  # Microsoft rotates refresh tokens: keep the newest
        return self._access

    def _call(self, method: str, path: str, body: Optional[dict] = None, *, safe_to_retry: bool, extra_headers: Optional[dict] = None) -> dict:
        attempts = 3 if safe_to_retry else 1
        for attempt in range(attempts):
            try:
                status, payload = self._http(method, f"{GRAPH}{path}", {"Authorization": f"Bearer {self._token()}", **(extra_headers or {})}, body, 20.0)
            except AdapterError as err:
                if err.retryable and attempt + 1 < attempts:
                    time.sleep(0.4 * (attempt + 1))
                    continue
                raise
            if status < 300:
                return payload if isinstance(payload, dict) else {}
            retryable = status in (429, 503, 504) or status >= 500
            if retryable and attempt + 1 < attempts:
                time.sleep(0.4 * (attempt + 1))
                continue
            code = (payload.get("error", {}) or {}).get("code", "") if isinstance(payload, dict) else ""
            if status == 401:
                self._access = None
            raise AdapterError(f"graph_{status}", f"Microsoft Graph answered {status} {code}".strip(), retryable=retryable)
        raise AdapterError("graph_unreachable", "Microsoft Graph did not answer", retryable=True)

    # ------------------------------------------------------------------ mailbox

    def _to_email(self, m: dict) -> Email:
        sender = (m.get("from") or {}).get("emailAddress", {})
        message_id = m.get("internetMessageId") or m["id"]  # stable across folder moves, so idempotency survives them
        self._ids[message_id] = m["id"]
        body = m.get("body") or {}
        return Email(
            message_id=message_id, sender=sender.get("address") or "unknown@unknown", sender_name=sender.get("name") or "",
            to=[r["emailAddress"]["address"] for r in m.get("toRecipients", []) if r.get("emailAddress", {}).get("address")],
            subject=(m.get("subject") or "")[:998], body=_text(body.get("content", ""), body.get("contentType", "text"))[:20000],
            received_at=datetime.fromisoformat(m["receivedDateTime"].replace("Z", "+00:00")), conversation_id=m.get("conversationId"), has_attachments=bool(m.get("hasAttachments")),
        )

    def list_recent_emails(self, limit: int = 25) -> list[Email]:
        query = f"?$top={int(limit)}&$orderby=receivedDateTime desc&$select={SELECT}"
        data = self._call("GET", "/me/mailFolders/inbox/messages" + urllib.parse.quote(query, safe="?$=&,"), safe_to_retry=True, extra_headers={"Prefer": 'outlook.body-content-type="text"'})
        return [self._to_email(m) for m in data.get("value", [])]

    def _graph_id(self, message_id: str) -> str:
        if message_id in self._ids:
            return self._ids[message_id]
        flt = urllib.parse.quote(f"internetMessageId eq '{message_id.replace(chr(39), chr(39) * 2)}'", safe="")
        found = self._call("GET", f"/me/messages?$filter={flt}&$select=id,internetMessageId&$top=1", safe_to_retry=True).get("value", [])
        if not found:
            raise AdapterError("not_found", "the email is no longer in the mailbox")
        self._ids[message_id] = found[0]["id"]
        return found[0]["id"]

    def get_email(self, message_id: str) -> Email:
        return self._to_email(self._call("GET", f"/me/messages/{self._graph_id(message_id)}?$select={SELECT}", safe_to_retry=True, extra_headers={"Prefer": 'outlook.body-content-type="text"'}))

    def draft_reply(self, message_id: str, body: str) -> dict:
        """Creates a reply draft in the mailbox. Sends nothing."""
        draft = self._call("POST", f"/me/messages/{self._graph_id(message_id)}/createReply", {}, safe_to_retry=False)
        self._call("PATCH", f"/me/messages/{draft['id']}", {"body": {"contentType": "Text", "content": body}}, safe_to_retry=False)
        return {"draft_id": draft["id"]}

    def send_reply(self, message_id: str, body: str) -> dict:
        """Sends a reply. Called by the service only for an approved (or policy-permitted) proposal; never retried automatically."""
        self._call("POST", f"/me/messages/{self._graph_id(message_id)}/reply", {"comment": body}, safe_to_retry=False)
        return {"sent": True}

    # ------------------------------------------------------------------ change notifications (webhooks)

    def create_subscription(self, notification_url: str, client_state: str, minutes: int) -> dict:
        """Asks Graph to call `notification_url` when a message is created in the inbox. Graph validates the URL during this call."""
        return self._call("POST", "/subscriptions", {"changeType": "created", "notificationUrl": notification_url, "resource": "me/mailFolders('inbox')/messages",
                                                      "expirationDateTime": _expiry(self._clock(), minutes), "clientState": client_state}, safe_to_retry=False)

    def renew_subscription(self, subscription_id: str, minutes: int) -> dict:
        return self._call("PATCH", f"/subscriptions/{urllib.parse.quote(subscription_id, safe='')}", {"expirationDateTime": _expiry(self._clock(), minutes)}, safe_to_retry=True)

    def list_subscriptions(self) -> list[dict]:
        return self._call("GET", "/subscriptions", safe_to_retry=True).get("value", [])

    def delete_subscription(self, subscription_id: str) -> None:
        self._call("DELETE", f"/subscriptions/{urllib.parse.quote(subscription_id, safe='')}", safe_to_retry=False)


class SecretsManagerBox:
    """The Graph connection secret ({tenant_id, client_id, refresh_token}) in AWS Secrets Manager."""

    def __init__(self, secret_id: str, region: str = "us-east-1", client=None):
        import boto3

        self._id, self._sm = secret_id, client or boto3.client("secretsmanager", region_name=region)

    def read(self) -> dict:
        import json

        try:
            return json.loads(self._sm.get_secret_value(SecretId=self._id)["SecretString"])
        except Exception as err:  # not connected yet, or no permission: never leak the secret id's contents
            raise AdapterError("graph_not_connected", f"the Outlook connection secret is not available ({type(err).__name__})") from None

    def write(self, value: dict) -> None:
        import json

        self._sm.put_secret_value(SecretId=self._id, SecretString=json.dumps(value))
