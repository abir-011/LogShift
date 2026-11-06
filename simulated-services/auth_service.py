
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
        "service_name": "auth-service",
        "service_version": "1.0.0",
        "environment": "development",
        "level": level,
        "event_type": event_type,
        "operation": "authenticate_user",
        "message": message,
        "message_template": message,
        "cloud": {"provider": "local"},
        "log_source": {"provider": "simulated"},
        "performance": {
            "duration_ms": random.randint(50, 300),
            "status_code": 200 if level == "INFO" else 401,
            "outcome": "success" if level == "INFO" else "failure"
        },
        "correlation": {
            "trace_id": f"tr-{uuid.uuid4().hex[:12]}",
            "request_id": f"req-{uuid.uuid4().hex[:8]}"
        },
        "attributes": {
            "user_id": f"user-{random.randint(1000, 9999)}",
            "authentication_method": "password"
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


def run_auth_service():
    events = [
        generate_log(
            "INFO",
            "login_success",
            "User authenticated successfully"
        ),
        generate_log(
            "WARNING",
            "login_failure",
            "Invalid password entered"
        ),
        generate_log(
            "ERROR",
            "suspicious_activity",
            "Multiple failed authentication attempts detected",
            {
                "type": "AuthenticationFailure",
                "message": "Repeated authentication failures detected"
            }
        )
    ]

    for event in events:
        send_log(event)


if __name__ == "__main__":
    print("Starting auth-service simulation...")
    run_auth_service()
    print("Auth-service simulation completed.")
