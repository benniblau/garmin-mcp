#!/usr/bin/env python3
"""
Read Garmin's badge challenges, and opt into the ones not yet joined.

Everything else in this project reads the local mirror. These read Garmin
directly, because a challenge's progress and join state change without any
activity being recorded and there is nothing in the database to mirror them.

**The join verb is `optIn`, not `join`.** That one word is why this took a
while to find: every `/join/{uuid}`, `/{uuid}/join` and `/player/{uuid}` shape
returns 404, `OPTIONS` on the challenge detail path reports only
`HEAD,GET,OPTIONS`, and python-garminconnect exposes challenges as read-only.
It was captured off the Connect web app on 2026-08-28:

    POST /badgechallenge-service/badgeChallenge/{uuid}/optIn/{YYYY-MM-DD} -> 204

The date is the local day the join is recorded under; it comes back as
`joinDateLocal`. There is no request body and no response body — so a 204 says
only that Garmin accepted the request, and every write here reads the challenge
back to find out what actually changed.

Opting into a challenge that is already joined answers **400**, not 204.

Which listing a challenge appears in depends on what kind it is:

    badgeChallenge/non-completed     monthly and quarterly challenges. These
                                     arrive already joined — 42 of 42 on the
                                     account this was written against.
    virtualChallenge/available       expeditions not yet joined
    virtualChallenge/inProgress      expeditions joined and under way

A successful opt-in moves an expedition from `available` to `inProgress`, sets
`userJoined` true and `joinable` false.

**Expeditions are one per `challengeGroupPk`.** Group 1 is the distance trails,
group 2 the ascent climbs. Joining one makes every other expedition in that
group `joinable: false` until it is finished — so `available` listing something
does not mean you can join it. Established 2026-08-28 by joining Rheinsteig
Trail (group 1) and watching the other ten group-1 trails turn un-joinable
while all nine group-2 climbs stayed open.
"""

from datetime import date as _date
from typing import Any, Dict, List, Optional

import garmin_files

BADGE_CHALLENGE = "/badgechallenge-service/badgeChallenge"
VIRTUAL_CHALLENGE = "/badgechallenge-service/virtualChallenge"

# The fields worth handing a caller. The raw objects carry ~30, most of them
# presentation (image ids, promotion codes, partner reward urls).
SUMMARY_FIELDS = ("uuid", "badgeChallengeName", "badgeChallengeStatusId",
                  "badgeUnitId", "badgeProgressValue", "badgeTargetValue",
                  "userJoined", "joinable", "joinDateLocal",
                  "startDate", "endDate", "badgeKey", "challengeGroupPk")


class ChallengeError(RuntimeError):
    """Garmin refused, or could not be reached. `status` is for REST."""

    def __init__(self, message: str, status: int = 503):
        super().__init__(message)
        self.status = status


def _summarise(c: Dict[str, Any]) -> Dict[str, Any]:
    return {k: c.get(k) for k in SUMMARY_FIELDS if c.get(k) is not None}


def _get(path: str) -> List[Dict[str, Any]]:
    garmin_files.authenticate()
    import garth                                                  # noqa: PLC0415
    try:
        return garth.connectapi(path) or []
    except Exception as e:                                        # noqa: BLE001
        raise ChallengeError(f"Garmin would not answer {path}: "
                             f"{type(e).__name__}: {e}") from e


def list_challenges(state: str = "joinable") -> List[Dict[str, Any]]:
    """
    Challenges in one of four states.

    joinable    expeditions not yet joined — the only ones opt_in accepts
    in_progress expeditions joined and under way
    current     monthly and quarterly challenges not yet completed
    completed   everything already earned
    """
    paths = {
        "joinable": f"{VIRTUAL_CHALLENGE}/available",
        "in_progress": f"{VIRTUAL_CHALLENGE}/inProgress",
        "current": f"{BADGE_CHALLENGE}/non-completed",
        "completed": f"{BADGE_CHALLENGE}/completed",
    }
    if state not in paths:
        raise ChallengeError(f"state must be one of {sorted(paths)}, "
                             f"got {state!r}", status=400)
    return [_summarise(c) for c in _get(paths[state])]


def get_challenge(uuid: str) -> Dict[str, Any]:
    """One challenge, by uuid, straight from Garmin."""
    garmin_files.authenticate()
    import garth                                                  # noqa: PLC0415
    try:
        return _summarise(garth.connectapi(f"{BADGE_CHALLENGE}/{uuid}") or {})
    except Exception as e:                                        # noqa: BLE001
        status = garmin_files._http_status(e)
        if status is not None and 400 <= status < 500:
            # Garmin answers 400 for a uuid it cannot parse and 404 for one it
            # can but does not know; both mean "not a challenge you can use".
            raise ChallengeError(f"Garmin has no challenge {uuid}",
                                 status=404) from e
        raise ChallengeError(f"Garmin would not describe {uuid}: "
                             f"{type(e).__name__}: {e}") from e


def opt_in(uuid: str, join_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Join a challenge. Returns its state afterwards, read back from Garmin.

    `join_date` is the local day to record the join under, YYYY-MM-DD,
    defaulting to today. Garmin answers 204 with no body, which says nothing
    about whether anything changed — so this reads the challenge back and
    reports what Garmin actually thinks, rather than trusting the status code.

    **Garmin answers 400 to an opt-in for a challenge already joined** —
    established 2026-08-28 by trying it. That is reported here as success
    rather than an error, provided the read-back confirms `userJoined`: the
    caller asked for the challenge to be joined, and it is. Treating it as a
    failure would make this impossible to retry safely after a timeout, which
    is exactly when a 204-with-no-body leaves you unsure whether it landed.
    """
    garmin_files.authenticate()
    import garth                                                  # noqa: PLC0415

    day = join_date or _date.today().isoformat()
    try:
        _date.fromisoformat(day)
    except ValueError:
        raise ChallengeError(f"join_date must be YYYY-MM-DD, got {day!r}",
                             status=400)

    path = f"{BADGE_CHALLENGE}/{uuid}/optIn/{day}"
    try:
        garth.client.post("connectapi", path, api=True)
    except Exception as e:                                        # noqa: BLE001
        status = garmin_files._http_status(e)
        if status is not None and 400 <= status < 500:
            # Garmin says no. The most common reason is that the challenge is
            # already joined, which is not a failure from the caller's point of
            # view — so ask Garmin what it thinks before deciding.
            try:
                current = get_challenge(uuid)
            except ChallengeError:
                current = {}
            if current.get("userJoined"):
                return current
            if status == 404 or not current:
                raise ChallengeError(
                    f"Garmin has no challenge {uuid}, or it cannot be joined",
                    status=404) from e
            raise ChallengeError(
                f"Garmin refused the opt-in for "
                f"{current.get('badgeChallengeName') or uuid} (HTTP {status}); "
                f"joinable={current.get('joinable')}", status=status) from e
        raise ChallengeError(f"Garmin would not process the opt-in for "
                             f"{uuid}: {type(e).__name__}: {e}") from e

    return get_challenge(uuid)
