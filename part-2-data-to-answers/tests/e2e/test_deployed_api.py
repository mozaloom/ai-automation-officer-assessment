"""Calls the DEPLOYED API (API Gateway -> AgentCore -> S3). Run: pytest -m e2e

Needs AWS credentials (profile with cognito-idp:AdminInitiateAuth) and either build/outputs.json
(written by cdk deploy) or API_URL / USER_POOL_ID / CLIENT_ID, plus DEMO_EMAIL / DEMO_PASSWORD
(or the git-ignored .demo-credentials file).
"""

import json
import os
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
        h["Authorization"] = token
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


# ------------------------------------------------------------------ assistant


def test_ask_is_grounded_in_returned_records(cfg, token, raw_rows):
    status, _, body = call(cfg, "POST", "/ask", {"prompt": "Where can I buy Olive Oil Extra Virgin in Amman?"}, token, {"x-session-id": session()})
    assert status == 200 and "error" not in body
    expected = [r for r in raw_rows if r["product_name"] == "Olive Oil Extra Virgin" and r["city"] == "Amman"]
    assert body["record_count"] == len(expected) and body["grounded"] is True
    assert {r["store_name"] for r in body["records"]} == {r["store_name"] for r in expected}
    assert all("sales_rep" not in r for r in body["records"])


def test_ambiguity_then_follow_up_keeps_the_session(cfg, token):
    sid = session()
    _, _, first = call(cfg, "POST", "/ask", {"prompt": "Where can I buy tea in Amman?"}, token, {"x-session-id": sid})
    assert first["records"] == [] and first["queries"][0]["ambiguous"]
    _, _, second = call(cfg, "POST", "/ask", {"prompt": "Black Tea Bags"}, token, {"x-session-id": sid})
    assert second["records"] and {r["product_name"] for r in second["records"]} == {"Black Tea Bags"}


def test_unknown_store_is_not_invented(cfg, token):
    _, _, body = call(cfg, "POST", "/ask", {"prompt": "Does Carrefour Paris have Basmati Rice?"}, token, {"x-session-id": session()})
    assert body["records"] == [] and body["queries"][0]["no_match"]


# ------------------------------------------------------------------ request validation (rejected at the edge)


@pytest.mark.parametrize("body", [{}, {"prompt": ""}, {"prompt": "x" * 501}, {"prompt": "hi", "action": "dashboard"}, {"prompt": 5}])
def test_invalid_bodies_are_rejected_with_400(cfg, token, body):
    assert call(cfg, "POST", "/ask", body, token, {"x-session-id": session()})[0] == 400


def test_missing_session_header_is_rejected(cfg, token):
    assert call(cfg, "POST", "/ask", {"prompt": "hi"}, token)[0] == 400
