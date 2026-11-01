"""Shared block-call runner for the capability handlers.

This module owns the two contracts every handler keeps and nothing else --
each handler builds its own inputs and makes its own domain decision:

* ``action=`` travels as a KEYWORD, from the handler's own
  ``BLOCK_DEFAULT_ACTIONS`` (the value read from each bound block's own
  contract), never inside the payload dict; ``prepare_block_input`` has
  already shaped the record into what the block accepts;
* every id in the handler's ``BLOCK_IDS`` is called, and a block refusal is
  returned as the capability's refusal -- ``ok: False`` with the refusing
  block named, and nothing persisted -- never reported as success (F1).

A block that raises is also a refusal: the block's own answer is the
diagnosis, so it is recorded in the same shape rather than escaping as a
500.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence, Tuple

#: A block answer with one of these statuses (or ``ok: False``) did not
#: succeed. "partial" is the word the workflow block uses for a pipeline
#: whose step failed, so reading only "error" would report a failed run as a
#: success.
FAILED_STATUSES = ("error", "failed", "partial")


def is_refusal(envelope: Any) -> bool:
    if not isinstance(envelope, dict):
        return False
    if envelope.get("ok") is False:
        return True
    if str(envelope.get("status") or "").lower() in FAILED_STATUSES:
        return True
    steps = envelope.get("results")
    if isinstance(steps, list):
        for step in steps:
            if isinstance(step, dict) and str(step.get("status") or "").lower() in FAILED_STATUSES:
                return True
    return False


def refusal_text(block_id: str, envelope: Any) -> str:
    if isinstance(envelope, dict):
        detail = envelope.get("error") or envelope.get("message")
        if not detail:
            failed = [
                step for step in (envelope.get("results") or [])
                if isinstance(step, dict)
                and str(step.get("status") or "").lower() in FAILED_STATUSES
            ]
            if failed:
                detail = "; ".join(
                    "%s (%s): %s" % (
                        step.get("step_id") or "step",
                        step.get("block") or "?",
                        str(step.get("error") or step.get("status"))[:160],
                    )
                    for step in failed
                )
    else:
        detail = envelope
    return "%s: %s" % (block_id, str(detail or "refused")[:240])


def call_blocks(
    block_ids: Sequence[str],
    default_actions: Dict[str, Any],
    inputs: Dict[str, Dict[str, Any]],
    *,
    entity: str | None = None,
    roster: Iterable[str] | None = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """Call every declared block once; return (answers, refusals).

    ``inputs`` holds one already-built record per block id. The record is
    passed through ``app.block_inputs.prepare_block_input`` so a field the
    block reads at its top level and a value that must be constructed from
    the record (a channel, a table name, a widget list) are settled here
    rather than demanded of the caller.
    """
    from app.block_inputs import prepare_block_input
    from app.dispatch import execute

    answers: Dict[str, Any] = {}
    peer_ids = list(roster or block_ids)
    for block_id in block_ids:
        action = default_actions.get(block_id)
        data = dict(inputs.get(block_id) or {})
        try:
            data = prepare_block_input(
                block_id, data, action=action, roster=peer_ids,
                entity=entity, default_actions=default_actions,
            )
        except Exception:  # a shaper that cannot apply leaves the record alone
            pass
        try:
            answers[block_id] = execute(block_id, data, action=action)
        except Exception as exc:  # a block refusal is an answer, not a 500
            answers[block_id] = {
                "status": "error",
                "ok": False,
                "block": block_id,
                "error": "%s: %s" % (type(exc).__name__, exc),
            }
    refusals = [
        refusal_text(block_id, envelope)
        for block_id, envelope in answers.items()
        if is_refusal(envelope)
    ]
    return answers, refusals
