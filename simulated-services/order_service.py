
import json
import uuid
import random
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

LOGSHIFT_URL = "http://localhost:8000/api/v1/logs/"


def generate_log(level, event_type, message, exception=None):
    return {
        "event_id": f"evt-{uuid.uuid4().hex[:12]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service_name": "order-service",
        "service_version": "1.0.0",
        "environment": "development",
        "level": level,
        "event_type": event_type,
        "operation": "process_order",
        "message": message,
        "message_template": message,
        "cloud": {"provider": "local"},
        "log_source": {"provider": "simulated"},
        "performance": {
            "duration_ms": random.randint(100, 5000),
            "status_code": 200 if level != "ERROR" else 500,
            "outcome": "failure" if level == "ERROR" else "success"
        },
        "correlation": {
            "trace_id": f"tr-{uuid.uuid4().hex[:12]}",
            "request_id": f"req-{uuid.uuid4().hex[:8]}"
        },
        "attributes": {
            "order_id": f"ord-{random.randint(10000, 99999)}",
            "customer_id": f"cust-{random.randint(1000, 9999)}"
        },
        "exception": exception or {},
        "raw": {}
    }


def send_log(log):
    request = Request(
        LOGSHIFT_URL,
        data=json.dumps(log).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urlopen(request, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))
            print(f"[SUCCESS] {result['event_id']} | HTTP {response.status}")

    except HTTPError as error:
        print(f"[HTTP ERROR] {error.code}: {error.read().decode('utf-8')}")

    except URLError as error:
        print(f"[CONNECTION ERROR] {error.reason}")


def run_order_service():
    events = [
        generate_log(
            "INFO",
            "order_created",
            "New order created successfully"
        ),
        generate_log(
            "WARNING",
            "processing_delay",
            "Order processing is taking longer than expected"
        ),
        generate_log(
            "ERROR",
            "order_processing_failure",
            "Failed to process customer order",
            {
                "type": "OrderProcessingError",
                "message": "Inventory service unavailable"
            }
        )
    ]

    for event in events:
        send_log(event)


if __name__ == "__main__":
    print("Starting order-service simulation...")
    run_order_service()
    print("Order-service simulation completed.")
