# =============================================================================
# AI SRE AGENT — Gemini-Powered Kubernetes Self-Healing
# =============================================================================
# NOTE: This file runs INSIDE the Robusta runner container in the cluster.
# The `robusta.api` module is pre-installed in that container image.
# Any "Cannot find module robusta.api" errors from your local IDE are
# EXPECTED false positives — the code works correctly in the cluster.
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

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent?key=" + GEMINI_API_KEY
)
CONFIDENCE_THRESHOLD = 0.75
BLOCKED_VERBS = re.compile(
    r"\b(delete\s+node|drain\s+|destroy|drop\s+database|rm\s+-rf\s+/)\b",
    re.IGNORECASE,
)

logger = logging.getLogger(__name__)


def _run(cmd, timeout=15):
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip() or result.stderr.strip()
    except Exception as e:
        return f"[command error: {e}]"


def _collect_context(namespace, name, kind="pod"):
    ctx = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "resource_kind": kind,
        "resource_name": name,
        "namespace": namespace,
    }
    ctx["resource_yaml"] = _run(
        f"kubectl get {kind} {name} -n {namespace} -o yaml 2>&1"
    )
    ctx["events"] = _run(
        f"kubectl get events -n {namespace} --sort-by=.lastTimestamp "
        f"--field-selector involvedObject.name={name} -o wide 2>&1"
    )
    ctx["namespace_events"] = _run(
        f"kubectl get events -n {namespace} --sort-by=.lastTimestamp 2>&1"
    )
    if kind == "pod":
        ctx["logs_current"] = _run(
            f"kubectl logs {name} -n {namespace} --all-containers --tail=100 2>&1"
        )
        ctx["logs_previous"] = _run(
            f"kubectl logs {name} -n {namespace} --all-containers --tail=50 --previous 2>&1"
        )
    ctx["describe"] = _run(f"kubectl describe {kind} {name} -n {namespace} 2>&1")
    ctx["namespace_pod_status"] = _run(f"kubectl get pods -n {namespace} -o wide 2>&1")
    return ctx


def _call_gemini(context):
    if not GEMINI_API_KEY or not _req:
        return {
            "diagnosis": "Gemini API key not set or requests library unavailable.",
            "severity": "unknown",
            "root_cause_category": "ConfigError",
            "fix_commands": [],
            "safe_to_auto_execute": False,
            "confidence": 0.0,
            "post_fix_verification": "",
            "explanation": "",
        }

    prompt = (
        "You are an elite Site Reliability Engineer (SRE) with deep expertise in "
        "Kubernetes, AWS EKS, and Django applications.\n\n"
        "A Kubernetes resource has failed in our cluster. Below is the COMPLETE diagnostic context.\n"
        "Your task is to:\n"
        "1. Diagnose the ROOT CAUSE precisely.\n"
        "2. Generate a sequence of kubectl/helm commands that will FIX the problem.\n"
        "3. Return a structured JSON response ONLY - no extra text, no markdown fences.\n\n"
        "=== DIAGNOSTIC CONTEXT ===\n"
        + json.dumps(context, indent=2, default=str)
        + "\n=== END CONTEXT ===\n\n"
        "Return ONLY this JSON (no markdown fences, no extra text):\n"
        '{"diagnosis":"...","severity":"critical|high|medium|low",'
        '"root_cause_category":"OOMKilled|ImagePullBackOff|CrashLoopBackOff|ConfigError|NetworkError|PVCError|IAMError|DatabaseError|Other",'
        '"fix_commands":["kubectl ..."],'
        '"safe_to_auto_execute":true,'
        '"confidence":0.0,'
        '"post_fix_verification":"kubectl command",'
        '"explanation":"..."}'
        "\n\nRULES:\n"
        "- Only include SAFE and REVERSIBLE commands.\n"
        "- Set safe_to_auto_execute=false if any fix deletes critical data or drains nodes.\n"
        "- If unsure, set confidence < 0.75 and safe_to_auto_execute=false.\n"
        "- Prefer kubectl rollout restart, kubectl patch, kubectl scale."
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048},
    }
    try:
        resp = _req.post(GEMINI_URL, json=payload, timeout=30)
        resp.raise_for_status()
        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except Exception as e:
        logger.error(f"Gemini API call failed: {e}")
        return {
            "diagnosis": f"Gemini API error: {e}",
            "severity": "unknown",
            "root_cause_category": "Other",
            "fix_commands": [],
            "safe_to_auto_execute": False,
            "confidence": 0.0,
            "post_fix_verification": "",
            "explanation": "",
        }


def _is_safe_command(cmd):
    return not BLOCKED_VERBS.search(cmd)


def _execute_fixes(fix_commands, confidence, safe):
    results = []
    if not safe or confidence < CONFIDENCE_THRESHOLD:
        results.append(
            f"WARNING: Auto-execution SKIPPED - confidence={confidence:.0%}, "
            f"safe_to_auto_execute={safe}. Manual review required."
        )
        return results
    for cmd in fix_commands:
        if not _is_safe_command(cmd):
            results.append(f"BLOCKED (destructive pattern): {cmd}")
            continue
        logger.info(f"AI-SRE executing: {cmd}")
        output = _run(cmd, timeout=60)
        results.append(f"EXECUTED: {cmd}\nOUTPUT: {output}")
    return results


def _build_finding(ctx, gemini, exec_results, resource_name):
    severity_map = {
        "critical": FindingSeverity.HIGH,
        "high": FindingSeverity.HIGH,
        "medium": FindingSeverity.MEDIUM,
        "low": FindingSeverity.LOW,
    }
    sev = severity_map.get(gemini.get("severity", "medium"), FindingSeverity.MEDIUM)
    confidence_pct = f"{gemini.get('confidence', 0):.0%}"
    finding = Finding(
        title=f"AI-SRE: {resource_name} - {gemini.get('root_cause_category', 'Failure')}",
        source=FindingType.MANUAL,
        severity=sev,
    )
    exec_text = "\n".join(exec_results) if exec_results else "(no commands executed)"
    finding.add_enrichment([
        MarkdownBlock(
            f"## AI Diagnosis (Confidence: {confidence_pct})\n"
            f"{gemini.get('diagnosis', 'No diagnosis available.')}\n\n"
            f"**Severity:** `{gemini.get('severity', 'unknown').upper()}`  "
            f"**Category:** `{gemini.get('root_cause_category', 'unknown')}`\n\n"
            f"## Fix Explanation\n{gemini.get('explanation', 'N/A')}\n\n"
            f"## Execution Results\n```\n{exec_text}\n```\n\n"
            f"## Verification Command\n```\n{gemini.get('post_fix_verification', 'kubectl get pods -A')}\n```"
        )
    ])
    return finding


@action
def ai_sre_pod_failure(event: PodEvent):
    """Triggered on pod crash/failure. Collects full context and calls Gemini AI for diagnosis and auto-remediation."""
    pod = event.get_pod()
    if not pod:
        return
    name = pod.metadata.name
    ns = pod.metadata.namespace
    logger.info(f"AI-SRE: Analyzing pod failure - {ns}/{name}")
    ctx = _collect_context(ns, name, kind="pod")
    gemini = _call_gemini(ctx)
    exec_results = _execute_fixes(
        gemini.get("fix_commands", []),
        gemini.get("confidence", 0.0),
        gemini.get("safe_to_auto_execute", False),
    )
    finding = _build_finding(ctx, gemini, exec_results, f"{ns}/{name}")
    event.add_finding(finding)


@action
def ai_sre_job_failure(event: JobEvent):
    """Triggered on Kubernetes Job failure. Sends full context to Gemini for diagnosis."""
    job = event.get_job()
    if not job:
        return
    name = job.metadata.name
    ns = job.metadata.namespace
    logger.info(f"AI-SRE: Analyzing job failure - {ns}/{name}")
    ctx = _collect_context(ns, name, kind="job")
    gemini = _call_gemini(ctx)
    exec_results = _execute_fixes(
        gemini.get("fix_commands", []),
        gemini.get("confidence", 0.0),
        gemini.get("safe_to_auto_execute", False),
    )
    finding = _build_finding(ctx, gemini, exec_results, f"job/{ns}/{name}")
    event.add_finding(finding)


@action
def ai_sre_prometheus_alert(event: PrometheusKubernetesAlert):
    """Triggered on ANY Prometheus alert. Generic catch-all for all other failure types."""
    alert = event.get_alert()
    labels = alert.labels if alert else {}
    name = (
        labels.get("pod")
        or labels.get("deployment")
        or labels.get("job_name")
        or "unknown"
    )
    ns = labels.get("namespace", "default")
    kind = "pod" if labels.get("pod") else "deployment"
    logger.info(f"AI-SRE: Analyzing Prometheus alert {alert.name if alert else 'unknown'} - {ns}/{name}")
    ctx = _collect_context(ns, name, kind=kind)
    ctx["alert_name"] = alert.name if alert else "unknown"
    ctx["alert_labels"] = labels
    ctx["alert_description"] = labels.get("description", "")
    gemini = _call_gemini(ctx)
    exec_results = _execute_fixes(
        gemini.get("fix_commands", []),
        gemini.get("confidence", 0.0),
        gemini.get("safe_to_auto_execute", False),
    )
    finding = _build_finding(
        ctx, gemini, exec_results,
        f"Alert:{ctx['alert_name']} {ns}/{name}"
    )
    event.add_finding(finding)
