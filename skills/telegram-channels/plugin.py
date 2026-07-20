import json
import re
import asyncio
import urllib.request
import urllib.parse
import ssl
from pathlib import Path

# Create a robust, unverified SSL context to protect against local signature or EOF handshakes
_SSL_CONTEXT = ssl._create_unverified_context()

def _get_channels_file(api):
    state_dir = Path(api.get_state_dir())
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "channels.json"

def _load_channels(api):
    path = _get_channels_file(api)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            # Preserve corrupted JSON file instead of silent omission
            try:
                corrupted_path = path.with_suffix(".corrupt.json")
                path.rename(corrupted_path)
                api.log("warning", f"Telegram Channels config was corrupted, preserved and renamed to {corrupted_path.name}: {str(e)}")
            except Exception:
                pass
    # Default example channels
    default = [
        {
            "username": "durov",
            "title": "Pavel Durov",
            "subscribers": "11.7M subscribers",
            "description": "Founder of Telegram."
        }
    ]
    _save_channels(api, default)
    return default

def _save_channels(api, channels):
    path = _get_channels_file(api)
    path.write_text(json.dumps(channels, indent=2, ensure_ascii=False), encoding="utf-8")

def _get_posts_file(api):
    return Path(api.get_state_dir()) / "posts.json"

def _get_search_file(api):
    return Path(api.get_state_dir()) / "search_results.json"

def _load_posts(api):
    path = _get_posts_file(api)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except:
            pass
    return []

def _save_posts(api, posts):
    path = _get_posts_file(api)
    path.write_text(json.dumps(posts, indent=2, ensure_ascii=False), encoding="utf-8")

def _load_search(api):
    path = _get_search_file(api)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except:
            pass
    return []

def _save_search(api, search_results):
    path = _get_search_file(api)
    path.write_text(json.dumps(search_results, indent=2, ensure_ascii=False), encoding="utf-8")

def scrape_channel_info(username: str) -> dict:
    # Lazy import to ensure robust extension cataloging
    from bs4 import BeautifulSoup
    
    url = f"https://t.me/s/{username}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CONTEXT) as response:
            html = response.read().decode("utf-8")
        
        soup = BeautifulSoup(html, "html.parser")
        
        # Channel Title
        title_el = soup.find(class_="tgme_channel_info_header_title")
        title = title_el.get_text(strip=True) if title_el else username
        
        # Subscribers
        counter_el = soup.find(class_="tgme_channel_info_counter")
        subscribers = counter_el.get_text(strip=True) if counter_el else "Unknown subscribers"
        
        # Description
        desc_el = soup.find(class_="tgme_channel_info_description")
        description = desc_el.get_text(strip=True) if desc_el else ""
        
        return {
            "username": username,
            "title": title,
            "subscribers": subscribers,
            "description": description
        }
    except Exception as e:
        return {
            "username": username,
            "title": username,
            "subscribers": "Error loading subscribers",
            "description": f"Failed to retrieve info: {str(e)}"
        }

def scrape_channel_posts(username: str) -> list:
    # Lazy import to ensure robust extension cataloging
    from bs4 import BeautifulSoup
    
    url = f"https://t.me/s/{username}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36"}
    req = urllib.request.Request(url, headers=headers)
    posts = []
    try:
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CONTEXT) as response:
            html = response.read().decode("utf-8")
        
        soup = BeautifulSoup(html, "html.parser")
        
        for wrap in soup.find_all(class_="tgme_widget_message_wrap"):
            msg_el = wrap.find(class_="tgme_widget_message")
            if not msg_el:
                continue
            post_link = msg_el.get("data-post", "")
            
            date_el = wrap.find(class_="tgme_widget_message_date")
            time_el = date_el.find("time") if date_el else None
            date_str = ""
            if time_el:
                date_str = time_el.get("datetime") or time_el.get_text(strip=True)
                
            text_el = wrap.find(class_="tgme_widget_message_text")
            text = text_el.get_text("\n", strip=True) if text_el else ""
            
            views_el = wrap.find(class_="tgme_widget_message_views")
            views = views_el.get_text(strip=True) if views_el else ""
                    
            posts.append({
                "post_url": f"https://t.me/{post_link}" if post_link else "",
                "date": date_str,
                "text": text,
                "views": views
            })
            
        # Reverse to get newest posts first
        posts.reverse()
        return posts
    except Exception as e:
        return [{"date": "Error", "views": "—", "text": f"Failed to fetch posts: {str(e)}"}]

def search_telegram_channels(query_str: str) -> list:
    # Lazy import to ensure robust extension cataloging
    from bs4 import BeautifulSoup
    
    url = "https://html.duckduckgo.com/html/"
    data = urllib.parse.urlencode({"q": f"site:t.me/s {query_str}"}).encode("utf-8")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://html.duckduckgo.com/"
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    results = []
    try:
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CONTEXT) as response:
            html = response.read().decode("utf-8")
        
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select("a.result__a"):
            title = a.get_text(" ", strip=True)
            href = a.get("href", "")
            
            actual_url = href
            match = re.search(r"uddg=([^&]+)", href)
            if match:
                actual_url = urllib.parse.unquote(match.group(1))
                
            if "t.me/" in actual_url:
                m = re.search(r"t\.me/(?:s/)?([a-zA-Z0-9_]{5,32})", actual_url)
                if m:
                    username = m.group(1)
                    if username.lower() not in {"joinchat", "share", "contact", "addstickers", "setlanguage", "socks", "proxy", "tag"}:
                        results.append({
                            "title": title,
                            "url": f"https://t.me/s/{username}",
                            "username": username
                        })
        return results
    except Exception as e:
        return [{"title": f"Search failed: {str(e)}", "url": "", "username": "error"}]

def register(api):
    # --- State Cache ---
    transient_state = {
        "posts": [],
        "search_results": []
    }

    # --- Tool Handlers (Agent-callable) ---
    def tool_search(ctx, query: str):
        """Search for Telegram channels via DuckDuckGo site:t.me/s layout."""
        return search_telegram_channels(query)

    def tool_read(ctx, username: str):
        """Scrape and read the newest posts of a public Telegram channel."""
        # Sanitize username
        username_clean = username.split("/")[-1].strip("@").strip()
        info = scrape_channel_info(username_clean)
        posts = scrape_channel_posts(username_clean)
        return {
            "info": info,
            "posts": posts
        }

    def tool_connect(ctx, username: str):
        """Subscribe to a public Telegram channel and add it to the connected panel."""
        username_clean = username.split("/")[-1].strip("@").strip()
        channels = _load_channels(api)
        if any(c["username"].lower() == username_clean.lower() for c in channels):
            return f"Channel @{username_clean} is already connected."
        info = scrape_channel_info(username_clean)
        channels.append(info)
        _save_channels(api, channels)
        return f"Successfully subscribed and connected to {info['title']} (@{username_clean})."

    def tool_disconnect(ctx, username: str):
        """Remove a public Telegram channel subscription from the connected panel."""
        username_clean = username.split("/")[-1].strip("@").strip()
        channels = _load_channels(api)
        updated = [c for c in channels if c["username"].lower() != username_clean.lower()]
        if len(updated) == len(channels):
            return f"Channel @{username_clean} was not connected."
        _save_channels(api, updated)
        return f"Successfully unsubscribed and disconnected from @{username_clean}."

    def tool_list_connected(ctx):
        """List all currently subscribed/connected public Telegram channels."""
        return _load_channels(api)

    # Register tools
    api.register_tool(
        "search",
        handler=tool_search,
        description="Search for Telegram channels via DuckDuckGo site:t.me/s layout.",
        schema={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search keyword"}},
            "required": ["query"],
        }
    )
    api.register_tool(
        "read",
        handler=tool_read,
        description="Read messages from a public Telegram channel web preview.",
        schema={
            "type": "object",
            "properties": {"username": {"type": "string", "description": "Channel username"}},
            "required": ["username"],
        }
    )
    api.register_tool(
        "connect",
        handler=tool_connect,
        description="Subscribe to a public Telegram channel and save to persistent list.",
        schema={
            "type": "object",
            "properties": {"username": {"type": "string", "description": "Channel username to connect"}},
            "required": ["username"],
        }
    )
    api.register_tool(
        "disconnect",
        handler=tool_disconnect,
        description="Unsubscribe/remove a Telegram channel from persistent list.",
        schema={
            "type": "object",
            "properties": {"username": {"type": "string", "description": "Channel username to disconnect"}},
            "required": ["username"],
        }
    )
    api.register_tool(
        "list_connected",
        handler=tool_list_connected,
        description="Load and list all connected public Telegram channels.",
        schema={
            "type": "object",
            "properties": {},
        }
    )

    # --- HTTP Route Handlers (Fully Non-blocking via asyncio.to_thread) ---
    async def route_status(request):
        channels = await asyncio.to_thread(_load_channels, api)
        posts = await asyncio.to_thread(_load_posts, api)
        search_results = await asyncio.to_thread(_load_search, api)
        return {
            "channels": channels,
            "posts": posts,
            "search_results": search_results
        }

    async def route_add(request):
        data = await request.json()
        raw_user = str(data.get("username") or "").strip()
        if not raw_user:
            return {"error": "Username is required"}
        username = raw_user.split("/")[-1].strip("@").strip()
        channels = await asyncio.to_thread(_load_channels, api)
        if not any(c["username"].lower() == username.lower() for c in channels):
            info = await asyncio.to_thread(scrape_channel_info, username)
            channels.append(info)
            await asyncio.to_thread(_save_channels, api, channels)
        posts = await asyncio.to_thread(_load_posts, api)
        search_results = await asyncio.to_thread(_load_search, api)
        return {
            "channels": channels,
            "posts": posts,
            "search_results": search_results
        }

    async def route_remove(request):
        data = await request.json()
        raw_user = str(data.get("username") or "").strip()
        if not raw_user:
            return {"error": "Username is required"}
        username = raw_user.split("/")[-1].strip("@").strip()
        channels = await asyncio.to_thread(_load_channels, api)
        updated = [c for c in channels if c["username"].lower() != username.lower()]
        await asyncio.to_thread(_save_channels, api, updated)
        posts = await asyncio.to_thread(_load_posts, api)
        search_results = await asyncio.to_thread(_load_search, api)
        return {
            "channels": updated,
            "posts": posts,
            "search_results": search_results
        }

    async def route_fetch(request):
        data = await request.json()
        raw_user = str(data.get("username") or "").strip()
        if not raw_user:
            return {"error": "Username is required"}
        username = raw_user.split("/")[-1].strip("@").strip()
        posts = await asyncio.to_thread(scrape_channel_posts, username)
        await asyncio.to_thread(_save_posts, api, posts)
        channels = await asyncio.to_thread(_load_channels, api)
        search_results = await asyncio.to_thread(_load_search, api)
        return {
            "channels": channels,
            "posts": posts,
            "search_results": search_results
        }

    async def route_search(request):
        data = await request.json()
        query = str(data.get("query") or "").strip()
        if not query:
            return {"error": "Query is required"}
        results = await asyncio.to_thread(search_telegram_channels, query)
        await asyncio.to_thread(_save_search, api, results)
        channels = await asyncio.to_thread(_load_channels, api)
        posts = await asyncio.to_thread(_load_posts, api)
        return {
            "channels": channels,
            "posts": posts,
            "search_results": results
        }

    api.register_route("status", route_status, methods=("GET",))
    api.register_route("add", route_add, methods=("POST",))
    api.register_route("remove", route_remove, methods=("POST",))
    api.register_route("fetch", route_fetch, methods=("POST",))
    api.register_route("search", route_search, methods=("POST",))

    # --- UI Declarative Tab ---
    api.register_ui_tab(
        "panel",
        "Telegram",
        icon="extension",
        render={
            "kind": "declarative",
            "schema_version": 1,
            "span": 2,
            "components": [
                {
                    "type": "poll",
                    "route": "status",
                    "auto_start": True,
                    "label": "Sync Subscriptions"
                },
                {
                    "type": "markdown",
                    "text": "### 📖 Read Latest Posts\nSelect and view the newest messages from any public Telegram channel."
                },
                {
                    "type": "form",
                    "route": "fetch",
                    "method": "POST",
                    "submit_label": "Fetch Posts",
                    "fields": [
                        {
                            "type": "text",
                            "name": "username",
                            "label": "Channel name or username (e.g., durov)",
                            "required": True
                        }
                    ]
                },
                {
                    "type": "table",
                    "path": "posts",
                    "columns": [
                        {"path": "date", "label": "Timestamp / Date"},
                        {"path": "views", "label": "Views"},
                        {"path": "text", "label": "Message Text"}
                    ]
                },
                {
                    "type": "markdown",
                    "text": "### 🔍 Search & Subscribe\nSearch DuckDuckGo for public Telegram channels and join them with one click."
                },
                {
                    "type": "form",
                    "route": "search",
                    "method": "POST",
                    "submit_label": "Search Channel",
                    "fields": [
                        {
                            "type": "text",
                            "name": "query",
                            "label": "Search Keywords (e.g. python, space)",
                            "required": True
                        }
                    ]
                },
                {
                    "type": "table",
                    "path": "search_results",
                    "columns": [
                        {"path": "title", "label": "Match"},
                        {"path": "username", "label": "Username"},
                        {"path": "url", "label": "Preview Link"}
                    ]
                },
                {
                    "type": "form",
                    "route": "add",
                    "method": "POST",
                    "submit_label": "Subscribe / Connect to Username",
                    "fields": [
                        {
                            "type": "text",
                            "name": "username",
                            "label": "Connect Username",
                            "required": True
                        }
                    ]
                },
                {
                    "type": "markdown",
                    "text": "### 📋 Manage Connected Channels"
                },
                {
                    "type": "table",
                    "path": "channels",
                    "columns": [
                        {"path": "title", "label": "Channel Name"},
                        {"path": "username", "label": "Username"},
                        {"path": "subscribers", "label": "Subscribers"},
                        {"path": "description", "label": "Description"}
                    ]
                },
                {
                    "type": "form",
                    "route": "remove",
                    "method": "POST",
                    "submit_label": "Disconnect Channel",
                    "fields": [
                        {
                            "type": "text",
                            "name": "username",
                            "label": "Disconnect Username",
                            "required": True
                        }
                    ]
                }
            ]
        }
    )
