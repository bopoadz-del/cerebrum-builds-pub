"""qa_itp_records -- inspection and test plan records tied to BOQ items.

One record is one inspection lot: the BOQ item it covers, its hold and witness
points, the inspection date and the test verdict, with sign-off. A lot is
accepted only when the test result is ``pass``; a failed or pending lot is
recorded as it was found. Defects stay open through the Defects Notification
Period (Clause 11.1, 365 days from Taking-Over), which is measured from the
Taking-Over date the record carries.

READS   the request record, the uploaded BOQ and the contract clause.
WRITES  the ITP evidence under STORAGE_PATH/workspace; the ROUTE persists the
        record, never this handler.
NEVER   marks a lot accepted without a passing test, or invents a Taking-Over
        date, a sign-off or a defect close-out.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any, Dict

from app import contract_data
from app import capability_support as _support
from app.capability_support import as_date, ok, refuse, run_blocks
from app.dispatch import BLOCK_DEFAULT_ACTIONS as _DISPATCH_DEFAULT_ACTIONS

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "qa_itp_records"
ENTITY = "qa_itp_records"
BLOCK_IDS = ["capture", "evidence_classifier", "evidence_verifier", "file_hasher"]
BLOCK_DEFAULT_ACTIONS = {
    block_id: _DISPATCH_DEFAULT_ACTIONS.get(block_id) for block_id in BLOCK_IDS
}

TEST_RESULTS = ("pass", "fail", "pending")


def _dnp_end(taking_over: date | None) -> date | None:
    if taking_over is None:
        return None
    return taking_over + timedelta(days=contract_data.DEFECTS_NOTIFICATION_DAYS)


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    input_digest = _support.input_digest(record)
    reference = _support.reference_of(record)
    item_code = _support.text_of(record, "boq_item").upper()

    line = None
    if item_code:
        line = contract_data.boq_item(item_code)
        if line is None:
            return refuse(
                f"boq_item {item_code!r} is not in the uploaded BOQ; known items: "
                + ", ".join(row["item"] for row in contract_data.boq_lines()),
                error_kind="unknown_boq_item",
                input_digest=input_digest,
            )

    test_result = (_support.text_of(record, "test_result") or "pending").lower()
    if test_result not in TEST_RESULTS:
        return refuse(
            "test_result must be one of: " + ", ".join(TEST_RESULTS),
            error_kind="invalid_test_result",
            input_digest=input_digest,
        )

    inspection_date = as_date(record.get("inspection_date")) or date.today()
    taking_over = as_date(record.get("taking_over_date"))
    close_out = as_date(record.get("defect_close_out_date"))
    defect_ref = _support.text_of(record, "defect_ref")
    dnp_end = _dnp_end(taking_over)

    if close_out is not None and not defect_ref:
        return refuse(
            "a close-out date was supplied but no defect_ref names the defect being closed",
            error_kind="no_defect_to_close",
            input_digest=input_digest,
        )
    if close_out is not None and taking_over is None:
        return refuse(
            "a defect cannot be closed out through the Defects Notification Period "
            "without the Taking-Over date it runs from",
            error_kind="missing_taking_over_date",
            input_digest=input_digest,
        )
    if close_out is not None and dnp_end is not None and close_out > dnp_end:
        return refuse(
            "defect close-out date falls after the Defects Notification Period end",
            error_kind="outside_defects_notification_period",
            input_digest=input_digest,
        )

    accepted = test_result == "pass"
    lot = {
        "reference": reference,
        "boq_item": (line or {}).get("item") or item_code,
        "boq_description": (line or {}).get("description"),
        "inspection_lot": _support.text_of(record, "inspection_lot") or reference,
        "inspection_date": inspection_date.isoformat(),
        "hold_point": _support.text_of(record, "hold_point"),
        "witness_point": _support.text_of(record, "witness_point"),
        "test_result": test_result,
        "accepted": accepted,
        "defect_ref": defect_ref,
        "defect_open": bool(defect_ref and close_out is None),
        "defect_closed": bool(defect_ref and close_out is not None),
        "defect_close_out_date": close_out.isoformat() if close_out else None,
        "signoff_by": _support.text_of(record, "signoff_by"),
        "taking_over_date": taking_over.isoformat() if taking_over else None,
        "defects_notification_days": contract_data.DEFECTS_NOTIFICATION_DAYS,
        "defects_notification_end": dnp_end.isoformat() if dnp_end else None,
        "clauses": {"defects_notification": contract_data.clause_number("defects_notification")},
        "citation": contract_data.CONTRACT_DOCUMENT,
    }
    # Payment release on the covered BOQ line is gated by this lot: the test
    # must have passed and no defect on the lot may still be open.
    release_gate = (
        "passed"
        if accepted and not lot["defect_open"]
        else ("open_defect" if accepted else "test_not_passed")
    )
    lot["payment_release"] = {
        "releasable": release_gate == "passed",
        "gate": release_gate,
        "boq_item": lot["boq_item"],
        "citation": contract_data.BOQ_DOCUMENT,
        "defects_clause": contract_data.clause_number("defects_notification"),
    }

    workspace = _support.workspace_dir(CAPABILITY_ID)
    stem = input_digest[:12]
    evidence_text = json.dumps(lot, indent=2, sort_keys=True)
    evidence_file = workspace / f"itp_{stem}.json"
    _support.write_artifact(workspace, evidence_file.name, evidence_text)

    packet = {
        "asset_type": "construction_itp",
        "documents": [evidence_file.name],
        "test_result": test_result,
        "inspection_lot": lot["inspection_lot"],
        "boq_item": lot["boq_item"],
    }
    inputs: Dict[str, Dict[str, Any]] = {
        "capture": {"text": evidence_text},
        "evidence_classifier": {"packet": packet},
        "evidence_verifier": {
            "content": evidence_text,
            "id": f"{reference[:60]}:{stem}",
        },
        "file_hasher": {"file_path": str(evidence_file)},
    }
    actions = {"evidence_verifier": "store", "file_hasher": "hash"}
    answers, refusal, unavailable = run_blocks(
        CAPABILITY_ID,
        record,
        BLOCK_IDS,
        inputs,
        actions=actions,
    )
    if refusal and "integrity record already stored" in refusal:
        # Storing identical evidence twice is idempotent, not a contract
        # failure: the same content is already on the integrity chain, so the
        # second pass verifies it instead of refusing the lot.
        verify_inputs = dict(inputs)
        verify_inputs["evidence_verifier"] = {
            "content": evidence_text,
            "id": inputs["evidence_verifier"]["id"],
        }
        answers, refusal, unavailable = run_blocks(
            CAPABILITY_ID,
            record,
            BLOCK_IDS,
            verify_inputs,
            actions={"evidence_verifier": "verify", "file_hasher": "hash"},
        )
    if refusal:
        return refuse(refusal, error_kind="block_refused", input_digest=input_digest)

    classifier = answers.get("evidence_classifier")
    verdict = {}
    if isinstance(classifier, dict):
        body = classifier.get("result") if isinstance(classifier.get("result"), dict) else {}
        verdict = {
            "evidence_class": body.get("evidence_class"),
            "verdict": body.get("verdict"),
            "reasons": body.get("reasons") or [],
        }

    result = {
        **lot,
        "evidence_file": _support.artifact_name("itp", lot),
        "evidence_class": verdict,
        "block_evidence": {
            "captured": isinstance(answers.get("capture"), dict)
            and answers["capture"].get("ok") is not False,
            "classified": isinstance(classifier, dict) and classifier.get("ok") is not False,
            "verified": isinstance(answers.get("evidence_verifier"), dict)
            and answers["evidence_verifier"].get("ok") is not False,
            "hashed": isinstance(answers.get("file_hasher"), dict)
            and answers["file_hasher"].get("ok") is not False,
        },
        "blocks_run": list(BLOCK_IDS),
        "authority": "layer 3 formulas",
    }
    if unavailable:
        result["blocks_unavailable"] = sorted(set(unavailable))
    return ok(CAPABILITY_ID, result, input_digest=input_digest)
