---
name: dss_orchestrator
description: Orchestration, diagnostics, and end-to-end execution of the Decision Support System (DSS) prototype modules.
version: 1.0.0
type: extension
runtime: python3
entry: plugin.py
permissions: [net, tool, route, widget]
env_from_settings: []
when_to_use: User asks to check DSS pipeline status, diagnose/troubleshoot skills, run end-to-end emergency matching/scenarios, or coordinate different elements of the prototype.
timeout_sec: 180
ui_tab:
  tab_id: panel
  title: DSS Orchestrator
  icon: tune
  render:
    kind: declarative
    schema_version: 1
    span: 2
    components:
      - type: poll
        route: status
        auto_start: True
        label: Sync Orchestrator
      - type: markdown
        text: "## 🛠️ DSS System Control Center\nThis dashboard manages, diagnoses, repairs, and coordinates the entire prototype decision support pipeline."
      - type: kv
        label: "🔍 System Diagnostics Overview"
        target: result
        fields:
          - label: "BS4 (BeautifulSoup)"
            path: env_diagnostics.bs4
          - label: "openpyxl (Excel Parser)"
            path: env_diagnostics.openpyxl
          - label: "Excel Data File status"
            path: env_diagnostics.excel_file
          - label: "Server Port"
            path: env_diagnostics.server_port
          - label: "Last Diagnostic Check"
            path: last_diagnostic_at
      - type: table
        label: "🧩 Skill Status Board"
        path: dss_skills_status
        columns:
          - path: name
            label: "Skill Name"
          - path: installed
            label: "Installed"
          - path: enabled
            label: "Enabled"
          - path: endpoint_live
            label: "HTTP Endpoint"
          - path: remarks
            label: "Action Items / Remarks"
      - type: markdown
        text: "### 🚦 Manual Pipeline Orchestration\nRun the entire DSS pipeline sequentially (channels parse ➡️ matching ➡️ tactical scenario generation) out-of-turn or on demand."
      - type: form
        route: run
        method: POST
        submit_label: "Run Complete Pipeline"
        fields:
          - type: select
            name: mode
            label: "Execution Mode"
            options:
              - value: "standard"
                label: "Standard Pipeline Execution"
              - value: "check_only"
                label: "Dry-run / Verification only"
            required: True
      - type: markdown
        text: "#### Execution Log"
      - type: code
        label: "Last Execution Result Log"
        path: run_result
      - type: table
        label: "🚨 Active DSS Scenario Summary"
        path: formatted_scenarios
        columns:
          - path: city
            label: "City"
          - path: incident_type
            label: "Incident Detected"
          - path: assets_affected
            label: "Assets at Risk"
          - path: action_plan
            label: "Recommended Tactical Action"
---

# DSS Orchestrator

The DSS Orchestrator acts as the master coordinator, health monitor, and workflow executor of the Ouroboros Decision Support System prototype.

It is designed to ensure seamless cooperation between:
- `telegram-channels` (Web-based news sensor)
- `temp_storage` (Shared persistent memory)
- `incident_ner` (NER disaster extraction)
- `asset_geo_matcher` (ATM and office spatial classifier)
- `risk_scenario_generator` (Emergency scenario synthesizer)
- `telegram-bridge` (Manager notification bridge)
