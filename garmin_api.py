#!/usr/bin/env python3
"""
Read Garmin Connect through the Personal API.

Garmin's Personal API (October 2026) gives one account read access with a key
created at https://connect.garmin.com/app/settings/personalApiToken — no
password, no MFA, no session file. Every read in this project goes through
here; garth survives only for the writes the Personal API does not offer
(FIT upload, activity visibility, challenge opt-in). See garmin_files.py.

How it works, as observed against the live API on 2026-11-05:

- The key is exchanged at TOKEN_PATH for a bearer token. The token arrives as
  a **bare JWT in text/plain**, not JSON, and lives 24 hours. There is no
  refresh token: asking again with the key is the refresh.
- The data paths are the Connect paths garth used, on another host. Not every
  one is offered: training readiness/status, max metrics, race predictions,
  endurance/hill score, blood pressure, devices and badge challenges all 404.
- Range endpoints cap the span: stress, steps and sleep summaries answer 400
  past ~28-31 days; v2 daily summaries took six months but 500'd on a year.
  The activity list answers 500 for a `limit` of 500 or more.
- The key itself expires (30 days to a year, chosen at creation), and nothing
  Garmin returns says when. GARMIN_PERSONAL_API_KEY_EXPIRES (YYYY-MM-DD) lets
  the health route warn before it does.
"""

import base64
import json
import os
import threading
import time
from datetime import date
from typing import Any, Optional

import requests

BASE_URL = os.getenv("GARMIN_PERSONAL_API_URL",
                     "https://personal.connectapi.garmin.com").rstrip("/")
TOKEN_PATH = "/personalapitoken-service/personal-api/personal-api-key/token"

REQUEST_TIMEOUT = 60

# Ask for a fresh token this long before the cached one expires, so a request
# never sets out with a token that dies in flight.
TOKEN_MARGIN = 300

_lock = threading.Lock()
_token: Optional[str] = None
_token_expires: float = 0.0
_session = requests.Session()


class ApiError(RuntimeError):
    """
    The Personal API could not be reached, or refused.

    `status` is Garmin's HTTP status when Garmin answered, else 503, so a REST
    layer can pass a 404 through as a 404 rather than claim Garmin is down.
    """

    def __init__(self, message: str, status: int = 503):
        super().__init__(message)
        self.status = status


def api_key() -> Optional[str]:
    """The Personal API key. GARMIN_ACCESS_TOKEN is the name it first had here."""
    return (os.getenv("GARMIN_PERSONAL_API_KEY")
            or os.getenv("GARMIN_ACCESS_TOKEN") or None)


def _jwt_exp(token: str) -> float:
    """The `exp` claim of a JWT, without verifying it — only to schedule renewal."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return float(json.loads(base64.urlsafe_b64decode(payload))["exp"])
    except Exception:                                             # noqa: BLE001
        return time.time() + 3600        # unknown: assume short, renew early


def token(force: bool = False) -> str:
    """A bearer token, exchanged from the key and cached until near expiry."""
    global _token, _token_expires
    with _lock:
        if not force and _token and time.time() < _token_expires - TOKEN_MARGIN:
            return _token

        key = api_key()
        if not key:
            raise ApiError("GARMIN_PERSONAL_API_KEY is not set — create a key at "
                           "https://connect.garmin.com/app/settings/personalApiToken")
        try:
            resp = _session.post(BASE_URL + TOKEN_PATH,
                                 headers={"Authorization": f"ApiKey {key}"},
                                 timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            raise ApiError(f"Garmin token exchange failed: {type(e).__name__}: {e}") from e

        if resp.status_code in (401, 403):
            raise ApiError("Garmin rejected the Personal API key (expired or "
                           f"deleted?) — HTTP {resp.status_code}", status=resp.status_code)
        if not resp.ok:
            raise ApiError(f"Garmin token exchange answered HTTP {resp.status_code}",
                           status=resp.status_code if resp.status_code < 500 else 503)

        # A bare JWT in text/plain. Tolerate JSON in case that changes.
        text = resp.text.strip()
        if text.startswith("{"):
            body = json.loads(text)
            text = body.get("access_token") or body.get("accessToken") or ""
        if text.count(".") != 2:
            raise ApiError("Garmin token exchange returned no token")

        _token, _token_expires = text, _jwt_exp(text)
        return _token


def _request(path: str, params: Optional[dict] = None) -> requests.Response:
    """GET with the bearer token, renewing it once if Garmin says it is stale."""
    for attempt in (0, 1):
        headers = {"Authorization": f"Bearer {token(force=attempt == 1)}"}
        try:
            resp = _session.get(BASE_URL + path, params=params, headers=headers,
                                timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            raise ApiError(f"Garmin request failed: {type(e).__name__}: {e}") from e
        if resp.status_code == 401 and attempt == 0:
            continue
        if not resp.ok:
            # The status goes into the message too: callers that only see the
            # text (the downloader's rate-limit backoff) look for "429".
            raise ApiError(f"Garmin answered HTTP {resp.status_code} for {path}: "
                           f"{resp.text[:120]}",
                           status=resp.status_code if resp.status_code < 500 else 503)
        return resp
    raise AssertionError("unreachable")


def get(path: str, params: Optional[dict] = None) -> Any:
    """GET JSON. An empty answer (Garmin uses 204 for "no data") is None."""
    resp = _request(path, params)
    if resp.status_code == 204 or not resp.content:
        return None
    try:
        return resp.json()
    except ValueError as e:
        raise ApiError(f"Garmin answered {path} with non-JSON") from e


def download(path: str, params: Optional[dict] = None) -> bytes:
    """GET raw bytes."""
    return _request(path, params).content


def status() -> dict:
    """
    What the health route reports: is a key configured, does it exchange,
    and — if GARMIN_PERSONAL_API_KEY_EXPIRES is set — how long it has left.
    Raises ApiError when the exchange fails.
    """
    token()
    out: dict = {"personal_api": "ok",
                 "token_expires_at": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                   time.gmtime(_token_expires))}
    expires = os.getenv("GARMIN_PERSONAL_API_KEY_EXPIRES")
    if expires:
        try:
            days = (date.fromisoformat(expires) - date.today()).days
            out["key_expires"] = expires
            out["key_days_left"] = days
        except ValueError:
            out["key_expires"] = f"unparseable: {expires!r}"
    return out
