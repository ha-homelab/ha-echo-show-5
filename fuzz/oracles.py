"""Check real PCM and synchronous lease boundaries without devices or timers."""

import base64
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(
    0, str(ROOT / "integrations/show5-intercom/custom_components/show5_intercom")
)
intercom_lease = importlib.import_module("lease")


async def forbidden_hook(*args):
    raise AssertionError("The synchronous oracle must never run resource hooks")


def intercom_boundaries(data: bytes) -> None:
    try:
        decoded = intercom_lease.decode_pcm(data.decode("utf-8", errors="replace"))
    except ValueError:
        pass
    else:
        assert 1764 <= len(decoded) <= intercom_lease.MAX_BYTES  # nosec B101
        assert len(decoded) % 2 == 0  # nosec B101 - PCM16 alignment
    # Independently generated valid PCM must round-trip; no speaker is opened.
    pcm = (data + b"\0" * 1764)[:4096]
    pcm = pcm[: len(pcm) - len(pcm) % 2]
    assert intercom_lease.decode_pcm(base64.b64encode(pcm).decode()) == pcm  # nosec B101
    try:
        query = json.loads(data)
    except (UnicodeDecodeError, ValueError, RecursionError):
        return
    if not isinstance(query, dict):
        return
    owner, token, mode = (query.get(key, "") for key in ("owner", "token", "mode"))
    if not all(isinstance(value, str) for value in (owner, token, mode)):
        return
    expired = query.get("expired") is True
    guard = intercom_lease.LeaseGuard(*(forbidden_hook for _ in range(4)))
    active = intercom_lease.Lease(
        "synthetic-token",
        "synthetic-owner",
        "talk",
        False,
        -1 if expired else float("inf"),
    )
    guard.active = active
    expected = (
        not expired
        and owner == active.owner
        and token == active.token
        and mode in ("", active.mode)
    )
    try:
        selected = guard.require(token, owner, mode)
    except ValueError:
        assert not expected  # nosec B101 - valid ownership must remain usable
    else:
        assert expected and selected is active  # nosec B101 - ownership boundary
    assert guard.active is active and guard.timer is None  # nosec B101
