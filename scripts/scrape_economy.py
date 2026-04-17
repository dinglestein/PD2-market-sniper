#!/usr/bin/env python3
from __future__ import annotations

import json

from economy import EconomyManager
from history import StateStore


if __name__ == "__main__":
    payload = EconomyManager(StateStore()).refresh(force=True)
    print(json.dumps({"refreshed_at": payload.get("refreshed_at"), "value_count": len(payload.get("values", {}))}, indent=2))
