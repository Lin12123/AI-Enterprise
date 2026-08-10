"""Execution result types for the fixed API executor."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OperationResult:
    operation_id: str
    operation_type: str
    status: str
    message: str = ""


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    message: str
    operations: tuple[OperationResult, ...] = ()
    outputs: tuple[str, ...] = ()
