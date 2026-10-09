"""Graph change notifications (MOCK Graph HTTP and a scripted mailbox): subscription lifecycle, handshake, authenticity, and the sync it triggers."""

import json

import pytest

from helpers import make_email
from inbox import api
from inbox.adapters.base import AdapterError
from inbox.adapters.sample import SampleMail
from inbox.store import MemoryStore
from inbox.webhook import MINUTES, Webhooks, valid_validation_token
from test_graph import make

URL = "https://api.example.com/v1/inbox/webhook"


class FakeMail:
    supports_webhooks = True
    mode = "graph"

    def __init__(self):
        self.subs, self.calls, self.fail_renew = {}, [], None

    def list_subscriptions(self):
        return [dict(s) for s in self.subs.values()]

    def delete_subscription(self, sid):
        self.calls.append(("delete", sid)); self.subs.pop(sid)

    def create_subscription(self, url, state, minutes):
        self.calls.append(("create", minutes)); sid = f"sub-{len(self.calls)}"
        self.subs[sid] = {"id": sid, "notificationUrl": url, "clientState": state, "expirationDateTime": "2026-10-12T00:00:00Z"}
        return self.subs[sid]

    def renew_subscription(self, sid, minutes):
        self.calls.append(("renew", sid))
        if self.fail_renew:
            raise self.fail_renew
        return self.subs[sid]


def test_graph_adapter_subscription_calls():
    g, http, _ = make((201, {"id": "S1"}), (200, {"id": "S1"}), (200, {"value": [{"id": "S1"}]}), (204, {}))
    assert g.create_subscription(URL, "state", 4200)["id"] == "S1"
    g.renew_subscription("S1", 4200); assert g.list_subscriptions() == [{"id": "S1"}]; g.delete_subscription("S1")
    (m1, u1, _, b1), (m2, u2, _, b2), (m3, u3, _, _), (m4, u4, _, _) = http.calls
    assert (m1, u1.endswith("/subscriptions")) == ("POST", True) and b1["changeType"] == "created" and b1["notificationUrl"] == URL and b1["clientState"] == "state"
    assert b1["resource"] == "me/mailFolders('inbox')/messages" and b1["expirationDateTime"].endswith(".000Z")
    assert (m2, u2.endswith("/subscriptions/S1")) == ("PATCH", True) and "expirationDateTime" in b2 and m3 == "GET" and m4 == "DELETE"


def test_ensure_creates_then_renews_and_heals_a_lost_subscription():
    mail, store = FakeMail(), MemoryStore()
    hooks = Webhooks(store, mail)
    first = hooks.ensure(URL)
    assert first["state"] == "active" and mail.calls == [("create", MINUTES)] and len(first["client_state"]) >= 32
    hooks.ensure(URL)
    assert mail.calls[-1][0] == "renew" and len([c for c in mail.calls if c[0] == "create"]) == 1
    mail.fail_renew = AdapterError("graph_404", "gone")  # Graph forgot it: create a fresh one, never leave a stale one
    healed = hooks.ensure(URL)
    assert healed["subscription_id"] != first["subscription_id"] and len(mail.subs) == 1 and healed["client_state"] != first["client_state"]


def test_a_temporary_renewal_failure_keeps_the_subscription_and_is_reported():
    mail, store = FakeMail(), MemoryStore()
    hooks = Webhooks(store, mail); hooks.ensure(URL)
    mail.fail_renew = AdapterError("graph_503", "busy", retryable=True)
    with pytest.raises(AdapterError):
        hooks.ensure(URL)
    assert store.get_meta("webhook")["state"] == "error" and len(mail.subs) == 1 and hooks.status()["error"] == "graph_503"


def test_only_our_client_state_is_genuine():
    mail, store = FakeMail(), MemoryStore()
    hooks = Webhooks(store, mail)
    assert not hooks.genuine({"value": [{"clientState": "x"}]})  # nothing subscribed yet
    state = hooks.ensure(URL)["client_state"]
    assert hooks.genuine({"value": [{"clientState": state}]}) and hooks.genuine({"value": [{"clientState": "no"}, {"clientState": state}]})
    for bad in ({"value": [{"clientState": "wrong"}]}, {"value": []}, {"value": "x"}, {}, [], None, {"value": [None, 5, {"clientState": 7}]}):
        assert not hooks.genuine(bad)


def test_validation_token_rules():
    assert valid_validation_token("Validation: Testing client application reachability for subscription Request-Id: 56d00e3a-c411-4f94-bec3-7d757de8b844")  # what Graph really sends
    assert valid_validation_token("abc-123_XYZ")
    assert not valid_validation_token("") and not valid_validation_token(None) and not valid_validation_token("a\nb") and not valid_validation_token("é") and not valid_validation_token("x" * 2000)


def hook_event(query=None, body=None):
    return {"httpMethod": "POST", "resource": "/inbox/webhook", "queryStringParameters": query, "body": json.dumps(body) if body is not None else None, "requestContext": {}}


def call_hook(world, **kw):
    sent = []
    out = api.handler(hook_event(**kw), None, service=world.svc, invoke_async=sent.append)
    return out, sent


@pytest.fixture()
def live_world(world):
    world.svc.mail = FakeMail()
    world.state = Webhooks(world.store, world.svc.mail).ensure(URL)["client_state"]
    return world


def test_handshake_echoes_the_token_as_plain_text(live_world):
    out, sent = call_hook(live_world, query={"validationToken": "tok-123"})
    assert out["statusCode"] == 200 and out["body"] == "tok-123" and out["headers"]["Content-Type"] == "text/plain" and sent == []
    graph_like = "Validation: Testing client application reachability for subscription Request-Id: 56d00e3a-c411-4f94-bec3-7d757de8b844"
    assert call_hook(live_world, query={"validationToken": graph_like})[0]["body"] == graph_like
    assert call_hook(live_world, query={"validationToken": "<script>\n"})[0]["statusCode"] == 400


def test_a_genuine_notification_starts_one_sync_as_the_system_and_a_forged_one_does_nothing(live_world):
    forged, sent = call_hook(live_world, body={"value": [{"clientState": "guess"}]})
    assert forged["statusCode"] == 401 and sent == []
    ok, sent = call_hook(live_world, body={"value": [{"clientState": live_world.state, "changeType": "created"}]})
    assert ok["statusCode"] == 202 and len(sent) == 1 and sent[0]["job"] == "sync" and sent[0]["principal"]["user_id"] == "system:webhook"
    assert call_hook(live_world, body=None)[0]["statusCode"] == 401  # no body: nothing to authenticate
    assert api.handler({**hook_event(), "body": "{not json"}, None, service=live_world.svc)["statusCode"] == 400


def test_a_notification_during_a_running_sync_asks_for_one_more_pass(live_world):
    note = {"value": [{"clientState": live_world.state}]}
    _, first = call_hook(live_world, body=note)
    _, second = call_hook(live_world, body=note)  # first sync still "running"
    assert len(first) == 1 and second == [] and live_world.store.get_meta("sync")["again"] is True


def test_worker_goes_round_again_when_asked_and_stops(world):
    world.svc.mail = SampleMail(emails=[make_email("w-1")])
    passes = []
    original = world.svc.mail.list_recent_emails
    world.svc.mail.list_recent_emails = lambda n: passes.append(1) or original(n)
    world.store.put_meta("sync", {"state": "running", "again": True, "started_at": "t", "lease_until": "2999"})
    principal = api._system_principal(world.svc)
    api._run_sync(world.svc, {"job": "sync", "principal": principal.model_dump()})
    assert len(passes) == 2 and not world.store.get_meta("sync")["again"] and world.store.get_meta("sync")["state"] == "done"


def test_hourly_job_renews_and_catches_up_but_does_nothing_for_a_sample_mailbox(live_world):
    sent = []
    out = api.handler({"job": "renew", "notification_url": URL}, None, service=live_world.svc, invoke_async=sent.append)
    assert out == {"webhook": "active"} and len(sent) == 1 and sent[0]["job"] == "sync"
    live_world.svc.mail.fail_renew = AdapterError("graph_503", "busy", retryable=True)
    out = api.handler({"job": "renew", "notification_url": URL}, None, service=live_world.svc, invoke_async=lambda p: None)
    assert out["webhook"] == "error"  # reported, never raised: the schedule must not crash
    live_world.svc.mail = SampleMail(emails=[])
    sample = []
    assert api.handler({"job": "renew", "notification_url": URL}, None, service=live_world.svc, invoke_async=sample.append) == {"webhook": "unavailable"} and sample == []


def test_config_reports_the_webhook_state_without_the_secret(live_world):
    from test_api import call
    live_world.async_calls = []
    status, body = call(live_world, "GET", "/inbox/config")
    assert status == 200 and body["webhook"]["state"] == "active" and "client_state" not in json.dumps(body["webhook"])
