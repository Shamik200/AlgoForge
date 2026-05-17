"""Error recovery utilities for live trading workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class RecoveryDecision:
    """Decision returned by the error recovery manager."""

    stage: str
    exception_type: str
    should_retry: bool
    retry_delay_seconds: float
    fallback_message: str
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ErrorRecoveryManager:
    """Classify failures and choose a safe recovery action."""

    def __init__(self, default_retry_delay_seconds: float = 2.0) -> None:
        self.default_retry_delay_seconds = default_retry_delay_seconds
        self._history: list[RecoveryDecision] = []

    @property
    def history(self) -> list[RecoveryDecision]:
        return list(self._history)

    def handle_exception(
        self,
        exception: Exception,
        stage: str,
        context: dict[str, Any] | None = None,
    ) -> RecoveryDecision:
        """Classify an exception and return the recovery plan."""
        exception_type = type(exception).__name__
        lower_name = exception_type.lower()
        message = str(exception).strip() or "unhandled error"

        if isinstance(exception, (TimeoutError, ConnectionError, OSError)):
            should_retry = True
            retry_delay = self.default_retry_delay_seconds
            fallback_message = f"retry:{stage}"
        elif isinstance(exception, (ValueError, KeyError, TypeError)):
            should_retry = False
            retry_delay = 0.0
            fallback_message = f"skip:{stage}"
        elif "network" in lower_name or "api" in lower_name:
            should_retry = True
            retry_delay = self.default_retry_delay_seconds
            fallback_message = f"retry:{stage}"
        else:
            should_retry = False
            retry_delay = 0.0
            fallback_message = f"fallback:{stage}"

        decision = RecoveryDecision(
            stage=stage,
            exception_type=exception_type,
            should_retry=should_retry,
            retry_delay_seconds=retry_delay,
            fallback_message=f"{fallback_message}:{message}",
            context=context or {},
        )
        self._history.append(decision)
        return decision
