"""The small envelope every local peer block answers with."""

from __future__ import annotations

from typing import Any, Dict, Optional


class Shim:
    """A block class app.blocks.BLOCK_REGISTRY hands to a peer block.

    The Store's workflow block constructs the class and calls execute(input,
    params); this matches that contract.
    """

    BLOCK_ID = ""
    DEFAULT_ACTION: Optional[str] = None

    async def execute(self, input_data: Any = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        data = input_data if isinstance(input_data, dict) else {"input": input_data}
        action = None
        if isinstance(params, dict):
            action = params.get("action") or params.get("operation")
        return self.handle(data, action=action, params=params or {})

    def handle(self, input_data: Any, action: Optional[str] = None,
               params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raise NotImplementedError


def ok(block_id: str, action: Optional[str], result: Any = None) -> Dict[str, Any]:
    return {
        "status": "success",
        "ok": True,
        "block": block_id,
        "action": action,
        "result": result if result is not None else {},
    }


def error(block_id: str, action: Optional[str], message: str) -> Dict[str, Any]:
    return {
        "status": "error",
        "ok": False,
        "block": block_id,
        "action": action,
        "error": str(message),
    }


def _input_and_params(kwargs: Dict[str, Any]) -> Any:
    kwargs = dict(kwargs or {})
    params = {k: v for k, v in kwargs.items() if k != "input"}
    input_data = kwargs.get(
        "input",
        {k: v for k, v in params.items() if k not in ("action", "operation")},
    )
    return input_data, params


def run_block(block_id: str, handler_class: Any, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    import asyncio

    instance = handler_class()
    return asyncio.run(instance.execute(*_input_and_params(kwargs)))
