#!/usr/bin/env python3
"""
API Drift Preemption Wire - Master Orchestrator
Emits both a global contract registry and dedicated per-service endpoints
(data/services/{slug}/today.json) for lightweight autonomous agent consumption.
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import List

from core.taxonomy import ServiceDriftRecord, Directive, ReasonCode
from core.diff_engine import OpenAPIDiffEngine
from connectors.apis_guru import TARGET_SERVICES, fetch_openapi_spec
from connectors.sdk_registry import get_sdk_metadata

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DATA_DIR = "data"
SERVICES_DIR = os.path.join(DATA_DIR, "services")
SPECS_CACHE_DIR = os.path.join(DATA_DIR, "specs")
ARCHIVE_DIR = os.path.join(DATA_DIR, "archive")

TODAY_FILE = os.path.join(DATA_DIR, "today.json")
QUEUE_FILE = os.path.join(DATA_DIR, "remediation_queue.jsonl")
LLMS_FILE = os.path.join(DATA_DIR, "llms.txt")

def generate_global_llms_txt(records: List[ServiceDriftRecord], now_iso: str) -> str:
    lines = [
        "# API Drift Preemption Wire",
        f"> Last updated: {now_iso} UTC | Upstream Contract Mutation Radar for AI Agents",
        "> Ingest dedicated endpoints per service at data/services/{slug}/today.json",
        "",
        "## Tracked Cloud Service Status",
        "| Service | Drift Score | Directive | Endpoints | Breaking Changes | Tracked SDK | Service Endpoint |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]
    for r in records:
        b_count = len(r.breaking_changes)
        lines.append(
            f"| **{r.service_name}** | `{r.drift_score}` | `{r.directive.value}` | "
            f"{r.total_endpoints:,} | {b_count} | `{r.sdk_package}@{r.sdk_latest_version}` | "
            f"[`data/services/{r.service_id}/today.json`](data/services/{r.service_id}/today.json) |"
        )
    return "\n".join(lines) + "\n"

def generate_service_llms_txt(record: ServiceDriftRecord, now_iso: str) -> str:
    lines = [
        f"# {record.service_name} API Drift Ground-Truth",
        f"> Last synchronized: {now_iso} UTC",
        f"> Action Directive: `{record.directive.value}` | Drift Score: {record.drift_score}/100",
        "",
        "## Active SDK State",
        f"- Package: `{record.sdk_package}` ({record.sdk_ecosystem})",
        f"- Version: `{record.sdk_latest_version}`",
        f"- Release Age: {record.sdk_release_age_days:.1f} days",
        "",
        "## Detected Breaking Changes"
    ]
    if not record.breaking_changes:
        lines.append("- Zero breaking changes detected. Specification is backward-compatible with current SDK.")
    else:
        for bc in record.breaking_changes:
            lines.append(f"- **[{bc.change_type}]** `{bc.method} {bc.path}`: {bc.detail} (Severity: {bc.severity})")

    lines.append(f"\n## Recommended Agent Action\n`{record.directive.value}`")
    return "\n".join(lines) + "\n"

def run():
    logging.info("Starting API Drift Preemption audit cycle...")
    os.makedirs(SPECS_CACHE_DIR, exist_ok=True)
    os.makedirs(SERVICES_DIR, exist_ok=True)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    date_str = now.strftime("%Y-%m-%d")

    diff_engine = OpenAPIDiffEngine()
    records: List[ServiceDriftRecord] = []

    for target in TARGET_SERVICES:
        service_id = target["service_id"]
        service_name = target["service_name"]
        spec_url = target["spec_url"]
        sdk_ecosystem = target["sdk_ecosystem"]
        sdk_package = target["sdk_package"]

        logging.info(f"Checking specification: {service_name} ({service_id})...")
        current_spec = fetch_openapi_spec(spec_url)
        cache_path = os.path.join(SPECS_CACHE_DIR, f"{service_id}.json")

        if not current_spec:
            current_spec = {
                "openapi": "3.0.0",
                "info": {"title": service_name, "version": "1.0.0"},
                "paths": {"/ping": {"get": {"responses": {"200": {"description": "ok"}}}}}
            }

        endpoints_map = diff_engine.extract_endpoints(current_spec)
        total_endpoints = len(endpoints_map)
        current_hash = diff_engine.compute_spec_hash(current_spec)

        sdk_ver, sdk_age_days = get_sdk_metadata(sdk_ecosystem, sdk_package)

        breaking_changes = []
        severity = 0.0
        reasons = []

        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    old_spec = json.load(f)
                breaking_changes, severity = diff_engine.diff_specs(old_spec, current_spec)
            except Exception as e:
                logging.warning(f"Failed diffing cache for {service_id}: {e}")

        if breaking_changes:
            for bc in breaking_changes:
                if bc.change_type == "ENDPOINT_OR_METHOD_REMOVED":
                    reasons.append(ReasonCode.ENDPOINT_REMOVED)
                elif bc.change_type == "NEW_REQUIRED_PARAMETER":
                    reasons.append(ReasonCode.NEW_REQUIRED_PARAMETER)

            lag_multiplier = 1.3 if sdk_age_days > 14.0 else 1.0
            if lag_multiplier > 1.0:
                reasons.append(ReasonCode.SDK_LAG_BEHIND_SPEC)

            drift_score = min(100.0, round(severity * lag_multiplier, 2))

            if drift_score >= 70.0:
                directive = Directive.GENERATE_COMPATIBILITY_SHIM
            elif drift_score >= 40.0:
                directive = Directive.PIN_SDK
            else:
                directive = Directive.ADD_CONTRACT_TEST
            confidence = 0.95
        else:
            if not os.path.exists(cache_path):
                reasons.append(ReasonCode.BASELINE_INITIALIZED)
            else:
                reasons.append(ReasonCode.SPEC_EXPANDED_COMPATIBLE)
            drift_score = 0.0
            directive = Directive.SAFE_TO_UPGRADE
            confidence = 0.90

        # Persist current specification snapshot for next cycle diff
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(current_spec, f, indent=2)

        record = ServiceDriftRecord(
            service_id=service_id,
            service_name=service_name,
            spec_url=spec_url,
            spec_hash_sha256=current_hash,
            total_endpoints=total_endpoints,
            breaking_changes=breaking_changes,
            sdk_ecosystem=sdk_ecosystem,
            sdk_package=sdk_package,
            sdk_latest_version=sdk_ver,
            sdk_release_age_days=sdk_age_days,
            drift_score=drift_score,
            directive=directive,
            confidence=confidence,
            reason_codes=list(set(reasons))
        )
        records.append(record)

        # WRITE VIRAL PER-SERVICE ARTIFACTS
        service_target_dir = os.path.join(SERVICES_DIR, service_id)
        os.makedirs(service_target_dir, exist_ok=True)

        service_payload = {
            "metadata": {
                "service_id": service_id,
                "service_name": service_name,
                "generated_at_utc": now_iso,
                "schema_version": "1.0.0"
            },
            "drift_status": record.model_dump()
        }

        with open(os.path.join(service_target_dir, "today.json"), "w", encoding="utf-8") as f:
            json.dump(service_payload, f, indent=2)

        with open(os.path.join(service_target_dir, "llms.txt"), "w", encoding="utf-8") as f:
            f.write(generate_service_llms_txt(record, now_iso))

    # Sort descending by drift score
    records.sort(key=lambda x: x.drift_score, reverse=True)

    month_dir = os.path.join(ARCHIVE_DIR, now.strftime("%Y"), now.strftime("%m"))
    os.makedirs(month_dir, exist_ok=True)

    global_payload = {
        "metadata": {
            "generated_at_utc": now_iso,
            "schema_version": "1.0.0",
            "services_tracked": len(records),
            "scoring_rule": "DriftScore = min(100.0, BreakageSeverity * SDKLagMultiplier)"
        },
        "services": [r.model_dump() for r in records]
    }

    # 1. Global registry endpoints
    with open(TODAY_FILE, "w", encoding="utf-8") as f:
        json.dump(global_payload, f, indent=2)

    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r.model_dump()) + "\n")

    with open(LLMS_FILE, "w", encoding="utf-8") as f:
        f.write(generate_global_llms_txt(records, now_iso))

    # 2. Historical archive
    archive_file = os.path.join(month_dir, f"{date_str}.json")
    with open(archive_file, "w", encoding="utf-8") as f:
        json.dump(global_payload, f, indent=2)

    logging.info(f"Published global and per-service endpoints for {len(records)} services.")

if __name__ == "__main__":
    run()
