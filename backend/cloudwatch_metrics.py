"""Amazon CloudWatch metrics and logging for LLM Council (Phase 4).

Publishes custom metrics like:
  - Model response latency (per model)
  - Token usage (input/output/total)
  - Error counts
  - Council deliberation total time
  - Cost estimates
"""

import time
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from functools import partial

from .aws_config import (
    get_cloudwatch_client,
    CLOUDWATCH_ENABLED,
    CLOUDWATCH_NAMESPACE,
)


# ---------------------------------------------------------------------------
# Metric Publisher
# ---------------------------------------------------------------------------

def _publish_metrics_sync(metrics: list):
    """Synchronous CloudWatch PutMetricData call."""
    if not CLOUDWATCH_ENABLED:
        return

    try:
        client = get_cloudwatch_client()
        # CloudWatch allows max 1000 metric data points per PutMetricData call
        # We batch into groups of 20 for safety
        for i in range(0, len(metrics), 20):
            batch = metrics[i:i + 20]
            client.put_metric_data(
                Namespace=CLOUDWATCH_NAMESPACE,
                MetricData=batch,
            )
    except Exception as e:
        print(f"[CloudWatch] Failed to publish metrics: {e}")


async def publish_metrics_async(metrics: list):
    """Async wrapper for publishing CloudWatch metrics."""
    if not CLOUDWATCH_ENABLED:
        return
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, partial(_publish_metrics_sync, metrics))


# ---------------------------------------------------------------------------
# Pre-built Metric Helpers
# ---------------------------------------------------------------------------

async def record_model_latency(model: str, provider: str, latency_ms: float):
    """Record the response latency for a single model query."""
    metrics = [
        {
            "MetricName": "ModelResponseLatency",
            "Dimensions": [
                {"Name": "Model", "Value": model},
                {"Name": "Provider", "Value": provider},
            ],
            "Value": latency_ms,
            "Unit": "Milliseconds",
            "Timestamp": datetime.now(timezone.utc),
        }
    ]
    await publish_metrics_async(metrics)


async def record_token_usage(
    model: str,
    provider: str,
    input_tokens: int,
    output_tokens: int,
):
    """Record token usage for a model query."""
    metrics = [
        {
            "MetricName": "InputTokens",
            "Dimensions": [
                {"Name": "Model", "Value": model},
                {"Name": "Provider", "Value": provider},
            ],
            "Value": input_tokens,
            "Unit": "Count",
            "Timestamp": datetime.now(timezone.utc),
        },
        {
            "MetricName": "OutputTokens",
            "Dimensions": [
                {"Name": "Model", "Value": model},
                {"Name": "Provider", "Value": provider},
            ],
            "Value": output_tokens,
            "Unit": "Count",
            "Timestamp": datetime.now(timezone.utc),
        },
        {
            "MetricName": "TotalTokens",
            "Dimensions": [
                {"Name": "Model", "Value": model},
                {"Name": "Provider", "Value": provider},
            ],
            "Value": input_tokens + output_tokens,
            "Unit": "Count",
            "Timestamp": datetime.now(timezone.utc),
        },
    ]
    await publish_metrics_async(metrics)


async def record_council_deliberation(
    total_time_ms: float,
    stage1_time_ms: float,
    stage2_time_ms: float,
    stage3_time_ms: float,
    num_models: int,
):
    """Record timing metrics for a full council deliberation."""
    now = datetime.now(timezone.utc)
    metrics = [
        {
            "MetricName": "CouncilDeliberationTime",
            "Value": total_time_ms,
            "Unit": "Milliseconds",
            "Timestamp": now,
        },
        {
            "MetricName": "Stage1Time",
            "Value": stage1_time_ms,
            "Unit": "Milliseconds",
            "Timestamp": now,
        },
        {
            "MetricName": "Stage2Time",
            "Value": stage2_time_ms,
            "Unit": "Milliseconds",
            "Timestamp": now,
        },
        {
            "MetricName": "Stage3Time",
            "Value": stage3_time_ms,
            "Unit": "Milliseconds",
            "Timestamp": now,
        },
        {
            "MetricName": "CouncilModelCount",
            "Value": num_models,
            "Unit": "Count",
            "Timestamp": now,
        },
    ]
    await publish_metrics_async(metrics)


async def record_error(model: str, provider: str, error_type: str):
    """Record an error event."""
    metrics = [
        {
            "MetricName": "ModelErrors",
            "Dimensions": [
                {"Name": "Model", "Value": model},
                {"Name": "Provider", "Value": provider},
                {"Name": "ErrorType", "Value": error_type},
            ],
            "Value": 1,
            "Unit": "Count",
            "Timestamp": datetime.now(timezone.utc),
        }
    ]
    await publish_metrics_async(metrics)


async def record_api_request(endpoint: str, method: str, status_code: int, latency_ms: float):
    """Record an API request metric."""
    metrics = [
        {
            "MetricName": "APIRequestLatency",
            "Dimensions": [
                {"Name": "Endpoint", "Value": endpoint},
                {"Name": "Method", "Value": method},
            ],
            "Value": latency_ms,
            "Unit": "Milliseconds",
            "Timestamp": datetime.now(timezone.utc),
        },
        {
            "MetricName": "APIRequestCount",
            "Dimensions": [
                {"Name": "Endpoint", "Value": endpoint},
                {"Name": "StatusCode", "Value": str(status_code)},
            ],
            "Value": 1,
            "Unit": "Count",
            "Timestamp": datetime.now(timezone.utc),
        },
    ]
    await publish_metrics_async(metrics)


# ---------------------------------------------------------------------------
# Timer context manager
# ---------------------------------------------------------------------------

class MetricsTimer:
    """Simple timer for measuring operation durations."""

    def __init__(self):
        self.start_time = None
        self.end_time = None

    def start(self):
        self.start_time = time.perf_counter()
        return self

    def stop(self):
        self.end_time = time.perf_counter()
        return self

    @property
    def elapsed_ms(self) -> float:
        if self.start_time is None:
            return 0.0
        end = self.end_time if self.end_time else time.perf_counter()
        return (end - self.start_time) * 1000
