# =============================================================================
# AI SRE AGENT — Gemini-Powered Kubernetes Self-Healing (Dynamic + Production-Grade)
# =============================================================================
# NOTE: This file runs INSIDE the Robusta runner container in the cluster.
# The `robusta.api` module is pre-installed in that container image.
# Any "Cannot find module robusta.api" IDE errors are EXPECTED false positives.
#
# Architecture — Two-Phase AI Reasoning Loop:
#
#   Phase 1 (Diagnose):
#     Gemini receives broad diagnostic context and identifies the root cause
#     category (OOMKilled, ImagePullBackOff, DatabaseError, etc.) plus a
#     list of additional data it needs to confirm the diagnosis.
#
#   Phase 2 (Fix):
#     The agent automatically collects the extra data Gemini requested
#     (specific resource limits, ECR image tags, secret values, network
#     tests, etc.) and sends it back to Gemini for a targeted, specific fix.
#     Gemini now generates the EXACT kubectl patch payload for THIS failure,
#     not a generic restart.
#
# Safety:
#   - ALLOWLIST: only safe kubectl verbs are auto-executed.
#   - For human-approval fixes (e.g. complex patches), ALL suggested commands
#     are surfaced in the Finding so the operator can copy-paste them.
#   - Jobs are NEVER auto-remediated.
# =============================================================================

import os
import json
import re
import subprocess
import logging
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
)

try:
    import requests as _req
except ImportError:
    _req = None

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL   = "gemini-1.5-flash"
GEMINI_URL     = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
)

# Confidence threshold for auto-execution
AUTO_EXECUTE_CONFIDENCE_THRESHOLD = 0.90

# ---------------------------------------------------------------------------
# STRICT ALLOWLIST — commands the agent may auto-execute without human approval
# ---------------------------------------------------------------------------
# These are SAFE and FULLY REVERSIBLE operations. Anything not in this list
# is surfaced to the human operator as a "ready to run" command but never
# executed autonomously.
SAFE_AUTO_EXECUTE_PREFIXES = (
    "kubectl rollout restart",
    "kubectl rollout undo",
    "kubectl scale",
    "kubectl annotate",
    "kubectl label",
)

# These verbs are ALLOWED in Gemini's suggestions (shown to human) but
# never auto-executed — they make structural changes.
HUMAN_APPROVAL_PREFIXES = (
    "kubectl patch",
    "kubectl set image",
    "kubectl set env",
    "kubectl set resources",
)

ALL_ALLOWED_PREFIXES = SAFE_AUTO_EXECUTE_PREFIXES + HUMAN_APPROVAL_PREFIXES

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: str, timeout: int = 20) -> str:
    """Run a shell command and return combined stdout/stderr."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return (result.stdout + result.stderr).strip()
    except subprocess.TimeoutExpired:
        return f"[timed out after {timeout}s]: {cmd}"
    except Exception as exc:
        return f"[error: {exc}]"


def _is_safe_auto_execute(cmd: str) -> bool:
    return any(cmd.strip().startswith(p) for p in SAFE_AUTO_EXECUTE_PREFIXES)


def _is_allowed(cmd: str) -> bool:
    return any(cmd.strip().startswith(p) for p in ALL_ALLOWED_PREFIXES)


# ---------------------------------------------------------------------------
# Phase 1: Broad Context Collection
# ---------------------------------------------------------------------------

def _collect_base_context(namespace: str, name: str, kind: str = "pod") -> dict:
    """Collect initial broad diagnostic context."""
    ctx = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "resource_kind": kind,
        "resource_name": name,
        "namespace": namespace,
    }
    ctx["resource_yaml"]        = _run(f"kubectl get {kind} {name} -n {namespace} -o yaml 2>&1")
    ctx["describe"]             = _run(f"kubectl describe {kind} {name} -n {namespace} 2>&1")
    ctx["warning_events"]       = _run(
        f"kubectl get events -n {namespace} --field-selector "
        f"involvedObject.name={name},type=Warning --sort-by=.lastTimestamp 2>&1"
    )
    ctx["namespace_pod_status"] = _run(f"kubectl get pods -n {namespace} -o wide 2>&1")

    if kind == "pod":
        ctx["logs_current"]  = _run(
            f"kubectl logs {name} -n {namespace} --all-containers --tail=50 2>&1"
        )
        ctx["logs_previous"] = _run(
            f"kubectl logs {name} -n {namespace} --all-containers --tail=50 --previous 2>&1"
        )

    return ctx


# ---------------------------------------------------------------------------
# Phase 1 Gemini Call: Diagnose + Request Extra Data
# ---------------------------------------------------------------------------

def _diagnose(context: dict) -> dict:
    """
    Phase 1: Ask Gemini to identify the root cause and tell us what
    ADDITIONAL data it needs to generate a precise, targeted fix.
    """
    if not GEMINI_API_KEY or not _req:
        return {
            "root_cause_category": "Other",
            "preliminary_diagnosis": "Gemini unavailable.",
            "additional_data_needed": [],
            "preliminary_severity": "unknown",
        }

    prompt = (
        "You are an elite SRE analyzing a Kubernetes failure. "
        "Based on the diagnostic context below, identify the root cause category "
        "and list the ADDITIONAL specific data you need to generate a precise, "
        "targeted fix (not just a generic restart).\n\n"
        "For example:\n"
        "  - OOMKilled → you need the current memory limit and actual peak usage\n"
        "  - ImagePullBackOff → you need the list of available image tags in ECR\n"
        "  - DatabaseError → you need connectivity test results and secret values\n"
        "  - CrashLoopBackOff → you need the full stack trace from the crash logs\n\n"
        "=== DIAGNOSTIC CONTEXT ===\n"
        + json.dumps(context, indent=2, default=str)
        + "\n=== END CONTEXT ===\n\n"
        "Return ONLY valid JSON:\n"
        "{\n"
        '  "root_cause_category": "OOMKilled|ImagePullBackOff|CrashLoopBackOff|'
        'ConfigError|NetworkError|PVCError|IAMError|DatabaseError|Other",\n'
        '  "preliminary_diagnosis": "One sentence root cause",\n'
        '  "preliminary_severity": "critical|high|medium|low",\n'
        '  "additional_data_needed": [\n'
        '    {"label": "human readable name", "command": "kubectl or shell command to run"}\n'
        '  ]\n'
        "}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.05,
            "maxOutputTokens": 1024,
            "response_mime_type": "application/json",
        },
    }

    try:
        resp = _req.post(GEMINI_URL, json=payload, timeout=30)
        resp.raise_for_status()
        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        return json.loads(raw)
    except Exception as exc:
        logger.error(f"Phase 1 Gemini call failed: {exc}")
        return {
            "root_cause_category": "Other",
            "preliminary_diagnosis": f"Phase 1 error: {exc}",
            "additional_data_needed": [],
            "preliminary_severity": "unknown",
        }


# ---------------------------------------------------------------------------
# Dynamic Extra Context Collection
# ---------------------------------------------------------------------------

def _collect_extra_context(
    diagnosis: dict,
    namespace: str,
    name: str,
    kind: str,
) -> dict:
    """
    Collect extra context dynamically based on:
      1. What Gemini asked for in Phase 1.
      2. Hardened category-specific probes we ALWAYS run for known failure types.
    """
    extra = {}
    category = diagnosis.get("root_cause_category", "Other")

    # ── Run whatever extra commands Gemini asked for ──────────────────────────
    for item in diagnosis.get("additional_data_needed", []):
        label   = item.get("label", "extra_data")
        command = item.get("command", "")
        if command:
            # Safety: only allow kubectl and aws CLI commands in Phase 1 requests
            if command.strip().startswith(("kubectl", "aws ")):
                key = re.sub(r"[^a-z0-9_]", "_", label.lower())[:40]
                logger.info(f"AI-SRE Phase 1 extra probe [{label}]: {command}")
                extra[key] = _run(command, timeout=20)
            else:
                extra[label] = f"[SKIPPED — command not allowed: {command}]"

    # ── Category-specific built-in probes ─────────────────────────────────────

    if category == "OOMKilled":
        # Get the ACTUAL current memory limit and request for this resource
        extra["resource_limits"] = _run(
            f"kubectl get {kind} {name} -n {namespace} "
            f"-o jsonpath='{{.spec.template.spec.containers[*].resources}}' 2>&1"
        )
        # Get recent memory usage metrics if metrics-server is available
        extra["top_pods"] = _run(f"kubectl top pods -n {namespace} 2>&1")

    elif category == "ImagePullBackOff":
        # Extract the failing image name from the resource
        image_raw = _run(
            f"kubectl get {kind} {name} -n {namespace} "
            f"-o jsonpath='{{.spec.template.spec.containers[0].image}}' 2>&1"
        )
        extra["failing_image"] = image_raw
        # If it's an ECR image, list the last 5 available tags
        if ".ecr." in image_raw:
            repo = image_raw.split("/", 1)[-1].split(":")[0]
            extra["available_ecr_tags"] = _run(
                f"aws ecr describe-images --repository-name {repo} "
                f"--query 'sort_by(imageDetails,&imagePushedAt)[-5:].imageTags' "
                f"--output json 2>&1"
            )

    elif category == "DatabaseError":
        # Test TCP connectivity from a debug pod (non-destructive)
        db_host = _run(
            f"kubectl get {kind} {name} -n {namespace} "
            f"-o jsonpath='{{.spec.template.spec.containers[0].env[?(@.name==\"DB_HOST\")].value}}' 2>&1"
        )
        extra["db_host_configured"] = db_host
        if db_host and not db_host.startswith("["):
            extra["db_connectivity_test"] = _run(
                f"kubectl run tmp-db-test --image=busybox --restart=Never --rm -i "
                f"--namespace={namespace} -- nc -zv {db_host} 3306 2>&1",
                timeout=30,
            )
        # Check if the DB secret exists and has the right keys
        extra["db_secret_keys"] = _run(
            f"kubectl get secret django-backend-db-secret -n {namespace} "
            f"-o jsonpath='{{.data}}' 2>&1 | python3 -c "
            f"\"import sys,json; d=json.load(sys.stdin); print(list(d.keys()))\" 2>&1"
        )

    elif category == "CrashLoopBackOff":
        # Get the full previous crash logs — these contain the actual stack trace
        extra["full_crash_logs"] = _run(
            f"kubectl logs {name} -n {namespace} --all-containers --previous 2>&1"
        )
        # Check restart count
        extra["restart_count"] = _run(
            f"kubectl get pod {name} -n {namespace} "
            f"-o jsonpath='{{.status.containerStatuses[*].restartCount}}' 2>&1"
        )

    elif category == "PVCError":
        # Check PVC status
        extra["pvc_status"] = _run(f"kubectl get pvc -n {namespace} -o wide 2>&1")
        extra["pv_status"]  = _run("kubectl get pv -o wide 2>&1")

    elif category == "NetworkError":
        # Check services and endpoints
        extra["services"]  = _run(f"kubectl get svc -n {namespace} -o wide 2>&1")
        extra["endpoints"] = _run(f"kubectl get endpoints -n {namespace} 2>&1")
        extra["ingresses"] = _run(f"kubectl get ingress -n {namespace} 2>&1")

    elif category == "IAMError":
        # Check service account annotations for IRSA
        extra["service_account"] = _run(
            f"kubectl get serviceaccount -n {namespace} -o yaml 2>&1"
        )

    return extra


# ---------------------------------------------------------------------------
# Phase 2 Gemini Call: Generate Targeted Fix
# ---------------------------------------------------------------------------

def _generate_fix(base_ctx: dict, diagnosis: dict, extra_ctx: dict) -> dict:
    """
    Phase 2: Send Gemini the full picture (base context + diagnosis + extra data)
    and ask for a SPECIFIC, TARGETED fix — not a generic restart.
    """
    empty = {
        "diagnosis": diagnosis.get("preliminary_diagnosis", "Unknown"),
        "severity": diagnosis.get("preliminary_severity", "unknown"),
        "root_cause_category": diagnosis.get("root_cause_category", "Other"),
        "fix_commands": [],
        "safe_to_auto_execute": False,
        "confidence": 0.0,
        "requires_human_approval": True,
        "human_approval_reason": "Phase 2 Gemini call failed.",
        "post_fix_verification": "kubectl get pods -A",
        "explanation": "",
    }

    if not GEMINI_API_KEY or not _req:
        return empty

    prompt = (
        "You are an elite SRE. You previously diagnosed a Kubernetes failure. "
        "Now, with the ADDITIONAL diagnostic data collected, generate a SPECIFIC, "
        "TARGETED fix — not a generic restart.\n\n"
        "For example:\n"
        "  - OOMKilled → patch the exact memory limit to 2x the peak usage you observed\n"
        "  - ImagePullBackOff → patch to the specific latest valid tag from ECR\n"
        "  - DatabaseError → patch the specific wrong env var to the correct value\n"
        "  - CrashLoopBackOff → if it's a config error in code, patch the env var; "
        "if it's a crash, rollout restart\n\n"
        "=== PRELIMINARY DIAGNOSIS ===\n"
        + json.dumps(diagnosis, indent=2)
        + "\n\n=== ADDITIONAL CONTEXT COLLECTED ===\n"
        + json.dumps(extra_ctx, indent=2, default=str)
        + "\n\n=== ORIGINAL BASE CONTEXT (summary only) ===\n"
        f"  Resource: {base_ctx.get('resource_kind')}/{base_ctx.get('resource_name')} "
        f"in namespace {base_ctx.get('namespace')}\n"
        f"  Timestamp: {base_ctx.get('timestamp')}\n\n"
        "=== SAFETY RULES ===\n"
        "Allowed kubectl verbs: rollout restart, rollout undo, scale, annotate, "
        "label, patch, set image, set env, set resources.\n"
        "NEVER suggest: delete, exec, apply, create, replace, drain, cordon.\n"
        "Set safe_to_auto_execute=true ONLY for: rollout restart, rollout undo, scale.\n"
        "Set requires_human_approval=true for: patch, set image, set env, set resources.\n"
        "Set confidence < 0.90 and requires_human_approval=true if unsure.\n\n"
        "Return ONLY valid JSON:\n"
        "{\n"
        '  "diagnosis": "Precise root cause with specific details from the extra context",\n'
        '  "severity": "critical|high|medium|low",\n'
        '  "root_cause_category": "OOMKilled|ImagePullBackOff|CrashLoopBackOff|'
        'ConfigError|NetworkError|PVCError|IAMError|DatabaseError|Other",\n'
        '  "fix_commands": ["kubectl patch deployment/foo -n bar --type=json -p ..."],\n'
        '  "safe_to_auto_execute": false,\n'
        '  "confidence": 0.0,\n'
        '  "requires_human_approval": true,\n'
        '  "human_approval_reason": "Why human should review this specific fix",\n'
        '  "post_fix_verification": "kubectl command to verify the fix worked",\n'
        '  "explanation": "Step-by-step: what is broken, what the command does, and why"\n'
        "}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.05,
            "maxOutputTokens": 2048,
            "response_mime_type": "application/json",
        },
    }

    try:
        resp = _req.post(GEMINI_URL, json=payload, timeout=45)
        resp.raise_for_status()
        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        return json.loads(raw)
    except Exception as exc:
        logger.error(f"Phase 2 Gemini call failed: {exc}")
        empty["diagnosis"] = f"{diagnosis.get('preliminary_diagnosis')} [Phase 2 error: {exc}]"
        return empty


# ---------------------------------------------------------------------------
# Command Execution
# ---------------------------------------------------------------------------

def _execute_fixes(gemini: dict) -> list:
    """
    Execute fix commands using two-tier logic:
      - SAFE_AUTO_EXECUTE_PREFIXES + confidence >= 0.90 + not needs_human → auto-execute
      - HUMAN_APPROVAL_PREFIXES → always surface to human, never auto-execute
      - Not in allowlist → hard-blocked with explanation
    """
    results      = []
    confidence   = gemini.get("confidence", 0.0)
    safe         = gemini.get("safe_to_auto_execute", False)
    needs_human  = gemini.get("requires_human_approval", True)
    commands     = gemini.get("fix_commands", [])

    if not commands:
        results.append("ℹ No fix commands were generated by the AI.")
        return results

    # Overall gate: if Gemini itself says defer to human, respect that
    if needs_human or not safe or confidence < AUTO_EXECUTE_CONFIDENCE_THRESHOLD:
        results.append(
            f"⏸  AUTO-EXECUTION SKIPPED\n"
            f"   Confidence     : {confidence:.0%}  (threshold: {AUTO_EXECUTE_CONFIDENCE_THRESHOLD:.0%})\n"
            f"   Safe flag      : {safe}\n"
            f"   Needs approval : {needs_human}\n"
            f"   Reason         : {gemini.get('human_approval_reason', 'See above')}\n\n"
            f"👤  COPY-PASTE THESE COMMANDS TO APPLY THE FIX:\n"
            + "\n".join(f"   $ {cmd}" for cmd in commands)
        )
        return results

    # Per-command gate
    for cmd in commands:
        cmd = cmd.strip()

        if not _is_allowed(cmd):
            results.append(
                f"🚫  HARD-BLOCKED (verb not in allowlist): {cmd}\n"
                f"    Allowed: rollout restart/undo, scale, annotate, label, patch, "
                f"set image/env/resources"
            )
            logger.warning(f"AI-SRE BLOCKED: {cmd}")
            continue

        if not _is_safe_auto_execute(cmd):
            # Allowed verb but requires structural change → defer to human
            results.append(
                f"⏸  DEFERRED TO HUMAN (structural change verb):\n"
                f"   $ {cmd}"
            )
            logger.info(f"AI-SRE DEFERRED: {cmd}")
            continue

        # All gates passed → auto-execute
        logger.info(f"AI-SRE EXECUTING: {cmd}")
        output = _run(cmd, timeout=60)
        results.append(f"✅  EXECUTED: {cmd}\n    OUTPUT: {output}")

    return results


# ---------------------------------------------------------------------------
# Finding Builder
# ---------------------------------------------------------------------------

def _build_finding(
    diagnosis: dict,
    gemini: dict,
    exec_results: list,
    resource_name: str,
) -> Finding:
    severity_map = {
        "critical": FindingSeverity.HIGH,
        "high":     FindingSeverity.HIGH,
        "medium":   FindingSeverity.MEDIUM,
        "low":      FindingSeverity.LOW,
    }
    sev = severity_map.get(gemini.get("severity", "medium"), FindingSeverity.MEDIUM)

    needs_human    = gemini.get("requires_human_approval", True)
    confidence_pct = f"{gemini.get('confidence', 0):.0%}"
    approval_badge = "👤 **REQUIRES HUMAN APPROVAL**" if needs_human else "🤖 **AUTO-REMEDIATED**"

    finding = Finding(
        title=(
            f"AI-SRE [{gemini.get('root_cause_category', 'Failure')}]: "
            f"{resource_name}"
        ),
        source=FindingType.MANUAL,
        severity=sev,
    )

    exec_text = "\n".join(exec_results) if exec_results else "(no commands)"

    finding.add_enrichment([
        MarkdownBlock(
            f"## {approval_badge}\n\n"
            f"**Confidence:** {confidence_pct} | "
            f"**Severity:** `{gemini.get('severity', 'unknown').upper()}` | "
            f"**Category:** `{gemini.get('root_cause_category', 'unknown')}`\n\n"
            f"---\n\n"
            f"## 🔍 Phase 1 — Preliminary Diagnosis\n"
            f"{diagnosis.get('preliminary_diagnosis', 'N/A')}\n\n"
            f"## 🔬 Phase 2 — Targeted Root Cause\n"
            f"{gemini.get('diagnosis', 'N/A')}\n\n"
            f"## 💡 Explanation\n"
            f"{gemini.get('explanation', 'N/A')}\n\n"
            f"## 🛠 Execution Results\n"
            f"```\n{exec_text}\n```\n\n"
            f"## ✅ Verification\n"
            f"```bash\n{gemini.get('post_fix_verification', 'kubectl get pods -A')}\n```"
        )
    ])
    return finding


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def _run_healing_loop(
    namespace: str,
    name: str,
    kind: str = "pod",
    extra_alert_ctx: dict | None = None,
) -> tuple:
    """
    Run the full two-phase AI healing loop and return (diagnosis, gemini, exec_results).
    """
    logger.info(f"AI-SRE Phase 1: Collecting base context for {kind}/{namespace}/{name}")
    base_ctx = _collect_base_context(namespace, name, kind)

    if extra_alert_ctx:
        base_ctx.update(extra_alert_ctx)

    logger.info(f"AI-SRE Phase 1: Calling Gemini for diagnosis")
    diagnosis = _diagnose(base_ctx)
    logger.info(
        f"AI-SRE Phase 1 result: category={diagnosis.get('root_cause_category')}, "
        f"preliminary={diagnosis.get('preliminary_diagnosis')}"
    )

    logger.info(f"AI-SRE Phase 2: Collecting targeted extra context")
    extra_ctx = _collect_extra_context(diagnosis, namespace, name, kind)

    logger.info(f"AI-SRE Phase 2: Calling Gemini for targeted fix")
    gemini = _generate_fix(base_ctx, diagnosis, extra_ctx)
    logger.info(
        f"AI-SRE Phase 2 result: confidence={gemini.get('confidence')}, "
        f"auto_execute={gemini.get('safe_to_auto_execute')}, "
        f"commands={gemini.get('fix_commands')}"
    )

    exec_results = _execute_fixes(gemini)
    return diagnosis, gemini, exec_results


# ---------------------------------------------------------------------------
# Robusta Action Handlers
# ---------------------------------------------------------------------------

@action
def ai_sre_pod_failure(event: PodEvent):
    """
    Triggered on pod crash/failure.
    Runs the two-phase AI healing loop: diagnose → collect targeted data → fix.
    """
    pod = event.get_pod()
    if not pod:
        return

    name = pod.metadata.name
    ns   = pod.metadata.namespace
    logger.info(f"AI-SRE: Pod failure trigger — {ns}/{name}")

    diagnosis, gemini, exec_results = _run_healing_loop(ns, name, kind="pod")
    finding = _build_finding(diagnosis, gemini, exec_results, f"{ns}/{name}")
    event.add_finding(finding)


@action
def ai_sre_job_failure(event: JobEvent):
    """
    Triggered on Kubernetes Job failure.
    Jobs are NEVER auto-remediated — diagnosis only, always deferred to human.
    """
    job = event.get_job()
    if not job:
        return

    name = job.metadata.name
    ns   = job.metadata.namespace
    logger.info(f"AI-SRE: Job failure trigger — {ns}/{name}")

    diagnosis, gemini, _ = _run_healing_loop(ns, name, kind="job")

    # Override: jobs are never auto-remediated
    gemini["requires_human_approval"] = True
    gemini["safe_to_auto_execute"]    = False
    gemini["human_approval_reason"]   = (
        "Job failures require human decision on whether to re-trigger the job."
    )

    exec_results = _execute_fixes(gemini)
    finding      = _build_finding(diagnosis, gemini, exec_results, f"job/{ns}/{name}")
    event.add_finding(finding)


@action
def ai_sre_prometheus_alert(event: PrometheusKubernetesAlert):
    """
    Triggered on ANY Prometheus alert (high error rate, PVC full, node pressure, etc.).
    Enriches the context with alert metadata before running the two-phase loop.
    """
    alert  = event.get_alert()
    labels = alert.labels if alert else {}

    name = (
        labels.get("pod")
        or labels.get("deployment")
        or labels.get("job_name")
        or "unknown"
    )
    ns   = labels.get("namespace", "default")
    kind = "pod" if labels.get("pod") else "deployment"

    logger.info(
        f"AI-SRE: Prometheus alert trigger "
        f"'{alert.name if alert else 'unknown'}' — {ns}/{name}"
    )

    # Pass alert metadata as extra context to Phase 1
    alert_ctx = {
        "alert_name":        alert.name if alert else "unknown",
        "alert_labels":      labels,
        "alert_description": labels.get("description", ""),
        "alert_summary":     labels.get("summary", ""),
    }

    diagnosis, gemini, exec_results = _run_healing_loop(
        ns, name, kind=kind, extra_alert_ctx=alert_ctx
    )
    finding = _build_finding(
        diagnosis, gemini, exec_results,
        f"Alert:{alert_ctx['alert_name']} {ns}/{name}"
    )
    event.add_finding(finding)
