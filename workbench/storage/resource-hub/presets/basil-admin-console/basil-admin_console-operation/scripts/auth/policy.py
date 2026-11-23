"""Secret-free policy template, not a host adapter or OAuth implementation.

Normalize documented host metadata before calling these functions. Action labels
are local decisions: the adapter must implement actual cards, refresh, resume,
and read-only verify using proven host capabilities. No network or secret access.
Carry counters and selected method across Attempts; never reset them on resume.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal


STATES = {
    "usable", "missing", "expiring", "expired", "invalid_token", "revoked",
    "refresh_rejected", "temporary_error", "refresh_unknown", "config_error",
    "permission_error", "injection_pending", "injection_failed", "declined",
    "skipped", "timed_out", "authorization_failed",
}


@dataclass(frozen=True)
class Decision:
    action: str
    reason: str
    method: str = "oauth2"


def status(*, access_present: bool, now: float, expires_at: float | None = None,
           refresh_margin: float = 60.0) -> dict:
    """Local availability only. Expiry is normalized host metadata, not JWT data."""
    if type(access_present) is not bool:
        raise ValueError("access_present must be boolean")
    for name, value in (("now", now), ("refresh_margin", refresh_margin), ("expires_at", expires_at)):
        if value is None and name == "expires_at":
            continue
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f"{name} must be a finite timestamp/duration")
    if refresh_margin < 0:
        raise ValueError("refresh_margin must be nonnegative")
    state = "missing"
    if access_present:
        state = "usable"
        if expires_at is not None:
            if expires_at <= now:
                state = "expired"
            elif expires_at <= now + refresh_margin:
                state = "expiring"
    return {"state": state, "configured": access_present, "verified": False,
            "expiry_known": expires_at is not None}


def oauth_decision(state: str, *, refresh_capability: Literal["available", "unavailable", "unknown"],
                   refresh_attempts: int = 0, reauth_attempts: int = 0,
                   initial_card_attempts: int = 0) -> Decision:
    """One refresh recovery cycle per incident; one reauthorization per task.

    'unavailable' means a known absent/unsupported refresh grant. Missing host
    functionality must be mapped to 'unknown' or config_error, never unavailable.
    The platform owns bounded transient backoff within its refresh cycle.
    """
    if state not in STATES or refresh_capability not in {"available", "unavailable", "unknown"}:
        raise ValueError("unsupported normalized OAuth state/capability")
    for count in (refresh_attempts, reauth_attempts, initial_card_attempts):
        if type(count) is not int or count < 0:
            raise ValueError("recovery counts must be nonnegative integers")
    if state == "usable":
        return Decision("ready", "verify the selected connection before original task continuation")
    if state in {"declined", "skipped", "timed_out", "authorization_failed"}:
        return Decision("stop", "do not reopen the card or collect another credential")
    if state in {"config_error", "permission_error", "injection_failed"}:
        return Decision("blocked", "repair the reported prerequisite without repeated consent")
    if state == "temporary_error":
        return Decision("retry_later", "use bounded platform backoff; do not open a card")
    if state == "refresh_unknown":
        return Decision("reconcile", "read managed state before reusing any old refresh grant")
    if state == "injection_pending":
        return Decision("resume", "obtain fresh host injection; old process environment is unchanged")
    if state == "missing":
        if refresh_capability == "unknown":
            return Decision("blocked", "establish whether a managed refresh grant exists")
        if refresh_capability == "available":
            if refresh_attempts:
                return Decision("blocked", "access credential still absent after refresh; check delivery")
            return Decision("managed_refresh", "restore absent access credential from the managed grant")
        if initial_card_attempts or reauth_attempts:
            return Decision("blocked", "authorization/injection remains absent after the card")
        return Decision("authorization_card", "initial consent through the native host card")
    if state in {"expired", "expiring", "invalid_token"}:
        if refresh_attempts:
            return Decision("stop", "fresh credential still unusable; do not loop recovery")
        if refresh_capability == "unknown":
            return Decision("blocked", "refresh support must be established by the host adapter")
        if refresh_capability == "available":
            return Decision("managed_refresh", "refresh silently before requesting consent")
        if state == "expiring":
            return Decision("ready", "token remains valid; no refresh grant, reauthorize only when needed")
    # Expired/invalid without a refresh grant, or explicit refresh rejection/revocation.
    if reauth_attempts:
        return Decision("stop", "reauthorization budget exhausted")
    return Decision("authorization_card", "reauthorization required by the connection state")


def may_retry_business(*, credential_verified: bool, safe_read: bool,
                       retries: int, write_outcome: str = "unknown",
                       idempotency_guaranteed: bool = False) -> bool:
    """A refresh is not permission to replay a write; the adapter supplies evidence."""
    if any(type(v) is not bool for v in (credential_verified, safe_read, idempotency_guaranteed)):
        raise ValueError("retry evidence must be boolean")
    if type(retries) is not int or retries < 0:
        raise ValueError("retries must be a nonnegative integer")
    if write_outcome not in {"unknown", "rejected_before_effect", "succeeded"}:
        raise ValueError("unsupported write outcome")
    if not credential_verified or retries >= 1 or write_outcome == "succeeded":
        return False
    return safe_read or write_outcome == "rejected_before_effect" or idempotency_guaranteed
