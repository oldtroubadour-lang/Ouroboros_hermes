---
name: risk_scenario_generator
description: Logic core generating structured decision scenarios and management risk summaries for bank operations when disasters occur.
version: 1.0.0
type: extension
runtime: python3
entry: plugin.py
dependencies: []
permissions: [net, tool, route, widget]
env_from_settings: []
when_to_use: User asks to generate response scenarios, summarize bank emergency risks, or assess operational needs for leadership decision-making.
timeout_sec: 120
---

# Risk Scenario Generator

Decision support system extension for bank leadership. It leverages the matched geospatial threat pairs `threat_mapping` in `temp_storage`, aligns them with optional guidelines from Downloads, and outputs 2-4 comprehensive operational-response scenarios satisfying client and bank needs.

## Tools
- `risk_scenario_generator__run_generation()`: Analyzes active threat pairings in temp_storage and compiles key risk response scenarios, persisting the result as 'risk_scenarios'.
