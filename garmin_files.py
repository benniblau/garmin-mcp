#!/usr/bin/env python3
"""
Move activity files in and out of Garmin Connect.

This module owns the Garmin session and both file paths, so the machine has
exactly one credential store and one session file to keep alive whoever is
transferring files. `export_fit.py` is the CLI on top of the download half;
the REST API in mcp_server.py exposes both.

**Download** — /download-service/files/activity/{id} serves the originally
recorded file as a ZIP wrapping the .fit, though some activities come back as
a bare FIT. Both shapes are unwrapped to the FIT itself.

**Upload** — /upload-service/upload/fit is the import endpoint the web client
uses for files recorded elsewhere, and the one write path Garmin exposes that
is useful to a third party. Third-party lore (documented in garminconnect's
source) holds that activities arriving this way are not re-exported to
connected services, which is what keeps an imported activity from duplicating
into Strava. That claim is not verified here.

Classifying the upload answer is the fiddly part:

    2xx with successes            -> uploaded, keep internalId
    409                           -> Garmin already has this activity
    2xx with a duplicate failure  -> same thing, said differently
    anything else                 -> failed, with Garmin's own message

garth raises on non-2xx, so a duplicate arrives as an exception whose status
code has to be dug out of the wrapped response.
"""

import hashlib
import io
import os
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional, Tuple

BASE = Path(__file__).parent

UPLOAD_PATH = "/upload-service/upload/fit"
DOWNLOAD_PATH = "/download-service/files/activity/{activity_id}"

# A FIT file carries its signature at bytes 8..12.
FIT_SIGNATURE = b".FIT"

# Garmin's web client sends these on uploads; without them the endpoint
# answers 403.
UPLOAD_HEADERS = {"NK": "NT", "origin": "https://sso.garmin.com"}

# garth defaults to 10 seconds for every request, which has been enough in
# practice but leaves no headroom for a slow link or a large file. It is set on
# the client rather than per-call: garth passes its own timeout to requests
# explicitly, so a `timeout=` kwarg on a call collides with it and raises.
REQUEST_TIMEOUT = 60

_authenticated = False


class GarminError(RuntimeError):
    """
    Garmin could not be authenticated, reached, or made to answer.

    `status` is what a REST layer should report. It defaults to 503 — the far
    end is unavailable, try later — but carries Garmin's own status when
    Garmin actually answered, so that asking for an activity that does not
    exist is a 404 to the caller rather than a claim that Garmin is down.
    """

    def __init__(self, message: str, status: int = 503):
        super().__init__(message)
        self.status = status


# The name this was introduced under, kept so callers that catch it still work.
UploadError = GarminError


@dataclass
class UploadResult:
    """Outcome of one upload, in the vocabulary a caller can act on."""
    status: str                       # uploaded | duplicate | failed
    upload_id: Optional[str] = None
    activity_id: Optional[str] = None
    message: Optional[str] = None
    http_status: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)


def authenticate(force: bool = False) -> None:
    """
    Establish a Garmin session: resume the saved one, or log in fresh.

    This module owns the session rather than borrowing it, so that a server
    importing it never inherits a CLI's habit of calling sys.exit — a missing
    credential must fail one request, not take the process down. export_fit.py
    delegates here and adds the exit itself.

    GARTH_SESSION_PATH selects the session directory. Done once per process:
    garth keeps the session on a module-level client, so a second call would
    only re-probe one that already works.
    """
    global _authenticated
    if _authenticated and not force:
        return

    try:
        import garth                                              # noqa: PLC0415
    except ImportError as e:
        raise GarminError("garth is required: pip install garth") from e

    garth.client.configure(timeout=REQUEST_TIMEOUT)

    session_path = os.getenv("GARTH_SESSION_PATH", str(BASE / ".garth"))
    os.makedirs(session_path, exist_ok=True)

    if os.path.exists(os.path.join(session_path, "oauth1_token.json")):
        try:
            garth.resume(session_path)
            # Resuming proves nothing on its own — the tokens may be stale.
            # One cheap real request is what says the session works.
            garth.connectapi("/activitylist-service/activities/search/activities",
                             params={"limit": 1})
            _authenticated = True
            return
        except Exception:                                         # noqa: BLE001
            pass                              # fall through to a fresh login

    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")
    if not email or not password:
        raise GarminError(
            f"No usable Garmin session in {session_path}, and GARMIN_EMAIL / "
            "GARMIN_PASSWORD are not set to make a new one")

    try:
        garth.login(email, password)
        garth.save(session_path)
    except Exception as e:                                        # noqa: BLE001
        raise GarminError(f"Garmin login failed: {e}") from e

    _authenticated = True


def fetch_activity_file(activity_id: Any) -> Tuple[bytes, str]:
    """
    Download one activity's originally recorded FIT. Returns (bytes, sha256).

    Garmin serves it as a ZIP wrapping the .fit, but some activities come back
    as a bare FIT — both are handled, because which one you get is not
    something the caller can predict from the activity.
    """
    authenticate()

    import garth                                                  # noqa: PLC0415

    try:
        raw = garth.download(DOWNLOAD_PATH.format(activity_id=activity_id))
    except Exception as e:                                        # noqa: BLE001
        status = _http_status(e)
        if status == 404:
            raise GarminError(f"Garmin has no activity {activity_id}",
                              status=404) from e
        if status is not None and status < 500:
            raise GarminError(
                f"Garmin refused to export {activity_id} (HTTP {status})",
                status=status) from e
        raise GarminError(f"Garmin would not export {activity_id}: "
                          f"{type(e).__name__}: {e}") from e

    if not raw:
        raise GarminError(f"Garmin returned no bytes for {activity_id}")

    if raw[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                names = [n for n in zf.namelist() if n.lower().endswith(".fit")]
                if not names:
                    raise GarminError(
                        f"The export for {activity_id} contained no .fit "
                        f"({zf.namelist()})")
                data = zf.read(names[0])
        except zipfile.BadZipFile as e:
            raise GarminError(
                f"The export for {activity_id} is not a readable ZIP") from e
    else:
        data = raw

    if len(data) < 14 or data[8:12] != FIT_SIGNATURE:
        raise GarminError(
            f"The export for {activity_id} is not a FIT file "
            f"({len(data)} bytes, starts {data[:16]!r})")

    return data, hashlib.sha256(data).hexdigest()


def _http_status(err: Exception) -> Optional[int]:
    """
    Dig the HTTP status out of a garth exception.

    GarthHTTPError wraps a requests.HTTPError in `.error`, whose `.response`
    carries the status. Older shapes put the response on the exception itself.
    """
    for candidate in (getattr(getattr(err, "error", None), "response", None),
                      getattr(err, "response", None)):
        status = getattr(candidate, "status_code", None)
        if status is not None:
            return status
    return None


def _response_body(err: Exception) -> Any:
    """The JSON body of a failed response, if there is one."""
    for candidate in (getattr(getattr(err, "error", None), "response", None),
                      getattr(err, "response", None)):
        if candidate is None:
            continue
        try:
            return candidate.json()
        except Exception:                                         # noqa: BLE001
            text = getattr(candidate, "text", None)
            if text:
                return text[:300]
    return None


def _failure_message(body: Any) -> Optional[str]:
    """
    Garmin's own words for why an upload was rejected.

    The envelope is detailedImportResult.failures[0].messages[0], where the
    message is itself an object with a `content` field.
    """
    if not isinstance(body, dict):
        return str(body)[:300] if body else None

    result = body.get("detailedImportResult") or {}
    failures = result.get("failures") or []
    if not failures:
        return body.get("message") or None

    messages = failures[0].get("messages") or []
    if not messages:
        return str(failures[0])[:300]

    first = messages[0]
    if isinstance(first, dict):
        return first.get("content") or str(first)[:300]
    return str(first)[:300]


def _classify(resp: Any) -> UploadResult:
    """Turn a 2xx upload response into an outcome."""
    try:
        body = resp.json()
    except Exception:                                             # noqa: BLE001
        return UploadResult(status="uploaded",
                            http_status=getattr(resp, "status_code", None),
                            message="Accepted, but the response was not JSON")

    result = (body or {}).get("detailedImportResult") or {}
    upload_id = result.get("uploadId")
    successes = result.get("successes") or []
    failures = result.get("failures") or []
    http_status = getattr(resp, "status_code", None)

    if successes:
        return UploadResult(
            status="uploaded",
            upload_id=str(upload_id) if upload_id is not None else None,
            activity_id=str(successes[0].get("internalId"))
            if successes[0].get("internalId") is not None else None,
            http_status=http_status,
        )

    message = _failure_message(body)
    if message and "duplicate" in message.lower():
        # Garmin sometimes accepts the request and reports the duplicate in
        # the body instead of answering 409.
        return UploadResult(status="duplicate",
                            upload_id=str(upload_id) if upload_id is not None else None,
                            message=message, http_status=http_status)

    if failures:
        return UploadResult(status="failed", message=message,
                            upload_id=str(upload_id) if upload_id is not None else None,
                            http_status=http_status)

    # Neither a success nor a failure: Garmin queued it without saying so.
    # This is the usual answer — the endpoint returns 202 and decides later.
    return UploadResult(status="uploaded",
                        upload_id=str(upload_id) if upload_id is not None else None,
                        message="Accepted with no import result reported",
                        http_status=http_status)


def upload_fit(data: bytes, filename: str = "activity.fit") -> UploadResult:
    """
    Upload one FIT file to Garmin Connect.

    Never raises for an outcome Garmin actually reported — a rejection and a
    duplicate are both results, not errors. UploadError is reserved for not
    getting an answer at all.

    garth reads `fp.name` when building the multipart part, so the payload is
    written to a real file rather than handed over as a BytesIO.
    """
    if not data:
        raise GarminError("No file content to upload")

    authenticate()

    import garth                                                  # noqa: PLC0415

    with tempfile.TemporaryDirectory(prefix="garmin_upload_") as tmpdir:
        path = Path(tmpdir) / Path(filename).name
        path.write_bytes(data)

        try:
            with open(path, "rb") as fp:
                resp = garth.client.post(
                    "connectapi", UPLOAD_PATH,
                    files={"file": (path.name, fp, "application/octet-stream")},
                    headers=UPLOAD_HEADERS,
                    api=True,
                )
        except Exception as e:                                    # noqa: BLE001
            status = _http_status(e)
            if status == 409:
                # Garmin already holds this activity. Not an error — it is the
                # expected answer to re-processing something.
                return UploadResult(status="duplicate", http_status=409,
                                    message="Garmin reported a duplicate (HTTP 409)")
            if status is None:
                # No response at all: a network fault, or a session that could
                # not be renewed. The caller should retry rather than record a
                # verdict on the file.
                raise GarminError(f"Garmin upload failed: {type(e).__name__}: {e}") from e
            body = _response_body(e)
            return UploadResult(
                status="failed", http_status=status,
                message=_failure_message(body) or f"{type(e).__name__}: {e}")

    return _classify(resp)
