from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


def sign_transaction_uid(payload: Dict[str, Any]) -> str:
    """Create a deterministic hash for transaction UIDs."""
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


__all__ = ["sign_transaction_uid"]
