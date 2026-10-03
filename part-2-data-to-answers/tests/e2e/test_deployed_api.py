"""Calls the DEPLOYED API (API Gateway -> AgentCore -> S3). Run: pytest -m e2e

Needs AWS credentials (profile with cognito-idp:AdminInitiateAuth) and either build/outputs.json
(written by cdk deploy) or API_URL / USER_POOL_ID / CLIENT_ID, plus DEMO_EMAIL / DEMO_PASSWORD
(or the git-ignored .demo-credentials file).
"""

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import boto3
import pytest

pytestmark = pytest.mark.e2e
ROOT = Path(__file__).resolve().parents[2]
ORIGIN = os.environ.get("WEB_ORIGIN", "https://xpand.medgan.ai")


def _outputs() -> dict:
    path = ROOT / "build" / "outputs.json"
    return next(iter(json.loads(path.read_text()).values())) if path.exists() else {}


@pytest.fixture(scope="module")
def cfg():
    out = _outputs()
    creds = {}
    if (ROOT / ".demo-credentials").exists():
        creds = dict(line.strip().split("=", 1) for line in (ROOT / ".demo-credentials").read_text().splitlines() if "=" in line)
    cfg = {
        "api": (os.environ.get("API_URL") or out.get("ApiUrl", "")).rstrip("/"),
        "pool": os.environ.get("USER_POOL_ID") or out.get("UserPoolId"),
        "client": os.environ.get("CLIENT_ID") or out.get("UserPoolClientId"),
        "email": os.environ.get("DEMO_EMAIL") or creds.get("email"),
        "password": os.environ.get("DEMO_PASSWORD") or creds.get("password"),
    }
    if not all(cfg.values()):
        pytest.skip("deployment outputs / demo credentials not available")
    return cfg


@pytest.fixture(scope="module")
def token(cfg):
    client = boto3.client("cognito-idp", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    result = client.admin_initiate_auth(
        UserPoolId=cfg["pool"], ClientId=cfg["client"], AuthFlow="ADMIN_USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": cfg["email"], "PASSWORD": cfg["password"]},
    )
    return result["AuthenticationResult"]["IdToken"]


def call(cfg, method, path, body=None, token=None, headers=None):
    h = {"Content-Type": "application/json", "Origin": ORIGIN, **(headers or {})}
    if token:
        h["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(cfg["api"] + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as resp:
            return resp.status, dict(resp.headers), json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as err:
        raw = err.read()
        try:
            return err.code, dict(err.headers), json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return err.code, dict(err.headers), {"raw": raw.decode()}


def stream(cfg, body, token, sid=None, stop_after=None):
    """POST /ask and read the Server-Sent Events as they arrive: returns (status, headers, [(seconds, event)])."""
    h = {"Content-Type": "application/json", "Accept": "text/event-stream", "Origin": ORIGIN, "x-session-id": sid or session()}
    if token:
        h["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(cfg["api"] + "/ask", data=json.dumps(body).encode(), headers=h, method="POST")
    started, events = time.perf_counter(), []
    try:
        with urllib.request.urlopen(request, timeout=90) as resp:
            for raw in resp:  # one line at a time: proves events are not buffered until the end
                line = raw.decode("utf-8").strip()
                if line.startswith("data:"):
                    events.append((time.perf_counter() - started, json.loads(line[5:])))
                    if stop_after and events[-1][1]["type"] == stop_after:
                        break
            return resp.status, dict(resp.headers), events
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers), [(0.0, {"raw": err.read().decode()})]


def final(events):
    return next(e for _, e in reversed(events) if e["type"] == "done")


def session():
    return f"e2e-{uuid.uuid4()}"


# ------------------------------------------------------------------ authentication


@pytest.mark.parametrize("method, path, body", [("GET", "/dashboard", None), ("POST", "/ask", {"prompt": "hi"})])
def test_missing_token_is_unauthorized(cfg, method, path, body):
    status, headers, _ = call(cfg, method, path, body, headers={"x-session-id": session()})
    assert status == 401
    assert headers.get("Access-Control-Allow-Origin") == ORIGIN  # browsers must be able to read the 401


def test_garbage_token_is_unauthorized(cfg):
    assert call(cfg, "GET", "/dashboard", token="not.a.jwt")[0] == 401
    assert stream(cfg, {"prompt": "hi"}, "not.a.jwt")[0] == 401


def test_cors_preflight(cfg):
    request = urllib.request.Request(cfg["api"] + "/ask", method="OPTIONS", headers={
        "Origin": ORIGIN, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,content-type,x-session-id"})
    with urllib.request.urlopen(request, timeout=30) as resp:
        headers = {k.lower(): v for k, v in resp.headers.items()}
    assert headers["access-control-allow-origin"] == ORIGIN
    assert {"authorization", "x-session-id"} <= set(h.strip() for h in headers["access-control-allow-headers"].lower().split(","))


# ------------------------------------------------------------------ dashboard


def test_dashboard_matches_the_csv(cfg, token, raw_rows):
    status, headers, body = call(cfg, "GET", "/dashboard", token=token)
    assert status == 200 and headers.get("Access-Control-Allow-Origin") == ORIGIN
    k = body["kpis"]
    assert (k["listings"], k["stores"], k["products"], k["cities"]) == (len(raw_rows), 40, 27, 12)
    assert k["in_stock"] + k["low_stock"] + k["out_of_stock"] == len(raw_rows)
    assert body["as_of"] == "2026-08-25"


def test_dashboard_filters(cfg, token, raw_rows):
    _, _, body = call(cfg, "GET", "/dashboard?city=Amman&status=Low%20Stock", token=token)
    expected = sum(1 for r in raw_rows if r["city"] == "Amman" and r["availability_status"] == "Low Stock")
    assert body["kpis"]["listings"] == expected and body["filters"] == {"city": "Amman", "status": "Low Stock"}


# ------------------------------------------------------------------ assistant (streamed)


def test_ask_streams_events_incrementally_and_is_grounded(cfg, token, raw_rows):
    status, headers, events = stream(cfg, {"prompt": "Where can I buy Olive Oil Extra Virgin in Amman?", "locale": "en"}, token)
    assert status == 200 and headers["Content-Type"].startswith("text/event-stream")
    assert headers.get("Access-Control-Allow-Origin") in (ORIGIN, "*")  # set by AgentCore/the runtime; requests are credential-less so "*" is fine
    kinds = [e["type"] for _, e in events]
    assert kinds[0] == "start" and kinds[-1] == "done" and "error" not in kinds
    assert kinds.index("records") < kinds.index("delta")  # the table is available before the text
    deltas = [t for t, e in events if e["type"] == "delta"]
    assert len(deltas) > 5 and deltas[0] < events[-1][0] - 0.2, "text arrived all at once: the response is being buffered"
    expected = [r for r in raw_rows if r["product_name"] == "Olive Oil Extra Virgin" and r["city"] == "Amman"]
    done = final(events)
    assert done["record_count"] == len(expected) and done["grounded"] is True
    assert {r["store_name"] for r in done["records"]} == {r["store_name"] for r in expected}
    assert all("sales_rep" not in r for r in done["records"])
    assert "".join(e["text"] for _, e in events if e["type"] == "delta").strip() == done["answer"]


def test_ask_in_arabic(cfg, token, raw_rows):
    _, _, events = stream(cfg, {"prompt": "وين بلاقي طحينة بعمان؟", "locale": "ar"}, token)
    done = final(events)
    expected = [r for r in raw_rows if r["product_name"] == "Tahini" and r["city"] == "Amman"]
    assert done["record_count"] == len(expected) and done["grounded"] is True
    assert any("\u0600" <= c <= "\u06ff" for c in done["answer"])


def test_ambiguity_then_follow_up_keeps_the_session(cfg, token):
    sid = session()
    first = final(stream(cfg, {"prompt": "Where can I buy tea in Amman?"}, token, sid)[2])
    assert first["records"] == [] and first["queries"][0]["ambiguous"]
    second = final(stream(cfg, {"prompt": "Black Tea Bags"}, token, sid)[2])
    assert second["records"] and {r["product_name"] for r in second["records"]} == {"Black Tea Bags"}


def test_unknown_store_is_not_invented(cfg, token):
    done = final(stream(cfg, {"prompt": "Does Carrefour Paris have Basmati Rice?"}, token)[2])
    assert done["records"] == [] and done["queries"][0]["no_match"]


def test_client_can_stop_reading_and_the_session_keeps_working(cfg, token):
    sid = session()
    _, _, partial = stream(cfg, {"prompt": "Where can I buy Basmati Rice?"}, token, sid, stop_after="delta")
    assert partial[-1][1]["type"] == "delta"
    done = final(stream(cfg, {"prompt": "Where can I buy Tahini in Irbid?"}, token, sid)[2])
    assert done["records"]


# ------------------------------------------------------------------ request validation (rejected at the edge)


@pytest.mark.parametrize("body", [{}, {"prompt": ""}, {"prompt": "x" * 501}, {"prompt": "hi", "action": "dashboard"}, {"prompt": 5}, {"prompt": "hi", "locale": "fr"}])
def test_invalid_bodies_are_rejected_with_400(cfg, token, body):
    assert call(cfg, "POST", "/ask", body, token, {"x-session-id": session()})[0] == 400


def test_missing_session_header_is_rejected(cfg, token):
    assert call(cfg, "POST", "/ask", {"prompt": "hi"}, token)[0] == 400


# ------------------------------------------------------------------ records (dashboard drill-down)


def test_records_for_a_product_match_the_csv(cfg, token, raw_rows):
    status, headers, body = call(cfg, "GET", "/records?product=Tahini&city=Amman", token=token)
    expected = [r for r in raw_rows if r["product_name"] == "Tahini" and r["city"] == "Amman"]
    assert status == 200 and headers.get("Access-Control-Allow-Origin") == ORIGIN
    assert body["total"] == len(expected) == len(body["records"]) and not body["truncated"]
    assert all("sales_rep" not in r for r in body["records"])


def test_records_for_a_store_and_requires_a_token(cfg, token, raw_rows):
    _, _, body = call(cfg, "GET", "/records?store=Sameh%20Mall%20Abdoun", token=token)
    assert body["total"] == sum(1 for r in raw_rows if r["store_name"] == "Sameh Mall Abdoun")
    assert call(cfg, "GET", "/records")[0] == 401
