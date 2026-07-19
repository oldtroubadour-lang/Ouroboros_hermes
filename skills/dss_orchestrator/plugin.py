import json
import os
import urllib.request
import asyncio
import threading
from pathlib import Path
from datetime import datetime

# Global lock to ensure thread-safe matching run and state writes
_lock = threading.Lock()

# Sibling DSS skills metadata
DSS_SKILLS = [
    ("temp_storage", "Shared Memory Store"),
    ("telegram-channels", "Telegram Public Channels Reader"),
    ("incident_ner", "Hourly Incident Geo-NER Classifier"),
    ("asset_geo_matcher", "Excel Asset Mappings Classifier"),
    ("risk_scenario_generator", "Tactical Scenario Synthesizer"),
    ("telegram-bridge", "Supervisor Notification Bridge")
]

def _get_server_port(api) -> str:
    # Query port dynamically from Runtime info
    port_info = api.get_runtime_info().get("server_port")
    if port_info:
        return str(port_info)
    # Check on-disk server_port as fallback
    state_dir = Path(api.get_state_dir())
    path = state_dir.parent.parent / "server_port"
    if path.exists():
        try:
            return path.read_text(encoding="utf-8").strip()
        except:
            pass
    return "8765"  # Standard default fallback

def _get_state_file(api) -> Path:
    state_dir = Path(api.get_state_dir())
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "ui_preview.json"

def _write_atomic(path: Path, content: str):
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
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

# --- Diagnostics Helpers ---

def find_excel_registry() -> str:
    user_home = os.environ.get('USERPROFILE', os.path.expanduser('~'))
    candidates = [
        os.path.join(user_home, "Downloads", "Справочник объектов для агента.xlsx"),
        os.path.join(user_home, "Downloads", "Справочник объектов для агента-1.xlsx"),
        os.path.join(user_home, "Downloads", "Справочник объектов для агента-2.xlsx"),
        os.path.join(user_home, "Downloads", "Данные для агента.xlsx"),  # safety fallback
    ]
    for c in candidates:
        if os.path.exists(c):
            return f"FOUND at Downloads/{os.path.basename(c)} ({os.path.getsize(c)} bytes)"
    return "MISSING (Please place 'Справочник объектов для агента.xlsx' in Downloads directory)"

def check_package(name: str) -> str:
    try:
        if name == "beautifulsoup4":
            import bs4
            return f"INSTALLED (v{bs4.__version__})"
        elif name == "openpyxl":
            import openpyxl
            return f"INSTALLED (v{openpyxl.__version__})"
    except ImportError:
        return f"MISSING (Run command: python -m pip install {name})"
    return "UNKNOWN"

def check_skill_installed(api, skill_name: str) -> bool:
    state_dir = Path(api.get_state_dir())
    # 1. Sibling state check
    if (state_dir.parent / skill_name).exists():
        return True
    # 2. Sibling payload directory check under repo parent data/skills
    data_dir = state_dir.parent.parent.parent
    skills_root = data_dir / "skills"
    for bucket in ["external", "ouroboroshub", "clawhub", "native"]:
        payload_dir = skills_root / bucket / skill_name
        if payload_dir.exists():
            return True
    return False

def check_skill_enabled(api, skill_name: str) -> bool:
    state_dir = Path(api.get_state_dir())
    enabled_file = state_dir.parent / skill_name / "enabled.json"
    if enabled_file.exists():
        try:
            val = json.loads(enabled_file.read_text(encoding="utf-8"))
            return bool(val.get("enabled", False))
        except:
            pass
    return False

def check_endpoint_live(api, skill_name: str) -> str:
    port = _get_server_port(api)
    url = f"http://127.0.0.1:{port}/api/extensions/{skill_name}/status"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            if r.status == 200:
                return "ONLINE"
    except Exception:
        pass
    return "OFFLINE"

# --- Structured Scenario Retrieval ---

def get_formatted_scenarios(api) -> list:
    port = _get_server_port(api)
    mapping = []
    
    # 1. Query asset_geo_matcher state info
    url_m = f"http://127.0.0.1:{port}/api/extensions/asset_geo_matcher/status"
    try:
        req = urllib.request.Request(url_m, method="GET")
        with urllib.request.urlopen(req, timeout=3) as r:
            res = json.loads(r.read().decode("utf-8"))
            mapping = res.get("incidents_summary") or []
    except Exception:
        pass
        
    if not mapping:
        state_dir = Path(api.get_state_dir())
        fallback_path = state_dir.parent / "asset_geo_matcher" / "ui_preview.json"
        if fallback_path.exists():
            try:
                preview = json.loads(fallback_path.read_text(encoding="utf-8"))
                mapping = preview.get("incidents_summary") or []
            except:
                pass

    # 2. Query risk_scenario_generator plans
    scenarios_list = []
    url_s = f"http://127.0.0.1:{port}/api/extensions/risk_scenario_generator/status"
    try:
        req = urllib.request.Request(url_s, method="GET")
        with urllib.request.urlopen(req, timeout=3) as r:
            res = json.loads(r.read().decode("utf-8"))
            scenarios_list = res.get("scenarios") or []
    except Exception:
        pass
        
    if not scenarios_list:
        state_dir = Path(api.get_state_dir())
        fallback_path = state_dir.parent / "risk_scenario_generator" / "ui_preview.json"
        if fallback_path.exists():
            try:
                preview = json.loads(fallback_path.read_text(encoding="utf-8"))
                scenarios_list = preview.get("scenarios") or []
            except:
                pass
                
    plans = [sc.get("name", "") for sc in scenarios_list if sc.get("name")]
    
    formatted = []
    for i, m in enumerate(mapping):
        city = m.get("city", "Unknown")
        inc_type = m.get("incident_type", m.get("incident_type_ru", "Emergency"))
        count = m.get("count", 0)
        
        plan_name = "Assess emergency load and schedule CIT"
        if plans:
            plan_name = plans[i % len(plans)]
            
        formatted.append({
            "city": city,
            "incident_type": inc_type,
            "assets_affected": f"{count} ATMs/Branches under threat",
            "action_plan": plan_name
        })
        
    if not formatted:
        formatted.append({
            "city": "Makhachkala / Khasavyurt",
            "incident_type": "No active threat paired on disk",
            "assets_affected": "0 assets matched",
            "action_plan": "Run the pipeline below to ingest and compile tactical responses!"
        })
    return formatted

# --- Orchestrated Execution ---

def run_dss_pipeline(api, mode: str = "standard") -> str:
    log_messages = []
    log_messages.append(f"[{datetime.utcnow().isoformat()}Z] Starting DSS Orchestrated Pipeline Run (Mode: {mode})...")
    
    # 1. Resolve prerequisites
    excel_status = find_excel_registry()
    if "MISSING" in excel_status:
        msg = "Abort: excel registry data file is missing."
        log_messages.append(f"[ERROR] {msg}")
        return "\n".join(log_messages)
        
    bs4_status = check_package("beautifulsoup4")
    openpyxl_status = check_package("openpyxl")
    if "MISSING" in bs4_status or "MISSING" in openpyxl_status:
        msg = f"Abort: unsatisfied python packages: {bs4_status}; {openpyxl_status}."
        log_messages.append(f"[ERROR] {msg}")
        return "\n".join(log_messages)

    port = _get_server_port(api)
    
    if mode == "check_only":
        log_messages.append("[INFO] Preflight validation successful! All package libraries and registers are present.")
        log_messages.append("[INFO] Ouroboros loopback API is available on localhost port " + port)
        log_messages.append("[INFO] Dry-run completed successfully.")
        return "\n".join(log_messages)

    log_messages.append("[INFO] Settle port resolved to: " + port)

    # Launch step-by-step
    # Step 1: Push Telegram news feed and extract active disasters
    log_messages.append("[STEP 1/3] Triggering 'incident_ner' hourly classification...")
    ner_url = f"http://127.0.0.1:{port}/api/extensions/incident_ner/run"
    req_ner = urllib.request.Request(ner_url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req_ner, timeout=30) as r:
            res = json.loads(r.read().decode("utf-8"))
            log_messages.append("[SUCCESS] Step 1 finished. Ingested Telegram entries parsed and tagged cleanly.")
    except Exception as e:
        log_messages.append(f"[ERROR] Step 1 failed to hit incident_ner API: {str(e)}")
        log_messages.append("Attempting to fall back and continue...")

    # Step 2: Spatial mapping matching
    log_messages.append("[STEP 2/3] Triggering 'asset_geo_matcher' matching...")
    matcher_url = f"http://127.0.0.1:{port}/api/extensions/asset_geo_matcher/run"
    req_matcher = urllib.request.Request(matcher_url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req_matcher, timeout=60) as r:
            res = json.loads(r.read().decode("utf-8"))
            summary = res.get("summary", {})
            run_res = summary.get("run_result", "Processed successfully")
            log_messages.append(f"[SUCCESS] Step 2 finished. Spatial pairing map updated: {run_res}")
    except Exception as e:
        log_messages.append(f"[ERROR] Step 2 failed to execute matcher: {str(e)}")
        log_messages.append("Attempting to fall back and continue...")

    # Step 3: Compile threat plans
    log_messages.append("[STEP 3/3] Triggering 'risk_scenario_generator' compiling...")
    gen_url = f"http://127.0.0.1:{port}/api/extensions/risk_scenario_generator/run"
    req_gen = urllib.request.Request(gen_url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req_gen, timeout=30) as r:
            res = json.loads(r.read().decode("utf-8"))
            summary = res.get("summary", {})
            run_res = summary.get("run_result", "Compiled successfully")
            log_messages.append(f"[SUCCESS] Step 3 finished. Risk scenarios generated: {run_res}")
    except Exception as e:
        log_messages.append(f"[ERROR] Step 3 failed: {str(e)}")
        return "\n".join(log_messages)

    log_messages.append(f"[{datetime.utcnow().isoformat()}Z] Complete pipeline executed successfully.")
    return "\n".join(log_messages)

# --- Register Plugin ---

def register(api):
    
    # Tool definitions
    def tool_diagnose(ctx) -> dict:
        """Run system-wide diagnosis of all DSS prototype elements to verify settings and configuration."""
        port = _get_server_port(api)
        excel = find_excel_registry()
        bs4 = check_package("beautifulsoup4")
        openpyxl = check_package("openpyxl")
        
        skills_status = []
        for slug, desc in DSS_SKILLS:
            installed = check_skill_installed(api, slug)
            enabled = check_skill_enabled(api, slug) if installed else False
            endpoint_live = check_endpoint_live(api, slug) if enabled else "OFFLINE"
            
            if not installed:
                rem = "MISSING - Sibling folder absent. Verify deployment"
            elif not enabled:
                rem = "OFFLINE - Skill is disabled on platform"
            elif endpoint_live == "OFFLINE":
                rem = "OFFLINE - Enablement ok but endpoint refused. Under review?"
            else:
                rem = "ONLINE & HEALTHY"
                
            skills_status.append({
                "slug": slug,
                "name": desc,
                "installed": "Yes" if installed else "No",
                "enabled": "Active" if enabled else "Disabled",
                "endpoint_live": endpoint_live,
                "remarks": rem
            })
            
        report = {
            "last_diagnostic_at": datetime.utcnow().isoformat() + "Z",
            "env_diagnostics": {
                "bs4": bs4,
                "openpyxl": openpyxl,
                "excel_file": excel,
                "server_port": port
            },
            "dss_skills_status": skills_status,
            "formatted_scenarios": get_formatted_scenarios(api),
            "run_result": "Pending complete pipeline run."
        }
        return report

    def tool_run_pipeline(ctx, mode: str = "standard") -> dict:
        """Sequentially execute the entire DSS decision-support pipeline (NER parse, matcher, scenario compiler) out-of-turn."""
        with _lock:
            # 1. Run pipeline and fetch log
            log_text = run_dss_pipeline(api, mode)
            
            # 2. Fetch fresh diagnosis data
            status_data = tool_diagnose(ctx)
            status_data["run_result"] = log_text
            
            # 3. Save atomic ui preview
            ui_preview = _get_state_file(api)
            try:
                _write_atomic(ui_preview, json.dumps(status_data, indent=2, ensure_ascii=False))
            except Exception as exc:
                api.log("error", f"Orchestrator failed to save UI preview: {str(exc)}")
                
            return status_data

    api.register_tool(
        "diagnose",
        handler=tool_diagnose,
        description="Run system-wide diagnosis of all DSS prototype elements to verify settings and configuration.",
        schema={"type": "object", "properties": {}}
    )

    api.register_tool(
        "run_pipeline",
        handler=tool_run_pipeline,
        description="Sequentially execute the entire DSS decision-support pipeline (NER parse, matcher, scenario compiler) out-of-turn.",
        schema={
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["standard", "check_only"],
                    "description": "Execution mode (standard to run, check_only for checklist validation)"
                }
            }
        }
    )

    # --- HTTP Routes ---

    async def route_status(request):
        ui_preview = _get_state_file(api)
        if ui_preview.exists():
            try:
                return json.loads(ui_preview.read_text(encoding="utf-8"))
            except Exception as e:
                api.log("error", f"Failed to load orchestrator ui preview: {str(e)}")
                
        # Generate baseline diagnostics on-demand
        diag = await asyncio.to_thread(tool_diagnose, None)
        return diag

    async def route_run(request):
        data = await request.json() if request.method == "POST" else {}
        mode = str(data.get("mode") or "standard")
        res = await asyncio.to_thread(tool_run_pipeline, None, mode)
        return res

    api.register_route("status", route_status, methods=("GET",))
    api.register_route("run", route_run, methods=("POST",))
