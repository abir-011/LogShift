import os
import json
import uuid
import random
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from heartbeat import send_heartbeat
import time

LOGSHIFT_URL = os.getenv(
    "LOGSHIFT_URL",
    "http://localhost:8000/api/v1/logs/"
)

LOGSHIFT_API_KEY = os.getenv("LOGSHIFT_INGEST_API_KEY")

if not LOGSHIFT_API_KEY:
    raise RuntimeError(
        "LOGSHIFT_INGEST_API_KEY environment variable is not set."
    )

def generate_log(level, event_type, message, performance, exception=None):
    return {
        "event_id": f"evt-{uuid.uuid4().hex[:12]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service_name": "payment-service",
        "service_version": "1.0.0",
        "environment": "development",
        "level": level,
        "event_type": event_type,
        "operation": "process_payment",
        "message": message,
        "message_template": message,
        "cloud": {
            "provider": "local"
        },
        "log_source": {
            "provider": "simulated"
        },
        "performance": performance,
        "correlation": {
            "trace_id": f"tr-{uuid.uuid4().hex[:12]}",
            "request_id": f"req-{uuid.uuid4().hex[:8]}"
        },
        "attributes": {
            "payment_id": f"pay-{random.randint(1000, 9999)}",
            "gateway": "stripe"
        },
        "exception": exception or {},
        "raw": {}
    }


def send_log(log):
    request = Request(
        LOGSHIFT_URL,
        data=json.dumps(log).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-API-Key": LOGSHIFT_API_KEY
        },
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

    except OSError as error:
        print(f"[CONNECTION ERROR] {error}")


def run_payment_service():
    events = [
        generate_log(
            "INFO",
            "payment_success",
            "Payment processed successfully",
            {
                "duration_ms": random.randint(100, 500),
                "status_code": 200,
                "outcome": "success"
            }
        ),
        generate_log(
            "ERROR",
            "dependency_failure",
            "Payment gateway timeout",
            {
                "duration_ms": 5032,
                "status_code": 504,
                "outcome": "failure"
            },
            {
                "type": "GatewayTimeout",
                "message": "Payment provider did not respond within 5 seconds"
            }
        ),
        generate_log(
            "WARNING",
            "slow_operation",
            "Payment processing is slower than expected",
            {
                "duration_ms": random.randint(2000, 4000),
                "status_code": 200,
                "outcome": "success"
            }
        )
    ]

    for event in events:
        send_log(event)
    try:
        while True:
            send_heartbeat(
                service_name="payment-service",
                environment="development",
                service_version="1.0.0",
            )

            time.sleep(30)

    except KeyboardInterrupt:
        print("[SERVICE] payment-service stopped.")

if __name__ == "__main__":
    print("Starting payment-service simulation...")
    run_payment_service()
    print("Payment-service simulation completed.")
