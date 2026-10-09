#!/usr/bin/env python3
"""One-time Outlook sign-in for the Inbox Reviewer (OAuth 2.0 device code flow, delegated, public client: no client secret).

Prerequisite: an Entra app registration in the medgan.ai tenant (single tenant, "Allow public client flows" = Yes) with DELEGATED Microsoft Graph
permissions Mail.ReadWrite, Mail.Send, offline_access, User.Read, admin-consented. See part-1-email-to-clickup/README.md for the exact portal steps.

Usage: connect_outlook.py --tenant-id <GUID> --client-id <GUID> [--mailbox xpand@medgan.ai]
It prints a short code and a URL; open the URL in a private window and sign in AS the mailbox. The refresh token is written only to AWS Secrets
Manager (xpand/inbox/graph); nothing secret is printed or saved to disk.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SCOPE = "Mail.ReadWrite Mail.Send offline_access User.Read"


def post(url, data):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read() or b"{}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant-id", required=True)
    ap.add_argument("--client-id", required=True)
    ap.add_argument("--mailbox", default="xpand@medgan.ai")
    ap.add_argument("--secret-id", default="xpand/inbox/graph")
    ap.add_argument("--region", default="us-east-1")
    args = ap.parse_args()
    base = f"https://login.microsoftonline.com/{args.tenant_id}/oauth2/v2.0"

    status, device = post(f"{base}/devicecode", {"client_id": args.client_id, "scope": SCOPE})
    if status != 200:
        print(f"Microsoft refused the request: {device.get('error')} - {device.get('error_description', '')[:200]}", file=sys.stderr)
        return 1
    print(f"\n1. Open {device['verification_uri']} in a private/incognito window\n2. Enter the code {device['user_code']}\n3. Sign in AS {args.mailbox}\n")
    deadline, interval = time.time() + int(device.get("expires_in", 900)), int(device.get("interval", 5))
    while time.time() < deadline:
        time.sleep(interval)
        status, token = post(f"{base}/token", {"grant_type": "urn:ietf:params:oauth:grant-type:device_code", "client_id": args.client_id, "device_code": device["device_code"]})
        if status == 200:
            break
        if token.get("error") not in ("authorization_pending", "slow_down"):
            print(f"Sign-in failed: {token.get('error')} - {token.get('error_description', '')[:200]}", file=sys.stderr)
            return 1
        interval += 5 if token.get("error") == "slow_down" else 0
    else:
        print("Timed out waiting for sign-in.", file=sys.stderr)
        return 1

    req = urllib.request.Request("https://graph.microsoft.com/v1.0/me?$select=userPrincipalName,mail", headers={"Authorization": f"Bearer {token['access_token']}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        me = json.loads(r.read())
    signed_in = (me.get("mail") or me.get("userPrincipalName") or "").lower()
    if signed_in != args.mailbox.lower():
        print(f"You signed in as {signed_in}, not {args.mailbox}. Nothing was stored. Run again and sign in as the mailbox.", file=sys.stderr)
        return 1

    import boto3

    sm = boto3.client("secretsmanager", region_name=args.region)
    value = json.dumps({"tenant_id": args.tenant_id, "client_id": args.client_id, "refresh_token": token["refresh_token"], "mailbox": args.mailbox})
    try:
        sm.put_secret_value(SecretId=args.secret_id, SecretString=value)
    except sm.exceptions.ResourceNotFoundException:
        sm.create_secret(Name=args.secret_id, Description="Microsoft Graph refresh token for the Inbox Reviewer mailbox", SecretString=value)
    print(f"Connected {args.mailbox}. Refresh token stored in Secrets Manager ({args.secret_id}); it was not displayed or written to disk.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
