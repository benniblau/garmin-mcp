#!/usr/bin/env python3
"""
Join every Garmin challenge that is open to be joined.

Meant for cron. Idempotent: it only ever acts on challenges Garmin itself
reports as `joinable` and not yet joined, so a run with nothing to do is
silent and costs two GETs.

WHAT IT ACTUALLY FINDS, which is less than the name suggests:

- **Monthly and quarterly challenges arrive already joined.** All 42 of them on
  the account this was written against. There is normally nothing to do here,
  and this exists to catch the exception rather than the rule.
- **Expeditions are one-per-group.** Garmin groups them — group 1 is the
  distance trails (West Highland Way, Via Transilvanica), group 2 the ascent
  climbs (Everest, Elbrus). Joining one makes every *other* expedition in that
  group `joinable: false` until it is finished. So a run joins at most one per
  group, however many are listed.

That last point is why GARMIN_CHALLENGE_PREFER exists. With nine climbs open
and one slot, something has to choose, and choosing alphabetically means
Elbrus by accident rather than Everest on purpose.

Usage:
    python join_challenges.py --dry-run     # say what would be joined
    python join_challenges.py               # join it
    python join_challenges.py --limit 1     # at most one per run

Environment:
    GARMIN_CHALLENGE_PREFER   comma-separated names, tried in order. A name
                              matches if it appears in the challenge name,
                              case-insensitively. Anything not listed is still
                              eligible, just after the preferences.
    GARMIN_CHALLENGE_SKIP     comma-separated names never to join.
"""

import argparse
import os
import sys
import time
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

import garmin_challenges

# Garmin is not rate-limiting this in any way we have seen, but a cron job
# firing twenty writes at a third party should still pace itself.
SLEEP_BETWEEN = 1.5


def _names(var: str) -> List[str]:
    return [p.strip().lower() for p in os.getenv(var, "").split(",") if p.strip()]


def _rank(challenge: Dict[str, Any], prefer: List[str]) -> int:
    """Position in the preference list, or one past the end."""
    name = (challenge.get("badgeChallengeName") or "").lower()
    for i, wanted in enumerate(prefer):
        if wanted in name:
            return i
    return len(prefer)


def candidates(prefer: List[str], skip: List[str]) -> List[Dict[str, Any]]:
    """
    Everything open to be joined, most-preferred first.

    Both listings are consulted: expeditions, and the monthly/quarterly
    challenges in case one ever arrives unjoined.
    """
    seen, out = set(), []
    for state in ("joinable", "current"):
        for c in garmin_challenges.list_challenges(state):
            uuid = c.get("uuid")
            if not uuid or uuid in seen:
                continue
            if c.get("userJoined") or not c.get("joinable"):
                continue
            name = (c.get("badgeChallengeName") or "").lower()
            if any(s in name for s in skip):
                continue
            seen.add(uuid)
            out.append(c)
    out.sort(key=lambda c: (_rank(c, prefer), c.get("badgeChallengeName") or ""))
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Join open Garmin challenges")
    p.add_argument("--dry-run", action="store_true",
                   help="List what would be joined; join nothing")
    p.add_argument("--limit", type=int, default=None,
                   help="Join at most this many in one run")
    args = p.parse_args(argv)

    prefer, skip = _names("GARMIN_CHALLENGE_PREFER"), _names("GARMIN_CHALLENGE_SKIP")

    try:
        open_now = candidates(prefer, skip)
    except garmin_challenges.ChallengeError as e:
        print(f"❌ {e}")
        return 1

    if not open_now:
        print("✅ nothing open to join")
        return 0

    print(f"📋 {len(open_now)} challenge(s) open to join"
          + (f", preferring {', '.join(prefer)}" if prefer else ""))
    for c in open_now:
        unit = {1: "m", 2: "m ascent"}.get(c.get("badgeUnitId"), "")
        print(f"   • {(c.get('badgeChallengeName') or ''):<28} "
              f"{c.get('badgeTargetValue') or 0:>9,.0f} {unit:<9} "
              f"group {c.get('challengeGroupPk')}")

    if args.dry_run:
        print("\n   dry run: nothing joined")
        return 0

    joined = blocked = failed = 0
    for n, c in enumerate(open_now[:args.limit] if args.limit else open_now):
        name = c.get("badgeChallengeName")
        if n:
            time.sleep(SLEEP_BETWEEN)
        try:
            after = garmin_challenges.opt_in(c["uuid"])
        except garmin_challenges.ChallengeError as e:
            # Expected once a group is taken: joining one expedition makes the
            # rest of its group un-joinable, and the listing we read is now
            # stale. Not a failure worth alarming a cron log about.
            if e.status and 400 <= e.status < 500:
                print(f"   ⏭  {name}: no longer joinable "
                      "(its group is taken by another expedition)")
                blocked += 1
            else:
                print(f"   ❌ {name}: {e}")
                failed += 1
            continue
        if after.get("userJoined"):
            print(f"   ✅ joined {name}")
            joined += 1
        else:
            print(f"   ⚠️  {name}: Garmin accepted the opt-in but still "
                  "reports it as not joined")
            failed += 1

    print(f"\n✅ {joined} joined, {blocked} blocked by an active expedition, "
          f"{failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
