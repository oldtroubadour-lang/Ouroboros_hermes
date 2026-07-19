import json
import re
import os
import asyncio
import threading
from pathlib import Path
from datetime import datetime

# Global threading lock to ensure thread-safe read-modify-write on index.json
_lock = threading.Lock()

def _get_index_file(api) -> Path:
    state_dir = Path(api.get_state_dir())
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "index.json"

def _get_store_dir(api) -> Path:
    state_dir = Path(api.get_state_dir())
    store_dir = state_dir / "store"
    store_dir.mkdir(parents=True, exist_ok=True)
    return store_dir

def _get_retrieved_file(api) -> Path:
    return Path(api.get_state_dir()) / "retrieved.json"

def _get_search_file(api) -> Path:
    return Path(api.get_state_dir()) / "search_results.json"

def _sanitize_key(key: str) -> str:
    # Retain strictly alphanumeric, dashes, and underscores
    clean = re.sub(r"[^a-zA-Z0-9_\-]", "", key).strip()
    if not clean or clean in {"", ".", ".."}:
        clean = "unnamed"
    return clean

def _get_key_path(api, key: str) -> Path:
    clean = _sanitize_key(key)
    store_dir = _get_store_dir(api)
    target = (store_dir / f"{clean}.txt").resolve()
    # Resolve containment explicitly post-resolution/symlink check
    if not target.is_relative_to(store_dir.resolve()):
        raise ValueError("Path traversal violation detected")
    return target

def _write_atomic(path: Path, content: str):
    # Cross-platform thread-safe and process-safe atomic save using standard library tempfile/replace
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write to temp file in same directory to ensure same-mount atomic replace
    fd, temp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(temp_path, str(path))
    except Exception as e:
        try:
            os.unlink(temp_path)
        except:
            pass
        raise e

def _load_index(api) -> dict:
    path = _get_index_file(api)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            # Preserve corrupted JSON file instead of silent clobbering
            try:
                corrupted_path = path.with_suffix(".corrupt.json")
                path.rename(corrupted_path)
                api.log("warning", f"Temp Storage index.json was corrupted, saved as {corrupted_path.name}: {str(e)}")
            except:
                pass
    return {"keys": {}}

def _save_index(api, index: dict):
    path = _get_index_file(api)
    _write_atomic(path, json.dumps(index, indent=2, ensure_ascii=False))

def _load_retrieved(api) -> dict:
    path = _get_retrieved_file(api)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except:
            pass
    return {}

def _save_retrieved(api, item: dict):
    path = _get_retrieved_file(api)
    _write_atomic(path, json.dumps(item, indent=2, ensure_ascii=False))

def _load_search_results(api) -> list:
    path = _get_search_file(api)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except:
            pass
    return []

def _save_search_results(api, results: list):
    path = _get_search_file(api)
    _write_atomic(path, json.dumps(results, indent=2, ensure_ascii=False))

# --- Tool Call Implementations ---

def store_write(api, key: str, value: str, description: str = "") -> dict:
    with _lock:
        key_clean = _sanitize_key(key)
        # Store individual body content
        target_path = _get_key_path(api, key_clean)
        _write_atomic(target_path, value)
        
        # Load index and update metadata
        index = _load_index(api)
        now_str = datetime.utcnow().isoformat() + "Z"
        
        is_new = key_clean not in index["keys"]
        created_at = index["keys"][key_clean]["created_at"] if not is_new else now_str
        
        meta = {
            "key": key_clean,
            "description": description or ("Updated entry" if not is_new else "Stored entry"),
            "size": len(value),
            "created_at": created_at,
            "updated_at": now_str
        }
        index["keys"][key_clean] = meta
        _save_index(api, index)
        return meta

def store_read(api, key: str) -> dict:
    key_clean = _sanitize_key(key)
    target_path = _get_key_path(api, key_clean)
    if not target_path.exists():
        return {"error": f"Key '{key_clean}' not found in storage."}
    
    value = target_path.read_text(encoding="utf-8")
    
    # Read index metadata
    with _lock:
        index = _load_index(api)
        meta = index["keys"].get(key_clean, {
            "key": key_clean,
            "description": "Orphaned text content resolved from disk",
            "size": len(value),
            "created_at": "unknown",
            "updated_at": "unknown"
        })
    
    result = {
        "key": key_clean,
        "description": meta["description"],
        "value": value,
        "size": meta["size"],
        "created_at": meta["created_at"],
        "updated_at": meta["updated_at"]
    }
    _save_retrieved(api, result)
    return result

def store_list(api) -> list:
    with _lock:
        index = _load_index(api)
        # Validate that disk files still exist (prevent deleted/stale entries)
        store_dir = _get_store_dir(api)
        valid_keys = []
        for k, meta in list(index["keys"].items()):
            file_path = store_dir / f"{k}.txt"
            if file_path.exists():
                valid_keys.append(meta)
            else:
                # Cleanup index
                index["keys"].pop(k, None)
        _save_index(api, index)
    # Sort keys by updated_at descending
    valid_keys.sort(key=lambda x: x["updated_at"], reverse=True)
    return valid_keys

def store_delete(api, key: str) -> dict:
    with _lock:
        key_clean = _sanitize_key(key)
        target_path = _get_key_path(api, key_clean)
        existed = target_path.exists()
        if existed:
            try:
                target_path.unlink()
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to delete disk payload for key '{key_clean}': {str(e)}"
                }
        
        index = _load_index(api)
        meta_existed = index["keys"].pop(key_clean, None)
        _save_index(api, index)
        
        # Clear retrieved cache if it matches
        retrieved = _load_retrieved(api)
        if retrieved.get("key") == key_clean:
            _save_retrieved(api, {})
            
        return {
            "success": existed or (meta_existed is not None),
            "msg": f"Successfully deleted key '{key_clean}'." if existed else f"Key '{key_clean}' was not found."
        }

def store_search(api, query: str) -> list:
    query_clean = query.strip().lower()
    if not query_clean:
        return []
    
    keys_meta = store_list(api)
    results = []
    
    for meta in keys_meta:
        k = meta["key"]
        description = meta["description"].lower()
        
        # Check key and description matches first
        key_match = query_clean in k.lower() or query_clean in description
        
        # Check content match
        content_match = False
        snippet = ""
        file_path = _get_key_path(api, k)
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            idx = content.lower().find(query_clean)
            if idx != -1:
                content_match = True
                # Generate a 100 character snippet
                start = max(0, idx - 40)
                end = min(len(content), idx + 60)
                snippet = content[start:end].replace("\n", " ").strip()
                if start > 0:
                    snippet = "..." + snippet
                if end < len(content):
                    snippet = snippet + "..."
        
        if key_match or content_match:
            results.append({
                "key": k,
                "description": meta["description"],
                "size": meta["size"],
                "snippet": snippet or "Match found in metadata.",
                "updated_at": meta["updated_at"]
            })
            
    _save_search_results(api, results)
    return results

def register(api):
    
    # --- Tool Definitions ---

    def tool_write(ctx, key: str, value: str, description: str = ""):
        """Store or update a text payload under the specified key."""
        return store_write(api, key, value, description)

    def tool_read(ctx, key: str):
        """Retrieve the textual contents and metadata for a given key."""
        return store_read(api, key)

    def tool_list(ctx):
        """List all available keys, notes, sizes, and timestamps."""
        return store_list(api)

    def tool_delete(ctx, key: str):
        """Delete a key and its associated text payload file from the store."""
        return store_delete(api, key)

    def tool_search(ctx, query: str):
        """Search across stored keys, notes, and full text payloads."""
        return store_search(api, query)

    api.register_tool(
        "write",
        handler=tool_write,
        description="Store or update a text payload under the specified key.",
        schema={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Safe identifier key"},
                "value": {"type": "string", "description": "The textual payload to be stored"},
                "description": {"type": "string", "description": "Optional short note summarizing the contents"}
            },
            "required": ["key", "value"]
        }
    )

    api.register_tool(
        "read",
        handler=tool_read,
        description="Retrieve the textual contents and metadata for a given key.",
        schema={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Safe identifier to load"}
            },
            "required": ["key"]
        }
    )

    api.register_tool(
        "list",
        handler=tool_list,
        description="List all available keys, notes, sizes, and timestamps.",
        schema={"type": "object", "properties": {}}
    )

    api.register_tool(
        "delete",
        handler=tool_delete,
        description="Delete a key and its associated text payload file from the store.",
        schema={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "The identifier key to delete"}
            },
            "required": ["key"]
        }
    )

    api.register_tool(
        "search",
        handler=tool_search,
        description="Search across stored keys, notes, and full text payloads.",
        schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search term to find"}
            },
            "required": ["query"]
        }
    )

    # --- HTTP Route Handlers (Fully Non-blocking via asyncio.to_thread forwarding) ---

    async def route_status(request):
        keys = await asyncio.to_thread(store_list, api)
        retrieved = await asyncio.to_thread(_load_retrieved, api)
        search_results = await asyncio.to_thread(_load_search_results, api)
        return {
            "keys": keys,
            "retrieved": retrieved,
            "search_results": search_results
        }

    async def route_store(request):
        data = await request.json()
        key = str(data.get("key") or "").strip()
        value = str(data.get("value") or "")
        description = str(data.get("description") or "").strip()
        if not key or not value:
            return {"error": "Key and value are both required fields."}
        
        await asyncio.to_thread(store_write, api, key, value, description)
        return await route_status(request)

    async def route_retrieve(request):
        data = await request.json()
        key = str(data.get("key") or "").strip()
        if not key:
            return {"error": "Key is a required field."}
        
        await asyncio.to_thread(store_read, api, key)
        return await route_status(request)

    async def route_delete(request):
        data = await request.json()
        key = str(data.get("key") or "").strip()
        if not key:
            return {"error": "Key is a required field."}
        
        await asyncio.to_thread(store_delete, api, key)
        return await route_status(request)

    async def route_search(request):
        data = await request.json()
        query = str(data.get("query") or "").strip()
        if not query:
            return {"error": "Query is a required field."}
        
        await asyncio.to_thread(store_search, api, query)
        return await route_status(request)

    api.register_route("status", route_status, methods=("GET",))
    api.register_route("store", route_store, methods=("POST",))
    api.register_route("retrieve", route_retrieve, methods=("POST",))
    api.register_route("delete", route_delete, methods=("POST",))
    api.register_route("search", route_search, methods=("POST",))

    # --- UI Declarative Tab layout ---

    api.register_ui_tab(
        "panel",
        "Temp Storage",
        icon="folder",
        render={
            "kind": "declarative",
            "schema_version": 1,
            "span": 2,
            "components": [
                {
                    "type": "poll",
                    "route": "status",
                    "auto_start": True,
                    "label": "Sync Storage"
                },
                {
                    "type": "markdown",
                    "text": "### 💾 Store / Update Text Payloads\nPersist text notes or large payload contents locally."
                },
                {
                    "type": "form",
                    "route": "store",
                    "method": "POST",
                    "submit_label": "Save Text",
                    "fields": [
                        {
                            "type": "text",
                            "name": "key",
                            "label": "Safe key identifier (e.g., prompt_lesson_1)",
                            "required": True
                        },
                        {
                            "type": "text",
                            "name": "description",
                            "label": "Optional short summary"
                        },
                        {
                            "type": "textarea",
                            "name": "value",
                            "label": "Content value (Markdown or plain text)",
                            "required": True
                        }
                    ]
                },
                {
                    "type": "markdown",
                    "text": "### 📖 Retrieve Stored Payload\nEnter a key to load and view its formatted text contents."
                },
                {
                    "type": "form",
                    "route": "retrieve",
                    "method": "POST",
                    "submit_label": "Retrieve Contents",
                    "fields": [
                        {
                            "type": "text",
                            "name": "key",
                            "label": "Enter key name to read",
                            "required": True
                        }
                    ]
                },
                {
                    "type": "markdown",
                    "text": "#### Retrieved Payload Information"
                },
                {
                    "type": "kv",
                    "target": "result",
                    "fields": [
                        {"label": "Key", "path": "retrieved.key"},
                        {"label": "Description", "path": "retrieved.description"},
                        {"label": "Size (bytes)", "path": "retrieved.size"},
                        {"label": "Last Updated", "path": "retrieved.updated_at"}
                    ]
                },
                {
                    "type": "code",
                    "label": "Payload Text Content",
                    "path": "retrieved.value"
                },
                {
                    "type": "markdown",
                    "text": "### 🔍 Search Stored items\nInstant case-insensitive text search over all keys, notes, and file contents."
                },
                {
                    "type": "form",
                    "route": "search",
                    "method": "POST",
                    "submit_label": "Search Storage",
                    "fields": [
                        {
                            "type": "text",
                            "name": "query",
                            "label": "Search terms",
                            "required": True
                        }
                    ]
                },
                {
                    "type": "table",
                    "path": "search_results",
                    "columns": [
                        {"path": "key", "label": "Key Name"},
                        {"path": "description", "label": "Summary Description"},
                        {"path": "snippet", "label": "Content Preview Match"}
                    ]
                },
                {
                    "type": "markdown",
                    "text": "### 📋 Manage Stored Elements"
                },
                {
                    "type": "table",
                    "path": "keys",
                    "columns": [
                        {"path": "key", "label": "Key Name"},
                        {"path": "description", "label": "Note Summary"},
                        {"path": "size", "label": "Length (chars)"},
                        {"path": "updated_at", "label": "Last Modified"}
                    ]
                },
                {
                    "type": "form",
                    "route": "delete",
                    "method": "POST",
                    "submit_label": "Delete Item",
                    "fields": [
                        {
                            "type": "text",
                            "name": "key",
                            "label": "Delete Key Name",
                            "required": True
                        }
                    ]
                }
            ]
        }
    )
