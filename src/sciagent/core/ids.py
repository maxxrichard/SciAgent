from __future__ import annotations

import uuid


def new_id(prefix: str) -> str:
    """Return a sortable-enough, human-readable identifier such as ``run_3f2a...``."""
    return f"{prefix}_{uuid.uuid4().hex[:20]}"
