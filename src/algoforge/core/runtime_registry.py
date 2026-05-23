"""Runtime Registry — Tracks active streams, strategies, models, and WebSocket clients.

Provides a thread-safe singleton for system-wide health and component status check.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ServiceStatus:
    name: str
    status: str  # "starting", "healthy", "degraded", "stopped"
    initialized_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict = field(default_factory=dict)


class RuntimeRegistry:
    """Thread-safe system runtime registry singleton."""

    _instance: RuntimeRegistry | None = None
    _lock = asyncio.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._services: dict[str, ServiceStatus] = {}
        self._active_connections: set[str] = set()
        self._active_strategies: list[str] = []
        self._active_models: list[str] = []
        self._active_streams: set[str] = set()
        self._initialized = True
        logger.info("runtime_registry.initialized")

    def register_service(self, name: str, status: str = "starting", details: dict | None = None) -> None:
        """Register or update service status in the registry."""
        self._services[name] = ServiceStatus(
            name=name,
            status=status,
            details=details or {},
        )
        logger.info("runtime_registry.service_registered", name=name, status=status)

    def update_service_status(self, name: str, status: str, details: dict | None = None) -> None:
        """Update existing service status and refresh its heartbeat timestamp."""
        if name in self._services:
            self._services[name].status = status
            self._services[name].last_heartbeat = datetime.now(timezone.utc)
            if details:
                self._services[name].details.update(details)
        else:
            self.register_service(name, status, details)

    def get_service_status(self, name: str) -> ServiceStatus | None:
        """Retrieve the status of a specific service."""
        return self._services.get(name)

    def register_strategy(self, name: str) -> None:
        """Add strategy to active listing."""
        if name not in self._active_strategies:
            self._active_strategies.append(name)

    def register_model(self, name: str) -> None:
        """Add ML/RL model to active listing."""
        if name not in self._active_models:
            self._active_models.append(name)

    def add_active_stream(self, symbol: str) -> None:
        """Register active websocket tick symbol feed."""
        self._active_streams.add(symbol)

    def remove_active_stream(self, symbol: str) -> None:
        """Deregister active websocket tick symbol feed."""
        self._active_streams.discard(symbol)

    def register_connection(self, client_id: str) -> None:
        """Track active client connection."""
        self._active_connections.add(client_id)

    def remove_connection(self, client_id: str) -> None:
        """Untrack client connection."""
        self._active_connections.discard(client_id)

    def get_health_report(self) -> dict:
        """Generate comprehensive system status dictionary for API telemetry."""
        now = datetime.now(timezone.utc)
        services_report = {}
        is_healthy = True

        for k, v in self._services.items():
            heartbeat_age = (now - v.last_heartbeat).total_seconds()
            status = v.status
            if heartbeat_age > 15.0 and status == "healthy":
                status = "degraded"
                is_healthy = False
            services_report[k] = {
                "status": status,
                "initialized_at": v.initialized_at.isoformat(),
                "heartbeat_age_s": round(heartbeat_age, 2),
                "details": v.details,
            }

        return {
            "status": "healthy" if is_healthy else "degraded",
            "active_connections_count": len(self._active_connections),
            "active_strategies": self._active_strategies,
            "active_models": self._active_models,
            "active_streams": list(self._active_streams),
            "services": services_report,
            "timestamp": now.isoformat(),
        }
