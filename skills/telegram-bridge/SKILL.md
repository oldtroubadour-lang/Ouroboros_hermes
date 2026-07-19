---
name: telegram-channels
description: Search for public Telegram channels, subscribe to connections, and view posts through a clean Widgets panel.
version: 1.0.0
type: extension
entry: plugin.py
runtime: python3
permissions: [net, tool, route, widget]
dependencies: ["beautifulsoup4>=4.15.0"]
install_specs:
  - kind: pip
    package: "beautifulsoup4>=4.15.0"
env_from_settings: []
when_to_use: User asks to search for, add, manage, or read public Telegram channels.
timeout_sec: 120
---

# Telegram Channels Extension

This extension allows the system to interact with public Telegram channels. It scrapes messages from public channel preview pages (such as `t.me/s/username`) and requires no authentication or user session credentials.

## Exposed Tools

- `search` — find public channels by keywords using DuckDuckGo.
- `read` — parse latest messages from a public channel.
- `connect` — subscribe to a channel to add it to your connected panel.
- `disconnect` — unsubscribe/remove a connected channel.
- `list_connected` — list all currently connected channels.

## Widgets Page Integration

After reviewing and enabling this skill, a "Telegram Channels" widget will appear on your Widgets page. You can add channels, search for them, and browse the latest posts in real-time.
