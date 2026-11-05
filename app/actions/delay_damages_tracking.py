"""delay_damages_tracking -- Clause 8.7 position for the project.

READS  caller payload dates/amounts, Clause 8.2 and 8.7 in the contract
       document, and the BOQ total as the Accepted Contract Amount default.
WRITES the capability response envelope only.
NEVER  applies damages without a cause, hides a cap, or reports success when
       formula_executor or validation refuses.
"""

from __future__ import annotations

from app import formulas
from app.authority import authority_label
from app.block_inputs import block_action, contract_citation, delay_formula_inputs, delay_values, validation_inputs
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "delay_damages_tracking"
ENTITY = "delay_damages_tracking"
BLOCK_IDS = ["formula_executor", "validation"]


def _failure(block_id, message):
    return {"ok": False, "error": f"{block_id}: {message}", "block": block_id, "record": None, "id": None}


def _is_failure(answer) -> bool:
    return not isinstance(answer, dict) or str(answer.get("status") or "").lower() in {
        "error",
        "failed",
        "refused",
        "validation_error",
        "fail",
    }


def handle(payload: dict) -> dict:
    data = dict(payload or {})
    values = delay_values(data)
    assessment = formulas.delay_damages(values["accepted_contract_amount"], values["days_of_delay"])

    try:
        formula_answer = execute(
            "formula_executor",
            delay_formula_inputs(data),
            action=block_action("formula_executor"),
        )
    except Exception as exc:  # noqa: BLE001
        return _failure("formula_executor", f"{type(exc).__name__}: {exc}")
    if _is_failure(formula_answer):
        return _failure("formula_executor", str(formula_answer.get("error") or "formula refused"))

    try:
        validation = execute(
            "validation",
            validation_inputs(data),
            action=block_action("validation"),
        )
    except Exception as exc:  # noqa: BLE001
        return _failure("validation", f"{type(exc).__name__}: {exc}")
    if _is_failure(validation) or str(validation.get("status") or "").lower() == "fail":
        stages = validation.get("stages") if isinstance(validation, dict) else None
        return _failure("validation", str(validation.get("fail_fast_stage") or stages or "validation failed"))

    executed = formula_answer.get("execution_result")
    corroborated = None
    if isinstance(executed, (int, float)):
        corroborated = round(float(executed), 2) == assessment["damages_amount"]

    record = {
        "id": None,
        "reference": str(data.get("reference") or "DD-POSITION"),
        "status": str(data.get("status") or "open"),
        "notice_reference": str(data.get("notice_reference") or ""),
        "commencement_date": data.get("commencement_date"),
        "completion_date": data.get("completion_date"),
        "actual_completion_date": data.get("actual_completion_date"),
        "accepted_contract_amount": assessment["accepted_contract_amount"],
        "days_of_delay": assessment["days_of_delay"],
        "daily_rate": assessment["daily_rate"],
        "damages_cap_ratio": assessment["cap_ratio"],
        "damages_amount": assessment["damages_amount"],
        "clause_reference": "8.2, 8.7",
    }
    return {
        "ok": True,
        "record": record,
        "id": None,
        "assessment": assessment,
        "formula_executor_agrees": corroborated,
        "validation_status": validation.get("status"),
        "authority": authority_label(
            "kernel_formula",
            detail="universal:late_fee_simple_v1 composed with Clause 8.7 cap ("
            + contract_citation() + ")",
        ),
    }
