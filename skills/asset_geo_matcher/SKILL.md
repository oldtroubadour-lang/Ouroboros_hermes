---
name: asset_geo_matcher
description: Geospatial match engine pairing bank offices and ATMs with local emergency incidents, persisting mapped threat profiles.
version: 1.0.0
type: extension
runtime: python3
entry: plugin.py
dependencies: ["openpyxl>=3.1.5"]
permissions: [net, tool, route, widget]
env_from_settings: []
when_to_use: User asks to map banks or ATMs to emergency zones, check active object threats, or run geospatial risk assessments.
timeout_sec: 120
---

# Asset Geo Matcher

An autonomous risk management extension that reads the bank's active workspace physical assets workbook and resolves/intersects their addresses with active disasters extracted in temp_storage.

## Tools
- `asset_geo_matcher__run_match()`: Runs the mapping job, scanning open incidents and pairing them with associated ATMs/branches from Downloads registry, updating temp_storage `threat_mapping`.
