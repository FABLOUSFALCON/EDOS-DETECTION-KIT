from typing import Any


def model_to_dict(obj: Any, **kwargs) -> Any:
    """Serialize Pydantic models in a way compatible with v1 and v2.

    If object has `model_dump` (Pydantic v2), use it. Otherwise fall back to
    `.dict()` (Pydantic v1). If object is not a Pydantic model, return it as-is.

    kwargs are forwarded to the underlying serialization call.
    """
    if obj is None:
        return None

    # Pydantic v2
    if hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump")):
        try:
            return obj.model_dump(**kwargs)
        except Exception:
            # Fall through to dict fallback
            pass

    # Pydantic v1
    if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
        try:
            return obj.dict(**kwargs)
        except Exception:
            pass

    # Not a pydantic model - return as-is
    return obj


"""
Pydantic compatibility helpers

Provides a small helper to convert Pydantic models to dicts while
supporting both Pydantic v2 (`model_dump`) and v1 (`dict`).
"""

from typing import Any


def model_to_dict(obj: Any, **kwargs) -> Any:
    """Return a dict-like serialization for a Pydantic model.

    If the object implements `model_dump` (Pydantic v2), use it; otherwise
    fall back to `dict()` (Pydantic v1). If the object is not a model,
    return it unchanged.
    """
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump(**kwargs)
        except Exception:
            # Fall back to dict if model_dump fails for some reason
            pass
    if hasattr(obj, "dict"):
        try:
            return obj.dict(**kwargs)
        except Exception:
            pass
    return obj
