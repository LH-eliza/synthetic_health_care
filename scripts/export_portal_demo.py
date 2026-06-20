#!/usr/bin/env python3
"""Write Margaret demo portal JSON for static Vercel deploy."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from portal_schema import demo_portal_payload  # noqa: E402

OUT = os.path.join(ROOT, "patient-portal", "src", "demoData.json")

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(demo_portal_payload(), f, indent=2)

print(f"Wrote {OUT}")
