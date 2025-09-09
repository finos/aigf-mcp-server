"""Basic health monitoring for local deployment.

Copyright 2024 Hugo Calderon

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Provides service health indicators, uptime tracking, and basic
diagnostics suitable for local development and troubleshooting.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional


class HealthStatus(Enum):
    """Service health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ServiceMetrics:
    """Basic service metrics for health monitoring."""

    requests_total: int = 0
    requests_successful: int = 0
    requests_failed: int = 0
    last_request_time: datetime | None = None
    average_response_time_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.requests_total == 0:
            return 100.0
        return (self.requests_successful / self.requests_total) * 100.0

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate as percentage."""
        return 100.0 - self.success_rate


@dataclass
class ServiceHealth:
    """Health status for a service component."""

    name: str
    status: HealthStatus
    message: str = ""
    metrics: ServiceMetrics = field(default_factory=ServiceMetrics)
    last_check: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert health status to dictionary for logging/display."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "last_check": self.last_check.isoformat(),
            "metrics": {
                "requests_total": self.metrics.requests_total,
                "requests_successful": self.metrics.requests_successful,
                "requests_failed": self.metrics.requests_failed,
                "success_rate": round(self.metrics.success_rate, 2),
                "failure_rate": round(self.metrics.failure_rate, 2),
                "average_response_time_ms": round(
                    self.metrics.average_response_time_ms, 2
                ),
                "last_request": (
                    self.metrics.last_request_time.isoformat()
                    if self.metrics.last_request_time
                    else None
                ),
            },
        }


class HealthMonitor:
    """Basic health monitoring for local deployment."""

    def __init__(self) -> None:
        """Initialize health monitor."""
        self.start_time = datetime.now()
        self.services: dict[str, ServiceHealth] = {}

        # Initialize core services
        self._initialize_services()

    def _initialize_services(self) -> None:
        """Initialize monitoring for core services."""
        core_services = [
            "content_service",
            "github_api",
            "cache_system",
            "discovery_service",
        ]

        for service in core_services:
            self.services[service] = ServiceHealth(
                name=service,
                status=HealthStatus.HEALTHY,
                message="Service initialized",
            )

    @property
    def uptime(self) -> timedelta:
        """Get service uptime."""
        return datetime.now() - self.start_time

    @property
    def uptime_seconds(self) -> float:
        """Get uptime in seconds."""
        return self.uptime.total_seconds()

    def record_request(
        self, service: str, success: bool, response_time_ms: float = 0.0
    ) -> None:
        """Record a request for health tracking."""
        if service not in self.services:
            self.services[service] = ServiceHealth(
                name=service,
                status=HealthStatus.HEALTHY,
                message="Service auto-discovered",
            )

        health = self.services[service]
        metrics = health.metrics

        # Update metrics
        metrics.requests_total += 1
        metrics.last_request_time = datetime.now()

        if success:
            metrics.requests_successful += 1
        else:
            metrics.requests_failed += 1

        # Update rolling average response time
        if response_time_ms > 0:
            current_avg = metrics.average_response_time_ms
            total_requests = metrics.requests_total
            metrics.average_response_time_ms = (
                current_avg * (total_requests - 1) + response_time_ms
            ) / total_requests

        # Update health status based on metrics
        self._update_health_status(service)

    def _update_health_status(self, service: str) -> None:
        """Update health status based on current metrics."""
        health = self.services[service]
        metrics = health.metrics

        # Health status logic for local deployment
        if metrics.requests_total == 0:
            health.status = HealthStatus.HEALTHY
            health.message = "No requests yet"
        elif metrics.failure_rate > 50:
            health.status = HealthStatus.UNHEALTHY
            health.message = f"High failure rate: {metrics.failure_rate:.1f}%"
        elif metrics.failure_rate > 20:
            health.status = HealthStatus.DEGRADED
            health.message = f"Elevated failure rate: {metrics.failure_rate:.1f}%"
        elif metrics.average_response_time_ms > 5000:  # 5 seconds
            health.status = HealthStatus.DEGRADED
            health.message = (
                f"Slow response time: {metrics.average_response_time_ms:.0f}ms"
            )
        else:
            health.status = HealthStatus.HEALTHY
            health.message = f"Operating normally ({metrics.success_rate:.1f}% success)"

        health.last_check = datetime.now()

    def get_service_health(self, service: str) -> ServiceHealth | None:
        """Get health status for a specific service."""
        return self.services.get(service)

    def get_overall_health(self) -> ServiceHealth:
        """Get overall system health status."""
        if not self.services:
            return ServiceHealth(
                name="system",
                status=HealthStatus.HEALTHY,
                message="System ready",
            )

        # Determine overall status
        statuses = [health.status for health in self.services.values()]

        if any(status == HealthStatus.UNHEALTHY for status in statuses):
            overall_status = HealthStatus.UNHEALTHY
            unhealthy_services = [
                name
                for name, health in self.services.items()
                if health.status == HealthStatus.UNHEALTHY
            ]
            message = f"Unhealthy services: {', '.join(unhealthy_services)}"
        elif any(status == HealthStatus.DEGRADED for status in statuses):
            overall_status = HealthStatus.DEGRADED
            degraded_services = [
                name
                for name, health in self.services.items()
                if health.status == HealthStatus.DEGRADED
            ]
            message = f"Degraded services: {', '.join(degraded_services)}"
        else:
            overall_status = HealthStatus.HEALTHY
            healthy_count = len([s for s in statuses if s == HealthStatus.HEALTHY])
            message = f"All {healthy_count} services healthy"

        # Calculate combined metrics
        total_requests = sum(h.metrics.requests_total for h in self.services.values())
        total_successful = sum(
            h.metrics.requests_successful for h in self.services.values()
        )
        total_failed = sum(h.metrics.requests_failed for h in self.services.values())

        combined_metrics = ServiceMetrics(
            requests_total=total_requests,
            requests_successful=total_successful,
            requests_failed=total_failed,
        )

        return ServiceHealth(
            name="system",
            status=overall_status,
            message=message,
            metrics=combined_metrics,
        )

    def get_health_summary(self) -> dict[str, Any]:
        """Get comprehensive health summary for logging/debugging."""
        overall = self.get_overall_health()

        return {
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": round(self.uptime_seconds, 1),
            "uptime_human": str(self.uptime).split(".")[0],  # Remove microseconds
            "overall_status": overall.status.value,
            "overall_message": overall.message,
            "services": {
                name: health.to_dict() for name, health in self.services.items()
            },
            "summary": {
                "total_services": len(self.services),
                "healthy_services": len(
                    [
                        h
                        for h in self.services.values()
                        if h.status == HealthStatus.HEALTHY
                    ]
                ),
                "degraded_services": len(
                    [
                        h
                        for h in self.services.values()
                        if h.status == HealthStatus.DEGRADED
                    ]
                ),
                "unhealthy_services": len(
                    [
                        h
                        for h in self.services.values()
                        if h.status == HealthStatus.UNHEALTHY
                    ]
                ),
            },
        }

    def reset_health(self) -> None:
        """Reset all health counters and error boundaries."""
        for _, health in self.services.items():
            # Reset metrics to initial state
            health.metrics = ServiceMetrics()
            health.status = HealthStatus.HEALTHY
            health.message = "Health counters reset"
            health.last_check = datetime.now()

        # Reset start time to current time (resets uptime)
        self.start_time = datetime.now()


class HealthMonitorManager:
    """Singleton manager for the global health monitor instance."""

    _instance: Optional["HealthMonitorManager"] = None
    _health_monitor: HealthMonitor | None = None

    def __new__(cls) -> "HealthMonitorManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_health_monitor(self) -> HealthMonitor:
        """Get the global health monitor instance."""
        if self._health_monitor is None:
            self._health_monitor = HealthMonitor()
        return self._health_monitor


# Global health monitor manager instance
_health_monitor_manager = HealthMonitorManager()


def get_health_monitor() -> HealthMonitor:
    """Get the global health monitor instance."""
    return _health_monitor_manager.get_health_monitor()
