from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from .graph_store import TxEvent

CHANNELS = ["wire", "ach", "card", "crypto", "cash"]
COUNTRIES = ["US", "US", "US", "US", "GB", "CY", "AE", "SG"]


def generate_stream(n: int, seed: int | None = None) -> list[TxEvent]:
    rng = random.Random(seed) if seed is not None else random.Random()
    accounts = [f"ACC_{i:04d}" for i in range(1, 350)]
    ring = [f"RING_{i:03d}" for i in range(1, 15)]

    base = datetime.now(timezone.utc) - timedelta(minutes=20)
    out: list[TxEvent] = []

    for i in range(max(1, int(n))):
        ts = base + timedelta(seconds=i * rng.uniform(1.0, 7.5))
        suspicious = rng.random() < 0.14

        if suspicious:
            sender = rng.choice(ring)
            receiver = rng.choice([x for x in ring if x != sender])
            amount = rng.uniform(4_500, 32_000)
            channel = rng.choice(["wire", "crypto", "cash"])
            country_from = rng.choice(["US", "GB", "CY"])
            country_to = rng.choice(["AE", "SG", "CY", "US"])
        else:
            sender = rng.choice(accounts)
            receiver = rng.choice([x for x in accounts if x != sender])
            amount = rng.lognormvariate(5.7, 0.85)
            channel = rng.choice(CHANNELS)
            country_from = rng.choice(COUNTRIES)
            country_to = rng.choice(COUNTRIES)

        out.append(
            TxEvent(
                tx_id=f"SIM-{i:08d}",
                sender_id=sender,
                receiver_id=receiver,
                amount=float(amount),
                currency="USD",
                channel=channel,
                country_from=country_from,
                country_to=country_to,
                timestamp_utc=ts,
            )
        )

    return out
