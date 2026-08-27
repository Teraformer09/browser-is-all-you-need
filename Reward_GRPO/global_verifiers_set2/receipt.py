"""Structured, hashable verifier receipts shared by every Set 2 policy."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

Status = Literal["PASS", "FAIL", "INVALID", "NOT_RUN"]


@dataclass
class PolicyReceipt:
    policy: str
    status: Status
    reason: str
    facts: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)


@dataclass
class VerificationReceipt:
    schema_version: int
    task_id: str
    manifest_sha256: str
    candidate_sha256: str
    status: Status
    policies: list[PolicyReceipt]
    returned_files: list[str] = field(default_factory=list)
    inherited_files: list[str] = field(default_factory=list)

    def payload(self) -> dict[str, Any]:
        return asdict(self)

    def write(self, path: Path) -> None:
        payload = self.payload()
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload["receipt_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def policy(policy: str, status: Status, reason: str, **facts: Any) -> PolicyReceipt:
    return PolicyReceipt(policy=policy, status=status, reason=reason, facts=facts)
