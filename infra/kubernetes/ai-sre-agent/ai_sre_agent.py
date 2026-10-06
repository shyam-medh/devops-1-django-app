import os
import json
import subprocess
import logging
import re
from datetime import datetime, timezone
from robusta.api import (
    action,
    Finding,
    FindingSeverity,
    FindingType,
    MarkdownBlock,
    PodEvent,
    JobEvent,
    PrometheusKubernetesAlert,
    KubernetesAnyChangeEvent,
    ExecutionBaseEvent
)

try:
    import requests as _req
except ImportError:
    _req = None

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
)

# ---------------------------------------------------------------------------
# Tools Definition
# ---------------------------------------------------------------------------
TOOLS = [
    {
        "functionDeclarations": [
            {
                "name": "kubectl_read",
                "description": "Read cluster state (read-only). Allowed commands: kubectl get, describe, logs, events.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "command": {
                            "type": "STRING",
                            "description": "The kubectl command to run, e.g. 'kubectl get pod <name> -n <ns>'"
                        }
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "http_probe",
                "description": "Perform an HTTP GET request to check endpoint health.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "url": {
                            "type": "STRING"
                        }
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "tcp_probe",
                "description": "Test TCP connectivity to a host and port from within the cluster.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "host": {
                            "type": "STRING"
                        },
                        "port": {
                            "type": "INTEGER"
                        },
                        "namespace": {
                            "type": "STRING"
                        }
                    },
                    "required": ["host", "port", "namespace"]
                }
            },
            {
                "name": "get_rollout_history",
                "description": "Get the rollout history of a deployment.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "deployment": {
                            "type": "STRING"
                        },
                        "namespace": {
                            "type": "STRING"
                        }
                    },
                    "required": ["deployment", "namespace"]
                }
            }
        ]
    }
]

def _run(cmd: str, timeout: int = 30) -> str:
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (result.stdout + result.stderr).strip()
    except subprocess.TimeoutExpired:
        return f"[timeout after {timeout}s]: {cmd}"
    except Exception as e:
        return f"[error: {e}]"

def execute_tool(name: str, args: dict) -> str:
    if name == "kubectl_read":
        cmd = args.get("command", "")
        if not cmd.startswith("kubectl ") or not any(v in cmd for v in [" get ", " describe ", " logs ", " events "]):
            return "Error: only kubectl get/describe/logs/events are allowed."
        if any(bad in cmd for bad in [";", "|", "&", ">", "<"]):
            return "Error: shell operators are not allowed."
        return _run(cmd)
    elif name == "http_probe":
        url = args.get("url")
        return _run(f"curl -sSL -D - --max-time 10 {url}")
    elif name == "tcp_probe":
        host = args.get("host")
        port = args.get("port")
        ns = args.get("namespace", "default")
        return _run(f"kubectl run tmp-tcp-probe-{int(datetime.now().timestamp())} --image=busybox --restart=Never --rm -i -n {ns} -- nc -zv {host} {port}")
    elif name == "get_rollout_history":
        dep = args.get("deployment")
        ns = args.get("namespace", "default")
        return _run(f"kubectl rollout history deployment/{dep} -n {ns}")
    return f"Unknown tool: {name}"

# ---------------------------------------------------------------------------
# Policy Engine
# ---------------------------------------------------------------------------
def _is_safe_command(cmd: str, is_django_ns: bool) -> tuple:
    cmd = cmd.strip()
    if not cmd.startswith("kubectl "):
        return False, "Not a kubectl command"
    
    # Must be in django namespace for write operations
    if not is_django_ns:
        return False, "Write operations only allowed in 'django' namespace."

    safe_prefixes = ["kubectl rollout restart", "kubectl rollout undo", "kubectl scale"]
    patch_prefixes = ["kubectl set image", "kubectl set env", "kubectl set resources", "kubectl patch"]

    for sp in safe_prefixes:
        if cmd.startswith(sp):
            return True, ""
            
    for pp in patch_prefixes:
        if cmd.startswith(pp):
            if "deployment" not in cmd and "deploy/" not in cmd:
                return False, "Patch operations only allowed on deployments."
            return True, ""
            
    return False, "Command verb not in allowlist."

# ---------------------------------------------------------------------------
# Investigation Loop
# ---------------------------------------------------------------------------
def _investigate(initial_prompt: str, is_django_ns: bool) -> dict:
    if not _req or not GEMINI_API_KEY:
        return {"error": "Missing requests module or GEMINI_API_KEY"}

    messages = [{"role": "user", "parts": [{"text": initial_prompt}]}]
    
    for step in range(12):
        payload = {
            "contents": messages,
            "tools": TOOLS,
            "systemInstruction": {
                "parts": [{"text": "You are an elite Kubernetes SRE. Investigate the failure step by step using tools. "
                                   "Once you identify the root cause, return a JSON response with the fix. "
                                   "Ensure the JSON matches exactly: { \"root_cause\": \"...\", \"evidence\": [\"...\"], \"fix_commands\": [\"...\"], \"risk\": \"high/low\", \"verification\": \"...\", \"rollback\": \"...\" }.\n"
                                   "Do not include any Markdown block backticks, just output raw JSON."}]
            },
            "generationConfig": {
                "temperature": 0.05,
            }
        }
        
        try:
            for attempt in range(3):
                try:
                    resp = _req.post(GEMINI_URL, json=payload, timeout=60)
                    resp.raise_for_status()
                    break
                except Exception as e:
                    if attempt == 2: raise
                    import time; time.sleep(2)
            data = resp.json()
            part = data["candidates"][0]["content"]["parts"][0]
            
            # Add model response to history
            messages.append({"role": "model", "parts": [part]})
            
            if "functionCall" in part:
                call = part["functionCall"]
                name = call["name"]
                args = call.get("args", {})
                logger.info(f"AI-SRE Tool call: {name}({args})")
                
                result = execute_tool(name, args)
                if len(result) > 5000:
                    result = result[:2500] + "\n...[TRUNCATED]...\n" + result[-2500:]
                    
                messages.append({
                    "role": "user", # The API for some reason requires the function response as user or tool role, let's use user role with functionResponse or just append text. Wait, standard is role: user for functionResponse in REST if we aren't strict, but let's use the correct REST structure.
                    "parts": [{"text": f"Function {name} returned:\n{result}"}]
                })
            else:
                text = part.get("text", "")
                m = re.search(r'\{.*\}', text, re.DOTALL)
                if m:
                    try:
                        parsed = json.loads(m.group(0))
                        parsed["steps"] = step + 1
                        return parsed
                    except json.JSONDecodeError:
                        return {"error": "Invalid JSON response", "raw": text}
                else:
                    return {"error": "No JSON found", "raw": text}
                    
        except Exception as e:
            logger.error(f"AI-SRE loop error: {e}")
            return {"error": str(e)}
            
    return {"error": "Max steps reached"}

# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def _run_healing_loop(context: str, namespace: str, resource: str):
    logger.info(f"AI-SRE starting investigation for {namespace}/{resource}")
    is_django = namespace == "django"
    
    prompt = f"Failure detected in namespace '{namespace}' on resource '{resource}'. Context: {context}\nInvestigate this issue using the provided tools."
    
    result = _investigate(prompt, is_django)
    if "error" in result:
        logger.error(f"AI-SRE investigation failed: {result['error']}")
        return result, []
        
    fix_results = []
    commands = result.get("fix_commands", [])
    if not commands:
        fix_results.append("No fix commands suggested.")
        return result, fix_results
        
    for cmd in commands:
        safe, reason = _is_safe_command(cmd, is_django)
        if not safe:
            fix_results.append(f"Blocked: {cmd} - {reason}")
            continue
            
        # Dry run
        dry_run_cmd = f"{cmd} --dry-run=server"
        dry_out = _run(dry_run_cmd)
        if "error" in dry_out.lower() or "forbidden" in dry_out.lower():
            fix_results.append(f"Dry run failed for {cmd}:\n{dry_out}")
            continue
            
        # Execute
        logger.info(f"AI-SRE Executing fix: {cmd}")
        out = _run(cmd)
        fix_results.append(f"Executed: {cmd}\nOutput: {out}")
        
    return result, fix_results

def _build_finding(title: str, ai_result: dict, exec_results: list) -> Finding:
    sev = FindingSeverity.HIGH
    finding = Finding(
        title=title,
        source=FindingType.ISSUE,
        aggregation_key=title,
        severity=sev,
    )
    
    if "error" in ai_result:
        finding.add_enrichment([MarkdownBlock(f"**AI Error:** {ai_result['error']}\n\n**Raw:**\n{ai_result.get('raw', '')}")])
        return finding
        
    exec_text = "\n".join(exec_results) if exec_results else "(no commands executed)"
    
    finding.add_enrichment([
        MarkdownBlock(
            f"## 🔍 Root Cause\n"
            f"{ai_result.get('root_cause', 'N/A')}\n\n"
            f"## 📊 Evidence\n"
            f"{chr(10).join(['- ' + e for e in ai_result.get('evidence', [])])}\n\n"
            f"## ⚠️ Risk: {ai_result.get('risk', 'unknown')}\n\n"
            f"## 🛠 Execution Results\n"
            f"```\n{exec_text}\n```\n\n"
            f"## 🔬 Verification\n"
            f"{ai_result.get('verification', 'N/A')}\n\n"
            f"## ⏪ Rollback\n"
            f"{ai_result.get('rollback', 'N/A')}"
        )
    ])
    return finding

# ---------------------------------------------------------------------------
# Robusta Action Handlers
# ---------------------------------------------------------------------------
@action
def ai_sre_pod_failure(event: PodEvent):
    pod = event.get_pod()
    if not pod: return
    ns, name = pod.metadata.namespace, pod.metadata.name
    context = f"Pod Crash/Failure: {ns}/{name}"
    res, execs = _run_healing_loop(context, ns, name)
    event.add_finding(_build_finding(f"AI-SRE Pod Fix: {ns}/{name}", res, execs))

@action
def ai_sre_job_failure(event: JobEvent):
    job = event.get_job()
    if not job: return
    ns, name = job.metadata.namespace, job.metadata.name
    context = f"Job Failure: {ns}/{name}"
    res, execs = _run_healing_loop(context, ns, name)
    event.add_finding(_build_finding(f"AI-SRE Job Fix: {ns}/{name}", res, execs))

@action
def ai_sre_prometheus_alert(event: PrometheusKubernetesAlert):
    alert = getattr(event, 'alert', None)
    if not alert: return
    labels = alert.labels
    ns = labels.get("namespace", "default")
    name = labels.get("pod") or labels.get("deployment") or "unknown"
    context = f"Prometheus Alert: {alert.name} for {ns}/{name}. Labels: {labels}"
    res, execs = _run_healing_loop(context, ns, name)
    event.add_finding(_build_finding(f"AI-SRE Alert: {alert.name}", res, execs))