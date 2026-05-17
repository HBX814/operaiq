"""
Synthetic Production Event Generator for OperaIQ.

Runs as an asyncio loop, publishing to Pub/Sub topic "operaiq-events" every 30s.
A Pub/Sub push subscription should forward to BigQuery via a Cloud Dataflow or
direct BigQuery subscription (recommended: use a BigQuery subscription on the topic).

Event types: DeploymentEvent, MetricEvent, IncidentEvent.
After a "failed" deployment, error_rate spikes for 5 minutes for the same service.
"""

import os
import time
import json
import random
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from google.cloud import pubsub_v1

# Configuration
PROJECT_ID = "operaiq"
TOPIC_ID = "operaiq-events"
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

# Setup Publisher
if not DRY_RUN:
    publisher = pubsub_v1.PublisherClient()
    topic_path = f"projects/{PROJECT_ID}/topics/{TOPIC_ID}"
else:
    publisher = None
    topic_path = None

SERVICES = ["payments", "auth", "inventory", "notifications", "search"]
METRIC_TYPES = ["error_rate", "p99_latency_ms", "request_rate", "cpu_percent"]
REGIONS = ["us-central1", "us-east1", "europe-west1", "asia-northeast1"]

# State for simulating spikes
_spike_registry = {}  # service -> end_time

def _now():
    return datetime.now(timezone.utc).isoformat()

def _is_spiking(service: str) -> bool:
    end_time = _spike_registry.get(service)
    if not end_time:
        return False
    if datetime.now(timezone.utc) > end_time:
        del _spike_registry[service]
        return False
    return True

def generate_deployment_event() -> dict:
    service = random.choice(SERVICES)
    status = random.choices(["success", "failed"], weights=[75, 25])[0]
    dep_id = str(uuid.uuid4())
    if status == "failed":
        _spike_registry[service] = datetime.now(timezone.utc) + timedelta(minutes=5)
    
    return {
        "event_type": "deployment",
        "service": service,
        "deployment_id": dep_id,
        "version": f"{random.randint(1,3)}.{random.randint(0,9)}.{random.randint(0,20)}",
        "status": status,
        "timestamp": _now(),
        "region": random.choice(REGIONS),
        "ingested_at": _now()
    }


def generate_metric_event(service: Optional[str] = None, metric_type: Optional[str] = None) -> dict:
    svc = service or random.choice(SERVICES)
    mt = metric_type or random.choice(METRIC_TYPES)
    spiking = _is_spiking(svc)
    if mt == "error_rate":
        value = round(random.uniform(15, 40), 2) if spiking else round(random.uniform(0.1, 2.5), 2)
    elif mt == "p99_latency_ms":
        value = round(random.uniform(1200, 5000), 1) if spiking else round(random.uniform(80, 600), 1)
    else:
        value = round(random.uniform(10, 95), 1)
    
    return {
        "event_type": "metric",
        "service": svc,
        "metric_type": mt,
        "value": float(value),
        "timestamp": _now(),
        "ingested_at": _now()
    }


def generate_incident_event(service: Optional[str] = None) -> dict:
    svc = service or random.choice(SERVICES)
    return {
        "event_type": "incident",
        "incident_id": str(uuid.uuid4()),
        "title": f"{svc.capitalize()} Service Issue",
        "service": svc,
        "severity": random.choice(["critical", "warning"]),
        "status": "open",
        "timestamp": _now(),
        "ingested_at": _now()
    }


def run_generator(iterations: int = 60, interval_sec: int = 1):
    print(f"Starting generator for {iterations} iterations...")
    for i in range(iterations):
        events = []
        if random.random() < 0.05: events.append(generate_deployment_event())
        if random.random() < 0.02: events.append(generate_incident_event())
        for svc in SERVICES:
            for mt in ["error_rate", "p99_latency_ms"]:
                events.append(generate_metric_event(svc, mt))
        
        print(f"[Iteration {i+1}] Generating {len(events)} events...")
        for event in events:
            if DRY_RUN:
                print(json.dumps(event))
            else:
                try:
                    publisher.publish(topic_path, data=json.dumps(event).encode("utf-8"))
                except Exception as e:
                    print(f"Publish error: {e}")
        
        time.sleep(interval_sec)

if __name__ == "__main__":
    run_generator()
