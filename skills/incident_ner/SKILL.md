---
name: incident_ner
description: Track emergency incidents and spatial threats from connected Telegram channels.
version: 1.0.0
type: extension
entry: plugin.py
runtime: python3
permissions: [net, tool, route, widget, supervised_task]
env_from_settings: []
when_to_use: User asks to analyze connected Telegram channel posts, extract incident logs, or check active_incidents.
timeout_sec: 120
scheduled_tasks:
  - name: sync_and_check
    cron: "0 * * * *"
    description: Hourly background task to transfer posts into temp_storage (messages_queue), do NER check, and purge old posts.
---

# Incident NER Extension

Analyzes connected Telegram channels, processes their messages in real-time, extracts structured emergency events (fires, flooding, connection blocks, fuel shortage, electrical blackouts) into active incident logs, and maintains the results in temp_storage.
