---
name: temp_storage
description: Temporary storage for textual or markdown payloads, making them searchable and easily accessible across tasks.
version: 1.0.0
type: extension
runtime: python3
entry: plugin.py
permissions: [tool, route, widget]
env_from_settings: []
when_to_use: User asks to store text data temporarily, retrieve stored notes, list stored payloads, search storage, or share text content between different tasks/skills.
timeout_sec: 60
---

# Temp Storage

Provides a reliable, local file-backed temporary storage for capturing, searching, and sharing textual notes or payload content across various client tasks and tools.

## Tools
- `temp_storage__write(key, value, description)`: Capture/write text and write metadata in index.
- `temp_storage__read(key)`: Retrieve/read stored text for a key.
- `temp_storage__list()`: List keys and metadata.
- `temp_storage__delete(key)`: Remove a text entry.
- `temp_storage__search(query)`: Search across stored metadata and payloads.
