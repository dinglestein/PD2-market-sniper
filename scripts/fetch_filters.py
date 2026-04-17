#!/usr/bin/env python3
from __future__ import annotations

import json

from config import FILTERS


if __name__ == "__main__":
    print(json.dumps({"count": len(FILTERS), "filters": FILTERS}, indent=2, ensure_ascii=False))
