"""Edge validation: a value must BE the type the capability declares.

The capability's own model is the contract: ``batch_code: str`` means a
number is not a batch code, ``curing_days: int`` means a list is not a curing
period, ``vat_exempt: bool`` means "yes" is not a decision. The route validates at the
edge, before the handler runs and before anything is stored, and answers 422
naming the field.

This is driven entirely by the model's declared annotations -- there is no
per-field or per-capability branch here, so a field added to a capability is
validated the moment it is declared.
"""

from __future__ import annotations

import math
import typing
from typing import Any, Dict

from fastapi import HTTPException

#: What each declared annotation accepts. ``None`` is always allowed for a
#: field the caller left out or explicitly nulled; the store holds NULL.
_ACCEPTS: Dict[str, tuple] = {
    "str": (str,),
    "int": (int,),
    "float": (int, float),
    "bool": (bool,),
}


def _declared_kind(annotation: Any) -> str:
    """The JSON kind a Python annotation names, or "" when it names none."""
    if annotation is str:
        return "str"
    if annotation is bool:
        return "bool"
    if annotation is int:
        return "int"
    if annotation is float:
        return "float"
    origin = typing.get_origin(annotation)
    if origin is typing.Union:
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return _declared_kind(args[0])
    return ""


def _hint_for(cls: Any, field: str) -> Any:
    """The annotation for one field, or None when the model declares none."""
    for name, annotation in typing.get_type_hints(cls).items():
        if name == field:
            return annotation
    return None


def reject_wrong_types(capability_id: str, payload: Dict[str, Any] | None) -> None:
    """Refuse a field whose value is not the type the model declares.

    A bool is refused where a number is declared (``isinstance(True, int)``
    is true in Python, and a flag is never a count), and a number is refused
    where text is declared.
    """
    from app.models import MODELS

    cls = MODELS.get(capability_id)
    if cls is None or not isinstance(payload, dict):
        return
    for name, value in payload.items():
        if value is None:
            continue
        annotation = _hint_for(cls, name)
        kind = _declared_kind(annotation) if annotation is not None else ""
        if not kind:
            continue
        accepts = _ACCEPTS.get(kind)
        if not accepts:
            continue
        if isinstance(value, bool) and kind != "bool":
            raise HTTPException(
                status_code=422, detail="%s must be a %s" % (name, kind)
            )
        if not isinstance(value, accepts):
            raise HTTPException(
                status_code=422, detail="%s must be a %s" % (name, kind)
            )
        # JSON's non-standard NaN/Infinity literals parse in Python and
        # compare False against every bound, so a min/max guard lets them
        # through. They are refused here, by the declared kind, on every
        # numeric field -- not only the bounded ones.
        if kind in ("int", "float") and not math.isfinite(float(value)):
            raise HTTPException(
                status_code=422, detail="%s must be a finite number" % name
            )
