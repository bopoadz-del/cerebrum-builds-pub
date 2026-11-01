"""batch_production_tracking -- follow a compost batch through production,
curing and quality checks.

Written by the factory WRITER role (codewhale exec).

The production floor's question is "is this batch ready, and if not what does
it need". The handler answers with the batch's own arithmetic (curing
progress, mass loss, quality verdict against the bands the factory sets) and
calls the three bound blocks:

* ``task_listing`` publishes the next production step as a work item;
* ``audit`` records the stage reading in the factory's audit trail;
* ``workflow`` runs the stage pipeline across the two.

Scope READS: the caller's payload, app/formulas.py, the vendored blocks.
Scope WRITES: caller output only -- the route owns persistence.
Scope NEVER: no network, no store write, no credential, no invented reading.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import formulas
from app.actions._blocks import call_blocks
from app.actions._common import (
    authority,
    nested_refusals,
    number_of,
    record_of,
    refusal,
    setting,
    setting_number,
    success,
    text_input,
    text_of,
    whole_of,
)
from app.block_inputs import default_block_action

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "batch_production_tracking"
ENTITY = CAPABILITY_ID

BLOCK_IDS: List[str] = ["workflow", "task_listing", "audit"]
BLOCK_DEFAULT_ACTIONS: Dict[str, Any] = {
    block_id: default_block_action(block_id) for block_id in BLOCK_IDS
}

AUTHORITY = authority(CAPABILITY_ID, 3, "formulas")

DEFAULT_ADDRESS = "Compost yard, Tunis"
_TASK_CATEGORY = "other"


def _quality_verdict(record: Dict[str, Any]) -> Dict[str, Any]:
    """Pass or fail against the bands the factory owns, one check each."""
    temp = number_of(record.get("temperature_c"))
    moisture = number_of(record.get("moisture_pct"))
    ph = number_of(record.get("ph"))
    cn = number_of(record.get("c_n_ratio"))
    t_max = setting_number("COMPOST_TEMPERATURE_MAX_C", 65.0)
    m_low = setting_number("COMPOST_MOISTURE_MIN_PCT", 40.0)
    m_high = setting_number("COMPOST_MOISTURE_MAX_PCT", 60.0)
    ph_low = setting_number("COMPOST_PH_MIN", 6.0)
    ph_high = setting_number("COMPOST_PH_MAX", 8.5)
    cn_low = setting_number("COMPOST_CN_MIN", 15.0)
    cn_high = setting_number("COMPOST_CN_MAX", 30.0)
    checks = {
        "temperature": {"value": temp, "band": [0.0, t_max], "ok": temp <= t_max},
        "moisture": {"value": moisture, "band": [m_low, m_high], "ok": m_low <= moisture <= m_high},
        "ph": {"value": ph, "band": [ph_low, ph_high], "ok": ph_low <= ph <= ph_high},
        "c_n_ratio": {"value": cn, "band": [cn_low, cn_high], "ok": cn_low <= cn <= cn_high},
    }
    failed = [name for name, check in checks.items() if not check["ok"]]
    return {
        "checks": checks,
        "failed": failed,
        "verdict": "fail" if failed else "pass",
        "declared_result": text_of("quality_result", record.get("quality_result")) or "pending",
    }


def _inputs(record: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    reference = text_of("reference", record.get("reference")) or "batch"
    code = text_of("batch_code", record.get("batch_code")) or reference
    stage = text_of("stage", record.get("stage")) or "mixing"
    title = "Batch %s: %s" % (code, stage)
    listing = {
        "title": title[:140],
        "description": text_input(record, "Compost batch", (
            "reference", "batch_code", "input_material", "input_kg", "stage",
            "started_on", "curing_days", "temperature_c", "moisture_pct",
            "ph", "c_n_ratio", "quality_result", "notes",
        ))[:5000],
        "category": _TASK_CATEGORY,
        "location": {"address": DEFAULT_ADDRESS},
    }
    event = {
        "event": "batch_stage_recorded",
        "actor": text_of("batch_code", record.get("batch_code")) or reference,
        "resource_type": "compost_batch",
        "resource_id": reference,
        "detail": "%s at %s" % (reference, stage),
    }
    steps = [
        {
            "id": "step_0",
            "block": "audit",
            "input": dict(event),
            "params": {"action": BLOCK_DEFAULT_ACTIONS.get("audit")},
        }
    ]
    return {
        "task_listing": listing,
        "audit": event,
        "workflow": {
            "pipeline_id": CAPABILITY_ID,
            "steps": steps,
            "result": {
                "reference": reference,
                "batch_code": code,
                "stage": stage,
                "quality_result": text_of("quality_result", record.get("quality_result")),
            },
        },
    }


def handle(payload: Any) -> Dict[str, Any]:
    """Track one compost batch and say what the floor does next."""
    record = record_of(CAPABILITY_ID, payload)
    reference = text_of("reference", record.get("reference"))
    code = text_of("batch_code", record.get("batch_code"))
    stage = text_of("stage", record.get("stage")) or "mixing"

    target_days = setting_number("COMPOST_CURING_TARGET_DAYS", 45.0)
    days = whole_of(record.get("curing_days"))
    progress = formulas.curing_progress_pct(days, target_days)
    quality = _quality_verdict(record)

    actions_due: List[str] = []
    if stage in ("mixing", "active_composting"):
        actions_due.append("turn_windrow")
    if stage == "curing" and progress >= 100.0:
        actions_due.append("screen_batch")
    if stage in ("quality_check", "packaged") and quality["verdict"] == "fail":
        actions_due.append("hold_batch")
    if stage == "rejected":
        actions_due.append("record_disposal")

    decision = {
        "reference": reference,
        "batch_code": code,
        "stage": stage,
        "input_material": text_of("input_material", record.get("input_material")),
        "input_kg": number_of(record.get("input_kg")),
        "output_kg": number_of(record.get("output_kg")),
        "mass_loss_pct": formulas.mass_loss_pct(record.get("input_kg"), record.get("output_kg")),
        "curing": {
            "days": days,
            "target_days": target_days,
            "progress_pct": progress,
            "ready": progress >= 100.0,
        },
        "quality": quality,
        "actions_due": actions_due,
    }

    inputs = _inputs(record)
    answers, refusals = call_blocks(
        BLOCK_IDS, BLOCK_DEFAULT_ACTIONS, inputs, entity=ENTITY, roster=BLOCK_IDS
    )
    for block_id, answer in answers.items():
        refusals.extend(nested_refusals(block_id, answer))

    if refusals:
        return refusal(CAPABILITY_ID, AUTHORITY, refusals, answers, result=decision)
    return success(CAPABILITY_ID, AUTHORITY, answers, result=decision)
