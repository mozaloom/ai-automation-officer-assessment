"""Microsoft Graph adapter with fake HTTP: OAuth refresh and rotation, mapping, drafts vs sends, error handling."""

import json

import pytest

from inbox.adapters.base import AdapterError
from inbox.adapters.graph import GraphAdapter, _text

MSG = {"id": "AAMk1", "internetMessageId": "<abc@mail>", "subject": "Q4 report", "from": {"emailAddress": {"name": "Layla", "address": "layla@medgan.ai"}},
       "toRecipients": [{"emailAddress": {"address": "xpand@medgan.ai"}}], "receivedDateTime": "2026-10-05T08:30:00Z", "body": {"contentType": "html", "content": "<p>Hello&nbsp;team</p><br>Please <b>prepare</b> it"},
       "conversationId": "conv1", "hasAttachments": True}


class Box:
    def __init__(self):
        self.value = {"tenant_id": "T", "client_id": "C", "refresh_token": "r1"}
        self.writes = []

    def read(self):
        return dict(self.value)

    def write(self, v):
        self.value = v
        self.writes.append(v)


class Http:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append((method, url, headers, body))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def make(*responses, form=None, box=None, clock=lambda: 1000.0):
    box = box or Box()
    form = form or (lambda url, data, timeout=15.0: (200, {"access_token": "AT", "expires_in": 3600, "refresh_token": "r2"}))
    http = Http(*responses)
    return GraphAdapter(box, http=http, form=form, clock=clock), http, box


def test_lists_and_maps_messages_with_a_stable_id_and_plain_text():
    g, http, _ = make((200, {"value": [MSG]}))
    (email,) = g.list_recent_emails(10)
    assert email.message_id == "<abc@mail>" and email.sender == "layla@medgan.ai" and email.has_attachments
    assert "Please prepare it" in email.body and "<" not in email.body and "&nbsp;" not in email.body
    method, url, headers, _ = http.calls[0]
    assert method == "GET" and "mailFolders/inbox/messages" in url and headers["Authorization"] == "Bearer AT" and "text" in headers["Prefer"]


def test_refresh_token_grant_rotates_the_stored_token_and_caches_the_access_token():
    seen = []
    g, _, box = make((200, {"value": []}), (200, {"value": []}), form=lambda url, data, timeout=15.0: seen.append((url, data)) or (200, {"access_token": "AT", "expires_in": 3600, "refresh_token": "r2"}))
    g.list_recent_emails(); g.list_recent_emails()
    assert len(seen) == 1 and seen[0][0].startswith("https://login.microsoftonline.com/T/") and seen[0][1]["grant_type"] == "refresh_token"
    assert "Mail.Send" in seen[0][1]["scope"] and "Mail.Read " not in seen[0][1]["scope"] + " "
    assert box.value["refresh_token"] == "r2" and box.value["tenant_id"] == "T"


def test_not_connected_and_refused_sign_in_are_clear_errors_without_secrets():
    empty = Box(); empty.value = {}
    g, _, _ = make(box=empty)
    with pytest.raises(AdapterError) as err:
        g.list_recent_emails()
    assert err.value.code == "graph_not_connected" and "connect_outlook" in str(err.value)
    g, _, _ = make(form=lambda *a, **k: (400, {"error": "invalid_grant"}))
    with pytest.raises(AdapterError) as err:
        g.list_recent_emails()
    assert err.value.code == "graph_auth" and "r1" not in str(err.value) and not err.value.retryable


def test_a_draft_is_created_but_not_sent():
    g, http, _ = make((200, {"value": [MSG]}), (201, {"id": "DRAFT1"}), (200, {}))
    g.list_recent_emails()
    assert g.draft_reply("<abc@mail>", "Thanks, will do.") == {"draft_id": "DRAFT1"}
    assert [c[0] for c in http.calls[1:]] == ["POST", "PATCH"] and http.calls[1][1].endswith("/AAMk1/createReply")
    assert not any(c[1].endswith("/reply") or c[1].endswith("/send") for c in http.calls)  # nothing was sent
    assert http.calls[2][3]["body"]["content"] == "Thanks, will do."


def test_send_reply_is_a_single_never_retried_call_and_looks_up_unknown_ids():
    g, http, _ = make((200, {"value": [{"id": "AAMk9"}]}), (503, {}), )
    with pytest.raises(AdapterError) as err:
        g.send_reply("<other@mail>", "Approved text")
    assert err.value.retryable and http.calls[-1][1].endswith("/AAMk9/reply") and http.calls[-1][3] == {"comment": "Approved text"}
    assert sum(1 for c in http.calls if c[1].endswith("/reply")) == 1


def test_reads_retry_and_errors_are_classified(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    g, http, _ = make((429, {}), (200, {"value": []}))
    assert g.list_recent_emails() == [] and len(http.calls) == 2
    g, _, _ = make((403, {"error": {"code": "ErrorAccessDenied"}}))
    with pytest.raises(AdapterError) as err:
        g.list_recent_emails()
    assert err.value.code == "graph_403" and not err.value.retryable and "ErrorAccessDenied" in str(err.value)


def test_html_to_text():
    assert _text("<style>x{}</style><p>A</p><p>B &amp; C</p>", "html") == "A\n B & C".replace("\n ", "\n")
    assert _text("plain  text", "text") == "plain text"
