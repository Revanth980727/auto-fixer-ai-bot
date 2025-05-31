
import time
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
import statistics
import logging

logger = logging.getLogger(__name__)

@dataclass
class MetricPoint:
    timestamp: str
    value: float
    tags: Dict[str, str] = field(default_factory=dict)

@dataclass
class PerformanceMetric:
    name: str
    points: deque = field(default_factory=lambda: deque(maxlen=1000))
    
    def add_point(self, value: float, tags: Optional[Dict[str, str]] = None):
        point = MetricPoint(
            timestamp=datetime.now(timezone.utc).isoformat(),
            value=value,
            tags=tags or {}
        )
        self.points.append(point)

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        return (time.time() - self.last_failure_time) > self.timeout
    
    def _on_success(self):
        self.failure_count = 0
        self.state = "CLOSED"
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

class MetricsCollector:
    def __init__(self):
        self.metrics: Dict[str, PerformanceMetric] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.agent_timings: Dict[str, List[float]] = defaultdict(list)
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.success_counts: Dict[str, int] = defaultdict(int)
        self.system_health: Dict[str, Any] = {
            "last_update": datetime.now(timezone.utc).isoformat(),
            "status": "healthy",
            "services": {}
        }
        
        # Start background cleanup task
        asyncio.create_task(self._cleanup_old_metrics())
    
    def get_or_create_metric(self, name: str) -> PerformanceMetric:
        """Get or create a performance metric"""
        if name not in self.metrics:
            self.metrics[name] = PerformanceMetric(name=name)
        return self.metrics[name]
    
    def record_agent_execution(self, agent_type: str, duration: float, success: bool, 
                              ticket_id: Optional[int] = None, context: Optional[Dict] = None):
        """Record agent execution metrics"""
        # Record timing
        self.agent_timings[agent_type].append(duration)
        
        # Keep only last 100 timings
        if len(self.agent_timings[agent_type]) > 100:
            self.agent_timings[agent_type] = self.agent_timings[agent_type][-100:]
        
        # Record success/failure
        if success:
            self.success_counts[agent_type] += 1
        else:
            self.error_counts[agent_type] += 1
        
        # Record detailed metric
        metric = self.get_or_create_metric(f"agent_execution_time_{agent_type}")
        tags = {
            "success": str(success),
            "agent": agent_type
        }
        if ticket_id:
            tags["ticket_id"] = str(ticket_id)
        
        metric.add_point(duration, tags)
        
        logger.info(f"Recorded {agent_type} execution: {duration:.2f}s, success: {success}")
    
    def record_pipeline_execution(self, ticket_id: int, total_duration: float, 
                                 stages_completed: int, success: bool):
        """Record end-to-end pipeline execution metrics"""
        metric = self.get_or_create_metric("pipeline_execution_time")
        tags = {
            "ticket_id": str(ticket_id),
            "success": str(success),
            "stages_completed": str(stages_completed)
        }
        metric.add_point(total_duration, tags)
        
        # Record pipeline success rate
        pipeline_type = "full_pipeline" if stages_completed >= 4 else "partial_pipeline"
        if success:
            self.success_counts[pipeline_type] += 1
        else:
            self.error_counts[pipeline_type] += 1
    
    def record_github_operation(self, operation: str, duration: float, success: bool):
        """Record GitHub API operation metrics"""
        metric = self.get_or_create_metric(f"github_{operation}_time")
        tags = {
            "operation": operation,
            "success": str(success)
        }
        metric.add_point(duration, tags)
        
        if success:
            self.success_counts[f"github_{operation}"] += 1
        else:
            self.error_counts[f"github_{operation}"] += 1
    
    def get_circuit_breaker(self, service_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for a service"""
        if service_name not in self.circuit_breakers:
            self.circuit_breakers[service_name] = CircuitBreaker()
        return self.circuit_breakers[service_name]
    
    def get_agent_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for all agents"""
        summary = {}
        
        for agent_type, timings in self.agent_timings.items():
            if timings:
                summary[agent_type] = {
                    "avg_duration": statistics.mean(timings),
                    "median_duration": statistics.median(timings),
                    "min_duration": min(timings),
                    "max_duration": max(timings),
                    "total_executions": len(timings),
                    "success_count": self.success_counts.get(agent_type, 0),
                    "error_count": self.error_counts.get(agent_type, 0),
                    "success_rate": self._calculate_success_rate(agent_type)
                }
        
        return summary
    
    def get_pipeline_performance_summary(self) -> Dict[str, Any]:
        """Get pipeline performance summary"""
        pipeline_metric = self.metrics.get("pipeline_execution_time")
        if not pipeline_metric or not pipeline_metric.points:
            return {"no_data": True}
        
        durations = [point.value for point in pipeline_metric.points]
        success_points = [point for point in pipeline_metric.points if point.tags.get("success") == "True"]
        
        return {
            "total_pipelines": len(durations),
            "successful_pipelines": len(success_points),
            "avg_duration": statistics.mean(durations) if durations else 0,
            "median_duration": statistics.median(durations) if durations else 0,
            "success_rate": len(success_points) / len(durations) if durations else 0,
            "avg_successful_duration": statistics.mean([p.value for p in success_points]) if success_points else 0
        }
    
    def get_system_health_status(self) -> Dict[str, Any]:
        """Get current system health status"""
        health_status = {
            "overall_status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "services": {},
            "circuit_breakers": {},
            "alerts": []
        }
        
        # Check circuit breaker states
        for service, breaker in self.circuit_breakers.items():
            health_status["circuit_breakers"][service] = {
                "state": breaker.state,
                "failure_count": breaker.failure_count
            }
            
            if breaker.state == "OPEN":
                health_status["overall_status"] = "degraded"
                health_status["alerts"].append(f"Circuit breaker OPEN for {service}")
        
        # Check agent performance
        agent_summary = self.get_agent_performance_summary()
        for agent_type, metrics in agent_summary.items():
            success_rate = metrics.get("success_rate", 0)
            if success_rate < 0.8:  # Less than 80% success rate
                health_status["overall_status"] = "degraded"
                health_status["alerts"].append(f"Low success rate for {agent_type}: {success_rate:.2%}")
        
        # Check recent error rates
        recent_errors = self._get_recent_error_rate()
        if recent_errors > 0.3:  # More than 30% error rate
            health_status["overall_status"] = "unhealthy"
            health_status["alerts"].append(f"High error rate: {recent_errors:.2%}")
        
        return health_status
    
    def get_performance_trends(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance trends over specified time period"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        trends = {}
        
        for metric_name, metric in self.metrics.items():
            recent_points = [
                point for point in metric.points
                if datetime.fromisoformat(point.timestamp.replace('Z', '+00:00')) > cutoff_time
            ]
            
            if len(recent_points) >= 2:
                values = [point.value for point in recent_points]
                timestamps = [datetime.fromisoformat(point.timestamp.replace('Z', '+00:00')) for point in recent_points]
                
                # Calculate trend (simple linear regression slope)
                n = len(values)
                x_values = [(ts - timestamps[0]).total_seconds() for ts in timestamps]
                
                if n > 1:
                    x_mean = statistics.mean(x_values)
                    y_mean = statistics.mean(values)
                    
                    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, values))
                    denominator = sum((x - x_mean) ** 2 for x in x_values)
                    
                    slope = numerator / denominator if denominator != 0 else 0
                    
                    trends[metric_name] = {
                        "data_points": n,
                        "avg_value": y_mean,
                        "trend_slope": slope,
                        "trend_direction": "increasing" if slope > 0 else "decreasing" if slope < 0 else "stable"
                    }
        
        return trends
    
    def _calculate_success_rate(self, agent_type: str) -> float:
        """Calculate success rate for an agent type"""
        successes = self.success_counts.get(agent_type, 0)
        errors = self.error_counts.get(agent_type, 0)
        total = successes + errors
        
        return successes / total if total > 0 else 0.0
    
    def _get_recent_error_rate(self, minutes: int = 30) -> float:
        """Get error rate in recent time period"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        
        total_recent = 0
        error_recent = 0
        
        for metric in self.metrics.values():
            for point in metric.points:
                point_time = datetime.fromisoformat(point.timestamp.replace('Z', '+00:00'))
                if point_time > cutoff_time:
                    total_recent += 1
                    if point.tags.get("success") == "False":
                        error_recent += 1
        
        return error_recent / total_recent if total_recent > 0 else 0.0
    
    async def _cleanup_old_metrics(self):
        """Background task to clean up old metric points"""
        while True:
            try:
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=48)
                
                for metric in self.metrics.values():
                    # Convert deque to list, filter, and recreate deque
                    recent_points = [
                        point for point in metric.points
                        if datetime.fromisoformat(point.timestamp.replace('Z', '+00:00')) > cutoff_time
                    ]
                    metric.points = deque(recent_points, maxlen=1000)
                
                # Reset old counts (keep rolling window)
                if len(self.agent_timings) > 0:
                    for agent_type in list(self.agent_timings.keys()):
                        if len(self.agent_timings[agent_type]) == 0:
                            del self.agent_timings[agent_type]
                
                await asyncio.sleep(3600)  # Run every hour
                
            except Exception as e:
                logger.error(f"Error in metrics cleanup: {e}")
                await asyncio.sleep(600)  # Wait 10 minutes on error

# Global metrics collector instance
metrics_collector = MetricsCollector()
